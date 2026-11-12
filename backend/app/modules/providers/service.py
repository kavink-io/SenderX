class ProviderService:

    PROVIDERS = {
        "sendgrid": {
            "name": "SendGrid",
            "channel": "email",
            "status": "supported"
        },
        "amazon_ses": {
            "name": "Amazon SES",
            "channel": "email",
            "status": "supported"
        },
        "meta_cloud_api": {
            "name": "Meta WhatsApp Cloud API",
            "channel": "whatsapp",
            "status": "supported"
        },
        "twilio": {
            "name": "Twilio",
            "channel": "sms",
            "status": "supported"
        },
        "msg91": {
            "name": "MSG91",
            "channel": "sms",
            "status": "supported"
        },
        "telegram_bot_api": {
            "name": "Telegram Bot API",
            "channel": "telegram",
            "status": "supported"
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