from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS

from .config import Config
from .extensions import bcrypt, db, jwt, migrate
from .routes import register_blueprints

load_dotenv()


def create_app(config_class: type[Config] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class or Config())

    # Explicitly allow requests from frontend URL (localhost:5173)
    # and allow credentials (cookies) to be passed back and forth.
    CORS(
        app,
        resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}},
        supports_credentials=True,
    )

    register_extensions(app)
    register_blueprints(app)
    register_healthcheck(app)

    with app.app_context():
        # Ensure tables exist so first-time developers can run without migrations
        db.create_all()

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)


def register_healthcheck(app: Flask) -> None:
    @app.get("/api/health")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}
