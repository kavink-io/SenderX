import sys
sys.path.insert(0, "backend")
from app.modules.templates.security import sanitize_html_css_boundary

test_html = """
<div style="color: #2563eb; position: fixed; top: 0; font-size: 14px; behavior: url(test.htc);">
  <a href="javascript:alert(1)">Click me</a>
  <img src="data:image/svg+xml;base64,PHN2Zz4=" alt="test">
  <p style="background-color: #ffffff; -moz-binding: url(x.xml); padding: 10px;">
    Safe content
  </p>
</div>
"""

sanitized = sanitize_html_css_boundary(test_html)
print("Sanitized HTML:")
print(sanitized)

assert "position" not in sanitized
assert "behavior" not in sanitized
assert "-moz-binding" not in sanitized
assert "javascript:" not in sanitized
assert "data:" not in sanitized
assert "color: #2563eb" in sanitized
assert "font-size: 14px" in sanitized
assert "background-color: #ffffff" in sanitized
assert "padding: 10px" in sanitized
print("ALL ASSERTIONS PASSED!")
