import sys
sys.path.insert(0, 'backend')
import socket
import re
from premailer import Premailer

dns_calls = []
orig_getaddrinfo = socket.getaddrinfo
def mock_getaddrinfo(*args, **kwargs):
    dns_calls.append(args[0] if args else kwargs.get('host'))
    raise socket.gaierror(-2, 'Name or service not known')

socket.getaddrinfo = mock_getaddrinfo

html = '<html><head><style>@import url("http://external-evil.com/style.css"); body { color: red; }</style></head><body><p>Hello</p></body></html>'
css = '@import url("http://another-evil.com/leak.css"); p { font-size: 14px; }'

merged_html = f"<style>{css}</style>{html}"

# Apply the stripping
cleaned_html = re.sub(r"@import\b[^;]+;?", "", merged_html, flags=re.IGNORECASE)
cleaned_html = re.sub(r"<link\b[^>]*>", "", cleaned_html, flags=re.IGNORECASE)

p = Premailer(
    cleaned_html,
    preserve_handlebar_syntax=True,
    allow_network=False,
    allow_loading_external_files=False,
    keep_style_tags=True,
    strip_important=False
)
compiled = p.transform()

print('DNS calls made after stripping:', dns_calls)
print('Compiled HTML contains:', compiled)
