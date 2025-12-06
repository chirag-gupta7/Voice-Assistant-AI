from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from ..extensions import db
from ..models import User

auth_bp = Blueprint("auth", __name__)


def _validated_preference(value: str | None) -> str:
    allowed = {"local", "device"}
    if value and value.lower() in allowed:
        return value.lower()
    return "local"


@auth_bp.post("/register")
def register():
    payload = request.get_json() or {}
    name = (payload.get("name") or "").strip()
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password")
    calendar_preference = _validated_preference(payload.get("calendar_preference"))

    if not all([name, email, password]):
        return jsonify({"message": "Name, email, and password are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409

    user = User(name=name, email=email, calendar_preference=calendar_preference)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=user.id)
    return jsonify({"token": access_token, "user": user.to_dict()})


@auth_bp.post("/login")
def login():
    payload = request.get_json() or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password")

    user = User.query.filter_by(email=email).first()

    if not user or not password or not user.check_password(password):
        return jsonify({"message": "Invalid email or password"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({"token": access_token, "user": user.to_dict()})


@auth_bp.get("/me")
@jwt_required()
def current_user():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify({"user": user.to_dict()})


@auth_bp.post("/google")
def google_login():
    payload = request.get_json() or {}
    token = payload.get("token")

    if not token:
        return jsonify({"message": "Token is required"}), 400

    try:
        client_id = current_app.config.get("GOOGLE_CLIENT_ID")
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)

        email = id_info.get("email")
        name = id_info.get("name") or email.split("@")[0]

        if not email:
            return jsonify({"message": "Invalid Google token"}), 401

        user = User.query.filter_by(email=email).first()
        if not user:
            import secrets

            user = User(name=name, email=email)
            user.set_password(secrets.token_hex(16))
            db.session.add(user)
            db.session.commit()

        access_token = create_access_token(identity=user.id)
        return jsonify({"token": access_token, "user": user.to_dict()})
    except ValueError:
        return jsonify({"message": "Invalid Google token"}), 401
    except Exception as exc:  # pragma: no cover
        return jsonify({"message": str(exc)}), 500


@auth_bp.patch("/me")
@jwt_required()
def update_user():
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    payload = request.get_json() or {}

    if "name" in payload:
        new_name = (payload.get("name") or "").strip()
        if new_name:
            user.name = new_name

    if "calendar_preference" in payload:
        user.calendar_preference = _validated_preference(payload.get("calendar_preference"))

    db.session.commit()

    return jsonify({"user": user.to_dict()})
