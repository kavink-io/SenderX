import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find main sections
sections = re.findall(r'<section[^>]*id=["\']([^"\']+)["\'][^>]*>', html)
print("=== SECTIONS ===")
for s in sections:
    print(f"  section id={s}")

# Find all id attributes with 'view' or 'section' or 'page' or 'panel'
all_ids = re.findall(r'id=["\']([^"\']+)["\']', html)
nav_links = re.findall(r'href=["\']#([^"\']+)["\']', html)
onclicks = re.findall(r'onclick=["\']([^"\']+)["\']', html)

print("\n=== HASH NAV LINKS ===")
for h in set(nav_links):
    print(f"  #{h}")

# Search for switchView or showView or similar in app.js
with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    js = f.read()

view_switches = re.findall(r'(?:switchView|showView|navigate|setActiveView|currentView)[^;\n]*', js)
print("\n=== VIEW SWITCHING IN JS ===")
for vs in view_switches[:20]:
    print(f"  {vs.strip()}")

# Find the main navigation items in index.html
sidebar_match = re.search(r'<aside[^>]*>([\s\S]*?)</aside>', html)
if sidebar_match:
    print("\n=== SIDEBAR CONTENT EXCERPT ===")
    print(sidebar_match.group(1)[:2000])
else:
    # search for sidebar div or class
    sb = re.search(r'<nav[^>]*class=["\'][^"\']*sidebar[^"\']*["\'][^>]*>([\s\S]*?)</nav>', html)
    if sb:
        print("\n=== SIDEBAR NAV EXCERPT ===")
        print(sb.group(1)[:2000])
    else:
        sb2 = re.search(r'<div[^>]*class=["\'][^"\']*sidebar[^"\']*["\'][^>]*>([\s\S]*?)</div>\s*<(?:main|div)', html)
        if sb2:
            print("\n=== SIDEBAR DIV EXCERPT ===")
            print(sb2.group(1)[:2000])

