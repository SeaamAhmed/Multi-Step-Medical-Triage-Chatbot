# tests/test_guidance_leaks.py
from src.guidance_agent import _leaks

CTX = ("Sumatriptan and ergotamine treat migraine. Acetaminophen relieves pain. "
       "Amoxicillin treats infection.")


def test_flags_prescription_drug_from_documents():
    assert "sumatriptan" in _leaks("You could take sumatriptan.", ["acetaminophen"], CTX, "{}")


def test_allowed_medicine_is_not_flagged():
    assert _leaks("Acetaminophen can help.", ["acetaminophen"], CTX, "{}") == []


def test_patients_own_medicine_is_not_flagged():
    patient_json = '{"current_medications": ["amoxicillin"]}'
    assert _leaks("You said you take amoxicillin.", [], CTX, patient_json) == []


def test_plain_advice_is_not_flagged():
    assert _leaks("Rest and drink water.", [], CTX, "{}") == []