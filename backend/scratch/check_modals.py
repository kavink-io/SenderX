import re

with open('frontend/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

parts = html.split('<div id="modal-')
for p in parts[1:]:
    modal_name = 'modal-' + p.split('"')[0]
    # find where modal ends (before next <div id="modal- or </body)
    end_idx = p.find('<!--') if '<!--' in p else len(p)
    block = p[:end_idx]
    btns = re.findall(r'<button[^>]*>(.*?)</button>', block, flags=re.DOTALL)
    clean_btns = [re.sub(r'<[^>]+>', '', b).strip() for b in btns]
    print(f'{modal_name}: {clean_btns}')
