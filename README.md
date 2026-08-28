# MediKiosk AI — Smart India Hackathon 2026

AI-powered OPD Patient Kiosk for faster, multilingual patient intake and intelligent doctor summaries.

---

## Project Overview

**MediKiosk AI** is a healthcare kiosk designed for primary health centers (PHCs) and community hospitals in Bharat. It enables patients to complete structured intake in **English and Hindi** via **voice input** or text, extracts information from **prescriptions and lab reports** via OCR, supports traditional **AYUSH Dashavidha Pariksha** pathways, and generates an assistive, evidence-linked **AI summary** for clinicians.

---

## Core Capabilities & Architecture

| Layer | Primary Technology | Fallback / Development Mode |
| :--- | :--- | :--- |
| **API Backend** | FastAPI + SQLAlchemy 2.0 + Pydantic | PostgreSQL (Railway / Docker Compose) |
| **Frontend** | Next.js + Tailwind CSS | Vercel Deployment |
| **Speech Intake** | Hosted Groq Whisper API | Browser Web Speech API & Mock Adapter |
| **AYUSH Intake** | Dashavidha Pariksha (Prakriti, Vikriti, Agni, Koshtha, Sattva) | Structured Kiosk & Clinic Forms |
| **Document OCR** | OCR Provider Pipeline | Mock / Offline Extractor |
| **AI Summarizer** | LLM Adapter with Explicit Provenance | Strict JSON Schema Validator |
| **Object Storage** | Hosted Private S3-compatible Storage | Local Storage / MinIO |
| **Security & RBAC** | JWT Tokens, Bcrypt, Append-only Audit Logs | Role-based Authorization Matrix |

---

## Repository & Git Workflow

```text
SIH/
├── apps/
│   └── api/
│       ├── app/
│       │   ├── api/             # Routers, dependencies, middleware
│       │   ├── core/            # Config, security, logging, exceptions
│       │   ├── db/              # Session, models, migrations, seed
│       │   ├── integrations/    # Speech, OCR, Summary, Storage adapter protocols
│       │   ├── repositories/    # Base data repositories
│       │   ├── schemas/         # Pydantic models & AYUSH schemas
│       │   └── services/        # Audit service & domain workflows
│       ├── tests/               # Automated test suites
│       ├── alembic.ini
│       ├── Dockerfile
│       └── requirements.txt
├── infra/
│   └── docker-compose.yml       # Local Postgres + MinIO support
├── .env.example
├── .gitignore
├── Procfile
├── railway.json
└── README.md
```

### Branch Ownership

Every team member develops on an isolated feature branch branched off `main`:

| Member | Branch | Domain Scope |
| :--- | :--- | :--- |
| **Backend Lead** | `main` | Core architecture, database models, migrations, security, shared contracts. |
| **Member 1** | `feature/auth` | Patient profile registration, OTP verification, login endpoints, auth UI. |
| **Member 2** | `feature/ai-summary` | Summarization prompts, LLM adapters, AYUSH provenance, doctor review. |
| **Member 3** | `feature/ocr-whisper` | Groq Whisper speech worker, document OCR extraction, storage uploads. |
| **Member 4** | `feature/doctor-queue` | FIFO clinic queue state machine, doctor workspace APIs & live queue UI. |

---

## Quick Start (Local Development)

### 1. Configure Environment
```bash
cp .env.example .env
```

### 2. Install Dependencies
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Database Migrations & Seed
```bash
alembic upgrade head
python -m app.db.seed
```

### 4. Run Automated Tests
```bash
pytest apps/api/tests -v
```

### 5. Launch API Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Documentation: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health Probe: [http://localhost:8000/health](http://localhost:8000/health)
- Readiness Probe: [http://localhost:8000/ready](http://localhost:8000/ready)

---

**Smart India Hackathon 2026 • MediKiosk AI**
