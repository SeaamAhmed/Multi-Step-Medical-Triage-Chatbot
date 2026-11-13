# src/safety.py
import re

# Phrases that mean "stop and get emergency help now".
# Based on the IITT red flags (pages 1-3) and ESI Level 1 and 2 (pages 11, 13),
# written in the everyday words a patient would actually type.
RED_FLAGS = [
    # consciousness and brain
    "unresponsive", "unconscious", "passed out", "fainted",
    "won't wake up", "not waking up", "seizure", "convulsion",
    "face drooping", "slurred speech", "having a stroke", "signs of a stroke",
    # breathing
    "can't breathe", "cannot breathe", "trouble breathing",
    "difficulty breathing", "struggling to breathe", "gasping", "choking",
    "blue lips", "turning blue", "whistling sound when breathing",
    # bleeding
    "heavy bleeding", "bleeding heavily", "won't stop bleeding",
    "coughing blood", "coughing up blood", "vomiting blood",
    # chest
    "chest pain", "chest tightness", "crushing chest",
    # allergy
    "throat is closing", "throat swelling", "severe allergic reaction", "anaphylaxis",
    # poisoning, bites, trauma
    "overdose", "poisoning", "swallowed poison", "snake bite", "snakebite",
    "gunshot", "been shot", "got shot", "stabbed", "hit by a car", "car accident",
    # other
    "low blood sugar", "hypoglyc", "painful erection", "testicular pain",
]

# Different reply: the person needs support, not just an ambulance.
CRISIS_FLAGS = [
    "suicide", "suicidal", "kill myself", "want to die", "end my life",
    "hurt myself", "self-harm", "self harm",
    "kill someone", "kill him", "kill her", "kill them",
]

EMERGENCY_MSG = ("This may be an emergency. Please call your local emergency "
                 "number or go to the nearest hospital right now. If someone "
                 "is with you, ask them to help.")

CRISIS_MSG = ("I'm really sorry you're going through this, and I'm glad you told me. "
              "You deserve support right now. Please contact your local emergency "
              "number or a crisis line in your country, or tell someone you trust "
              "and stay with them. If you are in immediate danger, call emergency "
              "services now.")


def _normalize(text: str) -> str:
    t = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    return re.sub(r"\s+", " ", t)


def _compile(phrases):
    # \b = start of a word, so "shot" cannot match inside "bloodshot"
    return [(p, re.compile(r"\b" + re.escape(p))) for p in phrases]


_RED = _compile(RED_FLAGS)
_CRISIS = _compile(CRISIS_FLAGS)


def _find(text: str, patterns):
    t = _normalize(text)
    return [p for p, rx in patterns if rx.search(t)]


def check_red_flags(text: str):
    return _find(text, _RED)


def check_crisis(text: str):
    return _find(text, _CRISIS)