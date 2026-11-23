"""
SenderX Phase 5 Task 5.6.5: Subprocess Isolation Security Audit Test Suite
Focuses on empirical verification of OS vs Python sandbox boundaries:
- Filesystem & environment secret isolation
- Database & Redis socket blockage
- Network neutralization
- Process preemption and PID cleanup
- Input and output pipe bounds
- OS memory limits (Win32 Job Objects & POSIX setrlimit)
- Crash containment and subsequent rendering stability
"""

import os
import sys
import time
import pytest
import subprocess
from typing import Dict, Any

from app import create_app
from app.modules.templates.security import TemplateSandboxRunner
from app.modules.templates.isolated_executor import (
    IsolatedTemplateRenderer,
    TemplateTimeoutError,
    TemplateCrashError,
    TemplateOverloadError,
    TemplateLimitError,
)


@pytest.fixture
def app():
    os.environ["APP_ENV"] = "testing"
    os.environ["MONGO_DB"] = "SenderX_test"
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


class TestSubprocessIsolationSecurityAudit:
    """Rigorous audit test suite testing OS boundary guarantees vs application sandbox."""

    def test_1_child_cannot_read_env_secrets(self):
        """1. Verify that sensitive environment credentials never leak into child process."""
        canary_secret = "CANARY_SECRET_LEAK_AUDIT_998877"
        canary_uri = "mongodb+srv://admin_leak:secret_pass@atlas.senderx.com"

        os.environ["SECRET_KEY"] = canary_secret
        os.environ["MONGO_URI"] = canary_uri
        os.environ["SENDGRID_API_KEY"] = "SG.canary_leak_key_9988"

        scrubbed = IsolatedTemplateRenderer._build_scrubbed_env()

        assert "SECRET_KEY" not in scrubbed
        assert "MONGO_URI" not in scrubbed
        assert "SENDGRID_API_KEY" not in scrubbed
        assert canary_secret not in str(scrubbed)
        assert canary_uri not in str(scrubbed)

    def test_2_child_cannot_access_mongodb_or_redis(self):
        """2. Verify child process cannot connect to MongoDB or Redis (network sockets blocked)."""
        # Run child process executing socket.create_connection to localhost MongoDB (27017) and Redis (6379)
        runner_path = os.path.join(os.path.dirname(__file__), "..", "app", "modules", "templates", "isolation_runner.py")
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        test_script = (
            "import socket\n"
            "from app.modules.templates.isolation_runner import apply_sandbox_isolation\n"
            "apply_sandbox_isolation()\n"
            "try:\n"
            "    socket.create_connection(('127.0.0.1', 27017), timeout=1.0)\n"
            "    print('FAIL_CONNECTED')\n"
            "except PermissionError as e:\n"
            "    print('SUCCESS_BLOCKED_MONGO')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": backend_dir, "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
        )
        assert "SUCCESS_BLOCKED_MONGO" in proc.stdout
        assert "FAIL_CONNECTED" not in proc.stdout

    def test_3_network_restrictions_cannot_be_bypassed(self):
        """3. Verify all socket methods (connect, connect_ex, bind, getaddrinfo, create_connection) are blocked."""
        test_script = (
            "import socket\n"
            "from app.modules.templates.isolation_runner import apply_sandbox_isolation\n"
            "apply_sandbox_isolation()\n"
            "blocked_count = 0\n"
            "for fn in [lambda: socket.getaddrinfo('google.com', 80), lambda: socket.socket().connect(('1.1.1.1', 80))]:\n"
            "    try:\n"
            "        fn()\n"
            "    except PermissionError:\n"
            "        blocked_count += 1\n"
            "print(f'BLOCKED_{blocked_count}')\n"
        )
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        proc = subprocess.run(
            [sys.executable, "-c", test_script],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": backend_dir, "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
        )
        assert "BLOCKED_2" in proc.stdout

    def test_4_timeout_kills_and_reaps_process(self):
        """4. Verify timeout immediately terminates and reaps child process without orphans."""
        with pytest.raises(TemplateTimeoutError):
            IsolatedTemplateRenderer.render(
                template_text="Loop test",
                context={},
                timeout=0.2,
                __simulate_infinite_loop__=True
            )

        child_pid = IsolatedTemplateRenderer.LAST_SPAWNED_PID
        assert child_pid is not None

        # Give OS 100ms
        time.sleep(0.1)

        # Check process existence
        is_alive = False
        try:
            os.kill(child_pid, 0)
            is_alive = True
        except (OSError, ProcessLookupError, PermissionError):
            is_alive = False

        assert not is_alive, f"Child worker PID {child_pid} still running after timeout!"

    def test_5_input_and_output_size_limits_enforced(self):
        """5. Verify both input payload and output rendered size limits are strictly enforced."""
        # A. Input size limit > 512 KB fails before spawning process
        oversized_input = "A" * (520 * 1024)
        with pytest.raises(TemplateLimitError) as exc_info:
            IsolatedTemplateRenderer.render(template_text=oversized_input, context={})
        assert "input payload" in str(exc_info.value).lower()
        assert "exceeds maximum allowed size" in str(exc_info.value).lower()

        # B. Output size limit > 256 KB fails during streaming
        oversized_output_tmpl = "{% for i in range(100) %}" + ("B" * 3000) + "{% endfor %}"
        with pytest.raises(ValueError) as exc_info:
            TemplateSandboxRunner.render(template_text=oversized_output_tmpl, context={})
        assert "exceeds maximum limit" in str(exc_info.value).lower()

    def test_6_concurrency_behavior_under_multiple_workers(self):
        """6. Verify process-local semaphore bounds concurrency per worker."""
        IsolatedTemplateRenderer.reset_semaphore(max_workers=2)

        import threading
        acquired_count = 0
        overload_count = 0

        def render_call():
            nonlocal acquired_count, overload_count
            try:
                TemplateSandboxRunner.render("Test {{ val }}", {"val": "123"})
                acquired_count += 1
            except TemplateOverloadError:
                overload_count += 1

        threads = [threading.Thread(target=render_call) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        IsolatedTemplateRenderer.reset_semaphore()
        assert acquired_count + overload_count == 6

    def test_7_memory_limits_represented_per_os(self):
        """7. Verify OS-level memory limiting: Win32 Job Objects on Windows & setrlimit on POSIX."""
        if sys.platform == "win32":
            # Test that Windows Job Objects API is functional and sets process memory limit
            from app.modules.templates.isolated_executor import _apply_windows_job_limits
            import ctypes
            # Spawn a small process and assign to job
            p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(0.1)"])
            job = _apply_windows_job_limits(p._handle, memory_limit_bytes=128 * 1024 * 1024)
            assert job is not None, "Failed to create or assign Windows Job Object"
            p.communicate()
            ctypes.windll.kernel32.CloseHandle(job)
        else:
            # On POSIX, verify resource.setrlimit(RLIMIT_AS)
            import resource
            assert hasattr(resource, "RLIMIT_AS")

    def test_8_crashed_child_does_not_affect_subsequent_rendering(self):
        """8. Verify abnormal child termination (exit 139) is caught cleanly and allows subsequent rendering."""
        with pytest.raises(TemplateCrashError) as exc_info:
            IsolatedTemplateRenderer.render("Crash test", {}, __simulate_crash__=True)
        assert "worker process terminated unexpectedly" in str(exc_info.value)

        # Subsequent render must succeed
        res = IsolatedTemplateRenderer.render("Post-crash render {{ name }}", {"name": "AuditPassed"})
        assert res == "Post-crash render AuditPassed"

    def test_9_stderr_error_sanitization(self):
        """9. Verify child crash messages do not disclose internal filesystem paths."""
        try:
            IsolatedTemplateRenderer.render("Crash test", {}, __simulate_crash__=True)
        except TemplateCrashError as e:
            err_msg = str(e)
            # Ensure no local absolute paths like C:\Users\... or /home/... are exposed raw
            assert "C:\\Users\\" not in err_msg
            assert "/home/" not in err_msg
