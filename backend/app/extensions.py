
from flask_restx import Api
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from pymongo import MongoClient
import redis


class SenderXApi(Api):
    """
    Custom Flask-RESTX Api subclass that routes Swagger UI documentation
    cleanly to /docs and /docs/ without creating a conflicting root ('/')
    rule that would collide with the frontend Single Page Application (SPA).
    """

    def _register_doc(self, app_or_blueprint):
        if self._add_specs and self._doc:
            app_or_blueprint.add_url_rule(self._doc, "doc", self.render_doc)
            if not self._doc.endswith("/"):
                app_or_blueprint.add_url_rule(self._doc + "/", "doc_slash", self.render_doc)

    @property
    def base_path(self):
        return "/"


api = SenderXApi(
    title="SenderX API",
    version="1.0",
    description="Multi-Channel Communication Platform",
    doc="/docs"
)

cors = CORS()
jwt = JWTManager()

mongo_client = None
mongo_db = None

redis_client = None
