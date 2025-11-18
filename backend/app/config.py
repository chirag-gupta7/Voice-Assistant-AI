import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///smartmeet.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-too")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    CORS_ORIGINS = [FRONTEND_URL]
