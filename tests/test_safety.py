# tests/test_safety.py
from src.safety import check_red_flags, check_crisis


def test_detects_chest_pain():
    assert check_red_flags("I have severe chest pain")


def test_detects_breathing():
    assert check_red_flags("I cannot breathe properly")


def test_curly_apostrophe():
    assert check_red_flags("I can\u2019t breathe")


def test_normal_text_ok():
    assert check_red_flags("I have a mild headache") == []


def test_no_false_alarm_on_shot_words():
    assert check_red_flags("I had a flu shot and my eyes are bloodshot") == []


def test_crisis_detected():
    assert check_crisis("I want to kill myself")


def test_crisis_is_separate_from_emergency():
    assert check_red_flags("I want to kill myself") == []