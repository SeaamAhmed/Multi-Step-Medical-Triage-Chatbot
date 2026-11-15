from src.guidance_agent import is_dose_question, drop_allergens
from src.schemas import PatientIntake


def test_dose_questions_detected():
    assert is_dose_question("how many paracetamol should I take?")
    assert is_dose_question("what is the dose?")
    assert is_dose_question("how many times a day should I take it")


def test_normal_questions_not_dose_questions():
    assert not is_dose_question("how long until it gets better?")
    assert not is_dose_question("will it go away soon?")
    assert not is_dose_question("okay, thanks")


def test_drop_allergens():
    p = PatientIntake()
    p.allergies = ["paracetamol"]
    result = drop_allergens(["acetaminophen", "antacid"], p)
    assert "acetaminophen" not in result
    assert "antacid" in result