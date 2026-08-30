# MediKiosk Backend Platform Foundation

Shared platform architecture, database models, migrations, auth foundations, provider adapter interfaces, and test harness for the **MediKiosk AI** healthcare kiosk platform.

---

## 1. Directory Layout

```text
apps/api/
├── app/
│   ├── api/
│   │   ├── dependencies.py          # Database sessions, JWT auth, RBAC, Request ID
│   │   ├── middleware.py            # Request ID, Logging, Global Error Envelopes
│   │   ├── router.py                # Root router (/health, /ready, /api/v1)
│   │   └── v1/
│   │       ├── api_router.py
│   │       └── endpoints/
│   │           ├── auth.py          # /login, /me foundation
│   │           ├── health.py        # /health, /ready probes
│   │           ├── platform.py      # /status, /seed, /audit
│   │           └── visits.py        # /visits intake foundation (AYUSH + Allopathic)
│   ├── core/
│   │   ├── config.py                # Typed Pydantic Settings
│   │   ├── exceptions.py            # Normalized error taxonomy
│   │   ├── logging.py               # Structured JSON logger with request tracing
│   │   └── security.py              # Native bcrypt hashing & JWT token handling
│   ├── db/
│   │   ├── base.py                  # SQLAlchemy DeclarativeBase + Mixins
│   │   ├── session.py               # Engine, SessionLocal, Health checks
│   │   ├── seed.py                  # Database seeder (Clinic, Users, Patient, AYUSH Visit)
│   │   ├── models/                  # Shared SQLAlchemy models
│   │   │   ├── ai_job.py
│   │   │   ├── audit.py             # Append-only audit events
│   │   │   ├── clinic.py
│   │   │   ├── enums.py             # Domain enums & AYUSH Dashavidha Pariksha enums
│   │   │   ├── input.py             # Raw evidence (audio, documents)
│   │   │   ├── patient.py           # Patient profile & privacy hashing
│   │   │   ├── queue.py             # Live clinic queue entries
│   │   │   ├── summary.py           # Clinical & AYUSH AI summaries
│   │   │   ├── user.py              # Staff accounts & roles
│   │   │   └── visit.py             # Clinical encounter + Dashavidha Pariksha
│   │   └── migrations/              # Alembic versioned migrations
│   ├── integrations/                # Provider Adapter Protocols & Mocks
│   │   ├── ocr.py                   # OCRProvider Protocol + Mock
│   │   ├── speech.py                # SpeechProvider Protocol (Groq Whisper + Mock)
│   │   ├── storage.py               # StorageProvider Protocol (S3/MinIO + Local)
│   │   └── summary.py               # SummaryProvider Protocol + Mock
│   ├── repositories/
│   │   └── base_repository.py       # Generic CRUD repository
│   ├── schemas/                     # Shared Pydantic 2.0 schemas
│   │   ├── ai_job.py
│   │   ├── audit.py
│   │   ├── ayush.py                 # Dashavidha Pariksha Pydantic schemas
│   │   ├── clinic.py
│   │   ├── common.py                # ApiResponse[T] & ApiErrorEnvelope
│   │   ├── input.py
│   │   ├── patient.py
│   │   ├── queue.py
│   │   ├── summary.py
│   │   ├── user.py
│   │   └── visit.py
│   ├── services/
│   │   ├── audit_service.py         # Append-only audit logger
│   │   └── base_service.py
│   └── main.py                      # FastAPI Application Factory & Lifespan
├── tests/                           # Pytest automated test suite
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_ayush.py
│   ├── test_contracts.py
│   ├── test_health.py
│   └── test_seed.py
├── alembic.ini
├── Dockerfile
└── requirements.txt
```

---

## 2. Environment Variables & Setup

Copy `.env.example` to `.env` at the root or within `apps/api/`:

```bash
cp .env.example .env
```

### Environment Keys Reference

