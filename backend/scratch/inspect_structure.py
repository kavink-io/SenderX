import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's see top level divs under <body>
body_content = re.search(r'<body[^>]*>([\s\S]*?)</body>', html).group(1)

# Find top level elements
top_level = re.findall(r'<div[^>]*class=["\']([^"\']+)["\'][^>]*id=["\']([^"\']+)["\']|<div[^>]*id=["\']([^"\']+)["\'][^>]*class=["\']([^"\']+)["\']', body_content)
print("=== TOP LEVEL CONTAINERS ===")
for t in top_level[:20]:
    print(t)

# Let's inspect the auth container
auth_match = re.search(r'(<div[^>]*id=["\']auth-[^>]*>[\s\S]*?</div>\s*<!-- App Layout)', html)
if not auth_match:
    auth_match = re.search(r'(<!-- Auth Container[\s\S]*?<!-- App Layout)', html)
if auth_match:
    print("\n=== AUTH CONTAINER EXCERPT ===")
    print(auth_match.group(1)[:1500])
else:
    # let's search for id="auth"
    m = re.search(r'<div[^>]*id=["\'](auth[^"\']*)["\'][^>]*>', html)
    if m:
        print(f"Found auth container: {m.group(0)}")

# Let's inspect the header/topbar
topbar = re.search(r'<header[^>]*>([\s\S]*?)</header>', html)
if topbar:
    print("\n=== HEADER / TOPBAR EXCERPT ===")
    print(topbar.group(1)[:1500])
