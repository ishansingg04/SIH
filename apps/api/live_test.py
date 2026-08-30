"""
Live integration test -- calls the real Groq API.
Uses SQLite in-memory DB (same as unit tests) so Postgres is not required.
GROQ_API_KEY is read from .env at repo root.

Usage (from repo root):
    python apps/api/live_test.py
"""

import asyncio
import io
import json
import math
import os
import struct
import sys
import time
import wave
from pathlib import Path

# ── 1. Load .env BEFORE anything else touches os.environ ─────────────────────
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

# ── 2. Force SQLite so we don't need a running Postgres ───────────────────────
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# ── 3. Python path ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

# ── 4. Now import app (settings already locked via env vars above) ────────────
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.api.dependencies import get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.user import User
from app.db.models.visit import Visit
from app.db.seed import seed_database
from app.main import app

# ── 5. Wire test DB ───────────────────────────────────────────────────────────
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)

Base.metadata.create_all(bind=_engine)
with _TestingSession() as _db:
    seed_database(_db)

def _override_get_db():
    session = _TestingSession()
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = _override_get_db

# Patch SessionLocal everywhere so background tasks use the test SQLite DB.
# The endpoints import SessionLocal by name at module load time, so we must
# patch both the source module and the endpoint modules that imported it.
import app.db.session as _db_session_mod
import app.api.v1.endpoints.uploads as _uploads_mod
import app.api.v1.endpoints.processing as _processing_mod

_db_session_mod.SessionLocal = _TestingSession
_uploads_mod.SessionLocal = _TestingSession
_processing_mod.SessionLocal = _TestingSession



# ── Output helpers ────────────────────────────────────────────────────────────
def ok(msg):   print(f"  [OK]   {msg}", flush=True)
def fail(msg): print(f"  [FAIL] {msg}", flush=True)
def info(msg): print(f"  -->    {msg}", flush=True)
def head(msg): print(f"\n{'='*60}\n {msg}\n{'='*60}", flush=True)


# ── Test asset generators ─────────────────────────────────────────────────────
def make_wav_bytes(duration_s: float = 2.0, freq: float = 440.0) -> bytes:
    """Generate a real WAV file (sine wave) entirely in-memory."""
    sample_rate = 16000
    n_samples = int(sample_rate * duration_s)
    raw = b"".join(
        struct.pack("<h", int(32767 * math.sin(2 * math.pi * freq * i / sample_rate)))
        for i in range(n_samples)
    )
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return wav_io.getvalue()


def get_prescription_image() -> tuple[bytes, str, str]:
    """Load the real prescription JPEG for OCR testing."""
    img_path = Path(__file__).parent / "test_prescription.jpg"
    if not img_path.exists():
        raise FileNotFoundError(f"Test image not found at {img_path}")
    data = img_path.read_bytes()
    return data, "prescription.jpg", "image/jpeg"


# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    print("\n" + "="*60, flush=True)
    print(" MEDIKIOSK -- Live Groq Integration Test", flush=True)
    print("="*60, flush=True)

    # Step 1: Env check
    head("Step 1 -- Environment Check")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key or "your_real_key" in groq_key:
        fail("GROQ_API_KEY not set or still a placeholder.")
        fail(f"Edit {_env_path} and add your real key.")
        sys.exit(1)
    ok(f"GROQ_API_KEY found  (starts with: {groq_key[:10]}...)")
    ok(f"WHISPER_PROVIDER_MODE = {os.environ.get('WHISPER_PROVIDER_MODE')}")
    ok(f"OCR_PROVIDER_MODE     = {os.environ.get('OCR_PROVIDER_MODE')}")

    # Step 2: DB already seeded above
    head("Step 2 -- Database (SQLite in-memory)")
    ok("Tables created + seed data loaded")

    client = TestClient(app)

    # Step 3: Auth
    head("Step 3 -- Authenticate")
    resp = client.post("/api/v1/auth/login", json={
        "email": "asha.devi@medikiosk.in",
        "password": "Patient@12345",
    })
    if resp.status_code != 200:
        fail(f"Login failed: {resp.status_code} -- {resp.text[:300]}")
        sys.exit(1)
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ok("Logged in as asha.devi@medikiosk.in")

    # Step 4: Find a consented visit
    head("Step 4 -- Find Visit With Consent")
    with _TestingSession() as db:
        visit = db.scalars(
            select(Visit).where(Visit.consent_at.isnot(None))
        ).first()
    if not visit:
        fail("No visit with consent in seed data.")
        sys.exit(1)
    visit_id = str(visit.id)
    ok(f"Visit ID: {visit_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 5: Groq Whisper
    # ─────────────────────────────────────────────────────────────────────────
    head("Step 5 -- Groq Whisper Transcription")
    wav_bytes = make_wav_bytes()
    info(f"Generated WAV: {len(wav_bytes):,} bytes (2s sine wave, 16kHz)")

    upload_resp = client.post(
        f"/api/v1/visits/{visit_id}/audio",
        headers=headers,
        files={"file": ("test.wav", wav_bytes, "audio/wav")},
        data={"language": "en"},
    )
    if upload_resp.status_code != 202:
        fail(f"Audio upload HTTP {upload_resp.status_code}")
        print(json.dumps(upload_resp.json(), indent=2), flush=True)
        sys.exit(1)

    audio_input_id = upload_resp.json()["data"]["input_id"]
    audio_provider  = upload_resp.json()["data"]["provider"]
    ok(f"Accepted  input_id={audio_input_id}  provider={audio_provider}")

    # Give BackgroundTask time to fire and call Groq
    info("Polling status (up to 40s)...")
    whisper_ok = False
    for i in range(20):
        time.sleep(2)
        poll = client.get(f"/api/v1/inputs/{audio_input_id}", headers=headers)
        if poll.status_code != 200:
            info(f"  [{i+1:02d}] poll HTTP {poll.status_code}")
            continue
        d = poll.json()["data"]
        info(f"  [{i+1:02d}] {d['status']:10s}  progress={d['progress']}%  attempts={d['attempts']}")
        if d["status"] == "COMPLETED":
            ok("Transcription COMPLETED")
            preview = d.get("result_preview") or "(empty -- sine wave has no speech)"
            ok(f"Text preview: {preview[:150]}")
            whisper_ok = True
            break
        if d["status"] == "FAILED":
            fail(f"Transcription FAILED  error_code={d.get('error_code')}")
            break
    else:
        fail("Transcription timed out after 40s")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 6: Groq Vision OCR
    # ─────────────────────────────────────────────────────────────────────────
    head("Step 6 -- Groq Vision OCR")
    png_bytes, img_filename, img_content_type = get_prescription_image()
    info(f"Loaded prescription image: {len(png_bytes):,} bytes ({img_filename})")

    doc_resp = client.post(
        f"/api/v1/visits/{visit_id}/uploads",
        headers=headers,
        files={"file": (img_filename, png_bytes, img_content_type)},
    )
    if doc_resp.status_code != 202:
        fail(f"Document upload HTTP {doc_resp.status_code}")
        print(json.dumps(doc_resp.json(), indent=2), flush=True)
        sys.exit(1)

    doc_input_id = doc_resp.json()["data"]["input_id"]
    doc_provider  = doc_resp.json()["data"]["provider"]
    ok(f"Accepted  input_id={doc_input_id}  provider={doc_provider}")

    info("Polling status (up to 40s)...")
    ocr_ok = False
    for i in range(20):
        time.sleep(2)
        poll = client.get(f"/api/v1/inputs/{doc_input_id}", headers=headers)
        if poll.status_code != 200:
            info(f"  [{i+1:02d}] poll HTTP {poll.status_code}")
            continue
        d = poll.json()["data"]
        info(f"  [{i+1:02d}] {d['status']:10s}  progress={d['progress']}%  attempts={d['attempts']}")
        if d["status"] == "COMPLETED":
            ok("OCR COMPLETED")
            preview = d.get("result_preview") or "(empty -- blank image)"
            ok(f"Text preview: {preview[:150]}")
            ocr_ok = True
            break
        if d["status"] == "FAILED":
            fail(f"OCR FAILED  error_code={d.get('error_code')}")
            break
    else:
        fail("OCR timed out after 40s")

    # ─────────────────────────────────────────────────────────────────────────
    # Step 7: Worker endpoint (operator role)
    # ─────────────────────────────────────────────────────────────────────────
    head("Step 7 -- Worker Observability")
    with _TestingSession() as db:
        op = db.scalars(
            select(User).where(User.email == "operator@medikiosk.in")
        ).first()
    op_token = create_access_token(
        subject=op.id, role=op.role.value, clinic_id=None
    )
    worker_resp = client.get(
        "/api/v1/worker/jobs",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    if worker_resp.status_code == 200:
        cnt = worker_resp.json()["data"]["total"]
        ok(f"Worker endpoint accessible -- {cnt} pending/retrying job(s)")
    else:
        fail(f"Worker endpoint HTTP {worker_resp.status_code}")

    # ─────────────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────────────
    head("RESULTS")
    print(f"  Groq Whisper   : {'PASS' if whisper_ok else 'FAIL'}", flush=True)
    print(f"  Groq Vision    : {'PASS' if ocr_ok    else 'FAIL'}", flush=True)
    print(flush=True)
    if whisper_ok and ocr_ok:
        print("  All live Groq tests PASSED. Ready to commit.", flush=True)
    else:
        print("  Some tests FAILED -- check output above.", flush=True)
    print(flush=True)


if __name__ == "__main__":
    run()
