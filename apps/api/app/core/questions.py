"""Typed Question Library & Slot Taxonomy for MediKiosk Adaptive Interview.

Defines all conversational information slots, multi-lingual questions (EN, HI),
pathway assignments (ALLOPATHIC, AYUSH), input types, and selection rules.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SlotType(str, Enum):
    # General / Allopathic Slots
    CHIEF_COMPLAINT = "chief_complaint"
    LOCATION = "location"
    DURATION = "duration"
    SEVERITY = "severity"
    TRAJECTORY = "trajectory"
    ASSOCIATED_SYMPTOMS = "associated_symptoms"
    MODIFYING_FACTORS = "modifying_factors"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    MEDICAL_HISTORY = "medical_history"

    # AYUSH Dashavidha Pariksha Slots
    PRAKRITI = "prakriti"
    VIKRITI = "vikriti"
    AGNI = "agni"
    KOSHTHA = "koshtha"
    SATTVA = "sattva"


class QuestionInputType(str, Enum):
    VOICE_OR_TEXT = "voice_or_text"
    SEVERITY_SCALE = "severity_scale"  # 0 to 10 scale
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"


class InterviewQuestion(BaseModel):
    id: str
    slot: SlotType
    text_en: str
    text_hi: str
    pathway: str = "ALLOPATHIC"  # "ALLOPATHIC", "AYUSH", or "BOTH"
    input_type: QuestionInputType = QuestionInputType.VOICE_OR_TEXT
    required: bool = True
    priority: int = 100  # Lower number = higher priority
    options_en: Optional[List[str]] = None
    options_hi: Optional[List[str]] = None
    validation_rule: Optional[Dict[str, Any]] = None

    def get_text(self, language: str = "en") -> str:
        lang = (language or "en").lower()
        if lang.startswith("hi"):
            return self.text_hi
        return self.text_en

    def get_options(self, language: str = "en") -> Optional[List[str]]:
        lang = (language or "en").lower()
        if lang.startswith("hi") and self.options_hi:
            return self.options_hi
        return self.options_en


# ==============================================================================
# QUESTION LIBRARY REGISTRY
# ==============================================================================

QUESTION_LIBRARY: List[InterviewQuestion] = [
    # 1. Chief Complaint (Initial statement / Fallback)
    InterviewQuestion(
        id="q_chief_complaint",
        slot=SlotType.CHIEF_COMPLAINT,
        text_en="What is the main health problem or symptom bringing you here today?",
        text_hi="आज आपको मुख्य रूप से क्या स्वास्थ्य समस्या या तकलीफ हो रही है?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=True,
        priority=10,
    ),
    # 2. Duration & Onset
    InterviewQuestion(
        id="q_duration",
        slot=SlotType.DURATION,
        text_en="How long have you been having this problem, and did it start suddenly or gradually?",
        text_hi="यह समस्या आपको कितने समय (दिनों/घंटों) से है, और यह अचानक शुरू हुई या धीरे-धीरे?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=True,
        priority=20,
    ),
    # 3. Body Location
    InterviewQuestion(
        id="q_location",
        slot=SlotType.LOCATION,
        text_en="Where in your body are you experiencing this pain or discomfort?",
        text_hi="यह दर्द या परेशानी आपके शरीर के किस हिस्से में हो रही है?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=True,
        priority=30,
    ),
    # 4. Severity Scale (0 to 10)
    InterviewQuestion(
        id="q_severity",
        slot=SlotType.SEVERITY,
        text_en="On a scale from 0 (no pain) to 10 (unbearable pain), how severe is your discomfort right now?",
        text_hi="0 (कोई दर्द नहीं) से 10 (असहनीय दर्द) के पैमाने पर, आपकी तकलीफ अभी कितनी तीव्र है?",
        pathway="BOTH",
        input_type=QuestionInputType.SEVERITY_SCALE,
        required=True,
        priority=40,
        validation_rule={"min": 0, "max": 10},
    ),
    # 5. Trajectory / Progression
    InterviewQuestion(
        id="q_trajectory",
        slot=SlotType.TRAJECTORY,
        text_en="Is your symptom getting better, worse, or staying the same?",
        text_hi="क्या आपकी तकलीफ में सुधार हो रहा है, यह बढ़ रही है, या वैसी ही बनी हुई है?",
        pathway="BOTH",
        input_type=QuestionInputType.SINGLE_CHOICE,
        required=False,
        priority=50,
        options_en=["Improving", "Worsening", "Constant", "Fluctuating"],
        options_hi=["सुधार हो रहा है", "बढ़ रहा है", "स्थिर है", "कम-ज्यादा होता रहता है"],
    ),
    # 6. Associated Symptoms
    InterviewQuestion(
        id="q_associated_symptoms",
        slot=SlotType.ASSOCIATED_SYMPTOMS,
        text_en="Are you experiencing any other symptoms, such as fever, cough, nausea, or dizziness?",
        text_hi="क्या आपको इसके साथ कोई अन्य लक्षण जैसे बुखार, खांसी, उल्टी, या चक्कर आना महसूस हो रहा है?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=60,
    ),
    # 7. Modifying / Aggravating / Relieving Factors
    InterviewQuestion(
        id="q_modifying_factors",
        slot=SlotType.MODIFYING_FACTORS,
        text_en="Does anything make your symptoms feel better or worse (e.g. resting, eating, moving)?",
        text_hi="क्या किसी चीज से (जैसे आराम करने, खाने, या चलने-फिरने से) आपकी तकलीफ कम या ज्यादा होती है?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=70,
    ),
    # 8. Medications Already Taken
    InterviewQuestion(
        id="q_medications",
        slot=SlotType.MEDICATIONS,
        text_en="Have you taken any medicines, home remedies, or painkillers for this condition?",
        text_hi="क्या आपने इस तकलीफ के लिए कोई दवा, घरेलू नुस्खा या पेनकिलर लिया है?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=80,
    ),
    # 9. Known Allergies
    InterviewQuestion(
        id="q_allergies",
        slot=SlotType.ALLERGIES,
        text_en="Do you have any known allergies to medicines, foods, or substances?",
        text_hi="क्या आपको किसी दवा, भोजन, या अन्य चीज से कोई एलर्जी है?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=90,
    ),
    # 10. Relevant Medical History
    InterviewQuestion(
        id="q_medical_history",
        slot=SlotType.MEDICAL_HISTORY,
        text_en="Do you have any ongoing health conditions like diabetes, high blood pressure, or asthma?",
        text_hi="क्या आपको पहले से कोई बीमारी है जैसे डायबिटीज, ब्लड प्रेशर, थायरॉयड, या अस्थमा?",
        pathway="BOTH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=100,
    ),

    # ==========================================================================
    # AYUSH DASHAVIDHA PARIKSHA SPECIFIC QUESTIONS
    # ==========================================================================
    # 11. Prakriti (Baseline Body Constitution)
    InterviewQuestion(
        id="q_ayush_prakriti",
        slot=SlotType.PRAKRITI,
        text_en="How would you describe your general physical build, skin texture, and sensitivity to cold or heat?",
        text_hi="आपकी शारीरिक बनावट कैसी है (दुबली/मध्यम/भारी), त्वचा सूखी या तैलीय है, और ठंड या गर्मी ज्यादा लगती है?",
        pathway="AYUSH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=True,
        priority=35,
    ),
    # 12. Agni (Digestive Fire & Appetite)
    InterviewQuestion(
        id="q_ayush_agni",
        slot=SlotType.AGNI,
        text_en="How is your appetite and digestion? (e.g. sharp hunger, irregular hunger, slow digestion, or bloating?)",
        text_hi="आपकी भूख और पाचन क्रिया कैसी है? (भूख समय पर लगती है, कभी कम कभी ज्यादा, या पेट भारी रहता है?)",
        pathway="AYUSH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=True,
        priority=45,
    ),
    # 13. Koshtha (Bowel Motility & Evacuation)
    InterviewQuestion(
        id="q_ayush_koshtha",
        slot=SlotType.KOSHTHA,
        text_en="How are your bowel movements? (e.g. regular daily, hard/constipated, or loose?)",
        text_hi="आपका पेट साफ होने की प्रक्रिया कैसी है? (रोजाना नियमित, कब्ज की शिकायत, या दस्त की प्रवृत्ति?)",
        pathway="AYUSH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=True,
        priority=55,
    ),
    # 14. Sattva (Mental Resilience & Sleep)
    InterviewQuestion(
        id="q_ayush_sattva",
        slot=SlotType.SATTVA,
        text_en="How is your sleep and stress level? Do you experience sound sleep or restlessness?",
        text_hi="आपकी नींद और मानसिक स्थिति कैसी है? नींद गहरी आती है या रात में बार-बार टूटती है?",
        pathway="AYUSH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=65,
    ),
    # 15. Vikriti (Imbalance Pattern)
    InterviewQuestion(
        id="q_ayush_vikriti",
        slot=SlotType.VIKRITI,
        text_en="What triggers or weather conditions seem to aggravate this current problem?",
        text_hi="किन कारणों, मौसम या खान-पान से यह वर्तमान समस्या बढ़ती हुई लगती है?",
        pathway="AYUSH",
        input_type=QuestionInputType.VOICE_OR_TEXT,
        required=False,
        priority=75,
    ),
]


# Lookup map by ID
QUESTION_BY_ID: Dict[str, InterviewQuestion] = {q.id: q for q in QUESTION_LIBRARY}
QUESTION_BY_SLOT: Dict[SlotType, List[InterviewQuestion]] = {}
for q in QUESTION_LIBRARY:
    QUESTION_BY_SLOT.setdefault(q.slot, []).append(q)


def get_question_by_id(question_id: str) -> Optional[InterviewQuestion]:
    """Retrieve question definition by unique question ID."""
    return QUESTION_BY_ID.get(question_id)


def get_default_slots_for_pathway(pathway: str) -> List[SlotType]:
    """Return the ordered list of required information slots for a pathway."""
    is_ayush = (pathway or "").upper() == "AYUSH"
    slots = [
        SlotType.CHIEF_COMPLAINT,
        SlotType.LOCATION,
        SlotType.DURATION,
        SlotType.SEVERITY,
    ]
    if is_ayush:
        slots.extend([
            SlotType.PRAKRITI,
            SlotType.AGNI,
            SlotType.KOSHTHA,
            SlotType.SATTVA,
        ])
    else:
        slots.extend([
            SlotType.TRAJECTORY,
            SlotType.ASSOCIATED_SYMPTOMS,
            SlotType.MEDICATIONS,
            SlotType.ALLERGIES,
        ])
    return slots


def get_next_question(
    missing_slots: List[str],
    answered_question_ids: List[str],
    pathway: str = "ALLOPATHIC",
    language: str = "en",
) -> Optional[InterviewQuestion]:
    """Select the highest priority unanswered question matching missing slots and pathway."""
    pathway_upper = (pathway or "ALLOPATHIC").upper()
    answered_set = set(answered_question_ids)

    candidate_questions: List[InterviewQuestion] = []
    for q in QUESTION_LIBRARY:
        if q.id in answered_set:
            continue
        if q.pathway != "BOTH" and q.pathway != pathway_upper:
            continue
        if q.slot.value in missing_slots or q.slot in missing_slots:
            candidate_questions.append(q)

    if not candidate_questions:
        return None

    # Sort candidates by:
    # 1. Required status (True first)
    # 2. Priority integer (Lowest number first)
    candidate_questions.sort(key=lambda item: (not item.required, item.priority))
    return candidate_questions[0]
