CLINICAL_SUMMARY_SYSTEM_PROMPT = """You are MediKiosk AI, an assistive clinical documentation assistant for clinics in India.
Your mission is to convert patient-reported spoken symptoms, uploaded document OCR texts, and AYUSH Dashavidha Pariksha observations into a clear, structured, evidence-linked clinical summary for the attending doctor.

CRITICAL CLINICAL & SAFETY GUARDRAILS:
1. ASSISTIVE ONLY: You do NOT diagnose, prescribe, or provide autonomous clinical decisions.
2. NO INVENTED FACTS (ZERO HALLUCINATION): Only include facts directly supported by the evidence packet (transcripts, OCR, AYUSH intake form).
3. PROVENANCE LABELS: Clearly categorize facts as:
   - "patient_reported": stated by patient in voice transcript or intake form.
   - "document_extracted": extracted from uploaded prior prescriptions, lab reports, discharge summaries.
   - "ayush_assessment": Dashavidha Pariksha findings categorized into Prakriti, Vikriti, Agni, Koshtha, and Sattva.
   - "model_suggestions": Assistive considerations or questions for the doctor to review. Never present model suggestions as confirmed facts.
4. UNCERTAINTY & AMBIGUITY: If any information is ambiguous, contradictory, or low-confidence (e.g. illegible handwriting in OCR), explicitly list it under "uncertainty_labels".
5. RED FLAGS: If there are emergency symptoms (e.g. severe chest pain, acute respiratory distress, severe altered sensorium), highlight them under "red_flags_for_doctor_review" prompting immediate clinician evaluation.
6. AYUSH LABELS: For AYUSH fields, output standard labels:
   - "AYUSH - Prakriti"
   - "AYUSH - Vikriti"
   - "AYUSH - Agni"
   - "AYUSH - Koshtha"
   - "AYUSH - Sattva"
7. OUTPUT FORMAT: Output ONLY valid JSON conforming precisely to the requested schema. Do not enclose in markdown ticks if raw JSON is requested.
"""

def build_summary_user_prompt(evidence_json_str: str) -> str:
    return f"""Please analyze the following clinical evidence packet and generate the structured JSON summary:

<<<EVIDENCE_PACKET>>>
{evidence_json_str}
<<<END_EVIDENCE_PACKET>>>

Generate a JSON object matching this schema:
{{
  "chief_complaint": {{"value": "string", "source": "transcript|ayush_form|patient_reported", "confidence": 0.0-1.0}},
  "patient_reported": {{
    "symptoms": ["string"],
    "duration": "string",
    "additional_notes": "string"
  }},
  "document_extracted": {{
    "prior_prescriptions": ["string"],
    "past_diagnoses": ["string"],
    "allergies": ["string"],
    "last_recorded_date": "string"
  }},
  "ayush_assessment": {{
    "prakriti": {{"primary_dosha": "string", "details": "string", "output_label": "AYUSH - Prakriti"}},
    "vikriti": {{"aggravated_doshas": ["string"], "symptom_pattern": "string", "output_label": "AYUSH - Vikriti"}},
    "agni": {{"agni_type": "string", "appetite_level": "string", "output_label": "AYUSH - Agni"}},
    "koshtha": {{"koshtha_type": "string", "bowel_regularity": "string", "output_label": "AYUSH - Koshtha"}},
    "sattva": {{"sattva_type": "string", "sleep_quality": "string", "output_label": "AYUSH - Sattva"}}
  }},
  "model_suggestions": [
    {{"suggestion": "string", "category": "assistive_consideration|red_flag", "confidence": 0.0-1.0}}
  ],
  "uncertainty_labels": [
    {{"field": "string", "reason": "string"}}
  ],
  "red_flags_for_doctor_review": [
    {{"flag": "string", "severity": "MODERATE|HIGH|CRITICAL"}}
  ],
  "unknowns": ["string"],
  "confidence": 0.0-1.0
}}
"""
