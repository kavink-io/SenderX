import os
import sys
import pytest
import bcrypt

LIVE_DB_NAME = "SenderX_db"
TEST_DB_NAME = "SenderX_test"

# Support TEST_MONGO_URI env var, defaulting to Config.MONGO_URI
test_mongo_uri = os.environ.get("TEST_MONGO_URI")
if test_mongo_uri:
    if "localhost:27017" in test_mongo_uri and "directConnection" not in test_mongo_uri:
        sep = "&" if "?" in test_mongo_uri else "?"
        test_mongo_uri = f"{test_mongo_uri}{sep}directConnection=true"
    os.environ["MONGO_URI"] = test_mongo_uri

# Support pytest-xdist worker DB (e.g. SenderX_test_gw0)
worker_id = os.environ.get("PYTEST_XDIST_WORKER")
if worker_id and worker_id != "master":
    worker_db = f"SenderX_test_{worker_id}"
else:
    worker_db = TEST_DB_NAME

# If user or environment explicitly points to the live DB, refuse immediately
if os.environ.get("MONGO_DB") == LIVE_DB_NAME or worker_db == LIVE_DB_NAME:
    raise RuntimeError(f"Safety violation: Refusing to run test suite because MONGO_DB equals live DB '{LIVE_DB_NAME}'!")

os.environ["MONGO_DB"] = worker_db

# Configure fast bcrypt for tests
os.environ["BCRYPT_ROUNDS"] = "4"

# Ensure backend root is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config.settings import Config
Config.MONGO_DB = worker_db
if test_mongo_uri:
    Config.MONGO_URI = test_mongo_uri
Config.BCRYPT_ROUNDS = 4

# Monkeypatch bcrypt.gensalt to enforce rounds=4 during tests
_orig_gensalt = bcrypt.gensalt
def _fast_gensalt(rounds=None, prefix=b"2b"):
    r = int(os.environ.get("BCRYPT_ROUNDS", "4"))
    return _orig_gensalt(rounds=r, prefix=prefix)
bcrypt.gensalt = _fast_gensalt


def pytest_configure(config):
    current_env_db = os.environ.get("MONGO_DB")
    if current_env_db == LIVE_DB_NAME or getattr(Config, "MONGO_DB", None) == LIVE_DB_NAME:
        raise RuntimeError(f"Safety violation: Refusing to run test suite because MONGO_DB equals live DB '{LIVE_DB_NAME}'!")


@pytest.fixture(autouse=True)
def ensure_test_database_isolation():
    current_env_db = os.environ.get("MONGO_DB")
    if current_env_db == LIVE_DB_NAME or getattr(Config, "MONGO_DB", None) == LIVE_DB_NAME:
        raise RuntimeError(f"Safety violation: Refusing to execute test against live DB '{LIVE_DB_NAME}'!")


@pytest.fixture(scope="session", autouse=True)
def session_db_lifecycle():
    current_env_db = os.environ.get("MONGO_DB", worker_db)
    if current_env_db == LIVE_DB_NAME or getattr(Config, "MONGO_DB", None) == LIVE_DB_NAME:
        raise RuntimeError(f"Safety violation: Refusing to initialize against live DB '{LIVE_DB_NAME}'!")

    from app import create_app
    from app.config.database_indexes import ensure_database_indexes
    test_app = create_app()
    with test_app.app_context():
        ensure_database_indexes(test_app, force=True)

    yield

    with test_app.app_context():
        db = test_app.mongo_db
        if db.name != LIVE_DB_NAME and db.name.startswith("SenderX_test"):
            try:
                test_app.mongo_client.drop_database(db.name)
            except Exception:
                pass


@pytest.fixture
def app():
    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        with app.app_context():
            yield c
