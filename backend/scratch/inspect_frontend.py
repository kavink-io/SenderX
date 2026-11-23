import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

view_matches = re.findall(r'<div[^>]*id=["\']view-([^"\']+)["\'][^>]*>', html)
modal_matches = re.findall(r'<div[^>]*id=["\']modal-([^"\']+)["\'][^>]*>', html)
nav_matches = re.findall(r'data-view=["\']([^"\']+)["\']', html)

print(f"=== VIEWS ({len(view_matches)}) ===")
for v in view_matches:
    print(f"  view-{v}")

print(f"\n=== NAV TARGETS ({len(set(nav_matches))}) ===")
for n in sorted(set(nav_matches)):
    print(f"  {n}")

print(f"\n=== MODALS ({len(modal_matches)}) ===")
for m in modal_matches:
    print(f"  modal-{m}")

with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

func_matches = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', js)
const_funcs = re.findall(r'(?:const|let|var)\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>', js)

print(f"\n=== JS FUNCTIONS ({len(func_matches)} declared, {len(const_funcs)} arrow) ===")
all_funcs = sorted(set(func_matches + const_funcs))
for fn in all_funcs[:30]:
    print(f"  {fn}")
print(f"  ... and {len(all_funcs) - 30} more")
