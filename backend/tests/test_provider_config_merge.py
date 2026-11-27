import copy

from cryptography.fernet import Fernet
from flask import Flask

from app.modules.provider_config.service import ProviderConfigService


class FakeProviderConfigCollection:
    def __init__(self):
        self.document = None

    def find_one(self, query, projection=None):
        if self.document is None:
            return None
        if any(self.document.get(key) != value for key, value in query.items()):
            return None
        return copy.deepcopy(self.document)

    def update_one(self, query, update, upsert=False):
        self.document = {**query, **update["$set"]}


def test_partial_provider_update_preserves_existing_encrypted_values():
    app = Flask(__name__)
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    collection = FakeProviderConfigCollection()
    app.mongo_db = {"provider_configs": collection}

    with app.app_context():
        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "initial-key", "from_email": "notifications@example.com"},
            organization_id="org-a",
        )
        encrypted_credentials = collection.document["credentials"]

        ProviderConfigService.save_configuration(
            "sendgrid",
            {"api_key": "rotated-key"},
            organization_id="org-a",
        )

        credentials = ProviderConfigService.get_decrypted_configuration(
            "sendgrid",
            organization_id="org-a",
        )
        other_organization_credentials = ProviderConfigService.get_decrypted_configuration(
            "sendgrid",
            organization_id="org-b",
        )

    assert collection.document["credentials"] != encrypted_credentials
    assert "rotated-key" not in collection.document["credentials"]
    assert credentials == {
        "api_key": "rotated-key",
        "from_email": "notifications@example.com",
    }
    assert other_organization_credentials is None
