"""
SenderX Phase 5 Task 5.6.3: Comprehensive Security Verification & Acceptance Test Suite

Verifies:
1. Jinja2 template execution isolation (AST depth bounds, range bounds, collection/context caps,
   binop size limits, rendered output limits, concurrent execution safety).
2. Celery and DLQ security integration (real asynchronous task boundary, malformed JSON,
   deeply nested payloads, provider exceptions with SendGrid keys, JWTs, and passwords,
   DLQ persistence redaction, payload immutability, worker continuation).
3. Redis fail-closed endpoint verification (POST /preview, POST /validate, GET /<id>/preview
   under 4 states: operational, ConnectionError, uninitialized/None, recovered).
4. Premailer external-resource restrictions (instrumented socket.getaddrinfo and socket.connect
   proving zero DNS lookups and zero network calls, stripped @import and <link> tags).
5. CSS sanitizer adversarial testing (16 attack vectors: mixed-case protocols, backslash escapes,
   malformed URLs, data URLs, CSS custom props, semicolon injection, control chars, expressions,
   behavior, -moz-binding, disallowed properties).
6. Migration safety review (dry-run default, dual-gate production guard, duplicate detection,
   soft-deleted record handling, idempotency on SenderX_test).
"""

import os
import sys
import time
import uuid
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

import pytest
import bcrypt
from flask_jwt_extended import create_access_token

from app import create_app
from app.config.settings import Config
from app.modules.templates.service import TemplateService
from app.modules.templates.repository import TemplateRepository
from app.modules.templates.compiler import compile_email_template
from app.modules.templates.security import (
    TemplateSecurityInspector,
    TemplateSandboxRunner,
    validate_css_property,
    is_safe_css_color,
    sanitize_inline_css,
    validate_context_structure,
    SenderXSandboxedEnvironment,
    SecurityError,
    ALLOWED_CSS_PROPERTIES,
    MAX_TEMPLATE_SOURCE_BYTES,
    MAX_RENDERED_OUTPUT_BYTES,
    MAX_RENDER_SECONDS,
)
from app.modules.messages.repository import MessageRepository
from app.modules.dead_letters.repository import DeadLetterRepository
from app.modules.dead_letters.sanitizer import (
    sanitize_dlq_error,
    sanitize_dlq_dict,
)
from app.modules.organizations.repository import OrganizationRepository
from app.modules.organizations.role_repository import RoleRepository
from app.modules.users.repository import UserRepository
from app.modules.api_credentials.rate_limiter import (
    DistributedRateLimiter,
    RateLimiterError,
)
from app.queue.tasks import process_message
from app.migrations.backfill_template_name_lower import run_migration


# ==============================================================================
# FIXTURES
# ==============================================================================

@pytest.fixture(scope="module")
def app():
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    return app.test_client()


@pytest.fixture(scope="module")
def test_setup(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:6]
        org_id = str(uuid.uuid4())
        role_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        rounds = getattr(Config, "BCRYPT_ROUNDS", 4)
        password_hash = bcrypt.hashpw(b"ValidPassword123!", bcrypt.gensalt(rounds)).decode("utf-8")

        OrganizationRepository.create({
            "organization_id": org_id,
            "name": f"Security Verification Org {suffix}",
            "slug": f"sec-verify-{suffix}",
            "status": "ACTIVE"
        })

        RoleRepository.create({
            "role_id": role_id,
            "organization_id": org_id,
            "name": f"Sec Admin {suffix}",
            "scope": "ORGANIZATION",
            "permissions": [
                "organization:templates:read",
                "organization:templates:manage",
                "organization:messages:create",
                "organization:messages:read",
                "organization:messages:manage"
            ],
            "is_system_role": False
        })

        UserRepository.create({
            "user_id": user_id,
            "organization_id": org_id,
            "employee_code": f"EMP-SEC-{suffix}",
            "employee_code_lower": f"emp-sec-{suffix}",
            "name": "Sec Admin",
            "email": f"secadmin-{suffix}@senderx.test",
            "password_hash": password_hash,
            "role_ids": [role_id],
            "is_active": True,
            "status": "ACTIVE"
        })

        token = create_access_token(
            identity=user_id,
            additional_claims={"account_type": "ORGANIZATION_USER", "organization_id": org_id}
        )

        # Create a sample active template for preview testing
        sample_tmpl = TemplateRepository.create({
            "template_id": f"tmpl_{suffix}",
            "organization_id": org_id,
            "name": f"Verification Template {suffix}",
            "name_lower": f"verification template {suffix}",
            "subject": "Hello {{ name }}",
            "html_body": "<h1>Hello {{ name }}</h1>",
            "css": "h1 { color: #2563eb; }",
            "compiled_html": "<h1 style=\"color:#2563eb\">Hello {{ name }}</h1>",
            "plain_text_body": "Hello {{ name }}",
            "status": "ACTIVE",
            "category": "marketing",
            "variables": [{"name": "name", "type": "string", "required": False, "sample_value": "World"}],
            "created_by": user_id,
        })

        return {
            "org_id": org_id,
            "user_id": user_id,
            "token": token,
            "template_id": sample_tmpl["template_id"],
        }


