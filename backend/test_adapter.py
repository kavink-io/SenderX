
import run

from app.adapters.adapter_registry import AdapterRegistry


with run.app.app_context():

    try:
        adapter = AdapterRegistry.get_adapter("sendgrid")

        print("Adapter initialized successfully")
        print("Adapter:", type(adapter).__name__)

    except Exception as error:
        print("Adapter initialization failed:", type(error).__name__)