| Variable | Purpose | Safe Local Default | Staging / Production |
| :--- | :--- | :--- | :--- |
| `APP_ENV` | Environment stage | `local` | `staging` / `production` |
| `DATABASE_URL` | PostgreSQL connection string | `sqlite:///./medikiosk.db` or local Postgres | Railway Managed Postgres URL |
| `JWT_SECRET` | Secret key for JWT signatures | Long random local string | Railway Secret |
| `JWT_EXPIRE_MINUTES` | Access token lifespan | `30` | `30` |
| `GROQ_API_KEY` | Groq Whisper / LLM API key | Blank (mock mode) | Railway Secret |
| `WHISPER_PROVIDER_MODE` | Speech transcription path | `mock` | `groq-hosted` |
| `AI_PROVIDER_MODE` | Summarization provider | `mock` | `groq` / `openai` |
| `WEB_SPEECH_FALLBACK` | Browser speech fallback flag | `true` | `true` |
| `AYUSH_INTAKE_ENABLED` | Enables Dashavidha Pariksha | `true` | `true` |
| `STORAGE_ENDPOINT` | S3 / MinIO storage endpoint | `http://localhost:9000` | Hosted S3 endpoint |
| `STORAGE_BUCKET` | Private storage bucket | `medikiosk-private` | Staging bucket |
| `CORS_ORIGINS` | Allowed frontend domains | `http://localhost:3000,http://localhost:5173` | `https://*.vercel.app` |
| `LOG_LEVEL` | Logging verbosity | `INFO` | `INFO` |

---

## 3. Database Migrations & Seeding

### Apply Alembic Migrations
```bash
alembic upgrade head
```

### Seed Initial Baseline Data
Populates the demo clinic (`PHC-NORTH-01`), 5 role-based test users, demo patient (Asha Devi), and a token `A12` visit with full AYUSH Dashavidha Pariksha data:
```bash
python -m app.db.seed
```

### Seeded User Credentials for Testing

| Email | Password | Role |
| :--- | :--- | :--- |
| `admin@medikiosk.in` | `Admin@12345` | Clinic Admin (`clinic_admin`) |
| `dr.sharma@medikiosk.in` | `Doctor@12345` | Doctor (`doctor`) |
| `reception@medikiosk.in` | `Reception@12345` | Receptionist (`receptionist`) |
| `operator@medikiosk.in` | `Operator@12345` | System Operator (`system_operator`) |
| `asha.devi@medikiosk.in` | `Patient@12345` | Patient (`patient`) |

---

## 4. Running the API Locally

