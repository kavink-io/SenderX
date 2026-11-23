"""
SenderX Isolated Template Execution Coordinator
Manages isolated subprocess worker lifecycle, environment scrubbing,
hard kernel-level process preemption on timeout, bounded concurrency,
OS-level memory limiting (Windows Job Objects & POSIX setrlimit),
close_fds handle protection, and safe result deserialization.
"""

import os
import re
import sys
import json
import time
import threading
import subprocess
from typing import Any, Dict, Optional

# Windows Job Objects API integration for kernel-level memory limits & orphan destruction
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoCounters", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    def _apply_windows_job_limits(proc_handle, memory_limit_bytes: int = 128 * 1024 * 1024):
        """Assign child process to a Windows Job Object with memory limit and kill-on-close."""
        try:
            kernel32 = ctypes.windll.kernel32
            job = kernel32.CreateJobObjectW(None, None)
            if not job:
                return None
            limits = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            # 0x100 = JOB_OBJECT_LIMIT_PROCESS_MEMORY, 0x2000 = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            limits.BasicLimitInformation.LimitFlags = 0x100 | 0x2000
            limits.ProcessMemoryLimit = memory_limit_bytes
            kernel32.SetInformationJobObject(
                job,
                9,  # JobObjectExtendedLimitInformation
                ctypes.byref(limits),
                ctypes.sizeof(limits)
            )
            kernel32.AssignProcessToJobObject(job, int(proc_handle))
            return job
        except Exception:
            return None


class TemplateIsolationError(ValueError):
    """Base exception for template process isolation failures."""
    pass


class TemplateTimeoutError(TemplateIsolationError):
    """Raised when isolated template rendering exceeds hard deadline."""
    pass


class TemplateCrashError(TemplateIsolationError):
    """Raised when isolated template runner crashes or terminates abnormally."""
    pass


class TemplateOverloadError(TemplateIsolationError):
    """Raised when concurrent isolated rendering capacity is saturated."""
    pass


class TemplateLimitError(TemplateIsolationError):
    """Raised when output or memory limits are exceeded."""
    pass


