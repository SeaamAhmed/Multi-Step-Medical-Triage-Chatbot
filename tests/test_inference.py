from src.schemas import PatientIntake
from src.intake_agent import (_score_from_text, _progression_from_text, _infer,
                              _derive_severity, _next_topic, _inference_note, _merge, _apply_plain_no, _clean_unknowns, _style_note)


def test_severity_words():
    assert _score_from_text("I have a mild headache") == 2
    assert _score_from_text("it's a severe headache") == 8
    assert _score_from_text("the worst pain ever") == 9
    assert _score_from_text("it's not too bad") == 3
    assert _score_from_text("it's bad") == 6
    assert _score_from_text("moderate pain") == 5


def test_unclear_severity_is_not_guessed():
    assert _score_from_text("I have a headache") is None
    assert _score_from_text("it's not severe") is None


def test_higher_severity_wins():
    assert _score_from_text("mild but sometimes severe") == 8


def test_progression_phrases():
    assert _progression_from_text("the pain is not stopping") == "same"
    assert _progression_from_text("it's not decreasing") == "same"
    assert _progression_from_text("it keeps increasing") == "worse"
    assert _progression_from_text("it's getting worse") == "worse"
    assert _progression_from_text("it's not getting worse") == "same"
    assert _progression_from_text("it's getting better") == "better"
    assert _progression_from_text("it's not getting better") == "same"
    assert _progression_from_text("headache since morning") is None


def test_infer_fills_and_marks_guesses():
    d = PatientIntake()
    _infer(d, "I have a mild headache and it is not stopping")
    assert d.severity_score_0_10 == 2
    assert d.progression == "same"
    assert set(d.inferred_fields) == {"severity_score_0_10", "progression"}


def test_infer_never_overrides_an_explicit_answer():
    d = PatientIntake()
    d.severity_score_0_10 = 7
    d.progression = "better"
    _infer(d, "mild and getting worse")
    assert d.severity_score_0_10 == 7
    assert d.progression == "better"
    assert d.inferred_fields == []


def test_severity_word_gives_a_score_when_text_is_silent():
    d = PatientIntake()
    d.severity = "moderate"
    _infer(d, "")
    assert d.severity_score_0_10 == 5


def test_questions_are_skipped_after_inference():
    d = PatientIntake(chief_complaint="headache", symptoms=["headache"],
                      age=44, sex="male", onset="morning")
    _infer(d, "it's a mild headache and not stopping")
    _derive_severity(d)
    assert _next_topic(d) == "any other symptoms they have noticed"


def test_inference_note_wording():
    d = PatientIntake()
    d.severity = "mild"
    d.severity_score_0_10 = 2
    d.progression = "same"
    d.inferred_fields = ["severity_score_0_10", "progression"]
    note = _inference_note(d)
    assert "mild" in note and "staying the same" in note

def test_merge_keeps_real_value_when_model_says_unknown():
    old = PatientIntake()
    old.progression = "same"
    new = PatientIntake()
    new.progression = "unknown"
    assert _merge(old, new).progression == "same"


def test_unknown_becomes_not_asked():
    d = PatientIntake()
    d.progression = "unknown"
    d.sex = "unknown"
    _clean_unknowns(d)
    assert d.progression is None and d.sex is None


def test_plain_no_means_empty_list():
    d = PatientIntake()
    _apply_plain_no(d, "any other symptoms they have noticed", "No.")
    assert d.associated_symptoms == []
    _apply_plain_no(d, "any allergies", "none")
    assert d.allergies == []


def test_no_to_another_topic_is_not_applied():
    d = PatientIntake()
    _apply_plain_no(d, "when it started", "no")
    assert d.associated_symptoms is None


def test_first_message_gets_a_warm_opening():
    assert "warm" in _style_note("their age", True)
    assert "warm" not in _style_note("their age", False)


def test_sex_question_is_simple():
    assert "male or female" in _style_note("their sex (male, female or other)", False)