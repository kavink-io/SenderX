
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()


class Config:

    APP_NAME = os.getenv("APP_NAME", "SenderX")

    APP_ENV = os.getenv("APP_ENV", "development")

    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    SECRET_KEY = os.getenv("SECRET_KEY")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    JWT_ACCESS_TOKEN_EXPIRES = 900

    JWT_REFRESH_TOKEN_EXPIRES = 604800

    JWT_TOKEN_LOCATION = ["headers"]

    JWT_HEADER_NAME = "Authorization"

    JWT_HEADER_TYPE = "Bearer"

    CREDENTIAL_ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY")

    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://localhost:27017"
    )

    MONGO_DB = os.getenv("MONGO_DB", "senderx")

    REDIS_URL = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0"
    )

    RABBITMQ_URL = os.getenv(
        "RABBITMQ_URL",
        "amqp://guest:guest@localhost:5672//"
    )

    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
    SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")

    # Media & Storage Settings
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
    MEDIA_STORAGE_BACKEND = os.getenv("MEDIA_STORAGE_BACKEND", STORAGE_BACKEND)
    MEDIA_LOCAL_STORAGE_DIR = os.getenv(
        "MEDIA_LOCAL_STORAGE_DIR",
        str(Path(__file__).resolve().parent.parent / "storage" / "uploads")
    )
    MEDIA_MAX_FILE_SIZE_BYTES = int(os.getenv("MEDIA_MAX_FILE_SIZE_BYTES", str(50 * 1024 * 1024)))  # 50 MB
    MEDIA_MAX_REQUEST_SIZE_BYTES = int(os.getenv("MEDIA_MAX_REQUEST_SIZE_BYTES", str(100 * 1024 * 1024)))  # 100 MB
    MAX_CONTENT_LENGTH = MEDIA_MAX_REQUEST_SIZE_BYTES

    # S3 Object Storage Configuration
    AWS_S3_BUCKET = os.getenv("AWS_S3_BUCKET")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
    AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL")
    AWS_S3_SSE = os.getenv("AWS_S3_SSE", "AES256")

    # Malware Scanner Settings
    CLAMAV_HOST = os.getenv("CLAMAV_HOST")
    CLAMAV_PORT = int(os.getenv("CLAMAV_PORT", "3310"))
    MEDIA_ALLOW_UNSCANNED_DISPATCH = os.getenv("MEDIA_ALLOW_UNSCANNED_DISPATCH", "false").lower() == "true"
