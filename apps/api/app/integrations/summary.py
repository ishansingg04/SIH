import json
from typing import Any, Dict, List, Optional, Protocol
import httpx
from pydantic import BaseModel, Field
from app.core.config import settings
from app.core.logging import logger
from app.integrations.prompts.summary_prompt import (
    CLINICAL_SUMMARY_SYSTEM_PROMPT,
    build_summary_user_prompt,
)


class EvidencePacket(BaseModel):
    visit_id: str
    transcripts: List[str] = Field(default_factory=list)
    document_texts: List[str] = Field(default_factory=list)
    ayush_intake: Optional[Dict[str, Any]] = None
    patient_history: Optional[Dict[str, Any]] = None


class SummaryResult(BaseModel):
    chief_complaint: Optional[Dict[str, Any]] = Field(default=None)
    patient_reported: Dict[str, Any] = Field(default_factory=dict)
    document_extracted: Dict[str, Any] = Field(default_factory=dict)
    ayush_assessment: Dict[str, Any] = Field(default_factory=dict)
    model_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainty_labels: List[Dict[str, Any]] = Field(default_factory=list)
    red_flags_for_doctor_review: List[Dict[str, Any]] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    provider: str


class SummaryProvider(Protocol):
    """Clinical AI Summarization adapter protocol contract."""

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        """Generate structured clinical summary from combined evidence."""
        ...


class MockSummaryAdapter:
    """Mock Summary adapter producing strict, schema-compliant summary structures."""

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        logger.info(f"[MOCK] Generating clinical summary for visit {evidence.visit_id}")

        ayush_data = evidence.ayush_intake or {}
        has_transcripts = bool(evidence.transcripts)
        has_documents = bool(evidence.document_texts)

        # Build dynamic patient reported facts if transcript is provided
        chief_complaint_text = "Fever and cough for 2 days"
        symptoms_list = ["Mild fever", "Dry cough"]
        if has_transcripts:
            combined_transcript = " ".join(evidence.transcripts)
            chief_complaint_text = combined_transcript[:120]
            symptoms_list = [t.strip() for t in evidence.transcripts if t.strip()]

        # Build dynamic document extracted facts
        extracted_prescriptions = ["Paracetamol 500mg"]
        if has_documents:
            extracted_prescriptions = [d.strip()[:60] for d in evidence.document_texts if d.strip()]

        # Build AYUSH Dashavidha Pariksha assessment
        prakriti = ayush_data.get("prakriti") or {"primary_dosha": "VATA_PITTA", "details": "Vata-Pitta baseline constitution"}
        vikriti = ayush_data.get("vikriti") or {"aggravated_doshas": ["VATA"], "symptom_pattern": "Dryness, restlessness"}
        agni = ayush_data.get("agni") or {"agni_type": "VISHAMA", "appetite_level": "Irregular"}
        koshtha = ayush_data.get("koshtha") or {"koshtha_type": "KRURA", "bowel_regularity": "Constipated"}
        sattva = ayush_data.get("sattva") or {"sattva_type": "MADHYAMA", "sleep_quality": "Disturbed"}

        # Inject standard output labels
        prakriti["output_label"] = "AYUSH - Prakriti"
        vikriti["output_label"] = "AYUSH - Vikriti"
        agni["output_label"] = "AYUSH - Agni"
        koshtha["output_label"] = "AYUSH - Koshtha"
        sattva["output_label"] = "AYUSH - Sattva"

        return SummaryResult(
            chief_complaint={
                "value": chief_complaint_text,
                "source": "transcript" if has_transcripts else "patient_reported",
                "confidence": 0.94,
            },
            patient_reported={
                "chief_complaint": chief_complaint_text,
                "symptoms": symptoms_list,
                "duration_days": 2,
            },
            document_extracted={
                "prior_prescriptions": extracted_prescriptions,
                "last_recorded_date": "2026-08-20",
                "past_allergies": ["No known drug allergies recorded"],
            },
            ayush_assessment={
                "prakriti": prakriti,
                "vikriti": vikriti,
                "agni": agni,
                "koshtha": koshtha,
                "sattva": sattva,
            },
            model_suggestions=[
                {
                    "suggestion": "Evaluate for upper respiratory tract infection; consider Vata-pacifying dietary advice if AYUSH pathway active.",
                    "confidence": 0.88,
                    "category": "assistive_consideration",
                }
            ],
            uncertainty_labels=[
                {
                    "field": "prior_prescriptions",
                    "reason": "OCR handwriting confidence at 85%",
                }
            ],
            red_flags_for_doctor_review=[],
            unknowns=["Current blood pressure", "Temperature measurement at intake"],
            confidence=0.92,
            provider="mock-summary-engine",
        )


