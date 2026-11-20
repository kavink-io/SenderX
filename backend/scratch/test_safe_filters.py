import jinja2
from jinja2 import nodes
from jinja2.sandbox import SandboxedEnvironment, SecurityError

class TestEnv(SandboxedEnvironment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Wrap center filter
        orig_center = self.filters["center"]
        def safe_center(val, width=80):
            if width > 1000:
                raise SecurityError("Filter width exceeds safe limit (max 1000)")
            return orig_center(val, width)
        self.filters["center"] = safe_center

env = TestEnv()
try:
    env.from_string("{{ 'x' | center(5000000) }}").render()
    print("Failed to catch huge center")
except (SecurityError, jinja2.exceptions.TemplateRuntimeError) as e:
    print("Successfully caught huge center:", e)