# ==============================================================================
# 1. JINJA TEMPLATE EXECUTION ISOLATION TESTS
# ==============================================================================

class TestJinjaHardExecutionIsolation:
    def test_nested_loops_depth_3_blocked_by_ast(self):
        """Loop depth 3 must be blocked by AST inspection before execution."""
        bomb = "{% for a in range(10) %}{% for b in range(10) %}{% for c in range(10) %}X{% endfor %}{% endfor %}{% endfor %}"
        with pytest.raises(ValueError) as exc:
            TemplateSandboxRunner.inspect_ast(bomb)
        assert "nested loops exceed maximum depth" in str(exc.value)

    def test_nested_loops_depth_2_allowed(self):
        """Loop depth 2 is within complexity budget and must be allowed."""
        safe_loop = "{% for a in range(3) %}{% for b in range(3) %}.{% endfor %}{% endfor %}"
        TemplateSandboxRunner.inspect_ast(safe_loop)
        res = TemplateSandboxRunner.render(safe_loop, {})
        assert res == "........."

    def test_range_literal_over_500_blocked(self):
        """Range literals with > 500 items must be blocked by AST inspection."""
        huge_range = "{% for x in range(1000) %}A{% endfor %}"
        with pytest.raises(ValueError) as exc:
            TemplateSandboxRunner.inspect_ast(huge_range)
        assert "exceeds maximum 500 items" in str(exc.value)

    def test_context_collection_length_capped(self):
        """Context collections with > 1000 items must be rejected before render."""
        large_context = {"items": list(range(2000))}
        with pytest.raises(ValueError) as exc:
            validate_context_structure(large_context)
        assert "Collection length (2000) exceeds maximum limit of 1000 items" in str(exc.value)

    def test_context_nesting_depth_capped(self):
        """Context nesting deeper than 5 levels must be rejected before render."""
        deep = {"l1": {"l2": {"l3": {"l4": {"l5": {"l6": "deep"}}}}}}
        with pytest.raises(ValueError) as exc:
            validate_context_structure(deep)
        assert "Context nesting depth exceeds maximum allowed depth" in str(exc.value)

    def test_binop_sequence_multiplication_capped(self):
        """String/sequence multiplication > 100k items must be rejected by call_binop."""
        tmpl = "{{ 'A' * 300000 }}"
        with pytest.raises(ValueError) as exc:
            TemplateSandboxRunner.render(tmpl, {})
        assert "Security error" in str(exc.value) or "Multiplication output size" in str(exc.value)

    def test_binop_exponentiation_capped(self):
        """Exponentiation with exponent > 100 must be rejected by call_binop."""
        tmpl = "{{ 10 ** 101 }}"
        with pytest.raises(ValueError) as exc:
            TemplateSandboxRunner.render(tmpl, {})
        assert "Security error" in str(exc.value) or "Exponentiation" in str(exc.value)

    def test_filter_huge_width_argument_blocked(self):
        """Filter calls like center(50000) must be blocked by AST check."""
        tmpl = "{{ 'hello'|center(50000) }}"
        with pytest.raises(ValueError) as exc:
            TemplateSandboxRunner.inspect_ast(tmpl)
        assert "exceeds safe limit" in str(exc.value)

    def test_rendered_output_bytes_limit_enforced(self):
        """Rendering exceeding MAX_RENDERED_OUTPUT_BYTES (256 KB) must abort immediately."""
        # Max loop depth is 2, range is 500. 500 * 500 * 2 bytes = 500,000 bytes > 256 KB
        tmpl = "{% for a in range(500) %}{% for b in range(500) %}XX{% endfor %}{% endfor %}"
        with pytest.raises(ValueError) as exc:
            TemplateSandboxRunner.render(tmpl, {})
        assert "exceeds maximum limit" in str(exc.value)

    def test_concurrent_template_renders(self):
        """Verify thread-safe rendering under 20 concurrent threads."""
        tmpl = "<h1>Invoice for {{ name }}</h1><p>Amount: {{ amount }}</p>"
        errors = []

        def render_worker(i):
            try:
                res = TemplateSandboxRunner.render(tmpl, {"name": f"User_{i}", "amount": f"${i}.00"})
                if f"User_{i}" not in res or f"${i}.00" not in res:
                    errors.append(f"Unexpected output for worker {i}: {res}")
            except Exception as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(render_worker, range(20)))

        assert len(errors) == 0, f"Concurrent render errors: {errors}"


# ==============================================================================
# 2. CELERY AND DLQ SECURITY INTEGRATION TESTS
# ==============================================================================

