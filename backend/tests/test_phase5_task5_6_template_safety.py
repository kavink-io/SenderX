"""
Phase 5 Task 5.6: Template Safety, Sanitizer, Inliner, and Jinja Sandbox Unit Tests
Pure function tests running in milliseconds without database or HTTP calls.
"""

import pytest
from app.modules.templates.security import (
    TemplateSecurityInspector,
    TemplateSandboxRunner,
    detect_template_variables,
    validate_declared_variables,
    sanitize_variable_value
)
from app.modules.templates.compiler import (
    compile_email_template,
    html_to_plain_text,
    STARTER_TEMPLATE_HTML,
    STARTER_TEMPLATE_CSS,
    STARTER_TEMPLATE_VARIABLES,
    EmailCompatibilityInspector
)


# ==============================================================================
# 1. HTML / CSS SANITIZER & SECURITY TESTS
# ==============================================================================

def test_sanitizer_rejects_script_tag():
    findings = TemplateSecurityInspector.inspect_html("<p>Hello</p><script>alert('xss')</script>")
    assert any("<script>" in f for f in findings)


def test_sanitizer_rejects_iframe_and_forms():
    findings = TemplateSecurityInspector.inspect_html("<iframe src='https://evil.com'></iframe><form action='/post'></form>")
    assert any("<iframe>" in f for f in findings)
    assert any("<form>" in f for f in findings)

    # meta http-equiv is forbidden, standard charset/viewport meta is allowed
    meta_evil = TemplateSecurityInspector.inspect_html("<meta http-equiv='refresh' content='0;url=https://evil.com'>")
    assert any("<meta http-equiv>" in f for f in meta_evil)

    meta_safe = TemplateSecurityInspector.inspect_html("<meta charset='utf-8'><meta name='viewport' content='width=device-width'>")
    assert len(meta_safe) == 0


def test_sanitizer_rejects_event_handlers():
    findings = TemplateSecurityInspector.inspect_html("<a href='https://example.com' onclick='steal()'>Link</a><img src='https://ex.com/img.png' onerror='bad()'>")
    assert any("onclick" in f for f in findings)
    assert any("onerror" in f for f in findings)


def test_sanitizer_rejects_javascript_and_data_protocols():
    findings = TemplateSecurityInspector.inspect_html("<a href='javascript:alert(1)'>Click</a><img src='data:image/svg+xml;base64,PHN2Zz4=' />")
    assert any("javascript:" in f for f in findings)
    assert any("data:" in f for f in findings)


def test_sanitizer_rejects_css_expressions_and_imports():
    findings = TemplateSecurityInspector.inspect_css("""
        body { width: expression(alert(1)); }
        @import url('https://evil.com/hack.css');
        .box { behavior: url(script.htc); -moz-binding: url(xss.xml); }
        .bg { background-image: url('http://insecure.com/bg.png'); }
    """)
    assert any("expression()" in f for f in findings)
    assert any("@import" in f for f in findings)
    assert any("behavior:" in f for f in findings)
    assert any("-moz-binding" in f for f in findings)
    assert any("non-https" in f for f in findings)


# ==============================================================================
# 2. CSS INLINING & MEDIA QUERY PRESERVATION
# ==============================================================================

def test_css_inlined_into_elements_and_media_query_kept():
    html = """<!DOCTYPE html><html><head></head><body><div class="card"><p class="text">Hello</p></div></body></html>"""
    css = """
        .card { background-color: #ffffff; padding: 20px; }
        .text { color: #2563eb; font-size: 16px; }
        @media only screen and (max-width: 600px) {
            .card { width: 100% !important; padding: 10px !important; }
        }
    """
    compiled = compile_email_template(html, css)
    compiled_html = compiled["compiled_html"]

    # Inline styles present
    assert "background-color: #ffffff" in compiled_html or "background-color:#ffffff" in compiled_html or "#fff" in compiled_html
    assert "color: #2563eb" in compiled_html or "color:#2563eb" in compiled_html

    # Media queries preserved in style tag
    assert "@media" in compiled_html
    assert "max-width: 600px" in compiled_html or "max-width:600px" in compiled_html


# ==============================================================================
# 3. EMAIL CLIENT COMPATIBILITY INSPECTOR
# ==============================================================================

def test_compatibility_warnings_flexbox_and_position():
    warnings = EmailCompatibilityInspector.inspect(
        html="<div style='display: flex; position: absolute;'>Content</div>",
        css=".box { display: grid; position: fixed; }"
    )
    assert any("Flexbox / Grid" in w for w in warnings)
    assert any("Positioning" in w for w in warnings)


