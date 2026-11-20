with open('frontend/js/app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'Close' in line:
        print(f'{i+1}: {line.strip()}')
