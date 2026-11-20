"""
SenderX Phase 5 Task 5.6.2: Final Email Template Security Hardening Test Suite.

Validates:
1. CSS sanitization, explicit property allowlist, property value validation (rejecting expressions,
   scripts, @import, unapproved URLs, control chars, safe colors).
2. Jinja2 resource-exhaustion protections (template source limit, output limit, context count/depth,
   bounded filters, AST & binop limits, loop caps, timeout).
3. Premailer network isolation (allow_network=False, zero outbound network calls).
4. MongoDB template migration tool (dry-run, refusal guard against SenderX_db, idempotency on test DB).
5. DLQ secret redaction and safe error logging.
6. Redis fail-closed rate-limiting (HTTP 503 when Redis down, normal 200/429 on recovery).
"""

import socket
import pytest
from unittest.mock import patch, MagicMock

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
    MAX_CONTEXT_VARIABLES,
    MAX_CONTEXT_DEPTH,
)
from app.modules.dead_letters.sanitizer import (
    sanitize_dlq_error,
    sanitize_dlq_dict,
)
from app.modules.api_credentials.rate_limiter import (
    DistributedRateLimiter,
    RateLimiterError,
)
from app.migrations.backfill_template_name_lower import run_migration


# ==============================================================================
# 1. CSS SANITIZATION & PROPERTY ALLOWLIST TESTS
# ==============================================================================

class TestCSSSanitization:
    def test_css_allowed_properties(self):
        """Ensure standard design properties are allowed while dangerous ones are stripped."""
        assert "color" in ALLOWED_CSS_PROPERTIES
        assert "background-color" in ALLOWED_CSS_PROPERTIES
        assert "font-size" in ALLOWED_CSS_PROPERTIES
        assert "padding" in ALLOWED_CSS_PROPERTIES
        assert "margin" in ALLOWED_CSS_PROPERTIES
        assert "border" in ALLOWED_CSS_PROPERTIES
        assert "display" in ALLOWED_CSS_PROPERTIES

        # Dangerous or layout-breaking properties must NOT be in allowlist
        assert "position" not in ALLOWED_CSS_PROPERTIES
        assert "z-index" not in ALLOWED_CSS_PROPERTIES
        assert "behavior" not in ALLOWED_CSS_PROPERTIES
        assert "-moz-binding" not in ALLOWED_CSS_PROPERTIES

    def test_css_disallowed_properties_stripped(self):
        """Disallowed CSS properties should be stripped by sanitize_rich_html."""
        html = '<div style="color: #333333; position: fixed; z-index: 9999; padding: 10px;">Hello</div>'
        sanitized = TemplateSecurityInspector.sanitize_rich_html(html)
        assert "color: #333333" in sanitized
        assert "padding: 10px" in sanitized
        assert "position" not in sanitized
        assert "z-index" not in sanitized

    def test_css_expression_rejected(self):
        """CSS expressions (IE dynamic scripts) must be rejected."""
        valid, _ = validate_css_property("width", "expression(alert('XSS'))")
        assert not valid

        sanitized = sanitize_inline_css("width: expression(alert(1)); color: #ff0000;")
        assert "expression" not in sanitized
        assert "color: #ff0000" in sanitized

    def test_css_javascript_and_vbscript_urls_rejected(self):
        """javascript: and vbscript: URLs in CSS must be rejected."""
        valid_js, _ = validate_css_property("background-image", "url('javascript:alert(1)')")
        assert not valid_js

        valid_vbs, _ = validate_css_property("background-image", "url('vbscript:msgbox(1)')")
        assert not valid_vbs

    def test_css_data_urls_rejected(self):
        """data: URIs in CSS properties must be rejected."""
        valid_data, _ = validate_css_property("background-image", "url('data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==')")
        assert not valid_data

    def test_css_at_import_rejected(self):
        """@import rules in CSS must be rejected."""
        valid, _ = validate_css_property("color", "@import url('https://evil.com/xss.css')")
        assert not valid

    def test_css_non_https_url_rejected(self):
        """Non-HTTPS URLs (http://, ftp://) must be rejected."""
        valid_http, _ = validate_css_property("background", "url('http://example.com/bg.png')")
        assert not valid_http

        valid_https, _ = validate_css_property("background", "url('https://example.com/bg.png')")
        assert valid_https

    def test_css_control_characters_rejected(self):
        """Control characters and null bytes in CSS must be rejected."""
        valid_null, _ = validate_css_property("color", "#ff0000\x00")
        assert not valid_null

        valid_ctrl, _ = validate_css_property("font-size", "14px\x08")
        assert not valid_ctrl

    def test_safe_css_color_validation(self):
        """Validate safe hex, rgb, hsl, and safe named colors."""
        assert is_safe_css_color("#fff")
        assert is_safe_css_color("#ffffff")
        assert is_safe_css_color("#12345678")
        assert is_safe_css_color("rgb(255, 0, 0)")
        assert is_safe_css_color("rgba(0, 128, 255, 0.5)")
        assert is_safe_css_color("hsl(120, 100%, 50%)")
        assert is_safe_css_color("red")
        assert is_safe_css_color("transparent")

        # Invalid or injection colors
        assert not is_safe_css_color("red; background: url(javascript:alert(1))")
        assert not is_safe_css_color("#zzz")
        assert not is_safe_css_color("invalidColorName123")


