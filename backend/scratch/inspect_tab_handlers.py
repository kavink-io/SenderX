import re

with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

# Find handleTabActivation or switchTab
m = re.search(r'function\s+switchTab\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', js)
if m:
    print("=== switchTab ===")
    print(m.group(1)[:1500])

m2 = re.search(r'function\s+handleTabActivation\s*\([^)]*\)\s*\{([\s\S]*?)\n\}', js)
if m2:
    print("\n=== handleTabActivation ===")
    print(m2.group(1)[:1500])

# Find all loader functions
loaders = re.findall(r'function\s+(load[a-zA-Z0-9_]+)\s*\(', js)
print(f"\n=== LOAD FUNCTIONS ({len(loaders)}) ===")
for l in loaders:
    print(f"  {l}")

