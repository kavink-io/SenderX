from flask import current_app


class ConfigurationService:

    @staticmethod
    def get_public_config():

        return {
            "application": {
                "name": current_app.config.get("APP_NAME"),
                "environment": current_app.config.get("APP_ENV"),
                "debug": current_app.config.get("DEBUG")
            },

            "database": {
                "mongodb": "configured",
                "redis": "configured",
                "rabbitmq": "configured"
            },

            "channels": [
                "email",
                "whatsapp",
                "sms",
                "telegram",
                "slack",
                "microsoft_teams",
                "webhook"
            ],

            "security": {
                "authentication": "JWT",
                "password_hashing": "bcrypt"
            }
        }