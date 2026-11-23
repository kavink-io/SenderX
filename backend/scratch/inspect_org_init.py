with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines[260:500]):
    print(f"{i+261:3d}: {line}", end="")
