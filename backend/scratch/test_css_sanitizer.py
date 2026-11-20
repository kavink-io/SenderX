import bleach
from bleach.css_sanitizer import CSSSanitizer

allowed_props = ['color', 'background-color', 'font-size', 'padding', 'margin', 'border', 'width']
cs = CSSSanitizer(allowed_css_properties=allowed_props)

samples = [
    '<p style="color: red; font-size: 14px;">Hello</p>',
    '<p style="color: expression(alert(1));">Malicious expression</p>',
    '<p style="background-color: #ff0000;">Safe bg</p>',
    '<p style="color: red; position: fixed; z-index: 9999;">Disallowed props</p>',
    '<p style="background-color: url(javascript:alert(1));">JS URL</p>',
    '<p style="color: rgba(255, 0, 0, 0.5);">RGBA</p>',
    '<p style="color: #123456;">Hex</p>',
    '<p style="color: #xyz;">Invalid hex</p>'
]

for s in samples:
    cleaned = bleach.clean(s, tags=['p'], attributes={'p': ['style']}, css_sanitizer=cs)
    print(f"INPUT:  {s}\nOUTPUT: {cleaned}\n")
