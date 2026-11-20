import re

files_to_clean = [
    "backend/tests/test_organizations_and_users.py",
    "backend/tests/test_phase5_task2_employee_roles.py",
    "backend/tests/test_phase5_task5_2_1_hardening.py",
    "backend/tests/test_phase5_task5_2_employee_id_role_profile.py",
    "backend/tests/test_phase5_task5_3_org_self_service.py",
    "backend/tests/test_phase5_task5_4_employee_delete_audit_ui.py"
]

for file_path in files_to_clean:
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    in_user_create_block = False
    
    for i, line in enumerate(lines):
        # We want to remove lines like:
        #   "password": "Password123!456",
        #   "password": "Password1234!@",
        #   "password": "StrongPassword123!",
        #   "password": f"Password123!{...}",
        # but NOT when creating an organization admin (admin_password) or testing login/password change!
        # Specifically, inside user_data dicts for UserService.create_user or client.post("/api/v1/users/", ...)
        
        # Check if line matches "password": "..." or 'password': '...'
        m = re.match(r'^(\s*)["\']password["\']:\s*["\'][^"\']+["\'],?\s*$', line)
        if m:
            # Let's inspect context: look back up to 10 lines
            context_window = "".join(lines[max(0, i-10):min(len(lines), i+10)])
            # If it's a test for /api/v1/auth/login or /api/v1/auth/change-password or /api/v1/organizations or admin_password or old_password/new_password, keep it!
            if any(k in context_window for k in ["/auth/login", "current_password", "new_password", "admin_password", "reset_password", "change-password"]):
                new_lines.append(line)
            elif "/api/v1/users/" in context_window or "UserService.create_user" in context_window or "user_data = {" in context_window or "emp_res = client.post" in context_window or "res = client.post(\n        \"/api/v1/users/\"" in context_window:
                print(f"Removing legacy password from {file_path}:{i+1} -> {line.strip()}")
                continue
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

print("Finished updating legacy test payloads.")
