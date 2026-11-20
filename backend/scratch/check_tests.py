import re
import glob

test_files = glob.glob("backend/tests/test_*.py")
for tf in test_files:
    with open(tf, "r", encoding="utf-8") as f:
        content = f.read()
    
    # We want to see where client.post("/api/v1/users/", ...) includes "password": "..."
    # Match pattern
    pattern = r'(\s*)"password":\s*"[^"]+",?\n'
    # Look for occurrences inside json={...} for /api/v1/users/
    count = 0
    lines = content.split("\n")
    in_user_post = False
    new_lines = []
    modified = False
    
    for i, line in enumerate(lines):
        if '/api/v1/users/' in line and 'client.post' in line:
            in_user_post = True
        elif in_user_post and ')' in line and not '{' in line:
            in_user_post = False
        
        # Check if line is "password": "..." while in_user_post (but NOT /api/v1/users/self/... or /api/v1/auth/...)
        # Wait, let's see which specific files fail!
        pass

print("Done scanning.")