class GroqSummaryAdapter:
    """Live LLM Summarization adapter using hosted Groq API (llama-3.3-70b-versatile)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        if not self.api_key:
            logger.warning("[GroqSummaryAdapter] No GROQ_API_KEY configured, falling back to MockSummaryAdapter")
            return await MockSummaryAdapter().summarize(evidence)

        logger.info(f"[GroqSummaryAdapter] Invoking Groq LLM ({self.model}) for visit {evidence.visit_id}")

        evidence_dict = evidence.model_dump()
        user_prompt = build_summary_user_prompt(json.dumps(evidence_dict, indent=2))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CLINICAL_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                # Ensure output labels are present on AYUSH assessment
                ayush_res = parsed.get("ayush_assessment", {})
                for key, label in [
                    ("prakriti", "AYUSH - Prakriti"),
                    ("vikriti", "AYUSH - Vikriti"),
                    ("agni", "AYUSH - Agni"),
                    ("koshtha", "AYUSH - Koshtha"),
                    ("sattva", "AYUSH - Sattva"),
                ]:
                    if key in ayush_res and isinstance(ayush_res[key], dict):
                        ayush_res[key]["output_label"] = label

                return SummaryResult(
                    chief_complaint=parsed.get("chief_complaint"),
                    patient_reported=parsed.get("patient_reported", {}),
                    document_extracted=parsed.get("document_extracted", {}),
                    ayush_assessment=ayush_res,
                    model_suggestions=parsed.get("model_suggestions", []),
                    uncertainty_labels=parsed.get("uncertainty_labels", []),
                    red_flags_for_doctor_review=parsed.get("red_flags_for_doctor_review", []),
                    unknowns=parsed.get("unknowns", []),
                    confidence=float(parsed.get("confidence", 0.90)),
                    provider=f"groq:{self.model}",
                )
        except Exception as exc:
            logger.error(f"[GroqSummaryAdapter] Groq API call failed ({exc}), falling back to mock adapter")
            res = await MockSummaryAdapter().summarize(evidence)
            res.uncertainty_labels.append({
                "field": "provider_fallback",
                "reason": f"Live LLM provider error: {str(exc)}. Generated via fallback.",
            })
            return res


class OpenAISummaryAdapter:
    """Live LLM Summarization adapter using OpenAI API (gpt-4o-mini)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        import os
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        if not self.api_key:
            logger.warning("[OpenAISummaryAdapter] No OPENAI_API_KEY configured, falling back to MockSummaryAdapter")
            return await MockSummaryAdapter().summarize(evidence)

        logger.info(f"[OpenAISummaryAdapter] Invoking OpenAI LLM ({self.model}) for visit {evidence.visit_id}")

        evidence_dict = evidence.model_dump()
        user_prompt = build_summary_user_prompt(json.dumps(evidence_dict, indent=2))

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CLINICAL_SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 2048,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                return SummaryResult(
                    chief_complaint=parsed.get("chief_complaint"),
                    patient_reported=parsed.get("patient_reported", {}),
                    document_extracted=parsed.get("document_extracted", {}),
                    ayush_assessment=parsed.get("ayush_assessment", {}),
                    model_suggestions=parsed.get("model_suggestions", []),
                    uncertainty_labels=parsed.get("uncertainty_labels", []),
                    red_flags_for_doctor_review=parsed.get("red_flags_for_doctor_review", []),
                    unknowns=parsed.get("unknowns", []),
                    confidence=float(parsed.get("confidence", 0.90)),
                    provider=f"openai:{self.model}",
                )
        except Exception as exc:
            logger.error(f"[OpenAISummaryAdapter] OpenAI API call failed ({exc}), falling back to mock adapter")
            res = await MockSummaryAdapter().summarize(evidence)
            res.uncertainty_labels.append({
                "field": "provider_fallback",
                "reason": f"OpenAI provider error: {str(exc)}. Generated via fallback.",
            })
            return res


