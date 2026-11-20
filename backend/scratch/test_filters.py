import jinja2

env = jinja2.Environment()
print("Normal center:", env.from_string("{{ 'x' | center(10) }}").render())

# What filters exist?
print("Available filters count:", len(env.filters))
for f in ["center", "indent", "format", "wordwrap"]:
    print(f, f in env.filters)
