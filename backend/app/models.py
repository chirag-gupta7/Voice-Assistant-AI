from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import Enum, func, JSON

from .extensions import bcrypt, db


class BaseModel:
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class User(BaseModel, db.Model):
    __tablename__ = "users"

    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    calendar_preference = db.Column(
        Enum("local", "device", name="calendar_preference_enum"),
        nullable=False,
        default="local",
    )
    google_credentials = db.Column(JSON, nullable=True)

    meetings = db.relationship("Meeting", back_populates="owner", cascade="all, delete")
    notes = db.relationship("Note", back_populates="owner", cascade="all, delete")
    logs = db.relationship("Log", back_populates="user", cascade="all, delete")

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "calendar_preference": self.calendar_preference,
            "created_at": self.created_at.isoformat(),
        }


class Meeting(BaseModel, db.Model):
    __tablename__ = "meetings"

    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    extra_data = db.Column(JSON, nullable=True)

    owner_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    owner = db.relationship("User", back_populates="meetings")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat(),
            "duration": self.duration_minutes,
            "extra_data": self.extra_data or {},
        }

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(minutes=self.duration_minutes)


class Note(BaseModel, db.Model):
    __tablename__ = "notes"

    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    owner = db.relationship("User", back_populates="notes")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
        }


class Log(BaseModel, db.Model):
    __tablename__ = "logs"

    level = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(120), nullable=True)
    extra_data = db.Column(JSON, nullable=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", back_populates="logs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "level": self.level,
            "message": self.message,
            "source": self.source,
            "extra_data": self.extra_data or {},
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
        }
