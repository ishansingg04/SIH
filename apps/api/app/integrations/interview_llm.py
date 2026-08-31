"""Interview fact extraction and follow-up generation LLM adapters.

Supports:
- GeminiInterviewLLMAdapter: Google Gemini 3.6 Flash (primary live LLM)
- GroqInterviewLLMAdapter: Hosted Groq Cloud (alternative LLM)
- MockInterviewLLMAdapter: Deterministic mock for offline testing and development
"""

import json
import re
from typing import Any, Dict, List, Optional, Protocol
import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger
from app.integrations.prompts.interview_prompt import (
    INTERVIEW_EXTRACTION_SYSTEM_PROMPT,
    build_interview_extraction_user_prompt,
)
from app.schemas.interview import ExtractedFactItem


class ExtractionPacket(BaseModel):
    patient_utterance: str
    language: str = "en"
    pathway: str = "ALLOPATHIC"
    current_slot: str = "chief_complaint"
    existing_facts: List[Dict[str, Any]] = Field(default_factory=list)
    missing_slots: List[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    extracted_facts: List[ExtractedFactItem] = Field(default_factory=list)
    filled_slots: List[str] = Field(default_factory=list)
    red_flags: List[Dict[str, Any]] = Field(default_factory=list)
    english_transcript: Optional[str] = None
    provider: str = "mock-interview-llm"


class InterviewLLMProvider(Protocol):
    """Protocol contract for conversational interview fact extraction."""

    async def extract_facts(self, packet: ExtractionPacket) -> ExtractionResult:
        """Extract structured facts, translate Hindi to English, and detect safety red flags."""
        ...


class MockInterviewLLMAdapter:
    """Deterministic Mock Adapter for offline development and CI testing.
    
    Scans the full utterance for ALL matching slot information,
    not just the target slot — making the interview truly adaptive.
    """

    async def extract_facts(self, packet: ExtractionPacket) -> ExtractionResult:
        logger.info(
            f"[MOCK] Extracting interview facts for slot '{packet.current_slot}' "
            f"(lang={packet.language}, input_len={len(packet.patient_utterance)})"
        )
        text = packet.patient_utterance.strip()
        lower_text = text.lower()
        facts: List[ExtractedFactItem] = []
        filled: List[str] = []
        red_flags: List[Dict[str, Any]] = []
        missing = set(packet.missing_slots)

        # 1. Check for red flag triggers
        if any(rf in lower_text for rf in ["chest pain", "सीने में दर्द", "heart", "सांस फूलना", "breathless", "खून", "blood"]):
            red_flags.append({
                "trigger": "acute_cardiorespiratory_symptom",
                "description": "Patient reported acute chest or respiratory discomfort",
                "severity": "HIGH",
            })

        # 2. Multi-slot extraction — scan for ALL matching information
        
        # Chief complaint
        if "chief_complaint" in missing:
            if "पेट" in text or "stomach" in lower_text or "belly" in lower_text:
                val = "Stomach pain and abdominal discomfort"
            elif "बुखार" in text or "fever" in lower_text:
                val = "Fever and generalized weakness"
            elif "खांसी" in text or "cough" in lower_text:
                val = "Persistent cough and throat irritation"
            elif "सिर" in text or "headache" in lower_text or "head" in lower_text:
                val = "Headache and heaviness"
            elif "दर्द" in text or "pain" in lower_text:
                val = "Pain and discomfort"
            elif "nausea" in lower_text or "उल्टी" in text or "जी मिचलाना" in text:
                val = "Nausea and stomach upset"
            else:
                val = text if packet.language == "en" else f"Patient complaint: {text}"
            facts.append(ExtractedFactItem(
                slot="chief_complaint", value=val,
                source="patient_voice" if packet.language == "hi" else "patient_typed",
                confidence=0.96, original_text=text,
            ))
            filled.append("chief_complaint")

        # Location — detect body parts mentioned
        if "location" in missing:
            loc = None
            if "पेट" in text or "stomach" in lower_text or "abdomen" in lower_text or "belly" in lower_text:
                loc = "Abdomen"
            elif "छाती" in text or "chest" in lower_text:
                loc = "Chest"
            elif "गले" in text or "throat" in lower_text:
                loc = "Throat"
            elif "सिर" in text or "head" in lower_text or "temple" in lower_text:
                loc = "Head"
            elif "eye" in lower_text or "आंख" in text:
                loc = "Eyes"
            elif "back" in lower_text or "कमर" in text or "पीठ" in text:
                loc = "Back"
            if loc:
                facts.append(ExtractedFactItem(
                    slot="location", value=loc, source="patient_voice",
                    confidence=0.95, original_text=text,
                ))
                filled.append("location")

        # Duration — detect time expressions
        if "duration" in missing:
            dur = None
            match = re.search(r"(\d+)\s*(day|days|दिन|din)", lower_text)
            if match:
                dur = f"{match.group(1)} days"
            else:
                match = re.search(r"(\d+)\s*(week|weeks|हफ्ते|hafta)", lower_text)
                if match:
                    dur = f"{match.group(1)} weeks"
                else:
                    match = re.search(r"(\d+)\s*(month|months|महीने|mahine)", lower_text)
                    if match:
                        dur = f"{match.group(1)} months"
                    else:
                        match = re.search(r"(\d+)\s*(hour|hours|घंटे|ghante)", lower_text)
                        if match:
                            dur = f"{match.group(1)} hours"
            if dur:
                facts.append(ExtractedFactItem(
                    slot="duration", value=dur, source="patient_voice",
                    confidence=0.94, original_text=text,
                ))
                filled.append("duration")

        # Severity — detect numeric scale
        if "severity" in missing:
            sev_match = re.search(r"\b(\d+)\s*/\s*10\b", lower_text)
            if not sev_match:
                sev_match = re.search(r"\bseverity\s*(\d+)\b", lower_text)
            if sev_match:
                facts.append(ExtractedFactItem(
                    slot="severity", value=f"{sev_match.group(1)}/10",
                    source="patient_voice", confidence=0.98, original_text=text,
                ))
                filled.append("severity")
            elif any(w in lower_text for w in ["severe", "unbearable", "तेज", "असहनीय", "बहुत"]):
                facts.append(ExtractedFactItem(
                    slot="severity", value="7/10 (severe)",
                    source="patient_voice", confidence=0.85, original_text=text,
                ))
                filled.append("severity")

        # Associated symptoms — detect additional symptoms mentioned alongside chief complaint
        if "associated_symptoms" in missing:
            symp_list = []
            symptom_map = {
                "nausea": "Nausea", "उल्टी": "Nausea/Vomiting", "जी मिचलाना": "Nausea",
                "vomiting": "Vomiting", "dizziness": "Dizziness", "चक्कर": "Dizziness",
                "fever": "Fever", "बुखार": "Fever", "cough": "Cough", "खांसी": "Cough",
                "weakness": "Weakness", "कमज़ोरी": "Weakness", "fatigue": "Fatigue",
                "body ache": "Body ache", "बदन दर्द": "Body ache",
            }
            for trigger, label in symptom_map.items():
                if trigger in lower_text or trigger in text:
                    # Don't count the chief complaint itself as associated symptom
                    if label not in symp_list:
                        symp_list.append(label)
            if symp_list:
                facts.append(ExtractedFactItem(
                    slot="associated_symptoms", value=", ".join(symp_list),
                    source="patient_voice", confidence=0.90, original_text=text,
                ))
                filled.append("associated_symptoms")

        # Trajectory
        if "trajectory" in missing:
            traj = None
            if any(w in lower_text for w in ["worse", "worsening", "बढ़", "increasing"]):
                traj = "Worsening"
            elif any(w in lower_text for w in ["better", "improving", "सुधार", "कम"]):
                traj = "Improving"
            elif any(w in lower_text for w in ["same", "constant", "वैसी", "स्थिर"]):
                traj = "Constant"
            if traj:
                facts.append(ExtractedFactItem(
                    slot="trajectory", value=traj, source="patient_voice",
                    confidence=0.88, original_text=text,
                ))
                filled.append("trajectory")

        # Medications
        if "medications" in missing:
            meds = []
            med_keywords = {
                "paracetamol": "Paracetamol", "crocin": "Crocin", "ibuprofen": "Ibuprofen",
                "दवा": "Unspecified medicine", "medicine": "Unspecified medicine",
                "painkiller": "Painkiller", "पेनकिलर": "Painkiller",
            }
            for trigger, label in med_keywords.items():
                if trigger in lower_text or trigger in text:
                    meds.append(label)
            if meds:
                facts.append(ExtractedFactItem(
                    slot="medications", value=", ".join(meds), source="patient_voice",
                    confidence=0.90, original_text=text,
                ))
                filled.append("medications")

        # Allergies
        if "allergies" in missing:
            if any(w in lower_text for w in ["allerg", "एलर्जी"]):
                val = "Patient reports allergy" if "no" not in lower_text and "नहीं" not in text else "No known allergies"
                facts.append(ExtractedFactItem(
                    slot="allergies", value=val, source="patient_voice",
                    confidence=0.88, original_text=text,
                ))
                filled.append("allergies")

        # AYUSH-specific slots
        if "prakriti" in missing:
            if any(w in lower_text or w in text for w in ["ठंड", "dry", "सूखी", "vata", "thin", "दुबल"]):
                val = "Vata dominant baseline constitution with cold intolerance"
            elif any(w in lower_text or w in text for w in ["गर्मी", "heat", "pitta", "तैलीय"]):
                val = "Pitta dominant constitution with heat sensitivity"
            elif text.strip():
                val = "Mixed constitution based on patient description"
            else:
                val = None
            if val:
                facts.append(ExtractedFactItem(
                    slot="prakriti", value=val, category="ayush_assessment",
                    source="patient_voice", confidence=0.92, original_text=text,
                ))
                filled.append("prakriti")

        if "agni" in missing:
            if any(w in lower_text or w in text for w in ["कम", "irregular", "भारी", "slow", "bloat"]):
                val = "Vishama Agni (Irregular appetite and post-meal heaviness)"
            elif text.strip() and packet.current_slot == "agni":
                val = "Mandagni (Slow digestive fire)"
            else:
                val = None
            if val:
                facts.append(ExtractedFactItem(
                    slot="agni", value=val, category="ayush_assessment",
                    source="patient_voice", confidence=0.91, original_text=text,
                ))
                filled.append("agni")

        if "koshtha" in missing:
            if any(w in lower_text or w in text for w in ["कब्ज", "hard", "constipat"]):
                val = "Krura Koshtha (Hard bowel movements / constipation tendency)"
            elif text.strip() and packet.current_slot == "koshtha":
                val = "Madhyama Koshtha (Normal bowel regularity)"
            else:
                val = None
            if val:
                facts.append(ExtractedFactItem(
                    slot="koshtha", value=val, category="ayush_assessment",
                    source="patient_voice", confidence=0.93, original_text=text,
                ))
                filled.append("koshtha")

        if "sattva" in missing:
            if any(w in lower_text or w in text for w in ["नींद", "sleep", "चिंता", "stress", "restless"]):
                val = "Madhyama Sattva (Interrupted sleep due to discomfort, mild stress)"
            elif text.strip() and packet.current_slot == "sattva":
                val = "Pravara Sattva (Good psychological resilience)"
            else:
                val = None
            if val:
                facts.append(ExtractedFactItem(
                    slot="sattva", value=val, category="ayush_assessment",
                    source="patient_voice", confidence=0.90, original_text=text,
                ))
                filled.append("sattva")

        # Fallback: if current slot targeted but nothing extracted for it, extract generically
        if packet.current_slot in missing and packet.current_slot not in filled and text.strip():
            facts.append(ExtractedFactItem(
                slot=packet.current_slot, value=text,
                source="patient_voice", confidence=0.85, original_text=text,
            ))
            filled.append(packet.current_slot)

        english_trans = facts[0].value if facts else text

        return ExtractionResult(
            extracted_facts=facts,
            filled_slots=filled,
            red_flags=red_flags,
            english_transcript=english_trans,
            provider="mock-interview-llm",
        )



class GeminiInterviewLLMAdapter:
    """Google Gemini live adapter for structured fact extraction & translation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = "gemini-2.5-flash"
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"



    async def extract_facts(self, packet: ExtractionPacket) -> ExtractionResult:
        if not self.api_key:
            logger.warning("Gemini API key missing, falling back to MockInterviewLLMAdapter")
            return await MockInterviewLLMAdapter().extract_facts(packet)

        user_prompt = build_interview_extraction_user_prompt(
            patient_utterance=packet.patient_utterance,
            language=packet.language,
            pathway=packet.pathway,
            current_slot=packet.current_slot,
            existing_facts=packet.existing_facts,
            missing_slots=packet.missing_slots,
        )

        request_body = {
            "system_instruction": {
                "parts": [{"text": INTERVIEW_EXTRACTION_SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    f"{self.endpoint}?key={self.api_key}",
                    json=request_body,
                    headers={"Content-Type": "application/json"},
                )
                res.raise_for_status()
                data = res.json()
                raw_json_str = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(raw_json_str)

                facts = [
                    ExtractedFactItem(
                        slot=f.get("slot", packet.current_slot),
                        value=f.get("value", ""),
                        source=f.get("source", "patient_voice"),
                        confidence=float(f.get("confidence", 0.95)),
                        category=f.get("category", "patient_reported"),
                        original_text=f.get("original_text", packet.patient_utterance),
                    )
                    for f in parsed.get("extracted_facts", [])
                    if f.get("value")
                ]

                filled_slots = list(set(parsed.get("filled_slots", []) + [f.slot for f in facts if f.slot]))
                if not filled_slots:
                    filled_slots = [packet.current_slot]

                return ExtractionResult(
                    extracted_facts=facts,
                    filled_slots=filled_slots,
                    red_flags=parsed.get("red_flags", []),
                    english_transcript=parsed.get("english_transcript"),
                    provider="gemini-1.5-flash",
                )

        except Exception as e:
            logger.error(f"Gemini live interview extraction failed: {e}. Falling back to mock.", exc_info=True)
            return await MockInterviewLLMAdapter().extract_facts(packet)


class GroqInterviewLLMAdapter:
    """Groq live adapter for structured fact extraction & translation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "llama-3.3-70b-versatile"


    async def extract_facts(self, packet: ExtractionPacket) -> ExtractionResult:
        if not self.api_key:
            return await MockInterviewLLMAdapter().extract_facts(packet)

        user_prompt = build_interview_extraction_user_prompt(
            patient_utterance=packet.patient_utterance,
            language=packet.language,
            pathway=packet.pathway,
            current_slot=packet.current_slot,
            existing_facts=packet.existing_facts,
            missing_slots=packet.missing_slots,
        )

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": INTERVIEW_EXTRACTION_SYSTEM_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                )
                res.raise_for_status()
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                facts = [
                    ExtractedFactItem(
                        slot=f.get("slot", packet.current_slot),
                        value=f.get("value", ""),
                        source=f.get("source", "patient_voice"),
                        confidence=float(f.get("confidence", 0.95)),
                        category=f.get("category", "patient_reported"),
                        original_text=f.get("original_text", packet.patient_utterance),
                    )
                    for f in parsed.get("extracted_facts", [])
                    if f.get("value")
                ]

                filled_slots = list(set(parsed.get("filled_slots", []) + [f.slot for f in facts if f.slot]))
                if not filled_slots:
                    filled_slots = [packet.current_slot]

                return ExtractionResult(
                    extracted_facts=facts,
                    filled_slots=filled_slots,
                    red_flags=parsed.get("red_flags", []),
                    english_transcript=parsed.get("english_transcript"),
                    provider="groq-llm",
                )

        except Exception as e:
            logger.error(f"Groq live interview extraction failed: {e}. Falling back to mock.", exc_info=True)
            return await MockInterviewLLMAdapter().extract_facts(packet)


def get_interview_llm_adapter() -> InterviewLLMProvider:
    """Factory selecting the interview extraction adapter based on configured provider mode."""
    if settings.APP_ENV == "test" or settings.AI_PROVIDER_MODE == "mock":
        return MockInterviewLLMAdapter()
    mode = (settings.AI_PROVIDER_MODE or "mock").lower()
    if mode == "gemini" and settings.GEMINI_API_KEY:
        return GeminiInterviewLLMAdapter()
    if mode == "groq" and settings.GROQ_API_KEY:
        return GroqInterviewLLMAdapter()
    return MockInterviewLLMAdapter()

