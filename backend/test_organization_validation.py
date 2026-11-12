from app import create_app
from app.modules.organizations.service import OrganizationService

app = create_app()

with app.app_context():

    test_cases = [
        (
            "Empty request",
            {},
            "All organization and admin fields are required"
        ),
        (
            "Invalid slug",
            {
                "name": "Test Company",
                "slug": "Test Company!",
                "admin_name": "Test Admin",
                "admin_email": "admin@test.com",
                "admin_password": "StrongPassword123!"
            },
            "Invalid organization slug"
        ),
        (
            "Invalid email",
            {
                "name": "Test Company",
                "slug": "test-company",
                "admin_name": "Test Admin",
                "admin_email": "invalid-email",
                "admin_password": "StrongPassword123!"
            },
            "Invalid admin email address"
        ),
        (
            "Short password",
            {
                "name": "Test Company",
                "slug": "test-company",
                "admin_name": "Test Admin",
                "admin_email": "admin@test.com",
                "admin_password": "short"
            },
            "Password must be at least 12 characters and at most 72 bytes"
        )
    ]

    for test_name, payload, expected in test_cases:
        result = OrganizationService.create_organization(
            payload,
            created_by="validation-test"
        )

        passed = (
            not result["success"]
            and result["message"] == expected
        )

        print(
            f"{'PASS' if passed else 'FAIL'}: {test_name}"
        )
        if not passed:
            print("  Actual:", result)