# tests/test_intake_logic.py
from src.schemas import PatientIntake
from src.intake_agent import _next_topic, _is_complete, _merge


def _all_answered(**changes):
    data = dict(
        age=44, sex="male", chief_complaint="headache", symptoms=["headache"],
        onset="morning", severity_score_0_10=5, progression="same",
        associated_symptoms=[], existing_conditions=[],
        current_medications=[], allergies=[],
    )
    data.update(changes)
    return PatientIntake(**data)


def test_first_topic_is_the_main_problem():
    assert "main problem" in _next_topic(PatientIntake())


def test_complete_when_everything_answered():
    p = _all_answered()
    assert _next_topic(p) is None
    assert _is_complete(p)


def test_unanswered_medicines_blocks_completion():
    p = _all_answered(current_medications=None)
    assert not _is_complete(p)
    assert "medicines" in _next_topic(p)


def test_pregnancy_asked_for_women_of_childbearing_age():
    p = _all_answered(sex="female", age=30, pregnant=None)
    assert "pregnant" in _next_topic(p)


def test_merge_keeps_earlier_answers():
    old = PatientIntake(age=44, allergies=[])
    merged = _merge(old, PatientIntake())
    assert merged.age == 44
    assert merged.allergies == []