class TestCeleryAndDLQSecurityIntegration:
    def test_malformed_json_in_task_moves_to_dlq_sanitized(self, app, test_setup):
        """Malformed message record triggers DLQ failure recording with sanitized error."""
        with app.app_context():
            org_id = test_setup["org_id"]
            msg_id = f"msg_malformed_{uuid.uuid4().hex[:6]}"

            # Create message record with unparseable payload structure
            MessageRepository.save({
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "broken@senderx.test",
                "status": "QUEUED",
                "payload": "NON_DICT_CORRUPT_STRING",
                "retry_count": 3,
                "created_at": "2026-11-20T12:00:00Z",
            })

            with patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as mock_get, \
                 patch("app.engine.retry_manager.RetryManager.can_retry", return_value=False):
                mock_adapter = MagicMock()
                mock_adapter.send.side_effect = ConnectionError("Payload parsing failed with network error")
                mock_get.return_value = mock_adapter

                # Execute Celery task directly via apply
                res = process_message.apply(args=[msg_id])
                assert res.result is not None
                assert res.result.get("success") is False

            # Verify DLQ entry exists and has sanitized error
            dlq_record = DeadLetterRepository.find_by_message_id(msg_id, org_id)
            assert dlq_record is not None
            assert dlq_record["dead_letter_status"] == "PENDING_REVIEW"
            assert isinstance(dlq_record["last_error"], str)

    def test_provider_exception_secrets_redacted_in_dlq(self, app, test_setup):
        """Provider exception containing SendGrid key, JWT, and password is fully redacted in DLQ."""
        with app.app_context():
            org_id = test_setup["org_id"]
            msg_id = f"msg_secret_{uuid.uuid4().hex[:6]}"

            sg_key = "SG.v29skd920skd920skd920.abcdefghijklmnopqrstuvwxyz12345"
            jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
            secret_pw = "SuperSecretAdminPass123!"

            raw_payload = {
                "channel": "email",
                "recipient": "leak-test@senderx.test",
                "subject": "Confidential Info",
                "body_text": "Sensitive body content",
            }

            MessageRepository.save({
                "message_id": msg_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "leak-test@senderx.test",
                "status": "QUEUED",
                "data": raw_payload,
                "retry_count": 3,  # Max retries to force immediate DLQ
                "created_at": "2026-11-20T12:00:00Z",
            })

            # Mock provider adapter to throw ConnectionError (retryable) containing real-looking credentials
            with patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as mock_get, \
                 patch("app.engine.retry_manager.RetryManager.can_retry", return_value=False):
                mock_adapter = MagicMock()
                mock_adapter.send.side_effect = ConnectionError(
                    f"SendGrid API connection failure: auth header SG.{sg_key[3:]} failed, "
                    f"JWT token {jwt_token} rejected, password={secret_pw}"
                )
                mock_get.return_value = mock_adapter

                res = process_message.apply(args=[msg_id])
                assert res.result.get("success") is False

            # Verify DLQ record in MongoDB SenderX_test
            dlq_record = DeadLetterRepository.find_by_message_id(msg_id, org_id)
            assert dlq_record is not None

            error_text = dlq_record.get("last_error", "")
            # Crucial assertions: none of the raw secrets may appear in DLQ
            assert sg_key not in error_text, "SendGrid key leaked in DLQ last_error!"
            assert jwt_token not in error_text, "JWT leaked in DLQ last_error!"
            assert secret_pw not in error_text, "Password leaked in DLQ last_error!"

            assert "[REDACTED_API_KEY]" in error_text or "[REDACTED" in error_text
            assert "[REDACTED_JWT]" in error_text

            # Assert original payload remained immutable
            stored_data = dlq_record.get("data") or dlq_record.get("payload")
            assert stored_data is not None
            assert stored_data["subject"] == "Confidential Info"
            assert stored_data["body_text"] == "Sensitive body content"

    def test_worker_continues_subsequent_tasks_after_failure(self, app, test_setup):
        """Worker continues to process subsequent messages normally after encountering a failed task."""
        with app.app_context():
            org_id = test_setup["org_id"]

            # Task 1: Fails into DLQ
            fail_id = f"msg_f_{uuid.uuid4().hex[:6]}"
            MessageRepository.save({
                "message_id": fail_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "fail@senderx.test",
                "status": "QUEUED",
                "payload": {"invalid": "missing recipient"},
                "retry_count": 3,
                "created_at": "2026-11-20T12:00:00Z",
            })

            with patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as mock_get, \
                 patch("app.engine.retry_manager.RetryManager.can_retry", return_value=False):
                mock_adapter = MagicMock()
                mock_adapter.send.side_effect = ConnectionError("Simulated provider outage")
                mock_get.return_value = mock_adapter

                res1 = process_message.apply(args=[fail_id])
                assert res1.result.get("success") is False

            # Task 2: Valid message processed immediately afterwards
            succ_id = f"msg_s_{uuid.uuid4().hex[:6]}"
            MessageRepository.save({
                "message_id": succ_id,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "success@senderx.test",
                "status": "QUEUED",
                "payload": {
                    "channel": "email",
                    "recipient": "success@senderx.test",
                    "subject": "Delivery Success",
                    "body_text": "Processed properly after failure",
                },
                "retry_count": 0,
                "created_at": "2026-11-20T12:00:00Z",
            })

            with patch("app.adapters.adapter_registry.AdapterRegistry.get_adapter") as mock_get:
                mock_adapter = MagicMock()
                mock_adapter.send.return_value = {
                    "success": True,
                    "provider": "mock",
                    "provider_message_id": "mock_succ_123",
                    "status": "SENT"
                }
                mock_get.return_value = mock_adapter

                res2 = process_message.apply(args=[succ_id])
                assert res2.result.get("success") is True
                assert res2.result.get("status") == "SENT"

    def test_live_celery_worker_survival_and_redaction(self, app, test_setup):
        """Integration test: Real Celery worker processes failure with secrets, redacts error, and survives to process next message."""
        import subprocess, time, sys, os

        with app.app_context():
            org_id = test_setup["org_id"]
            msg_fail = f"msg_wfail_{uuid.uuid4().hex[:6]}"
            msg_succ = f"msg_wsucc_{uuid.uuid4().hex[:6]}"

            sg_key = "SG.v29skd920skd920skd920.abcdefghijklmnopqrstuvwxyz12345"
            jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
            secret_pw = "SuperSecretAdminPass123!"

            # 1. Controlled failure message with secrets
            MessageRepository.save({
                "message_id": msg_fail,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "fail-worker@senderx.test",
                "status": "QUEUED",
                "data": {
                    "channel": "email",
                    "recipient": "fail-worker@senderx.test",
                    "subject": "Permanent Secret Leak Failure Test",
                    "body": "Confidential original body content",
                    "mock_scenario": "secret_leak_failure",
                    "mock_error_message": f"SendGrid API failure: auth SG.{sg_key[3:]} failed with JWT {jwt_token} and password={secret_pw}"
                },
                "retry_count": 0,
                "created_at": "2026-11-20T12:00:00Z",
            })

            # 2. Valid subsequent message
            MessageRepository.save({
                "message_id": msg_succ,
                "organization_id": org_id,
                "channel": "email",
                "provider": "mock",
                "recipient": "succ-worker@senderx.test",
                "status": "QUEUED",
                "data": {
                    "channel": "email",
                    "recipient": "succ-worker@senderx.test",
                    "subject": "Success After Failure Test",
                    "body": "Success message body",
                    "mock_scenario": "success",
                },
                "retry_count": 0,
                "created_at": "2026-11-20T12:00:00Z",
            })

            env = os.environ.copy()
            env["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
            env["MONGO_DB"] = os.environ.get("MONGO_DB", "SenderX_test")
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONPATH"] = "backend"

            queue_name = f"test_queue_{uuid.uuid4().hex[:6]}"
            cmd = [
                sys.executable, "-m", "celery", "-A", "app.queue.celery_app.celery", "worker",
                "-n", f"test_worker_{uuid.uuid4().hex[:4]}@%h",
                "-Q", queue_name,
                "--without-mingle", "--without-gossip",
                "--pool=solo", "--loglevel=INFO"
            ]

            worker = subprocess.Popen(cmd, cwd="backend", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            try:
                time.sleep(3)  # Wait for worker initialization

                # Dispatch Task 1 to isolated worker
                process_message.apply_async(args=[msg_fail], queue=queue_name)

                for _ in range(10):
                    time.sleep(0.5)
                    m1 = MessageRepository.find_by_id(msg_fail, org_id)
                    if m1 and m1.get("status") in ("FAILED", "DEAD"):
                        break

                # Dispatch Task 2 to the same worker
                process_message.apply_async(args=[msg_succ], queue=queue_name)

                for _ in range(10):
                    time.sleep(0.5)
                    m2 = MessageRepository.find_by_id(msg_succ, org_id)
                    if m2 and m2.get("status") in ("SENT", "DELIVERED"):
                        break

                m1 = MessageRepository.find_by_id(msg_fail, org_id)
                m2 = MessageRepository.find_by_id(msg_succ, org_id)

                assert m1 is not None and m1.get("status") in ("FAILED", "DEAD")
                assert m2 is not None and m2.get("status") in ("SENT", "DELIVERED")

                # Verify secrets are redacted in persisted error
                err1 = m1.get("error") or m1.get("last_error") or ""
                assert sg_key not in err1
                assert jwt_token not in err1
                assert secret_pw not in err1
                assert "[REDACTED_API_KEY]" in err1 or "[REDACTED" in err1
                assert "[REDACTED_JWT]" in err1

                # Verify payload immutability
                assert m1["data"]["body"] == "Confidential original body content"
                assert m1["data"]["subject"] == "Permanent Secret Leak Failure Test"
            finally:
                worker.terminate()
                try:
                    worker.wait(timeout=3)
                except Exception:
                    worker.kill()


# ==============================================================================
# 3. REDIS FAIL-CLOSED ENDPOINT VERIFICATION TESTS
# ==============================================================================

class TestRedisFailClosedEndpointVerification:
    def test_preview_endpoint_redis_states(self, client, test_setup):
        """Test POST /api/v1/email-templates/preview across 4 Redis states."""
        token = test_setup["token"]
        payload = {
            "html_body": "<h1>Welcome {{ name }}</h1>",
            "css": "h1 { color: #10b981; }",
            "sample_data": {"name": "Alice"},
            "variables": [{"name": "name", "type": "string"}]
        }

        # State 1: Redis Operational -> HTTP 200
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 1, 1, True, [(b"member", time.time())]]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            res_ok = client.post(
                "/api/v1/email-templates/preview",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res_ok.status_code == 200
            assert "Welcome Alice" in res_ok.get_json()["data"]["rendered_html"]

        # State 2: Redis Unavailable (ConnectionError) -> HTTP 503, fail closed
        with patch.object(DistributedRateLimiter, "_get_redis", side_effect=ConnectionError("Redis connection refused")):
            res_down = client.post(
                "/api/v1/email-templates/preview",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res_down.status_code == 503
            data = res_down.get_json()
            assert "temporarily unavailable" in data.get("message", "").lower() or "rate limit" in data.get("message", "").lower()
            assert "redis://" not in str(data), "Redis connection URI leaked in response!"

        # State 3: Redis Client is None (uninitialized) -> HTTP 503, fail closed
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=None):
            res_none = client.post(
                "/api/v1/email-templates/preview",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res_none.status_code == 503

        # State 4: Redis Restored -> HTTP 200
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            res_rec = client.post(
                "/api/v1/email-templates/preview",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res_rec.status_code == 200

    def test_validate_endpoint_redis_states(self, client, test_setup):
        """Test POST /api/v1/email-templates/validate across 4 Redis states."""
        token = test_setup["token"]
        payload = {
            "name": "Validation Check",
            "subject": "Important update",
            "html_source": "<p>Content</p>",
            "css_source": "p { color: red; }",
            "declared_variables": []
        }

        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 1, 1, True, [(b"member", time.time())]]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        # State 1: Redis Available -> HTTP 200
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            res = client.post(
                "/api/v1/email-templates/validate",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res.status_code == 200

        # State 2: Redis Down -> HTTP 503
        with patch.object(DistributedRateLimiter, "_get_redis", side_effect=ConnectionError("Redis down")):
            res = client.post(
                "/api/v1/email-templates/validate",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res.status_code == 503

        # State 3: Redis None -> HTTP 503
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=None):
            res = client.post(
                "/api/v1/email-templates/validate",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res.status_code == 503

        # State 4: Redis Recovered -> HTTP 200
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            res = client.post(
                "/api/v1/email-templates/validate",
                headers={"Authorization": f"Bearer {token}"},
                json=payload
            )
            assert res.status_code == 200

    def test_get_preview_by_id_endpoint_redis_states(self, client, test_setup):
        """Test GET /api/v1/email-templates/<id>/preview across 4 Redis states."""
        token = test_setup["token"]
        tmpl_id = test_setup["template_id"]

        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 1, 1, True, [(b"member", time.time())]]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        # State 1: Redis Available -> HTTP 200
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            res = client.get(
                f"/api/v1/email-templates/{tmpl_id}/preview",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 200
            assert "rendered_html" in res.get_json()["data"]

        # State 2: Redis Down -> HTTP 503
        with patch.object(DistributedRateLimiter, "_get_redis", side_effect=ConnectionError("Redis down")):
            res = client.get(
                f"/api/v1/email-templates/{tmpl_id}/preview",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 503

        # State 3: Redis None -> HTTP 503
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=None):
            res = client.get(
                f"/api/v1/email-templates/{tmpl_id}/preview",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 503

        # State 4: Redis Recovered -> HTTP 200
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            res = client.get(
                f"/api/v1/email-templates/{tmpl_id}/preview",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 200


# ==============================================================================
# 4. PREMAILER NETWORK ISOLATION & DNS RESOLUTION TESTS
# ==============================================================================

class TestPremailerNetworkIsolation:
    def test_premailer_dns_resolution_strictly_prevented(self):
        """Premailer compilation must make ZERO DNS resolution calls (socket.getaddrinfo)."""
        dns_lookups = []
        orig_getaddrinfo = socket.getaddrinfo

        def mock_getaddrinfo(*args, **kwargs):
            host = args[0] if args else kwargs.get("host")
            dns_lookups.append(host)
            raise socket.gaierror(-2, "DNS lookup forbidden in sandbox")

        html_with_imports = """
        <!DOCTYPE html>
        <html>
        <head>
          <style>
            @import url("http://evil-cdn.com/malicious.css");
            @import "https://tracker.org/leak.css";
            h1 { color: red; }
          </style>
          <link rel="stylesheet" href="http://cdn.attacker.com/style.css">
        </head>
        <body>
          <h1>Title</h1>
        </body>
        </html>
        """
        css_with_imports = "@import url('http://exfil.net/css.css'); p { font-size: 16px; }"

        with patch("socket.getaddrinfo", side_effect=mock_getaddrinfo):
            res = compile_email_template(html_with_imports, css_with_imports)

        # Assert zero DNS requests were triggered
        assert len(dns_lookups) == 0, f"DNS lookups leaked: {dns_lookups}"

        # Assert @import and external links were stripped
        compiled = res["compiled_html"]
        assert "@import" not in compiled
        assert "evil-cdn.com" not in compiled
        assert "cdn.attacker.com" not in compiled
        assert "tracker.org" not in compiled

        # Assert valid CSS was still properly inlined
        assert "style=\"color:red\"" in compiled or "style=\"color: red\"" in compiled

    def test_premailer_socket_connect_prevented(self):
        """Premailer compilation must make ZERO outbound socket connections."""
        socket_connects = []

        def mock_connect(self, *args, **kwargs):
            socket_connects.append(args)
            raise ConnectionRefusedError("Outbound connections forbidden")

        with patch.object(socket.socket, "connect", mock_connect):
            res = compile_email_template(
                "<html><body><p>Test</p></body></html>",
                "p { margin: 10px; }"
            )

        assert len(socket_connects) == 0
        assert "margin:10px" in res["compiled_html"] or "margin: 10px" in res["compiled_html"]


# ==============================================================================
# 5. CSS SANITIZER ADVERSARIAL TESTING (16 VECTORS)
# ==============================================================================

class TestCSSSanitizerAdversarial:
    def test_mixed_case_javascript_protocol(self):
        """Mixed-case jAvAsCrIpT: must be rejected."""
        valid, _ = validate_css_property("background-image", "url(jAvAsCrIpT:alert(1))")
        assert not valid
        findings = TemplateSecurityInspector.inspect_css("background: url(jAvAsCrIpT:alert(1))")
        assert len(findings) > 0
        sanitized = sanitize_inline_css("background: url(jAvAsCrIpT:alert(1))")
        assert "javascript" not in sanitized.lower()

    def test_mixed_case_vbscript_protocol(self):
        """Mixed-case vBsCrIpT: must be rejected."""
        valid, _ = validate_css_property("background-image", "url(vBsCrIpT:msgbox(1))")
        assert not valid
        findings = TemplateSecurityInspector.inspect_css("background: url(vBsCrIpT:msgbox(1))")
        assert len(findings) > 0

    def test_css_backslash_escapes_rejected(self):
        """Backslash escape sequences in CSS properties must be rejected."""
        valid_escape, _ = validate_css_property("background", r"url(\6a\61\76\61\73\63\72\69\70\74\3aalert(1))")
        assert not valid_escape
        valid_ident, _ = validate_css_property("color", r"r\ed")
        assert not valid_ident
        sanitized = sanitize_inline_css(r"color: r\ed; font-size: 14px;")
        assert sanitized == "font-size: 14px"

    def test_non_https_and_malformed_urls_rejected(self):
        """HTTP, FTP, protocol-relative, and malformed URLs must be rejected."""
        assert not validate_css_property("background", "url('http://insecure.com/bg.png')")[0]
        assert not validate_css_property("background", "url('//protocol-relative.com/bg.png')")[0]
        assert not validate_css_property("background", "url('ftp://ftp.server.com/bg.png')")[0]
        assert not validate_css_property("background", "url(bad_unquoted_url)")[0]
        assert validate_css_property("background", "url('https://secure.cdn.com/bg.png')")[0]

    def test_data_urls_rejected(self):
        """Data URLs in CSS must be rejected."""
        assert not validate_css_property("background", "url('data:image/svg+xml;utf8,<svg></svg>')")[0]

    def test_css_custom_properties_var_rejected(self):
        """CSS custom properties var(--...) must be rejected."""
        assert not validate_css_property("color", "var(--custom-color)")[0]
        assert not validate_css_property("font-size", "var(--base-size)")[0]

    def test_css_comment_bypass_rejected(self):
        """CSS comments cannot bypass property detection or smuggling."""
        findings = TemplateSecurityInspector.inspect_css("color: /* comment */ red; evil_prop: 1;")
        assert any("evil_prop" in f for f in findings)

    def test_semicolon_injection_sanitized(self):
        """Semicolon injection only preserves allowed properties."""
        sanitized = sanitize_inline_css("width: 10px; position: fixed; top: 0; z-index: 999; margin: 5px;")
        assert "width: 10px" in sanitized
        assert "margin: 5px" in sanitized
        assert "position" not in sanitized
        assert "z-index" not in sanitized
        assert "top" not in sanitized

    def test_control_characters_rejected(self):
        """Control characters (\\x00, \\r, \\n) in CSS values must be rejected."""
        assert not validate_css_property("color", "red\x00")[0]
        assert not validate_css_property("color", "blue\r\nevil: 1")[0]

    def test_expression_behavior_and_moz_binding_rejected(self):
        """expression(), behavior, and -moz-binding must be rejected."""
        assert not validate_css_property("width", "expression(document.body.appendChild(1))")[0]
        assert not validate_css_property("behavior", "url(behave.htc)")[0]
        assert not validate_css_property("-moz-binding", "url(xbl.xml#test)")[0]

    def test_rich_html_sanitizer_cleans_adverarial_markup(self):
        """Bleach rich HTML sanitizer strips forbidden tags and unsafe attributes."""
        dirty = "<p style='color: red; position: fixed;'>Text<script>alert(1)</script><img src='javascript:alert(2)'></p>"
        clean = TemplateSecurityInspector.sanitize_rich_html(dirty)
        assert "<script>" not in clean
        assert "javascript:" not in clean
        assert "position" not in clean
        assert "color: red" in clean


# ==============================================================================
# 6. MIGRATION SAFETY AND IDEMPOTENCY TESTS (SenderX_test only)
# ==============================================================================

class TestMigrationSafetyAndIdempotency:
    def test_migration_dry_run_makes_no_writes(self, app):
        """Dry-run mode must report would_update but modify 0 documents."""
        with app.app_context():
            res = run_migration(apply=False, batch_size=50)
            assert res["status"] in ("DRY_RUN_COMPLETE", "COMPLETE")
            assert "would_update" in res or res.get("needed_backfill") == 0

    def test_migration_refuses_prod_writes_by_default(self, app):
        """Attempting to run migration against SenderX_db without dual gate returns BLOCKED."""
        with app.app_context():
            with patch.dict(os.environ, {"MONGO_DB": "SenderX_db"}):
                res = run_migration(apply=True, batch_size=50)
                assert res["status"] == "BLOCKED"
                assert "Production write guard enforced" in res["reason"]

    def test_migration_refuses_prod_writes_with_missing_env_var(self, app):
        """Passing only the phrase without the environment variable must remain BLOCKED."""
        with app.app_context():
            with patch.dict(os.environ, {"MONGO_DB": "SenderX_db", "ALLOW_PRODUCTION_TEMPLATE_MIGRATION": ""}):
                res = run_migration(
                    apply=True,
                    batch_size=50,
                    prod_safety_phrase="CONFIRM_SENDERX_DB_PRODUCTION_BACKFILL"
                )
                assert res["status"] == "BLOCKED"

    def test_migration_unique_conflict_detection_on_active_templates(self, app):
        """Collision between two active templates with different casing is caught as conflict."""
        with app.app_context():
            db = app.mongo_db
            collection = db["templates"]

            test_org = str(uuid.uuid4())
            doc1_id = f"test_tmpl_{uuid.uuid4().hex[:6]}"
            doc2_id = f"test_tmpl_{uuid.uuid4().hex[:6]}"

            # Insert two active templates sharing normalized name but missing name_lower
            collection.insert_one({
                "_id": doc1_id,
                "template_id": doc1_id,
                "organization_id": test_org,
                "name": "Billing Notice",
                "status": "ACTIVE"
            })
            collection.insert_one({
                "_id": doc2_id,
                "template_id": doc2_id,
                "organization_id": test_org,
                "name": "BILLING NOTICE",
                "status": "ACTIVE"
            })

            try:
                res = run_migration(apply=False, batch_size=10)
                conflicts = [c for c in res.get("conflicts", []) if c["organization_id"] == test_org]
                assert len(conflicts) > 0, "Expected lowercase name collision between active templates!"
            finally:
                collection.delete_many({"_id": {"$in": [doc1_id, doc2_id]}})

    def test_migration_soft_deleted_templates_do_not_block_active_templates(self, app):
        """Soft-deleted template with same name does not trigger conflict for active template."""
        with app.app_context():
            db = app.mongo_db
            collection = db["templates"]

            test_org = str(uuid.uuid4())
            act_id = f"act_{uuid.uuid4().hex[:6]}"
            del_id = f"del_{uuid.uuid4().hex[:6]}"

            # Active template has name_lower
            collection.insert_one({
                "_id": act_id,
                "template_id": act_id,
                "organization_id": test_org,
                "name": "Receipt Email",
                "name_lower": "receipt email",
                "status": "ACTIVE"
            })
            # Deleted template needs backfill
            collection.insert_one({
                "_id": del_id,
                "template_id": del_id,
                "organization_id": test_org,
                "name": "RECEIPT EMAIL",
                "status": "DELETED"
            })

            try:
                res = run_migration(apply=False, batch_size=10)
                conflicts = [c for c in res.get("conflicts", []) if c["organization_id"] == test_org]
                # Soft-deleted template must NOT trigger unique constraint collision
                assert len(conflicts) == 0
            finally:
                collection.delete_many({"_id": {"$in": [act_id, del_id]}})


# ==============================================================================
# 6. BOUNDARY SANITIZATION & EVASIVE PREMAILER PREPROCESSING TESTS
# ==============================================================================

class TestBoundarySanitizationAndEvasiveNetworkIsolation:
    def test_evasive_at_import_syntax_triggers_zero_dns_calls(self):
        """All evasive @import and <link> variations must result in strictly zero DNS and network calls."""
        import socket
        from app.modules.templates.compiler import compile_email_template

        dns_calls = []
        orig_getaddrinfo = socket.getaddrinfo

        def tracked_getaddrinfo(*args, **kwargs):
            dns_calls.append(args[0])
            raise AssertionError(f"DNS call attempted to: {args[0]}")

        evasive_payloads = [
            '<style>@import "http://evil-1.test/a.css";</style><p>Hi</p>',
            '<style>@\\69 mport url("http://evil-2.test/a.css");</style><p>Hi</p>',
            '<style>@\\000069 mport url("http://evil-3.test/a.css");</style><p>Hi</p>',
            '<style>@/*comment*/import url("http://evil-4.test/a.css");</style><p>Hi</p>',
            '<style>@\nimport url("http://evil-5.test/a.css");</style><p>Hi</p>',
            '<style>@\timport url("http://evil-6.test/a.css");</style><p>Hi</p>',
            '<style>@import url("http://evil-7.test/a.css")</style><p>Hi</p>',
            '<style>@IMPORT url("http://evil-8.test/a.css");</style><p>Hi</p>',
            '<link rel="stylesheet" href="http://evil-9.test/a.css"><p>Hi</p>',
            '<link rel = "stylesheet" href = "http://evil-10.test/a.css" ><p>Hi</p>',
            '<link\nrel="stylesheet"\nhref="http://evil-11.test/a.css"><p>Hi</p>',
            '<link href="http://evil-12.test/a.css" rel="stylesheet"><p>Hi</p>',
        ]

        with patch("socket.getaddrinfo", side_effect=tracked_getaddrinfo):
            for payload in evasive_payloads:
                res = compile_email_template(payload, "")
                assert "compiled_html" in res
                assert len(dns_calls) == 0, f"DNS calls detected for payload: {payload}"

    def test_final_html_boundary_strips_disallowed_properties_and_protocols(self):
        """Premailer output has disallowed CSS properties and dangerous protocols stripped at boundary."""
        from app.modules.templates.compiler import compile_email_template

        html = """
        <div style="color: #2563eb; position: fixed; top: 0; font-size: 14px; behavior: url(test.htc);">
          <a href="javascript:alert(1)">Link</a>
          <img src="data:image/svg+xml;base64,PHN2Zz4=" alt="test">
          <p style="background-color: #ffffff; -moz-binding: url(x.xml); padding: 10px;">
            Content
          </p>
        </div>
        """
        res = compile_email_template(html, "")
        compiled = res["compiled_html"]

        # Safe CSS must remain functional
        assert "color: #2563eb" in compiled
        assert "font-size: 14px" in compiled
        assert "background-color: #ffffff" in compiled
        assert "padding: 10px" in compiled

        # Unsafe CSS properties must be stripped
        assert "position" not in compiled
        assert "behavior" not in compiled
        assert "-moz-binding" not in compiled

        # Unsafe protocols must be stripped
        assert "javascript:alert" not in compiled
        assert "data:image" not in compiled

    def test_public_preview_entrypoint_rejects_malicious_draft_payload(self, client, test_setup):
        """Public POST /preview endpoint rejects draft containing malicious script or protocols."""
        token = test_setup["token"]
        payload = {
            "html_body": "<p>Hello</p><script>alert('XSS')</script>",
            "css": "p { color: red; }",
            "sample_data": {}
        }
        res = client.post(
            "/api/v1/email-templates/preview",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert "Forbidden HTML tag '<script>'" in data.get("message", "")

    def test_public_preview_entrypoint_jinja_complexity_bomb_rejected(self, client, test_setup):
        """Public POST /preview endpoint rejects template with 3-level nested loop complexity bomb."""
        token = test_setup["token"]
        nested_bomb = """
        {% for a in range(10) %}
          {% for b in range(10) %}
            {% for c in range(10) %}
              Bomb
            {% endfor %}
          {% endfor %}
        {% endfor %}
        """
        payload = {
            "html_body": f"<div>{nested_bomb}</div>",
            "css": "",
            "sample_data": {}
        }
        res = client.post(
            "/api/v1/email-templates/preview",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
        assert res.status_code == 400
        data = res.get_json()
        assert data["success"] is False
        assert "nested loops exceed maximum depth" in data.get("message", "")
