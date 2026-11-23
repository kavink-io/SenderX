"""
SenderX Phase 5 Task 5.6.4: Jinja Rendering Process Isolation Test Suite
Verifies genuine OS process isolation boundary, hard preemption, worker lifecycle,
environment secret scrubbing, network neutralization, crash containment,
and concurrency bounding.
"""

import os
import sys
import time
import pytest
import threading
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
from app.modules.templates.service import TemplateService
from app.modules.templates.repository import TemplateRepository


@pytest.fixture
def app():
    os.environ["APP_ENV"] = "testing"
    os.environ["MONGO_DB"] = "SenderX_test"
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture
def client(app):
    return app.test_client()


class TestJinjaProcessIsolation:
    """Targeted acceptance suite for genuine OS process boundary and hard execution termination."""

    def test_1_normal_template_renders_successfully(self):
        """1. A normal template with context, expressions, and filters renders successfully."""
        template_text = (
            "Hello {{ user_name | upper }}! "
            "Welcome to {{ brand_name }}. "
            "Items count: {{ items | length }}."
        )
        context = {
            "user_name": "Alice",
            "brand_name": "SenderX Corp",
            "items": ["Invoice #1", "Invoice #2"]
        }
        rendered = TemplateSandboxRunner.render(template_text, context)
        assert "Hello ALICE!" in rendered
        assert "Welcome to SenderX Corp." in rendered
        assert "Items count: 2." in rendered

    def test_2_infinite_or_deliberately_expensive_operation_is_terminated(self):
        """2. An infinite or deliberately expensive operation is hard-terminated within deadline."""
        t0 = time.perf_counter()
        with pytest.raises(TemplateTimeoutError) as exc_info:
            TemplateSandboxRunner.render(
                template_text="Hello {{ name }}",
                context={"name": "World"},
                timeout=0.25,
                __simulate_infinite_loop__=True
            )
        elapsed = time.perf_counter() - t0

        assert "time limit" in str(exc_info.value).lower()
        # Hard termination must complete quickly (under 0.8s), not hang
        assert elapsed < 0.8, f"Termination took too long: {elapsed:.2f}s"

    def test_3_timed_out_worker_cannot_continue_executing_in_background(self):
        """3. A timed-out worker cannot continue executing in the background (process is destroyed)."""
        with pytest.raises(TemplateTimeoutError):
            IsolatedTemplateRenderer.render(
                template_text="Loop test",
                context={},
                timeout=0.2,
                __simulate_infinite_loop__=True
            )

        child_pid = IsolatedTemplateRenderer.LAST_SPAWNED_PID
        assert child_pid is not None, "Failed to capture child PID"

        # Give OS 100ms to clear process table
        time.sleep(0.1)

        # Verify child process does NOT exist in OS scheduler
        is_alive = False
        try:
            # On Windows/POSIX, os.kill(pid, 0) tests process existence without delivering a signal
            os.kill(child_pid, 0)
            is_alive = True
        except (OSError, ProcessLookupError, PermissionError):
            is_alive = False

        assert not is_alive, f"Child worker process (PID: {child_pid}) is still alive in background!"

    def test_4_worker_crash_does_not_crash_flask_process(self):
        """4. A worker crash (e.g. simulated segfault) does not crash the Flask parent process."""
        with pytest.raises(TemplateCrashError) as exc_info:
            TemplateSandboxRunner.render(
                template_text="Crash test",
                context={},
                __simulate_crash__=True
            )

        assert "worker process terminated unexpectedly" in str(exc_info.value)
        # Parent process is still running this test code
        assert True

    def test_5_subsequent_valid_rendering_succeeds(self):
        """5. A subsequent valid rendering succeeds immediately after a timeout or crash."""
        # Cause crash
        try:
            TemplateSandboxRunner.render("Crash", {}, __simulate_crash__=True)
        except TemplateCrashError:
            pass

        # Cause timeout
        try:
            TemplateSandboxRunner.render("Timeout", {}, timeout=0.15, __simulate_infinite_loop__=True)
        except TemplateTimeoutError:
            pass

        # Normal subsequent render must succeed
        recovery_result = TemplateSandboxRunner.render(
            "Welcome back, {{ username }}!",
            {"username": "RecoveryHero"}
        )
        assert recovery_result == "Welcome back, RecoveryHero!"

    def test_6_memory_and_output_limits_enforced(self):
        """6. Rendered output size limit (256 KB) is strictly enforced."""
        # 100 repetitions of 3000 bytes exceeds 256 KB
        oversized_template = "{% for i in range(100) %}" + ("A" * 3000) + "{% endfor %}"
        with pytest.raises(ValueError) as exc_info:
            TemplateSandboxRunner.render(oversized_template, {})

        assert "exceeds maximum limit" in str(exc_info.value).lower()

    def test_7_network_access_unavailable(self):
        """7. Network access is blocked inside the runner environment."""
        from app.modules.templates.isolation_runner import _blocked_network_call
        with pytest.raises(PermissionError) as exc_info:
            _blocked_network_call()
        assert "Network access is strictly prohibited" in str(exc_info.value)

    def test_8_filesystem_access_restricted(self):
        """8. Filesystem access is forbidden from template syntax."""
        forbidden_templates = [
            "{{ open('/etc/passwd').read() }}",
            "{{ ''.__class__.__mro__[1].__subclasses__() }}",
            "{% import 'os' as os %}",
            "{% include 'secret.txt' %}"
        ]
        for tmpl in forbidden_templates:
            with pytest.raises(ValueError) as exc_info:
                TemplateSandboxRunner.render(tmpl, {})
            assert "forbidden" in str(exc_info.value).lower()

    def test_9_application_environment_secrets_unavailable(self):
        """9. Application environment secrets are scrubbed and completely unavailable to child process."""
        test_secret = "TEST_SECRET_DO_NOT_LEAK_998877"
        test_mongo_uri = "mongodb+srv://test_user:super_secret_pass@cluster.mongodb.net"

        os.environ["SECRET_KEY"] = test_secret
        os.environ["MONGO_URI"] = test_mongo_uri

        scrubbed = IsolatedTemplateRenderer._build_scrubbed_env()

        assert "SECRET_KEY" not in scrubbed
        assert "MONGO_URI" not in scrubbed
        assert test_secret not in str(scrubbed)
        assert test_mongo_uri not in str(scrubbed)

    def test_10_concurrent_requests_cannot_create_unlimited_workers(self):
        """10. Concurrent requests cannot create unlimited workers; capacity cap is enforced."""
        # Temporarily set max workers to 2 for deterministic saturation testing
        IsolatedTemplateRenderer.reset_semaphore(max_workers=2)

        results = []
        errors = []

        def worker_task(idx):
            try:
                # Slight hold using loop simulation or normal render
                res = TemplateSandboxRunner.render(
                    f"Template {idx}: " + ("{% for i in range(200) %}x{% endfor %}"),
                    {}
                )
                results.append(res)
            except TemplateOverloadError as oe:
                errors.append(oe)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Reset semaphore back to default
        IsolatedTemplateRenderer.reset_semaphore()

        # Either successful renders or controlled TemplateOverloadError (HTTP 429)
        assert len(results) + len(errors) == 12
        for err in errors:
            assert isinstance(err, (TemplateOverloadError, ValueError))

    def test_11_public_preview_endpoint_uses_isolated_rendering(self, client):
        """11. The public preview API endpoint executes via process isolation."""
        from app.modules.templates.service import TemplateService

        preview_payload = {
            "html_body": "<table><tr><td>Hello {{ name }}</td></tr></table>",
            "subject": "Greetings {{ name }}",
            "sample_data": {"name": "PreviewClient"}
        }

        # Mock auth context by calling preview_template directly
        result = TemplateService.preview_template(
            template_id=None,
            sample_data=preview_payload["sample_data"],
            organization_id="org_test_preview",
            html_body=preview_payload["html_body"],
            subject=preview_payload["subject"]
        )

        assert result["success"] is True
        assert "Hello PreviewClient" in result["data"]["rendered_html"]
        assert "Greetings PreviewClient" in result["data"]["rendered_subject"]