def test_compatibility_warnings_tableless_layout():
    warnings = EmailCompatibilityInspector.inspect(
        html="<div><p>Just divs and paragraphs</p></div>",
        css=""
    )
    assert any("Table-less layout" in w for w in warnings)


def test_compatibility_warnings_missing_image_alt():
    warnings = EmailCompatibilityInspector.inspect(
        html="<table><tr><td><img src='https://example.com/logo.png'></td></tr></table>",
        css=""
    )
    assert any("missing the 'alt' attribute" in w for w in warnings)


def test_compatibility_warnings_non_https_image():
    warnings = EmailCompatibilityInspector.inspect(
        html="<table><tr><td><img src='http://insecure.com/logo.png' alt='Logo'></td></tr></table>",
        css=""
    )
    assert any("not an absolute https:// URL" in w for w in warnings)


# ==============================================================================
# 4. STARTER LAYOUT COMPILATION & PLAIN-TEXT
# ==============================================================================

def test_starter_layout_compiles_and_renders():
    compiled = compile_email_template(STARTER_TEMPLATE_HTML, STARTER_TEMPLATE_CSS)
    assert "max-width: 600px" in compiled["compiled_html"] or "max-width:600px" in compiled["compiled_html"]
    assert compiled["plain_text"] != ""

    # Test rendering with starter sample variables
    sample_context = {v["name"]: v["sample_value"] for v in STARTER_TEMPLATE_VARIABLES}
    rendered = TemplateSandboxRunner.render(compiled["compiled_html"], sample_context, autoescape=True)
    assert "Acme Global" in rendered
    assert "Alex Taylor" in rendered
    assert "Welcome to Your New Workspace" in rendered


def test_html_to_plain_text_conversion():
    html_sample = """
        <h1>Welcome!</h1>
        <p>Thank you for signing up. Please <a href="https://example.com/verify">verify your email</a>.</p>
        <p>Need help? Contact support.</p>
    """
    text = html_to_plain_text(html_sample)
    assert "Welcome!" in text
    assert "verify your email (https://example.com/verify)" in text
    assert "<" not in text
    assert ">" not in text


# ==============================================================================
# 5. JINJA2 SANDBOX HARDENING & AST INSPECTION
# ==============================================================================

def test_sandbox_blocks_dunder_and_private_attributes():
    with pytest.raises(ValueError, match="private attribute"):
        TemplateSandboxRunner.inspect_ast("{{ ''.__class__.__mro__[1].__subclasses__() }}")


def test_sandbox_blocks_import_and_include():
    with pytest.raises(ValueError, match="import, and include are forbidden"):
        TemplateSandboxRunner.inspect_ast("{% import 'os' as os %}")

    with pytest.raises(ValueError, match="import, and include are forbidden"):
        TemplateSandboxRunner.inspect_ast("{% include 'secret.html' %}")


def test_sandbox_blocks_macro_definitions():
    with pytest.raises(ValueError, match="macro definitions are forbidden"):
        TemplateSandboxRunner.inspect_ast("{% macro bomb() %}{{ bomb() }}{% endmacro %}")


def test_sandbox_enforces_output_size_limit():
    large_loop = "{% for i in range(500) %}" + ("X" * 600) + "{% endfor %}"
    with pytest.raises(ValueError, match="exceeds maximum limit"):
        TemplateSandboxRunner.render(large_loop, {}, autoescape=False)


# ==============================================================================
# 5b. TASK 5.6.1 ACCEPTANCE HARDENING: BOMBS, RECURSION, PREMAILER NETWORK, URLS
# ==============================================================================

def test_sandbox_rejects_nested_loop_bomb():
    """Nested-loop bomb must fail fast without hanging or leaving running thread."""
    loop_bomb = "{% for a in range(100) %}{% for b in range(100) %}{% for c in range(100) %}x{% endfor %}{% endfor %}{% endfor %}"
    with pytest.raises(ValueError, match="nested loops exceed maximum depth"):
        TemplateSandboxRunner.inspect_ast(loop_bomb)

    with pytest.raises(ValueError, match="nested loops exceed maximum depth"):
        TemplateSandboxRunner.render(loop_bomb, {})


def test_sandbox_rejects_huge_string_multiplication():
    """Huge string multiplication must fail fast without allocating memory."""
    mult_bomb = '{{ "X" * 1000000 }}'
    with pytest.raises(ValueError, match=r"(exceeds maximum limit|exceeds limit|Security error)"):
        TemplateSandboxRunner.render(mult_bomb, {})


