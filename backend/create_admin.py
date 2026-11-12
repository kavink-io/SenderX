
import uuid
import getpass
import bcrypt

from app import create_app
from app.modules.auth.repository import AuthRepository


def create_admin():

    app = create_app()

    with app.app_context():

        print("\n===== SenderX Admin Setup =====\n")

        email = input("Admin email: ").strip().lower()

        if not email or "@" not in email:
            print("Invalid email.")
            return

        if AuthRepository.find_by_email(email):
            print("An account with this email already exists.")
            return

        password = getpass.getpass("Admin password: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if password != confirm_password:
            print("Passwords do not match.")
            return

        if len(password) < 12 or len(password.encode("utf-8")) > 72:
            print("Password must be at least 12 characters and at most 72 bytes.")
            return

        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12)
        ).decode("utf-8")

        admin_data = {
            "admin_id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_hash,
            "role": "SUPER_ADMIN",
            "is_active": True
        }

        AuthRepository.create_admin(admin_data)

        print("\nSUPER_ADMIN created successfully.")
        print(f"Email: {email}")


if __name__ == "__main__":
    create_admin()
