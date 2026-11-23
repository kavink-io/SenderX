import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find all divs with class="modal" or class="modal ... "
modals = re.findall(r'<div[^>]*class=["\'][^"\']*modal(?:\s+[^"\']*)?["\'][^>]*id=["\']([^"\']+)["\']|<div[^>]*id=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*modal(?:\s+[^"\']*)?["\']', html)
modal_ids = [m[0] or m[1] for m in modals]
print("All modals found by modal class:")
for mid in modal_ids:
    print(f"  {mid}")
