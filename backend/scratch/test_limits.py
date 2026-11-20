import time
import jinja2
from jinja2 import nodes
from jinja2.sandbox import SandboxedEnvironment, SecurityError

class HardenedSandboxedEnv(SandboxedEnvironment):
    intercepted_binops = frozenset(['*', '**', '+'])
    def call_binop(self, context, op, l, r):
        if op == '*':
            if isinstance(l, (str, list, tuple)) and isinstance(r, int) and len(l) * r > 262144:
                raise SecurityError(f"Multiplication size {len(l)*r} exceeds 256 KB limit")
            if isinstance(r, (str, list, tuple)) and isinstance(l, int) and len(r) * l > 262144:
                raise SecurityError(f"Multiplication size {len(r)*l} exceeds 256 KB limit")
        elif op == '**' and isinstance(r, (int, float)) and r > 100:
            raise SecurityError("Exponentiation exceeds limit")
        return super().call_binop(context, op, l, r)

def inspect_ast(text):
    env = HardenedSandboxedEnv()
    ast = env.parse(text)
    for n in ast.find_all(nodes.For):
        if getattr(n, 'recursive', False):
            raise ValueError("Recursive loops are forbidden")
    def get_depth(node):
        max_c = 0
        for c in node.iter_child_nodes():
            max_c = max(max_c, get_depth(c))
        if isinstance(node, nodes.For):
            return 1 + max_c
        return max_c
    depth = get_depth(ast)
    if depth > 2:
        raise ValueError(f"Nested loop depth {depth} exceeds max allowed depth of 2")

t0 = time.perf_counter()
try:
    inspect_ast('{% for a in range(100) %}{% for b in range(100) %}{% for c in range(100) %}x{% endfor %}{% endfor %}{% endfor %}')
    print('Loop bomb not caught')
except ValueError as e:
    print(f"Test (a) nested loop bomb caught in {(time.perf_counter()-t0)*1000:.2f}ms: {e}")

t0 = time.perf_counter()
try:
    env = HardenedSandboxedEnv()
    tmpl = env.from_string('{{ "A" * 1000000 }}')
    tmpl.render()
    print('Huge multiplication not caught')
except SecurityError as e:
    print(f"Test (b) huge multiplication caught in {(time.perf_counter()-t0)*1000:.2f}ms: {e}")

t0 = time.perf_counter()
try:
    inspect_ast('{% for x in items recursive %}{{ loop(items) }}{% endfor %}')
    print('Recursion not caught')
except ValueError as e:
    print(f"Test (c) deep recursion caught in {(time.perf_counter()-t0)*1000:.2f}ms: {e}")
