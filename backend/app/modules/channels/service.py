class ChannelService:

    SUPPORTED_CHANNELS = {
        "email": {
            "name": "Email",
            "providers": ["sendgrid", "ses", "smtp"],
            "status": "available"
        },
        "whatsapp": {
            "name": "WhatsApp",
            "providers": ["meta"],
            "status": "available"
        },
        "sms": {
            "name": "SMS",
            "providers": ["twilio"],
            "status": "available"
        },
        "telegram": {
            "name": "Telegram",
            "providers": ["mock"],
            "status": "mock_only",
            "note": "Mock adapter only; live Telegram Bot API delivery is not implemented."
        },
        "slack": {
            "name": "Slack",
            "providers": ["slack_api"],
            "status": "planned"
        },
        "microsoft_teams": {
            "name": "Microsoft Teams",
            "providers": ["teams"],
            "status": "available"
        },
        "webhook": {
            "name": "Webhook",
            "providers": ["http"],
            "status": "planned"
        }
    }

    @classmethod
    def get_all_channels(cls):
        return cls.SUPPORTED_CHANNELS

    @classmethod
    def get_channel(cls, channel_name):
        return cls.SUPPORTED_CHANNELS.get(
            channel_name.lower()
        )