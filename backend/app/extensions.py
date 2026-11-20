
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
    title="SenderX API & Email Template Studio",
    version="1.0",
    description=(
        "SenderX Multi-Channel Communication Platform & Email Template Studio.\n\n"
        "Security & Template Guidelines:\n"
        "- Plain Text Default: All incoming variable values are treated as plain text, auto-escaped, and never executed.\n"
        "- Markup Detection: String fields containing markup are recorded with 'contains_markup' metadata.\n"
        "- Threat Rejection: Dangerous patterns (script tags, event handlers, javascript: URLs, CR/LF in subject) return HTTP 422.\n"
        "- Rich Content: 'body_html' is sanitized via an allowlist sanitizer only when declared as 'rich'.\n"
        "- Conflict Prevention: Cannot supply both 'template_id' and raw 'html'/'html_body' in message dispatch (HTTP 422)."
    ),
    doc="/docs"
)

cors = CORS()
jwt = JWTManager()

mongo_client = None
mongo_db = None

redis_client = None