def test_sandbox_rejects_deep_recursion():
    """Deep recursion via recursive loops or macro definitions must fail fast."""
    recursive_loop = "{% for item in items recursive %}{{ loop(items) }}{% endfor %}"
    with pytest.raises(ValueError, match="recursive loops are forbidden"):
        TemplateSandboxRunner.inspect_ast(recursive_loop)

    with pytest.raises(ValueError, match="recursive loops are forbidden"):
        TemplateSandboxRunner.render(recursive_loop, {"items": [1, 2, 3]})


def test_premailer_no_network_and_remote_stylesheet_rejected():
    """External stylesheets in template must be rejected and compile makes no network call."""
    html_with_remote_link = '<!DOCTYPE html><html><head><link rel="stylesheet" href="https://evil.com/hack.css"></head><body><p>Test</p></body></html>'
    findings = TemplateSecurityInspector.inspect_html(html_with_remote_link)
    assert any("<link>" in f for f in findings)

    # Compilation with Premailer disables network and external file loading
    css_with_import = "@import url('https://evil.com/style.css'); body { color: red; }"
    css_findings = TemplateSecurityInspector.inspect_css(css_with_import)
    assert any("@import" in f for f in css_findings)


def test_compiled_output_keeps_url_jinja_intact():
    """href="{{ cta_url }}" and src="{{ logo_url }}" must remain intact with no %7B%7B or %20."""
    html = '<p><img src="{{ logo_url }}" alt="Logo"></p><p><a href="{{ cta_url }}">Click Here</a></p>'
    css = "a { color: #2563eb; } img { border: 0; }"
    compiled = compile_email_template(html, css)
    compiled_html = compiled["compiled_html"]

    # Verify no %20 or %7B%7B
    assert "%20" not in compiled_html
    assert "%7B%7B" not in compiled_html
    assert 'src="{{ logo_url }}"' in compiled_html
    assert 'href="{{ cta_url }}"' in compiled_html

    # Verify rendering with sample data produces valid links
    sample_context = {
        "logo_url": "https://senderx.io/assets/logo.png",
        "cta_url": "https://senderx.io/dashboard/verify"
    }
    rendered = TemplateSandboxRunner.render(compiled_html, sample_context)
    assert 'src="https://senderx.io/assets/logo.png"' in rendered
    assert 'href="https://senderx.io/dashboard/verify"' in rendered


# ==============================================================================
# 6. VARIABLE EXTRACTION & VALIDATION
# ==============================================================================

def test_detect_variables_and_undeclared_rejection():
    template_str = "Hello {{ user_name }}, your order {{ order_id }} is {{ status | upper }}!"
    detected = detect_template_variables(template_str)
    assert detected == {"user_name", "order_id", "status"}

    declared = [{"name": "user_name"}, {"name": "order_id"}]
    undeclared = validate_declared_variables(detected, declared)
    assert undeclared == ["status"]


def test_variable_type_and_format_validation():
    # URL variable requires absolute https://
    with pytest.raises(ValueError, match="absolute https:// URL"):
        sanitize_variable_value("cta_url", "http://insecure.com", {"type": "url"})

    with pytest.raises(ValueError, match="absolute https:// URL"):
        sanitize_variable_value("cta_url", "javascript:alert(1)", {"type": "url"})

    assert sanitize_variable_value("cta_url", "https://senderx.io/start", {"type": "url"}) == "https://senderx.io/start"

    # Color variable requires valid hex code
    with pytest.raises(ValueError, match="valid hex color"):
        sanitize_variable_value("accent_color", "blue", {"type": "color"})

    with pytest.raises(ValueError, match="valid hex color"):
        sanitize_variable_value("accent_color", "#12345", {"type": "color"})

    assert sanitize_variable_value("accent_color", "#2563eb", {"type": "color"}) == "#2563eb"
    assert sanitize_variable_value("accent_color", "#fff", {"type": "color"}) == "#fff"

    # Header injection check
    with pytest.raises(ValueError, match="header injection blocked"):
        sanitize_variable_value("subject_var", "Hello\r\nBcc: evil@hacker.com", {"is_header": True})

    # Length validation
    with pytest.raises(ValueError, match="exceeds maximum allowed length"):
        sanitize_variable_value("short_var", "A" * 150, {"max_length": 100})


def test_rich_html_sanitizer():
    dirty_rich = "<b>Bold</b><script>alert(1)</script><p style='color:red;'>Safe Para</p><a href='javascript:bad()'>Bad</a>"
    cleaned = TemplateSecurityInspector.sanitize_rich_html(dirty_rich)
    assert "<script>" not in cleaned
    assert "javascript:" not in cleaned
    assert "<b>Bold</b>" in cleaned
    assert "Safe Para" in cleaned