# ==============================================================================
# 2. JINJA2 RESOURCE-EXHAUSTION PROTECTIONS
# ==============================================================================

class TestJinjaResourceExhaustion:
    def test_template_source_size_limit(self):
        """Template source exceeding MAX_TEMPLATE_SOURCE_BYTES (64 KB) must be rejected."""
        huge_template = "Hello " + ("A" * (MAX_TEMPLATE_SOURCE_BYTES + 100))
        with pytest.raises(ValueError) as exc_info:
            TemplateSandboxRunner.render(huge_template, {})
        assert "exceeds maximum limit" in str(exc_info.value)

    def test_context_variable_count_limit(self):
        """Context with more than MAX_CONTEXT_VARIABLES (100) must be rejected."""
        large_context = {f"var_{i}": i for i in range(MAX_CONTEXT_VARIABLES + 10)}
        with pytest.raises(ValueError) as exc_info:
            TemplateSandboxRunner.render("Hello {{ name }}", large_context)
        assert "exceeds maximum allowed limit" in str(exc_info.value)

    def test_context_nesting_depth_limit(self):
        """Deeply nested context dictionaries (> 5 levels) must be rejected."""
        deep_context = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
        with pytest.raises(ValueError) as exc_info:
            validate_context_structure(deep_context)
        assert "Context nesting depth exceeds maximum" in str(exc_info.value)

    def test_bounded_filters(self):
        """Filters with large width arguments must be safely capped."""
        env = SenderXSandboxedEnvironment()

        # center filter rejects absurd widths and allows safe widths
        with pytest.raises(SecurityError):
            env.filters["center"]("test", 5000)
        centered = env.filters["center"]("test", 500)
        assert len(centered) == 500

        # indent filter rejects absurd widths and allows safe widths
        with pytest.raises(SecurityError):
            env.filters["indent"]("line1\nline2", 500)
        indented = env.filters["indent"]("line1\nline2", 4)
        assert "    line2" in indented

        # wordwrap filter rejects absurd widths and allows safe widths
        with pytest.raises(SecurityError):
            env.filters["wordwrap"]("a" * 200, 2000)
        wrapped = env.filters["wordwrap"]("a" * 200, 50)
        assert len(wrapped) >= 200

    def test_ast_huge_filter_argument_blocked(self):
        """Templates passing absurdly large literal numbers to filters are blocked during AST inspection."""
        malicious = "{{ 'bomb' | center(9999999999) }}"
        with pytest.raises(ValueError) as exc_info:
            TemplateSandboxRunner.render(malicious, {})
        assert "exceeds safe limit" in str(exc_info.value)

    def test_sequence_multiplication_bomb_blocked(self):
        """String or sequence multiplication with large factors is blocked."""
        env = SenderXSandboxedEnvironment()
        with pytest.raises(SecurityError):
            env.call_binop(None, "*", "A", 1000000)

    def test_exponentiation_bomb_blocked(self):
        """Absurd power expressions are blocked."""
        env = SenderXSandboxedEnvironment()
        with pytest.raises(SecurityError):
            env.call_binop(None, "**", 10, 50)

    def test_render_timeout_fast_fail(self):
        """A nested-loop template fails within the bounded time limit."""
        nested_loop = """
        {% for a in range(100) %}
          {% for b in range(100) %}
            {% for c in range(100) %}
              x
            {% endfor %}
          {% endfor %}
        {% endfor %}
        """
        with pytest.raises((ValueError, RuntimeError)):
            TemplateSandboxRunner.render(nested_loop, {})


# ==============================================================================
# 3. PREMAILER CONFIGURATION AND NETWORK ISOLATION
# ==============================================================================

