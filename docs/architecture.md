# SmartMeet AI Architecture

## System Overview

SmartMeet AI is split into a Flask REST API and a React SPA:

- **Frontend (React + Tailwind)** handles authentication, meeting visualization, voice capture, and REST calls.
- **Backend (Flask + SQLAlchemy)** exposes JWT-protected endpoints for auth, meetings, calendar sync, and voice command parsing.

A PostgreSQL (or SQLite) database stores users and meetings. External services (OpenAI, Google Calendar, SendGrid, Firebase) plug in via environment variables and dedicated service classes.

## Key Flows

1. **Login/Register**
   - User submits credentials via React forms
   - Backend hashes passwords with Bcrypt, returns JWT
   - Token persists in `localStorage` and is appended to subsequent calls

2. **Meeting Scheduling**
   - User invokes voice input (Web Speech API)
   - Transcript is sent to `/api/voice/process`
   - Backend parser extracts title/date/duration
   - Meeting is stored via `/api/meetings`

3. **Calendar Sync (stub)**
   - Frontend triggers `/api/calendar/sync`
   - Future enhancement: use Google Calendar API service + OAuth tokens

## Data Model (simplified)

```
User
├── id (UUID)
├── name
├── email (unique)
├── password_hash
└── created_at

Meeting
├── id (UUID)
├── title
├── description
├── start_time (UTC)
├── duration_minutes
└── owner_id → User.id
```

## Deployment Notes

- Package backend with Gunicorn + reverse proxy (nginx) or Azure App Service
- Containerize both services and push to Azure Container Apps/AKS
- Use GitHub Actions (CI) to lint, test, and deploy automatically

## Roadmap

- Real OpenAI parsing + fallback heuristics
- Google Calendar OAuth + background sync jobs
- Notifications via SendGrid + Firebase Cloud Messaging
- Multi-tenant support and role-based access control
