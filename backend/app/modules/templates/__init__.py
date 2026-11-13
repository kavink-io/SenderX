"""
SenderX Templates Module
"""

from app.modules.templates.routes import templates_bp
from app.modules.templates.service import TemplateService
from app.modules.templates.repository import TemplateRepository

__all__ = ["templates_bp", "TemplateService", "TemplateRepository"]
