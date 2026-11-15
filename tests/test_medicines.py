# tests/test_medicines.py
from src.schemas import PatientIntake
from src.medicines import allowed_medicines

CTX = ("Acetaminophen and ibuprofen relieve headache. An antacid helps "
       "heartburn. Sumatriptan treats migraine.")


def patient(**changes):
    data = dict(age=44, sex="male", existing_conditions=[],
                current_medications=[], allergies=[])
    data.update(changes)
    return PatientIntake(**data)


def test_names_only_listed_medicines_found_in_documents():
    names = allowed_medicines(patient(), CTX)
    assert set(names) == {"acetaminophen", "ibuprofen", "antacid"}


def test_prescription_drug_never_allowed():
    assert "sumatriptan" not in allowed_medicines(patient(), CTX)


def test_medicine_not_in_documents_is_not_allowed():
    assert allowed_medicines(patient(), "Sumatriptan treats migraine.") == []


def test_unknown_age_or_child_gets_nothing():
    assert allowed_medicines(patient(age=None), CTX) == []
    assert allowed_medicines(patient(age=8), CTX) == []


def test_unanswered_safety_questions_block_everything():
    assert allowed_medicines(patient(allergies=None), CTX) == []


def test_high_blood_pressure_blocks_ibuprofen():
    names = allowed_medicines(patient(existing_conditions=["high blood pressure"]), CTX)
    assert "ibuprofen" not in names
    assert "acetaminophen" in names


def test_elderly_do_not_get_ibuprofen():
    assert "ibuprofen" not in allowed_medicines(patient(age=79), CTX)


def test_aspirin_allergy_blocks_ibuprofen():
    names = allowed_medicines(patient(allergies=["aspirin"]), CTX)
    assert "ibuprofen" not in names
    assert "acetaminophen" in names


def test_pregnancy_blocks_ibuprofen():
    names = allowed_medicines(patient(sex="female", pregnant=True), CTX)
    assert "ibuprofen" not in names


def test_already_taking_paracetamol_is_not_repeated():
    names = allowed_medicines(patient(current_medications=["paracetamol"]), CTX)
    assert "acetaminophen" not in names