import time
import concurrent.futures
from app.modules.templates.security import (
    TemplateSandboxRunner,
    TemplateSecurityInspector,
    MAX_RENDERED_OUTPUT_BYTES,
)

tests = {
    'large_nested_loop_output': '{% for x in range(100) %}{% for y in range(100) %}x{% endfor %}{% endfor %}',
    'nested_loop_depth_3': '{% for a in range(10) %}{% for b in range(10) %}{% for c in range(10) %}x{% endfor %}{% endfor %}{% endfor %}',
    'huge_range_literal': '{% for x in range(1000) %}x{% endfor %}',
    'sequence_mult': '{{ "A" * 500000 }}',
    'exponentiation': '{{ 10 ** 100 }}',
    'output_limit_exceeded': '{{ "A" * 300000 }}',
}

print("=== TEMPLATE ISOLATION BENCHMARK RESULTS ===")
for name, tpl in tests.items():
    t0 = time.time()
    try:
        res = TemplateSandboxRunner.render(tpl, {})
        print(f"PASS {name}: COMPLETED in {time.time()-t0:.4f}s (len={len(res)})")
    except Exception as e:
        print(f"BLOCK {name}: BLOCKED in {time.time()-t0:.4f}s with {type(e).__name__}: {e}")

# Large collection iteration
ctx = {'items': list(range(1000))}
t0 = time.time()
try:
    res = TemplateSandboxRunner.render('{% for x in items %}{{ x }} {% endfor %}', ctx)
    print(f"PASS large_collection_1000: COMPLETED in {time.time()-t0:.4f}s (len={len(res)})")
except Exception as e:
    print(f"BLOCK large_collection_1000: with {e}")

# Excessive collection iteration (> 1000 items in context)
ctx_large = {'items': list(range(2000))}
t0 = time.time()
try:
    res = TemplateSandboxRunner.render('{% for x in items %}{{ x }} {% endfor %}', ctx_large)
    print(f"PASS large_collection_2000: COMPLETED in {time.time()-t0:.4f}s (len={len(res)})")
except Exception as e:
    print(f"BLOCK large_collection_2000: BLOCKED in {time.time()-t0:.4f}s with {type(e).__name__}: {e}")

# Concurrent requests benchmark
def run_render(i):
    return TemplateSandboxRunner.render('Hello {{ name }} #{{ i }}', {'name': 'World', 'i': i})

t0 = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(run_render, i) for i in range(50)]
    results = [f.result() for f in futures]
print(f"PASS concurrent_50_renders: COMPLETED in {time.time()-t0:.4f}s (all {len(results)} success)")
