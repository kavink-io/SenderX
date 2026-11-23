import re

with open("frontend/index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find all modals and their titles / forms
modal_blocks = re.findall(r'(<div[^>]*id=["\'](modal-[^"\']+)["\'][^>]*>[\s\S]*?</div>\s*</div>\s*</div>)', html)
print(f"=== FOUND {len(modal_blocks)} MODAL BLOCKS ===")
for block, modal_id in modal_blocks:
    title_m = re.search(r'<h[234][^>]*>([^<]+)</h[234]>', block)
    title = title_m.group(1).strip() if title_m else "No title"
    forms = re.findall(r'<form[^>]*id=["\']([^"\']+)["\']', block)
    buttons = re.findall(r'<button[^>]*id=["\']([^"\']+)["\'][^>]*>([^<]+)</button>', block)
    print(f"\nModal ID: {modal_id}")
    print(f"  Title: {title}")
    if forms:
        print(f"  Forms: {forms}")
    btn_summary = [f"{bid} ({btxt.strip()})" for bid, btxt in buttons[:5]]
    print(f"  Buttons: {', '.join(btn_summary)}")
