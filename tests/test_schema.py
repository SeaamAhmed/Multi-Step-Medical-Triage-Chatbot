# tests/test_schema.py
from src.schemas import PatientIntake


def test_empty_intake_valid():
    p = PatientIntake()
    assert p.intake_complete is False
    assert p.symptoms == []


def test_filled_intake():
    p = PatientIntake(age=15, symptoms=["fever"], severity="mild")
    assert p.age == 15


def test_not_asked_is_none_but_none_answer_is_empty_list():
    assert PatientIntake().allergies is None
    assert PatientIntake(allergies=[]).allergies == []