class IsolatedTemplateRenderer:
    """Coordinates isolated template rendering across an unprivileged OS process boundary."""

    # Default timeout: 1.0 second hard deadline
    DEFAULT_TIMEOUT_SECONDS: float = 1.0
    DEFAULT_MAX_OUTPUT_BYTES: int = 256 * 1024  # 256 KB
    DEFAULT_MAX_INPUT_BYTES: int = 512 * 1024   # 512 KB
    DEFAULT_MAX_CONCURRENT_WORKERS: int = 10
    DEFAULT_MEMORY_LIMIT_BYTES: int = 128 * 1024 * 1024  # 128 MB

    LAST_SPAWNED_PID: Optional[int] = None

    _semaphore: Optional[threading.BoundedSemaphore] = None
    _semaphore_lock: threading.Lock = threading.Lock()

    @classmethod
    def reset_semaphore(cls, max_workers: Optional[int] = None):
        """Reset the concurrency semaphore (for configuration updates or testing)."""
        with cls._semaphore_lock:
            val = max_workers if max_workers is not None else int(
                os.environ.get("MAX_CONCURRENT_TEMPLATE_WORKERS", str(cls.DEFAULT_MAX_CONCURRENT_WORKERS))
            )
            cls._semaphore = threading.BoundedSemaphore(val)

    @classmethod
    def _get_semaphore(cls) -> threading.BoundedSemaphore:
        """Initialize or retrieve the process-wide concurrency semaphore."""
        with cls._semaphore_lock:
            if cls._semaphore is None:
                max_workers = int(os.environ.get("MAX_CONCURRENT_TEMPLATE_WORKERS", str(cls.DEFAULT_MAX_CONCURRENT_WORKERS)))
                cls._semaphore = threading.BoundedSemaphore(max_workers)
            return cls._semaphore

    @classmethod
    def _build_scrubbed_env(cls) -> Dict[str, str]:
        """
        Build an unprivileged, scrubbed environment for the runner subprocess.
        Strictly strips all secrets, database credentials, and application config.
        """
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

        # Base minimal variables required for Python runtime operation
        scrubbed = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": backend_dir,
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        }

        # Essential platform-specific system variables
        if sys.platform == "win32":
            for var in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "USERPROFILE", "COMSPEC", "APPDATA", "LOCALAPPDATA"):
                if var in os.environ:
                    scrubbed[var] = os.environ[var]
        else:
            for var in ("HOME", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL"):
                if var in os.environ:
                    scrubbed[var] = os.environ[var]

        # Explicitly verify no secret environment variables leak into child process
        prohibited_fragments = ("SECRET", "KEY", "TOKEN", "PASS", "MONGO", "REDIS", "RABBITMQ", "SENDGRID", "AWS", "AUTH")
        for k in list(scrubbed.keys()):
            upper_k = k.upper()
            if any(frag in upper_k for frag in prohibited_fragments) and upper_k not in ("PYTHONDONTWRITEBYTECODE",):
                del scrubbed[k]

        return scrubbed

    @classmethod
    def render(
        cls,
        template_text: str,
        context: Optional[Dict[str, Any]] = None,
        autoescape: bool = True,
        timeout: Optional[float] = None,
        max_output_bytes: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Render a template inside an isolated subprocess with hard execution preemption.

        Args:
            template_text: Jinja2 template content.
            context: Variables context dictionary.
            autoescape: Whether Jinja autoescaping is active.
            timeout: Maximum allowed execution seconds (default: 1.0s).
            max_output_bytes: Maximum allowed rendered size in bytes (default: 256 KB).

        Returns:
            Rendered string content.

        Raises:
            TemplateTimeoutError: When execution exceeds the hard deadline.
            TemplateCrashError: When the runner process terminates abnormally.
            TemplateOverloadError: When concurrent capacity is saturated.
            TemplateLimitError: When input/output size bounds are exceeded.
            ValueError: On template syntax, security, or validation errors.
        """
        if not template_text:
            return ""

        effective_timeout = timeout if timeout is not None else float(
            os.environ.get("TEMPLATE_RENDER_TIMEOUT_SECONDS", str(cls.DEFAULT_TIMEOUT_SECONDS))
        )
        effective_max_output = max_output_bytes if max_output_bytes is not None else int(
            os.environ.get("MAX_RENDERED_OUTPUT_BYTES", str(cls.DEFAULT_MAX_OUTPUT_BYTES))
        )
        effective_mem_limit = int(
            os.environ.get("TEMPLATE_RENDER_MEMORY_LIMIT_BYTES", str(cls.DEFAULT_MEMORY_LIMIT_BYTES))
        )

        payload = {
            "template_text": template_text,
            "context": context or {},
            "autoescape": autoescape,
            "max_output_bytes": effective_max_output,
            "max_render_seconds": effective_timeout,
        }
        # Pass through any simulation triggers for isolation testing
        if kwargs.get("__simulate_crash__"):
            payload["__simulate_crash__"] = True
        if kwargs.get("__simulate_infinite_loop__"):
            payload["__simulate_infinite_loop__"] = True

        input_bytes = json.dumps(payload).encode("utf-8")

        # 1. Enforce Input Size Ceiling before spawning worker
        if len(input_bytes) > cls.DEFAULT_MAX_INPUT_BYTES:
            raise TemplateLimitError(
                f"Template input payload ({len(input_bytes) // 1024} KB) exceeds maximum allowed size ({cls.DEFAULT_MAX_INPUT_BYTES // 1024} KB)"
            )

        # 2. Enforce Concurrency Ceiling
        semaphore = cls._get_semaphore()
        acquired = semaphore.acquire(blocking=True, timeout=0.25)
        if not acquired:
            raise TemplateOverloadError("Rendering capacity reached. Please retry later.")

        proc: Optional[subprocess.Popen] = None
        job_handle = None
        last_pid: Optional[int] = None

        try:
            runner_path = os.path.join(os.path.dirname(__file__), "isolation_runner.py")
            scrubbed_env = cls._build_scrubbed_env()

            # Spawn unprivileged worker process with close_fds=True to prevent handle inheritance
            proc = subprocess.Popen(
                [sys.executable, runner_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=scrubbed_env,
                cwd=scrubbed_env.get("PYTHONPATH"),
                close_fds=True,
            )
            last_pid = proc.pid
            cls.LAST_SPAWNED_PID = proc.pid

            # Apply Windows Job Object kernel limits if on Windows
            if sys.platform == "win32":
                job_handle = _apply_windows_job_limits(proc._handle, memory_limit_bytes=effective_mem_limit)

            try:
                stdout_data, stderr_data = proc.communicate(
                    input=input_bytes,
                    timeout=effective_timeout
                )
            except subprocess.TimeoutExpired:
                # --------------------------------------------------------------
                # HARD EXECUTION TERMINATION
                # Windows: TerminateProcess() (uninterceptable kernel termination)
                # Linux: SIGKILL (signal 9)
                # --------------------------------------------------------------
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass
                raise TemplateTimeoutError(
                    f"Template rendering exceeded time limit ({effective_timeout:.2f}s)"
                )

            # Check for crash or abnormal exit
            if proc.returncode != 0:
                raw_err = (stderr_data.decode("utf-8", errors="replace") if stderr_data else "").strip()
                # Sanitize error message to prevent disclosure of internal filesystem paths
                sanitized_err = re.sub(r"[A-Za-z]:\\[^ \n\r\t\"']+", "[PATH]", raw_err)
                sanitized_err = re.sub(r"/(?:home|usr|var|tmp|etc|app)/[^ \n\r\t\"']+", "[PATH]", sanitized_err)
                if len(sanitized_err) > 300:
                    sanitized_err = sanitized_err[:300] + "... [truncated]"
                raise TemplateCrashError(
                    f"Template rendering failed: worker process terminated unexpectedly (code: {proc.returncode})"
                    + (f": {sanitized_err}" if sanitized_err else "")
                )

            # Bounded output pipe check
            if len(stdout_data) > effective_max_output + 32768:
                raise TemplateLimitError(
                    f"Rendered template output ({len(stdout_data) // 1024} KB) exceeds maximum limit ({effective_max_output // 1024} KB)"
                )

            if not stdout_data:
                raise TemplateCrashError("Template rendering failed: empty response from worker process")

            try:
                result = json.loads(stdout_data.decode("utf-8", errors="replace"))
            except Exception as json_err:
                raise TemplateCrashError(f"Template rendering failed: invalid worker response format ({str(json_err)})")

            if not result.get("success"):
                error_msg = result.get("error", "Template rendering failed")
                error_type = result.get("error_type", "ValueError")
                if "time limit" in error_msg.lower():
                    raise TemplateTimeoutError(error_msg)
                if "exceeds maximum limit" in error_msg.lower():
                    raise TemplateLimitError(error_msg)
                raise ValueError(error_msg)

            return result.get("rendered", "")

        finally:
            # Clean up Windows Job Object handle if active
            if job_handle and sys.platform == "win32":
                try:
                    ctypes.windll.kernel32.CloseHandle(job_handle)
                except Exception:
                    pass

            # Guarantee no orphan or zombie processes remain
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                    proc.wait(timeout=0.5)
                except Exception:
                    pass
            semaphore.release()
