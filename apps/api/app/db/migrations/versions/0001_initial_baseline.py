"""Initial baseline database schema for MediKiosk platform.

Revision ID: 0001_initial_baseline
Revises: None
Create Date: 2026-08-28 22:50:00.000000+00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Clinics table
    op.create_table(
        "clinics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("ayush_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supported_languages", sa.JSON(), nullable=False),
        sa.Column("queue_policy", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_clinics_id", "clinics", ["id"])
    op.create_index("ix_clinics_code", "clinics", ["code"], unique=True)

    # 2. Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id", ondelete="SET NULL", name="fk_users_clinic_id_clinics"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_clinic_id", "users", ["clinic_id"])
    op.create_index("ix_users_role", "users", ["role"])

    # 3. Patients table
    op.create_table(
        "patients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("phone_masked", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id", ondelete="SET NULL", name="fk_patients_clinic_id_clinics"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_patients_id", "patients", ["id"])
    op.create_index("ix_patients_phone_hash", "patients", ["phone_hash"], unique=True)
    op.create_index("ix_patients_clinic_id", "patients", ["clinic_id"])

    # 4. Visits table (with AYUSH Dashavidha Pariksha fields)
    op.create_table(
        "visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patients.id", ondelete="CASCADE", name="fk_visits_patient_id_patients"), nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id", ondelete="CASCADE", name="fk_visits_clinic_id_clinics"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="WAITING"),
        sa.Column("intake_pathway", sa.String(length=50), nullable=False, server_default="ALLOPATHIC"),
        sa.Column("token", sa.String(length=20), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_language", sa.String(length=10), nullable=False, server_default="en"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_visits_created_by_users"), nullable=True),
        # AYUSH Dashavidha Pariksha fields
        sa.Column("prakriti", sa.JSON(), nullable=True),
        sa.Column("vikriti", sa.JSON(), nullable=True),
        sa.Column("agni", sa.JSON(), nullable=True),
        sa.Column("koshtha", sa.JSON(), nullable=True),
        sa.Column("sattva", sa.JSON(), nullable=True),
        sa.Column("ayush_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("clinic_id", "token", "service_date", name="uq_visits_clinic_token_date"),
    )
    op.create_index("ix_visits_id", "visits", ["id"])
    op.create_index("ix_visits_patient_id", "visits", ["patient_id"])
    op.create_index("ix_visits_clinic_id", "visits", ["clinic_id"])
    op.create_index("ix_visits_status", "visits", ["status"])
    op.create_index("ix_visits_intake_pathway", "visits", ["intake_pathway"])
    op.create_index("ix_visits_clinic_status_date", "visits", ["clinic_id", "status", "service_date"])

    # 5. Queue entries table
    op.create_table(
        "queue_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE", name="fk_queue_entries_visit_id_visits"), unique=True, nullable=False),
        sa.Column("clinic_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clinics.id", ondelete="CASCADE", name="fk_queue_entries_clinic_id_clinics"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(length=50), nullable=False, server_default="WAITING"),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_queue_entries_id", "queue_entries", ["id"])
    op.create_index("ix_queue_entries_visit_id", "queue_entries", ["visit_id"], unique=True)
    op.create_index("ix_queue_entries_clinic_id", "queue_entries", ["clinic_id"])
    op.create_index("ix_queue_entries_state", "queue_entries", ["state"])
    op.create_index("ix_queue_clinic_state", "queue_entries", ["clinic_id", "state"])

    # 6. Visit inputs table
    op.create_table(
        "visit_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE", name="fk_visit_inputs_visit_id_visits"), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_visit_inputs_id", "visit_inputs", ["id"])
    op.create_index("ix_visit_inputs_visit_id", "visit_inputs", ["visit_id"])
    op.create_index("ix_visit_inputs_kind", "visit_inputs", ["kind"])
    op.create_index("ix_visit_inputs_visit_kind", "visit_inputs", ["visit_id", "kind"])

    # 7. AI Jobs table
    op.create_table(
        "ai_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE", name="fk_ai_jobs_visit_id_visits"), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="mock"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("payload_in", sa.JSON(), nullable=True),
        sa.Column("payload_out", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_jobs_id", "ai_jobs", ["id"])
    op.create_index("ix_ai_jobs_visit_id", "ai_jobs", ["visit_id"])
    op.create_index("ix_ai_jobs_type", "ai_jobs", ["type"])
    op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])
    op.create_index("ix_ai_jobs_idempotency_key", "ai_jobs", ["idempotency_key"], unique=True)
    op.create_index("ix_ai_jobs_status_created", "ai_jobs", ["status", "created_at"])

    # 8. Summaries table
    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("visit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("visits.id", ondelete="CASCADE", name="fk_summaries_visit_id_visits"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_summaries_reviewed_by_users"), nullable=True),
        sa.Column("review_status", sa.String(length=50), nullable=False, server_default="DRAFT"),
        sa.Column("doctor_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("visit_id", "version", name="uq_summaries_visit_version"),
    )
    op.create_index("ix_summaries_id", "summaries", ["id"])
    op.create_index("ix_summaries_visit_id", "summaries", ["visit_id"])
    op.create_index("ix_summaries_review_status", "summaries", ["review_status"])
    op.create_index("ix_summaries_visit_review", "summaries", ["visit_id", "review_status"])

    # 9. Audit Events table
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_audit_events_actor_id_users"), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_id", "audit_events", ["id"])
    op.create_index("ix_audit_events_actor_id", "audit_events", ["actor_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_entity_type", "audit_events", ["entity_type"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("ix_audit_events_req_entity", "audit_events", ["request_id", "entity_type", "entity_id"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("summaries")
    op.drop_table("ai_jobs")
    op.drop_table("visit_inputs")
    op.drop_table("queue_entries")
    op.drop_table("visits")
    op.drop_table("patients")
    op.drop_table("users")
    op.drop_table("clinics")
