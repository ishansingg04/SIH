# MediKiosk AI — Smart India Hackathon 2026

AI-powered OPD Patient Kiosk for faster, multilingual patient intake and intelligent doctor summaries.

---

## Project Overview

**MediKiosk AI** is a healthcare kiosk designed for hospitals and clinics where patients enter their symptoms before meeting the doctor. The system supports **English and Hindi**, accepts **voice or text input**, extracts information from **lab reports and prescriptions**, and generates a structured **AI summary** for the doctor.

The goal is to reduce OPD waiting time, improve documentation quality, and give doctors complete patient context before consultation.

---

## Core Features

### Patient Kiosk

* English / Hindi language selection
* New & Existing patient registration
* Voice input (Whisper)
* Text input
* Upload previous prescriptions & lab reports
* OCR extraction from medical documents
* Patient review screen before submission
* Automatic queue token generation

### Doctor Dashboard

* Secure doctor login
* Live patient queue
* Open patient by token number
* AI-generated structured medical summary
* Previous visit history (for existing patients)
* View uploaded reports and prescriptions

---

## Tech Stack

| Layer          | Technology             |
| -------------- | ---------------------- |
| Frontend       | Next.js + Tailwind CSS |
| Backend        | FastAPI                |
| AI             | OpenAI GPT + Whisper   |
| OCR            | PaddleOCR              |
| Database       | PostgreSQL             |
| File Storage   | MinIO                  |
| Authentication | JWT                    |

---

## Backend Architecture

```text
backend/
│
├── app/
│   ├── api/          # REST endpoints
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic schemas
│   ├── services/     # AI, OCR & business logic
│   ├── db/           # Database configuration
│   └── main.py
│
├── tests/
├── requirements.txt
└── README.md
```

---

## Git Workflow (Mandatory)

**Never push directly to `main`.**

Every member works on their own feature branch.

| Member       | Branch                 |
| ------------ | ---------------------- |
| Backend Lead | `main`                 |
| Member 1     | `feature/auth`         |
| Member 2     | `feature/ai-summary`   |
| Member 3     | `feature/ocr-whisper`  |
| Member 4     | `feature/doctor-queue` |

### Daily Workflow

```bash
# Update your branch with latest backend
git checkout feature/your-branch
git pull origin main

# Work with Antigravity / Cursor

git add .
git commit -m "Completed feature"
git push origin feature/your-branch
```

Create a **Pull Request** after completing your feature. Only the Backend Lead merges into `main`.

---

## Patient Flow

1. Select Language (English / Hindi)
2. Login or Register
3. Enter symptoms (Voice/Text)
4. Upload reports (optional)
5. OCR + Whisper processing
6. Patient reviews extracted information
7. Submit
8. Queue token generated
9. Doctor receives AI summary

---

## Doctor Flow

1. Login
2. View live patient queue
3. Call patient by token
4. Open detailed summary
5. Review reports & history
6. Begin consultation

---

## Current Status

* [ ] Backend initialization
* [ ] Database schema
* [ ] Authentication APIs
* [ ] Whisper integration
* [ ] OCR integration
* [ ] AI summary generation
* [ ] Doctor queue
* [ ] Frontend UI

---

## Team Rules

* One feature = One branch
* Pull latest `main` before starting work
* Keep commits small and meaningful
* Open Pull Request for every completed feature
* Do not modify another member's feature branch

---

**Smart India Hackathon 2026 • MediKiosk AI**
