import re

with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

# Find global variables at the top of app.js
top_chunk = js[:4000]
print("=== TOP CHUNK OF APP.JS ===")
print(top_chunk[:2500])

# Find event listeners
listeners = re.findall(r'addEventListener\(["\']([^"\']+)["\']', js)
print(f"\n=== EVENT LISTENERS ({len(listeners)}) ===")
for l in set(listeners):
    print(f"  {l}")

