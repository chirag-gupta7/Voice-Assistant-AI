from flask import Blueprint, Flask

from .auth import auth_bp
from .calendar import calendar_bp
from .meetings import meetings_bp
from .voice import voice_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(meetings_bp, url_prefix="/api/meetings")
    app.register_blueprint(voice_bp, url_prefix="/api/voice")
    app.register_blueprint(calendar_bp, url_prefix="/api/calendar")
