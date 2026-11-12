
from flask import Flask
from pymongo import MongoClient
import redis
from app.queue.celery_app import create_celery
from app.modules.health.routes import health_bp
from app.modules.channels.routes import channels_bp
from app.modules.configuration.routes import configuration_bp
from app.modules.providers.routes import providers_bp
from app.modules.provider_config.routes import provider_config_bp
from app.modules.messages.routes import messages_bp
from app.modules.validation.routes import validation_bp
from app.modules.dead_letters.routes import dead_letters_bp
from app.config.settings import Config
from app.extensions import (
    api,
    cors,
    jwt
)
from app.modules.auth.routes import auth_bp

def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)
    jwt.init_app(app)

    cors.init_app(app)

    app.mongo_client = MongoClient(
        app.config["MONGO_URI"],
        serverSelectionTimeoutMS=3000
    )

    app.mongo_db = app.mongo_client[
        app.config["MONGO_DB"]
    ]

    app.redis_client = redis.Redis.from_url(
        app.config["REDIS_URL"],
        decode_responses=True
    )
    
    

    api.init_app(app)
    app.register_blueprint(
    auth_bp,
    url_prefix="/api/v1/auth"
    )
    app.register_blueprint(
    health_bp,
    url_prefix="/api/v1/health"
    )
    app.register_blueprint(
    dead_letters_bp,
    url_prefix="/api/v1/dead-letters"
    )
    app.register_blueprint(
    channels_bp,
    url_prefix="/api/v1/channels"
    )
    app.register_blueprint(
    configuration_bp,
    url_prefix="/api/v1/configuration"
    )
    app.register_blueprint(
    providers_bp,
    url_prefix="/api/v1/providers"
    )
    app.register_blueprint(
    provider_config_bp,
    url_prefix="/api/v1/provider-config"
    )
    app.register_blueprint(
    messages_bp,
    url_prefix="/api/v1/messages"
    )
    app.register_blueprint(
    validation_bp,
    url_prefix="/api/v1/validation"
    )
    app.celery = create_celery(app)
    

    return app
