# try_persona.py - runs the guidance for a ready-made patient (1 Gemini request each)
import sys
from src.schemas import PatientIntake
from src.retriever import retrieve
from src.guidance_agent import answer

BASE = dict(symptoms=["headache"], chief_complaint="headache", onset="this morning",
            severity="moderate", severity_score_0_10=5, progression="same",
            associated_symptoms=[], existing_conditions=[], current_medications=[],
            allergies=[], intake_complete=True)
PERSONAS = {
    "pregnant": dict(BASE, age=28, sex="female", pregnant=True),
    "warfarin": dict(BASE, age=70, sex="male", current_medications=["warfarin"],
                     existing_conditions=["heart problem"]),
    "adult": dict(BASE, age=44, sex="male"),
    "child": dict(BASE, age=8, sex="male", chief_complaint="cough",
                  symptoms=["cough", "sore throat"], severity="mild",
                  severity_score_0_10=2),
}
name = sys.argv[1] if len(sys.argv) > 1 else "pregnant"
p = PatientIntake(**PERSONAS[name])
triage, medical = retrieve(p)
print(answer(p, triage, medical))