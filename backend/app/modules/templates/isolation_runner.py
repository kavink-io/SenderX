"""
SenderX Isolated Template Runner (Subprocess Entry Point)
Executes strictly inside an unprivileged child process with scrubbed environment,
no database connections, no Redis/RabbitMQ sockets, and no application secrets.
"""

import os
import sys
import json
import time
import socket
import importlib.util
import jinja2
from jinja2.sandbox import SecurityError

# ------------------------------------------------------------------------------
# 1. HARD NETWORK ISOLATION (Neutralize network sockets & DNS resolution)
# ------------------------------------------------------------------------------
def _blocked_network_call(*args, **kwargs):
    raise PermissionError("Network access is strictly prohibited in isolated template runner")


def apply_sandbox_isolation():
    """Apply process-level network neutralization and resource caps inside runner process."""
    # Keep socket.socket class intact so types/modules load, but block network actions
    socket.socket.connect = _blocked_network_call
    socket.socket.connect_ex = _blocked_network_call
    socket.socket.bind = _blocked_network_call
    socket.getaddrinfo = _blocked_network_call
    socket.create_connection = _blocked_network_call

    # Neutralize cssutils fetchers if cssutils is imported
    try:
        import cssutils
        cssutils._fetch._defaultFetcher = lambda url: None
        cssutils.util._defaultFetcher = lambda url: None
    except Exception:
        pass

    # Resource limits on POSIX platforms (e.g. Linux container)
    try:
        import resource
        max_as_bytes = 128 * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (max_as_bytes, max_as_bytes))
    except Exception:
        pass

# Direct load security module without loading app/__init__.py (Flask/MongoDB/Redis/Celery)
_curr_dir = os.path.dirname(os.path.abspath(__file__))
_security_path = os.path.join(_curr_dir, "security.py")
_spec = importlib.util.spec_from_file_location("template_security", _security_path)
_sec_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sec_mod)

TemplateSandboxRunner = _sec_mod.TemplateSandboxRunner
validate_context_structure = _sec_mod.validate_context_structure


def main():
    apply_sandbox_isolation()
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            sys.stdout.write(json.dumps({
                "success": False,
                "rendered": None,
                "error": "No input payload provided to isolation runner",
                "error_type": "ValueError"
            }))
            sys.stdout.flush()
            return
        
        payload = json.loads(raw_input)
    except Exception as err:
        sys.stdout.write(json.dumps({
            "success": False,
            "rendered": None,
            "error": f"Failed to parse runner input payload: {str(err)}",
            "error_type": "ValueError"
        }))
        sys.stdout.flush()
        return

    template_text = payload.get("template_text", "")
    context = payload.get("context") or {}
    autoescape = payload.get("autoescape", True)
    max_output_bytes = payload.get("max_output_bytes", 256 * 1024)
    max_render_seconds = payload.get("max_render_seconds", 1.0)
    crash_simulation = payload.get("__simulate_crash__", False)
    infinite_loop_simulation = payload.get("__simulate_infinite_loop__", False)

    # Simulation triggers for testing hard process isolation
    if crash_simulation:
        sys.exit(139)  # Simulated SIGSEGV / abnormal termination

    if infinite_loop_simulation:
        while True:
            time.sleep(0.01)

    if not template_text:
        sys.stdout.write(json.dumps({
            "success": True,
            "rendered": "",
            "error": None,
            "error_type": None
        }))
        sys.stdout.flush()
        return

    try:
        # In-runner AST inspection & context validation (defense-in-depth)
        TemplateSandboxRunner.inspect_ast(template_text)
        if context:
            validate_context_structure(context)

        rendered = TemplateSandboxRunner.render_in_process(template_text, context, autoescape=autoescape)

        response = {
            "success": True,
            "rendered": rendered,
            "error": None,
            "error_type": None
        }
    except jinja2.exceptions.UndefinedError as err:
        response = {
            "success": False,
            "rendered": None,
            "error": f"Missing required variable: {err.message}",
            "error_type": "UndefinedError"
        }
    except SecurityError as err:
        response = {
            "success": False,
            "rendered": None,
            "error": f"Security error during template rendering: {str(err)}",
            "error_type": "SecurityError"
        }
    except RecursionError:
        response = {
            "success": False,
            "rendered": None,
            "error": "Template rendering failed: recursion limit exceeded",
            "error_type": "RecursionError"
        }
    except ValueError as err:
        response = {
            "success": False,
            "rendered": None,
            "error": str(err),
            "error_type": "ValueError"
        }
    except Exception as err:
        response = {
            "success": False,
            "rendered": None,
            "error": f"Template rendering failed: {str(err)}",
            "error_type": type(err).__name__
        }

    sys.stdout.write(json.dumps(response))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