```bash
# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **OpenAPI JSON Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
- **Liveness Probe**: [http://localhost:8000/health](http://localhost:8000/health)
- **Readiness Probe**: [http://localhost:8000/ready](http://localhost:8000/ready)
- **Platform Status & Flags**: [http://localhost:8000/api/v1/platform/status](http://localhost:8000/api/v1/platform/status)

---

## 5. Running Automated Tests

Run the test suite with coverage:

```bash
pytest apps/api/tests -v
```

---

## 6. AYUSH & Dashavidha Pariksha Implementation

The platform includes dedicated fields and Pydantic schemas for the 5 key dimensions of Dashavidha Pariksha:

1. **Prakriti (`AYUSH - Prakriti`)**: Baseline physical and physiological constitution (Vata, Pitta, Kapha, Dwandwaja, Tridoshaja), patient traits, clinician notes.
2. **Vikriti (`AYUSH - Vikriti`)**: Current dosha imbalance, aggravated elements, and symptom progression patterns.
3. **Agni (`AYUSH - Agni`)**: Digestive and metabolic fire state: `MANDA` (slow), `TIKSHNA` (intense), `VISHAMA` (irregular), `SAMA` (balanced), appetite levels.
4. **Koshtha (`AYUSH - Koshtha`)**: Gut motility and bowel regularity: `KRURA` (hard/constipated), `MRIDU` (soft), `MADHYAMA` (moderate).
5. **Sattva (`AYUSH - Sattva`)**: Mental temperament and psychological resilience: `PRAVARA` (high), `MADHYAMA` (moderate), `AVARA` (low), sleep disturbance, stress prompts.

---

## 7. Teammate Integration Seams

| Feature Branch | Teammate | Owned Contracts & Extension Points |
| :--- | :--- | :--- |
| `feature/auth` | Member 1 | Use `app/db/models/user.py`, `app/schemas/user.py`, `app/api/dependencies.py` (`get_current_user`, `require_roles`). Add OTP registration, password reset, and patient auth flows in `app/api/v1/endpoints/auth.py`. |
| `feature/ai-summary` | Member 2 | Use `app/db/models/summary.py`, `app/schemas/summary.py`, `SummaryProvider` protocol in `app/integrations/summary.py`. Implement prompt templates, Groq/OpenAI adapters, and preserve explicit AYUSH provenance. |
| `feature/ocr-whisper` | Member 3 | Use `app/db/models/input.py`, `app/db/models/ai_job.py`, `SpeechProvider` in `app/integrations/speech.py`, `OCRProvider` in `app/integrations/ocr.py`, and `StorageProvider` in `app/integrations/storage.py`. |
| `feature/doctor-queue` | Member 4 | Use `app/db/models/queue.py`, `app/db/models/visit.py`, `app/schemas/queue.py`. Implement queue state machine transitions (`WAITING` -> `CALLED` -> `IN_PROGRESS` -> `COMPLETED`) and doctor review endpoints. |

---

## 8. Deployment Strategy

- **Frontend**: Next.js deployed to **Vercel** with CORS allowed via `CORS_ORIGINS`.
- **API & Worker**: FastAPI deployed to **Railway** via `Dockerfile` and `railway.json`.
- **Database**: Managed PostgreSQL on Railway.
- **Object Storage**: Hosted S3-compatible private object storage.
- **Local Dev Support**: `infra/docker-compose.yml` provides local Postgres & MinIO containers.

---

## 9. Doctor Live Queue & Workspace Module

**Branch**: `feature/doctor-queue` | **Owner**: Member 4

### FIFO State Machine & Business Invariants

The doctor queue module implements strict FIFO dispatching and guarded state transitions:

```
[ WAITING ] ──── claim_next ───► [ CALLED ] ──── start ────► [ IN_PROGRESS ] ──── complete ───► [ COMPLETED ]
     │                                │                             │
     ├──── cancel ───► [ CANCELLED ]  ├──── no_show ──► [ NO_SHOW ] └──── flag ───────► [ NEEDS_REVIEW ]
     │                                └──── cancel ───► [ CANCELLED ]
```

### API Endpoints

| Method | Path | Auth | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/queue/today` | Staff (`doctor`, `receptionist`, `admin`) | Fetch today's waiting list in strict FIFO order with wait times |
| `GET` | `/api/v1/queue/summary` | Staff | Real-time counts (waiting, in-progress, completed, max wait) |
| `POST` | `/api/v1/queue/claim-next` | Doctor, Admin | Claim and call the next eligible patient in FIFO sequence |
| `POST` | `/api/v1/queue/{id}/in-progress` | Doctor, Admin | Transition called patient to in-progress consultation |
| `POST` | `/api/v1/queue/{id}/no-show` | Doctor, Receptionist, Admin | Mark unresponsive patient as `NO_SHOW` |
| `POST` | `/api/v1/queue/{id}/cancel` | Doctor, Receptionist, Admin | Cancel a queue entry |
| `GET` | `/api/v1/doctor/workspace/{visit_id}` | Doctor, Admin | Unified clinical context (demographics, AYUSH findings, AI summary, raw inputs) |
| `POST` | `/api/v1/visits/{id}/complete` | Doctor, Admin | Complete encounter with mandatory `disposition` and consultation notes |
| `POST` | `/api/v1/visits/{id}/summary/review` | Doctor, Admin | Confirm, edit, or reject AI-generated clinical summary |

### Test Console UI

Open [http://localhost:8000/doctor-test](http://localhost:8000/doctor-test) to access the interactive doctor console:

- Live queue auto-refreshing every 5 seconds
- Token calling and status transitions
- Full AYUSH Dashavidha Pariksha cards (Prakriti, Vikriti, Agni, Koshtha, Sattva)
- Structured AI Clinical Summary review and confirmation
- Evidence audio transcripts and OCR preview
- Sign & Complete consultation with clinical disposition

### Running Automated Tests

```bash
# Run full suite (26 tests including 12 queue tests)
pytest apps/api/tests/ -v

# Run queue tests specifically
pytest apps/api/tests/test_queue.py -v
```