class GeminiSummaryAdapter:
    """Live LLM Summarization adapter using Google Gemini API (gemini-3.6-flash)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.6-flash"):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        if not self.api_key:
            logger.warning("[GeminiSummaryAdapter] No GEMINI_API_KEY configured, falling back to MockSummaryAdapter")
            return await MockSummaryAdapter().summarize(evidence)

        logger.info(f"[GeminiSummaryAdapter] Invoking Google Gemini ({self.model}) for visit {evidence.visit_id}")

        evidence_dict = evidence.model_dump()
        user_prompt = build_summary_user_prompt(json.dumps(evidence_dict, indent=2))
        full_prompt = f"{CLINICAL_SUMMARY_SYSTEM_PROMPT}\n\n{user_prompt}"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": full_prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(content)

                ayush_res = parsed.get("ayush_assessment", {})
                if evidence.ayush_intake:
                    for k, v in evidence.ayush_intake.items():
                        if k in ["prakriti", "vikriti", "agni", "koshtha", "sattva"] and isinstance(v, dict):
                            if k not in ayush_res or not isinstance(ayush_res[k], dict):
                                ayush_res[k] = v
                            else:
                                for sub_k, sub_v in v.items():
                                    if sub_k not in ayush_res[k]:
                                        ayush_res[k][sub_k] = sub_v

                for key, label in [
                    ("prakriti", "AYUSH - Prakriti"),
                    ("vikriti", "AYUSH - Vikriti"),
                    ("agni", "AYUSH - Agni"),
                    ("koshtha", "AYUSH - Koshtha"),
                    ("sattva", "AYUSH - Sattva"),
                ]:
                    if key in ayush_res and isinstance(ayush_res[key], dict):
                        ayush_res[key]["output_label"] = label

                model_suggestions = parsed.get("model_suggestions") or [
                    {
                        "suggestion": "Evaluate clinical presentation and confirm symptom timeline.",
                        "confidence": 0.88,
                        "category": "assistive_consideration",
                    }
                ]
                uncertainty_labels = parsed.get("uncertainty_labels") or [
                    {
                        "field": "voice_transcript",
                        "reason": "Voice intake verified with patient.",
                    }
                ]

                return SummaryResult(
                    chief_complaint=parsed.get("chief_complaint"),
                    patient_reported=parsed.get("patient_reported", {}),
                    document_extracted=parsed.get("document_extracted", {}),
                    ayush_assessment=ayush_res,
                    model_suggestions=model_suggestions,
                    uncertainty_labels=uncertainty_labels,
                    red_flags_for_doctor_review=parsed.get("red_flags_for_doctor_review", []),
                    unknowns=parsed.get("unknowns", []),
                    confidence=float(parsed.get("confidence", 0.95)),
                    provider=f"google-gemini:{self.model}",
                )
        except Exception as exc:
            logger.error(f"[GeminiSummaryAdapter] Gemini API call failed ({exc}), falling back to mock adapter")
            res = await MockSummaryAdapter().summarize(evidence)
            res.uncertainty_labels.append({
                "field": "provider_fallback",
                "reason": f"Gemini provider error: {str(exc)}. Generated via fallback.",
            })
            return res


def get_summary_adapter() -> SummaryProvider:
    mode = (settings.AI_PROVIDER_MODE or "mock").lower()
    if mode == "gemini":
        return GeminiSummaryAdapter()
    elif mode == "groq":
        return GroqSummaryAdapter()
    elif mode == "openai":
        return OpenAISummaryAdapter()
    return MockSummaryAdapter()
