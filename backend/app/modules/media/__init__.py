"""
SenderX Media Management Module
Centralized attachments and media processing.
"""

from app.modules.media.routes import media_bp
from app.modules.media.service import MediaService
from app.modules.media.repository import MediaRepository

__all__ = ["media_bp", "MediaService", "MediaRepository"]
