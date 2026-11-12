"""
SenderX - SendGrid Configuration Utility
Stores encrypted SendGrid credentials into MongoDB via ProviderConfigService.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()

import run
from app.modules.provider_config.service import ProviderConfigService


def save_sendgrid_credentials(api_key=None, from_email=None):
    api_key = api_key or os.getenv("SENDGRID_API_KEY")
    from_email = from_email or os.getenv("SENDGRID_FROM_EMAIL", "kavinvijay206@gmail.com")

    if not api_key:
        print("Error: SendGrid API key is missing. Set SENDGRID_API_KEY in .env or pass as argument.")
        return False

    with run.app.app_context():
        try:
            ProviderConfigService.save_configuration(
                "sendgrid",
                {
                    "api_key": api_key,
                    "from_email": from_email
                }
            )
            print("Successfully encrypted and saved SendGrid credentials to MongoDB database!")
            print(f"Provider: sendgrid | Sender: {from_email}")
            return True
        except Exception as error:
            print(f"Failed to save to database: {type(error).__name__} - {error}")
            return False


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else None
    email = sys.argv[2] if len(sys.argv) > 2 else None
    save_sendgrid_credentials(key, email)
