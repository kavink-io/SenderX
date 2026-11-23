import re

with open("frontend/css/style.css", "r", encoding="utf-8") as f:
    css = f.read()

# Find root variables
root_match = re.search(r':root\s*\{([\s\S]*?)\}', css)
if root_match:
    print("=== ROOT CSS VARIABLES ===")
    vars_found = [line.strip() for line in root_match.group(1).splitlines() if line.strip().startswith("--")]
    for v in vars_found:
        print(f"  {v}")

# Find [data-theme="light"] variables
light_match = re.search(r'\[data-theme=["\']?light["\']?\]\s*\{([\s\S]*?)\}', css)
if light_match:
    print("\n=== LIGHT THEME OVERRIDES ===")
    vars_found = [line.strip() for line in light_match.group(1).splitlines() if line.strip().startswith("--")]
    for v in vars_found:
        print(f"  {v}")

# Find all @media queries
media_queries = re.findall(r'@media[^{]+', css)
print(f"\n=== MEDIA QUERIES ({len(media_queries)}) ===")
for mq in set(media_queries):
    print(f"  {mq.strip()}")
