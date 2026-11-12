
import json

from cryptography.fernet import Fernet
from flask import current_app


class ProviderConfigService:

    @staticmethod
    def _cipher():

        key = current_app.config.get(
            "CREDENTIAL_ENCRYPTION_KEY"
        )

        if not key:
            raise ValueError(
                "Encryption key is not configured"
            )

        return Fernet(key.encode())

    @classmethod
    def save_configuration(cls, provider, credentials):

        encrypted_credentials = cls._cipher().encrypt(
            json.dumps(credentials).encode()
        ).decode()

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        collection.update_one(
            {"provider": provider},
            {
                "$set": {
                    "provider": provider,
                    "credentials": encrypted_credentials,
                    "configured": True
                }
            },
            upsert=True
        )

        return True

    @staticmethod
    def get_configuration_status(provider):

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        return collection.find_one(
            {
                "provider": provider
            },
            {
                "_id": 0,
                "provider": 1,
                "configured": 1
            }
        )

    @staticmethod
    def get_all_configuration_statuses():

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        return list(
            collection.find(
                {},
                {
                    "_id": 0,
                    "provider": 1,
                    "configured": 1
                }
            )
        )

    @classmethod
    def get_decrypted_configuration(cls, provider):

        collection = current_app.mongo_db[
            "provider_configs"
        ]

        document = collection.find_one({
            "provider": provider,
            "configured": True
        })

        if not document:
            return None

        encrypted_credentials = document.get(
            "credentials"
        )

        if not encrypted_credentials:
            return None

        decrypted = cls._cipher().decrypt(
            encrypted_credentials.encode()
        )

        return json.loads(decrypted.decode())
