
import getpass
import bcrypt

from app import create_app
from flask import current_app

app = create_app()

with app.app_context():

    email = input("Enter SUPER_ADMIN email: ").strip().lower()

    password = getpass.getpass("Enter new password: ")
    confirm_password = getpass.getpass("Confirm new password: ")

    if password != confirm_password:
        print("Passwords do not match.")
        raise SystemExit(1)

    if len(password) < 12 or len(password.encode("utf-8")) > 72:
        print("Password must be at least 12 characters and at most 72 bytes.")
        raise SystemExit(1)

    admin = current_app.mongo_db["admins"].find_one({
        "email": email,
        "role": "SUPER_ADMIN"
    })

    if not admin:
        print("SUPER_ADMIN account not found.")
        raise SystemExit(1)

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")

    result = current_app.mongo_db["admins"].update_one(
        {"admin_id": admin["admin_id"]},
        {"$set": {"password_hash": password_hash}}
    )

    if result.modified_count == 1:
        print("SUPER_ADMIN password reset successfully!")
    else:
        print("Password was not changed. Check the database record.")
