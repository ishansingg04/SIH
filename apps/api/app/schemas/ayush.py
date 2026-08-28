from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import AgniType, KoshthaType, PrakritiDosha, SattvaType


class PrakritiSchema(BaseModel):
    """AYUSH - Prakriti: Patient constitution and dosha assessment."""

    model_config = ConfigDict(from_attributes=True)

    primary_dosha: Optional[PrakritiDosha] = Field(None, description="Dominant constitutional dosha")
    secondary_dosha: Optional[PrakritiDosha] = Field(None, description="Secondary constitutional dosha")
    patient_observations: Optional[str] = Field(None, description="Patient-reported physical and physiological traits")
    clinician_notes: Optional[str] = Field(None, description="Clinician constitutional evaluation notes")


class VikritiSchema(BaseModel):
    """AYUSH - Vikriti: Current state of dosha imbalance and symptom patterns."""

    model_config = ConfigDict(from_attributes=True)

    aggravated_doshas: List[PrakritiDosha] = Field(default_factory=list, description="Doshas currently aggravated")
    symptom_pattern: str = Field(..., description="Current imbalance and symptom progression pattern")
    onset_factors: Optional[str] = Field(None, description="Reported triggers or dietary/seasonal factors")


class AgniSchema(BaseModel):
    """AYUSH - Agni: Digestive and metabolic capacity evaluation."""

    model_config = ConfigDict(from_attributes=True)

    agni_type: AgniType = Field(AgniType.SAMA, description="Digestive fire state: Manda, Tikshna, Vishama, Sama")
    appetite_level: Optional[str] = Field(None, description="Appetite level (e.g., poor, normal, excessive, irregular)")
    digestion_speed_hours: Optional[float] = Field(None, description="Typical post-meal digestion duration")
    patient_description: Optional[str] = Field(None, description="Patient wording regarding digestion and hunger")


class KoshthaSchema(BaseModel):
    """AYUSH - Koshtha: Bowel patterns and alimentary canal motility."""

    model_config = ConfigDict(from_attributes=True)

    koshtha_type: KoshthaType = Field(KoshthaType.MADHYAMA, description="Gut motility: Krura (hard), Mridu (soft), Madhyama")
    bowel_regularity: Optional[str] = Field(None, description="Frequency and regularity of bowel movements")
    laxative_dependency: bool = Field(default=False, description="Whether laxatives or external aids are used")
    patient_notes: Optional[str] = Field(None, description="Patient-reported digestive comfort")


class SattvaSchema(BaseModel):
    """AYUSH - Sattva: Mental resilience, temperament, sleep, and emotional wellbeing."""

    model_config = ConfigDict(from_attributes=True)

    sattva_type: SattvaType = Field(SattvaType.MADHYAMA, description="Mental strength: Pravara (high), Madhyama, Avara (low)")
    sleep_quality: Optional[str] = Field(None, description="Sleep duration, continuity, and restfulness")
    stress_level: Optional[str] = Field(None, description="Reported stress or anxiety prompts (low, medium, high)")
    wellbeing_prompts: Optional[str] = Field(None, description="Patient-reported emotional state and resilience notes")


class DashavidhaParikshaBundle(BaseModel):
    """Complete AYUSH Dashavidha Pariksha Intake Bundle."""

    model_config = ConfigDict(from_attributes=True)

    prakriti: Optional[PrakritiSchema] = Field(None, description="AYUSH - Prakriti evaluation")
    vikriti: Optional[VikritiSchema] = Field(None, description="AYUSH - Vikriti evaluation")
    agni: Optional[AgniSchema] = Field(None, description="AYUSH - Agni evaluation")
    koshtha: Optional[KoshthaSchema] = Field(None, description="AYUSH - Koshtha evaluation")
    sattva: Optional[SattvaSchema] = Field(None, description="AYUSH - Sattva evaluation")
    ayush_notes: Optional[str] = Field(None, description="General AYUSH clinician observations")
