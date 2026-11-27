
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

    BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

    SECRET_KEY = os.getenv("SECRET_KEY")

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    OTP_HMAC_SECRET = os.getenv("OTP_HMAC_SECRET")
    AUTH_OTP_EMAIL_PROVIDER = os.getenv("AUTH_OTP_EMAIL_PROVIDER")

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
    AWS_SES_FROM_EMAIL = os.getenv("AWS_SES_FROM_EMAIL")
    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = os.getenv("SMTP_PORT", "587")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

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

    # Webhook & Reverse Proxy Settings
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
    WEBHOOK_PUBLIC_BASE_URL = os.getenv("WEBHOOK_PUBLIC_BASE_URL") or PUBLIC_BASE_URL
    TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"
    TRUSTED_PROXY_IPS = [
        ip.strip()
        for ip in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
        if ip.strip()
    ]
    TRUSTED_FORWARDED_HOSTS = [
        h.strip().lower()
        for h in os.getenv("TRUSTED_FORWARDED_HOSTS", "").split(",")
        if h.strip()
    ]

    # JSON Validation & Resource-Exhaustion Limits
    VALIDATION_MAX_BODY_BYTES = int(os.getenv("VALIDATION_MAX_BODY_BYTES", str(1 * 1024 * 1024)))
    VALIDATION_MAX_DEPTH = int(os.getenv("VALIDATION_MAX_DEPTH", "20"))
    VALIDATION_MAX_NODES = int(os.getenv("VALIDATION_MAX_NODES", "5000"))
    VALIDATION_MAX_ARRAY_LENGTH = int(os.getenv("VALIDATION_MAX_ARRAY_LENGTH", "1000"))
    VALIDATION_MAX_OBJECT_KEYS = int(os.getenv("VALIDATION_MAX_OBJECT_KEYS", "500"))
    VALIDATION_MAX_STRING_LENGTH = int(os.getenv("VALIDATION_MAX_STRING_LENGTH", "200000"))
    PAYLOAD_INGEST_MAX_BYTES = int(os.getenv("PAYLOAD_INGEST_MAX_BYTES", str(10 * 1024 * 1024)))

    # Distributed Rate Limiting & Abuse Protection Limits
    RATE_LIMIT_AUTH_LOGIN_IP_RPM = int(os.getenv("RATE_LIMIT_AUTH_LOGIN_IP_RPM", "20"))
    RATE_LIMIT_AUTH_LOGIN_PAIR_FAILURE_MAX = int(
        os.getenv("RATE_LIMIT_AUTH_LOGIN_PAIR_FAILURE_MAX", os.getenv("RATE_LIMIT_AUTH_LOGIN_FAILURE_MAX", "5"))
    )
    RATE_LIMIT_AUTH_LOGIN_FAILURE_MAX = RATE_LIMIT_AUTH_LOGIN_PAIR_FAILURE_MAX
    RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS", "300"))
    RATE_LIMIT_AUTH_LOGIN_GLOBAL_FAILURE_MAX = int(os.getenv("RATE_LIMIT_AUTH_LOGIN_GLOBAL_FAILURE_MAX", "15"))
    RATE_LIMIT_AUTH_LOGIN_GLOBAL_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_AUTH_LOGIN_GLOBAL_WINDOW_SECONDS", "900"))
    RATE_LIMIT_AUTH_LOGIN_GLOBAL_BASE_BACKOFF_SECONDS = int(
        os.getenv("RATE_LIMIT_AUTH_LOGIN_GLOBAL_BASE_BACKOFF_SECONDS", "2")
    )
    RATE_LIMIT_AUTH_LOGIN_GLOBAL_MAX_BACKOFF_SECONDS = int(
        os.getenv("RATE_LIMIT_AUTH_LOGIN_GLOBAL_MAX_BACKOFF_SECONDS", "30")
    )
    RATE_LIMIT_AUTH_OTP_VERIFY_IP_MAX = int(os.getenv("RATE_LIMIT_AUTH_OTP_VERIFY_IP_MAX", "15"))
    RATE_LIMIT_AUTH_OTP_VERIFY_EMAIL_MAX = int(os.getenv("RATE_LIMIT_AUTH_OTP_VERIFY_EMAIL_MAX", "10"))
    RATE_LIMIT_AUTH_OTP_VERIFY_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_AUTH_OTP_VERIFY_WINDOW_SECONDS", "300"))
    RATE_LIMIT_AUTH_SET_PASSWORD_MAX = int(os.getenv("RATE_LIMIT_AUTH_SET_PASSWORD_MAX", "10"))
    RATE_LIMIT_AUTH_REFRESH_RPM = int(os.getenv("RATE_LIMIT_AUTH_REFRESH_RPM", "30"))
    RATE_LIMIT_VALIDATION_USER_RPM = int(os.getenv("RATE_LIMIT_VALIDATION_USER_RPM", "60"))
    RATE_LIMIT_VALIDATION_APP_RPM = int(os.getenv("RATE_LIMIT_VALIDATION_APP_RPM", "150"))
    RATE_LIMIT_VALIDATION_ORG_RPM = int(os.getenv("RATE_LIMIT_VALIDATION_ORG_RPM", "300"))
    RATE_LIMIT_MESSAGE_CREATE_USER_RPM = int(os.getenv("RATE_LIMIT_MESSAGE_CREATE_USER_RPM", "120"))
    RATE_LIMIT_MESSAGE_CREATE_ORG_RPM = int(os.getenv("RATE_LIMIT_MESSAGE_CREATE_ORG_RPM", "1000"))
