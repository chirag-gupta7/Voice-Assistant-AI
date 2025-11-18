# 🚀 SmartMeet AI

SmartMeet AI is an intelligent, voice-powered meeting scheduler that pairs a modern React frontend with a secure Flask backend. Users can authenticate, dictate meeting requests with natural language, sync calendars, and review their upcoming events from any device.

## ✨ Highlights

- 🎤 Voice scheduling via the Web Speech API with graceful fallbacks
- 🔐 JWT-based auth with password hashing and protected API routes
- 📅 CRUD meeting management with SQLAlchemy models and migrations
- 🤝 Ready-made Google Calendar + OpenAI env hooks for future integrations
- 🧪 Jest/RTL + Pytest scaffolding hooks so you can expand test coverage quickly

## 📁 Project Layout

```
smartmeet-ai/
├── backend/           # Flask API, PostgreSQL-ready models, services
├── frontend/          # React 18 app with Tailwind UI + Auth context
├── docs/              # Extra documentation (architecture, API notes)
├── .gitignore
└── README.md
```

## ⚙️ Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL 15+ (SQLite used by default for local dev)
- OpenAI + Google API credentials for advanced features

## 🚀 Quick Start

### 1. Backend

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
flask db upgrade
python run.py
```

API runs on `http://localhost:5000` by default.

### 2. Frontend

```powershell
cd frontend
npm install
cp .env.example .env.local
# edit .env.local
npm start
```

App runs on `http://localhost:3000`.

## 🧱 Next Steps

1. Populate `.env` files with OpenAI + Google credentials
2. Point `REACT_APP_API_URL` to your backend host
3. Swap the sample voice parser with OpenAI or LangChain logic
4. Extend the calendar service to call Google Calendar

## 📝 Documentation

See `docs/architecture.md` for a deeper dive into flow diagrams, data models, and upcoming roadmap items.
