from enum import Enum


class UserRole(str, Enum):
    PATIENT = "patient"
    RECEPTIONIST = "receptionist"
    DOCTOR = "doctor"
    CLINIC_ADMIN = "clinic_admin"
    SYSTEM_OPERATOR = "system_operator"


class VisitStatus(str, Enum):
    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_PROGRESS = "IN_PROGRESS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


class IntakePathway(str, Enum):
    ALLOPATHIC = "ALLOPATHIC"
    AYUSH = "AYUSH"


class InputKind(str, Enum):
    AUDIO = "AUDIO"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    PDF = "PDF"
    AYUSH_FORM = "AYUSH_FORM"


class InputStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AIJobType(str, Enum):
    TRANSCRIPTION = "TRANSCRIPTION"
    OCR = "OCR"
    NORMALIZATION = "NORMALIZATION"
    SUMMARIZATION = "SUMMARIZATION"


class AIJobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class SummaryReviewStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EDITED = "EDITED"


# AYUSH Dashavidha Pariksha Enums
class PrakritiDosha(str, Enum):
    VATA = "VATA"
    PITTA = "PITTA"
    KAPHA = "KAPHA"
    VATA_PITTA = "VATA_PITTA"
    PITTA_KAPHA = "PITTA_KAPHA"
    VATA_KAPHA = "VATA_KAPHA"
    TRIDOSHAJA = "TRIDOSHAJA"


class AgniType(str, Enum):
    MANDA = "MANDA"          # Slow/hypoactive
    TIKSHNA = "TIKSHNA"      # Intense/hyperactive
    VISHAMA = "VISHAMA"      # Irregular/variable
    SAMA = "SAMA"            # Balanced/normal


class KoshthaType(str, Enum):
    KRURA = "KRURA"          # Hard/constipated
    MRIDU = "MRIDU"          # Soft/lax
    MADHYAMA = "MADHYAMA"    # Moderate/regular


class SattvaType(str, Enum):
    PRAVARA = "PRAVARA"      # High/resilient
    MADHYAMA = "MADHYAMA"    # Medium
    AVARA = "AVARA"          # Low/vulnerable
