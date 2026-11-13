# src/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

NOT_ASKED = "null = not asked yet; empty list = person said none"


class PatientIntake(BaseModel):
    age: Optional[int] = Field(None, description="Age in years")
    sex: Optional[Literal["male", "female", "other", "unknown"]] = None
    pregnant: Optional[bool] = None
    chief_complaint: Optional[str] = Field(None, description="Main problem, in user's words")
    symptoms: List[str] = []
    onset: Optional[str] = Field(None, description="When it started")
    duration: Optional[str] = None
    severity: Optional[Literal["mild", "moderate", "severe", "unknown"]] = None
    severity_score_0_10: Optional[int] = None
    progression: Optional[Literal["better", "same", "worse", "unknown"]] = None
    associated_symptoms: Optional[List[str]] = Field(None, description=NOT_ASKED)
    existing_conditions: Optional[List[str]] = Field(None, description=NOT_ASKED)
    current_medications: Optional[List[str]] = Field(None, description=NOT_ASKED)
    allergies: Optional[List[str]] = Field(None, description=NOT_ASKED)
    red_flags_reported: List[str] = []
    intake_complete: bool = False