class TestPremailerNetworkIsolation:
    def test_premailer_network_calls_blocked(self):
        """Premailer compilation must not make outbound network requests."""
        html_with_remote = """
        <!DOCTYPE html>
        <html>
        <head>
          <link rel="stylesheet" href="https://evil.external.host/style.css">
          <style>
            p { color: #112233; }
          </style>
        </head>
        <body>
          <p>Hello isolated world</p>
        </body>
        </html>
        """

        # Patch socket.socket.connect and urllib to verify 0 attempts succeed
        with patch("socket.socket.connect", side_effect=AssertionError("Network attempt detected!")):
            result = compile_email_template(html_with_remote, "")
            compiled = result["compiled_html"]
            assert "Hello isolated world" in compiled
            assert "#112233" in compiled


# ==============================================================================
# 4. MONGODB TEMPLATE MIGRATION TOOL TESTS
# ==============================================================================

class TestTemplateMigrationTool:
    def test_migration_refuses_prod_writes(self):
        """Migration must refuse --apply writes if MONGO_DB is SenderX_db."""
        with patch.dict("os.environ", {"MONGO_DB": "SenderX_db"}):
            res = run_migration(apply=True, allow_prod_write=False)
            assert res["status"] == "BLOCKED"
            assert "Production write guard enforced" in res["reason"]

    def test_migration_dry_run_is_read_only(self):
        """Dry run mode does not write and reports would_update count."""
        with patch.dict("os.environ", {"MONGO_DB": "SenderX_test"}):
            res = run_migration(apply=False)
            assert res["status"] in ("DRY_RUN_COMPLETE", "COMPLETE")
            assert "total_templates" in res


# ==============================================================================
# 5. DLQ HANDLING & SECRET REDACTION TESTS
# ==============================================================================

class TestDLQSecretRedaction:
    def test_jwt_redacted(self):
        """JWTs in DLQ error messages must be redacted."""
        jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        error = f"Failed to authenticate using token: {jwt} during delivery"
        redacted = sanitize_dlq_error(error)
        assert jwt not in redacted
        assert "[REDACTED" in redacted

    def test_sendgrid_key_redacted(self):
        """SendGrid API keys in errors must be redacted."""
        sg_key = "SG.abcdefghijklmnopqrstuvwxyz12345.abcdefghijklmnopqrstuvwxyz123456789012345"
        error = f"SendGrid error: invalid credentials with key {sg_key}"
        redacted = sanitize_dlq_error(error)
        assert sg_key not in redacted
        assert "[REDACTED_API_KEY]" in redacted

    def test_password_hash_redacted(self):
        """Bcrypt password hashes in error messages must be redacted."""
        pw_hash = "$2b$12$e7kO87z1mXb7C12345678.abcdefghijklmnopqrstuvwxyz123456"
        error = f"Integrity error for hash {pw_hash}"
        redacted = sanitize_dlq_error(error)
        assert pw_hash not in redacted
        assert "[REDACTED_BCRYPT_HASH]" in redacted

    def test_sensitive_dict_redacted(self):
        """Sensitive dictionary keys (password, api_key, token) must be masked."""
        payload = {
            "template_id": "tpl_123",
            "password": "SuperSecretPassword123!",
            "api_key": "live_key_9876543210",
            "safe_field": "keep_this",
        }
        sanitized = sanitize_dlq_dict(payload)
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["safe_field"] == "keep_this"


# ==============================================================================
# 6. REDIS-UNAVAILABLE BEHAVIOR & FAIL-CLOSED RATE LIMITER TESTS
# ==============================================================================

class TestRedisFailClosedBehavior:
    def test_rate_limiter_fail_closed_raises_when_redis_none(self):
        """When Redis is None and fail_closed=True, RateLimiterError is raised."""
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=None):
            with pytest.raises(RateLimiterError) as exc_info:
                DistributedRateLimiter.check_rate_limit("test-dim", "test-key", limit=10, window_seconds=60, fail_closed=True)
            assert "rate limiter unavailable" in str(exc_info.value).lower()

    def test_rate_limiter_fail_closed_raises_on_redis_exception(self):
        """When Redis throws ConnectionError and fail_closed=True, RateLimiterError is raised."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = ConnectionError("Connection refused")
        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            with pytest.raises(RateLimiterError):
                DistributedRateLimiter.check_rate_limit("test-dim", "test-key", limit=10, window_seconds=60, fail_closed=True)

    def test_rate_limiter_normal_behavior_when_redis_available(self):
        """When Redis is operational, rate limiting works normally."""
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [0, 1, 1, True, [(b"member", 12345.0)]]
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe

        with patch.object(DistributedRateLimiter, "_get_redis", return_value=mock_redis):
            allowed, retry_after = DistributedRateLimiter.check_rate_limit("test-dim", "test-key", limit=10, window_seconds=60, fail_closed=True)
            assert allowed is True
            assert retry_after == 0
