
import run

from app.modules.provider_config.service import ProviderConfigService


with run.app.app_context():

    credentials = (
        ProviderConfigService.get_decrypted_configuration(
            "sendgrid"
        )
    )

    if not credentials:
        print("SendGrid configuration not found")

    else:
        print("SendGrid configuration decrypted successfully")
        print("API key available:", bool(credentials.get("api_key")))
        print("Sender email:", credentials.get("from_email"))
