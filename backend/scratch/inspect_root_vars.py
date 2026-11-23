import re

with open("frontend/css/style.css", "r", encoding="utf-8") as f:
    css = f.read()

root_match = re.search(r':root\s*\{([\s\S]*?)\}', css)
if root_match:
    print("=== ROOT CSS VARIABLES ===")
    print(root_match.group(1))
