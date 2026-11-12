class ChannelService:

    SUPPORTED_CHANNELS = {
        "email": {
            "name": "Email",
            "providers": ["sendgrid", "amazon_ses"],
            "status": "available"
        },
        "whatsapp": {
            "name": "WhatsApp",
            "providers": ["meta_cloud_api"],
            "status": "available"
        },
        "sms": {
            "name": "SMS",
            "providers": ["twilio", "msg91"],
            "status": "available"
        },
        "telegram": {
            "name": "Telegram",
            "providers": ["telegram_bot_api"],
            "status": "available"
        },
        "slack": {
            "name": "Slack",
            "providers": ["slack_api"],
            "status": "planned"
        },
        "microsoft_teams": {
            "name": "Microsoft Teams",
            "providers": ["microsoft_graph"],
            "status": "planned"
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