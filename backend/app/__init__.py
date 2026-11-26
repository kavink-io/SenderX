
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
from app.modules.organizations.routes import organizations_bp, platform_bp
from app.modules.users.routes import users_bp
from app.modules.analytics.routes import analytics_bp
from app.modules.templates.routes import templates_bp
from app.modules.media.routes import media_bp
from app.modules.payloads.routes import payloads_bp
from app.modules.api_credentials.routes import api_credentials_bp
from app.modules.applications.routes import applications_bp
from app.modules.whatsapp.routes import whatsapp_bp
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

    mongo_kwargs = {
        "serverSelectionTimeoutMS": 5000
    }
    mongo_uri = app.config.get("MONGO_URI", "")
    is_tls = "mongodb+srv://" in mongo_uri or "tls=true" in mongo_uri.lower() or "ssl=true" in mongo_uri.lower()
    if is_tls:
        try:
            import certifi
            mongo_kwargs["tlsCAFile"] = certifi.where()
        except Exception:
            pass

    app.mongo_client = MongoClient(
        app.config["MONGO_URI"],
        **mongo_kwargs
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
    organizations_bp,
    url_prefix="/api/v1/organizations"
    )
    app.register_blueprint(
    platform_bp,
    url_prefix="/api/v1/platform"
    )
    app.register_blueprint(
    users_bp,
    url_prefix="/api/v1/users"
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
    app.register_blueprint(
    analytics_bp,
    url_prefix="/api/v1/analytics"
    )
    app.register_blueprint(
        templates_bp,
        url_prefix="/api/v1/templates"
    )
    app.register_blueprint(
        templates_bp,
        url_prefix="/api/v1/email-templates",
        name="email_templates"
    )
    app.register_blueprint(
    media_bp,
    url_prefix="/api/v1/media"
    )
    app.register_blueprint(
    payloads_bp,
    url_prefix="/api/v1/payloads"
    )
    app.register_blueprint(
    api_credentials_bp,
    url_prefix="/api/v1/api-credentials"
    )
    app.register_blueprint(
    applications_bp,
    url_prefix="/api/v1/applications"
    )
    app.register_blueprint(
        whatsapp_bp,
        url_prefix="/api/v1/whatsapp"
    )
    app.celery = create_celery(app)

    try:
        from app.config.database_indexes import ensure_database_indexes
        ensure_database_indexes(app)
    except Exception as e:
        app.logger.warning(f"Could not initialize database indexes: {e}")

    # Serve static frontend application and assets
    import os
    from flask import send_from_directory, request
    frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
    if os.path.exists(os.path.join(frontend_dist, "index.html")):
        frontend_dir = frontend_dist
    else:
        frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))

    @app.after_request
    def set_cache_headers(response):
        # Prevent browser disk caching of root SPA index page and assets to avoid stale script cache
        if request.path in ["/", "/index.html"] or request.path.startswith("/js/") or request.path.startswith("/css/") or request.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    @app.route("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/assets/<path:filename>")
    def serve_assets(filename):
        return send_from_directory(os.path.join(frontend_dir, "assets"), filename)

    @app.route("/css/<path:filename>")
    def serve_css(filename):
        return send_from_directory(os.path.join(frontend_dir, "css"), filename)

    @app.route("/js/<path:filename>")
    def serve_js(filename):
        return send_from_directory(os.path.join(frontend_dir, "js"), filename)

    @app.route("/<path:path>")
    def serve_static_or_spa(path):
        if path.startswith("api/") or path == "docs" or path.startswith("docs/") or path == "swagger.json" or path.startswith("swaggerui/"):
            return {"error": "Resource not found"}, 404
        file_path = os.path.join(frontend_dir, path)
        if os.path.isfile(file_path):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    return app
