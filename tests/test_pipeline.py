# tests/test_pipeline.py
from src import pipeline
from src.pipeline import ChatSession


def _session():
    s = ChatSession()
    s.agent.step = lambda m: (_ for _ in ()).throw(AssertionError("intake must not run"))
    return s


def test_red_flag_stops_before_intake():
    r = _session().send("I have severe chest pain and cannot breathe")
    assert r["stage"] == "emergency"


def test_crisis_stops_before_intake():
    r = _session().send("I want to kill myself")
    assert r["stage"] == "crisis"


def test_normal_flow_gives_guidance(monkeypatch):
    monkeypatch.setattr(pipeline, "retrieve", lambda p: ([], []))
    monkeypatch.setattr(pipeline, "answer", lambda p, t, m: "GUIDANCE")
    s = ChatSession()

    def fake_step(msg):
        s.patient.intake_complete = True
        return "Thanks."
    s.agent.step = fake_step

    r = s.send("I have a mild headache")
    assert r["stage"] == "followup"
    assert "GUIDANCE" in r["reply"]


def test_empty_message_is_ignored():
    r = _session().send("   ")
    assert r["stage"] == "intake"

def test_followup_gets_a_conversational_reply(monkeypatch):
    monkeypatch.setattr(pipeline, "follow_up", lambda *a, **k: "FOLLOW")
    s = _session()
    s.stage = "followup"
    r = s.send("will it go away soon?")
    assert r["reply"] == "FOLLOW"
    assert r["stage"] == "followup"


def test_dose_question_in_followup_never_reaches_the_model(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("model must not be called for dose questions")
    monkeypatch.setattr(pipeline, "follow_up", boom)
    s = _session()
    s.stage = "followup"
    r = s.send("how many paracetamol should I take?")
    assert "package label" in r["reply"]


def test_new_red_flag_in_followup_triggers_emergency():
    s = _session()
    s.stage = "followup"
    r = s.send("now I have severe chest pain and cannot breathe")
    assert r["stage"] == "emergency"

def test_allergy_in_followup_is_recorded(monkeypatch):
    monkeypatch.setattr(pipeline, "follow_up", lambda *a, **k: "OK")
    s = _session()
    s.stage = "followup"
    s.patient.allergies = []
    s.send("actually I'm allergic to paracetamol")
    assert any(w in " ".join(s.patient.allergies) for w in ("paracetamol", "acetaminophen"))

def test_failed_guidance_can_be_retried(monkeypatch):
    calls = {"n": 0}

    def flaky(p, t, m):
        calls["n"] += 1
        return pipeline.ERROR_MSG if calls["n"] == 1 else "GUIDANCE"

    monkeypatch.setattr(pipeline, "retrieve", lambda p: ([], []))
    monkeypatch.setattr(pipeline, "answer", flaky)
    s = ChatSession()

    def fake_step(msg):
        s.patient.intake_complete = True
        return "Thanks."
    s.agent.step = fake_step

    assert s.send("headache")["stage"] == "retry"
    r = s.send("ok")
    assert r["stage"] == "followup"
    assert "GUIDANCE" in r["reply"]