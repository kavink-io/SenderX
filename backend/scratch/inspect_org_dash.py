with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines[500:750]):
    print(f"{i+501:3d}: {line}", end="")
