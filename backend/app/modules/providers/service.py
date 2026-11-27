class ProviderService:

    PROVIDERS = {
        "sendgrid": {
            "name": "SendGrid",
            "channel": "email",
            "status": "supported"
        },
        "ses": {
            "name": "Amazon SES",
            "channel": "email",
            "status": "supported"
        },
        "smtp": {
            "name": "SMTP",
            "channel": "email",
            "status": "supported"
        },
        "meta": {
            "name": "Meta WhatsApp Cloud API",
            "channel": "whatsapp",
            "status": "supported"
        },
        "twilio": {
            "name": "Twilio",
            "channel": "sms",
            "status": "supported"
        },
        "teams": {
            "name": "Microsoft Teams (Graph API)",
            "channel": "microsoft_teams",
            "status": "supported"
        },
        "telegram": {
            "name": "Telegram (Mock Only)",
            "channel": "telegram",
            "status": "mock_only",
            "note": "Mock adapter only; live Telegram Bot API adapter is not implemented."
        }
    }

    @classmethod
    def get_all_providers(cls):
        return cls.PROVIDERS

    @classmethod
    def get_provider(cls, provider_name):
        return cls.PROVIDERS.get(provider_name.lower())

    @classmethod
    def get_providers_by_channel(cls, channel_name):
        return {
            key: value
            for key, value in cls.PROVIDERS.items()
            if value["channel"] == channel_name.lower()
        }