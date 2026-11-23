with open("frontend/js/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines[750:1000]):
    print(f"{i+751:3d}: {line}", end="")
