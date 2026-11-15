# src/medicines.py
"""Medicine safety: the CODE decides which medicines may be named.
The model only words the advice. STARTING LIST - must be reviewed by a
qualified person before real use."""
from src.schemas import PatientIntake

ALLOWED = {
    "acetaminophen": {
        "display": "acetaminophen (also called paracetamol)",
        "aliases": ["acetaminophen", "paracetamol"],
        "min_age": 12, "max_age": 120,
        "avoid_conditions": ["liver", "alcohol"],
        "avoid_allergies": ["acetaminophen", "paracetamol"],
        "avoid_pregnant": False,
    },
    "ibuprofen": {
        "display": "ibuprofen",
        "aliases": ["ibuprofen"],
        "min_age": 12, "max_age": 64,
        "avoid_conditions": ["ulcer", "kidney", "asthma", "heart", "bleeding",
                             "blood pressure", "hypertension", "gastritis", "stomach"],
        "avoid_allergies": ["ibuprofen", "aspirin", "nsaid", "naproxen",
                            "anti-inflammatory"],
        "avoid_with": ["aspirin", "naproxen", "warfarin", "blood thinner", "nsaid"],
        "avoid_pregnant": True,
    },
    "antacid": {
        "display": "an antacid",
        "aliases": ["antacid"],
        "min_age": 12, "max_age": 120,
        "avoid_conditions": ["kidney"],
        "avoid_allergies": [],
        "avoid_pregnant": False,
    },
    "cetirizine": {
        "display": "cetirizine",
        "aliases": ["cetirizine"],
        "min_age": 12, "max_age": 120,
        "avoid_conditions": ["kidney", "liver"],
        "avoid_allergies": ["cetirizine", "hydroxyzine", "antihistamine"],
        "avoid_pregnant": True,
    },
}


def _mentions(items, words) -> bool:
    text = " ".join(items or []).lower()
    return any(w in text for w in words)


def allowed_medicines(p: PatientIntake, context: str) -> list:
    """Medicines the bot may name: on the list, found in the documents,
    and safe for this patient. An empty list means name no medicine."""
    # unanswered safety questions -> name nothing
    if (p.age is None or p.existing_conditions is None
            or p.current_medications is None or p.allergies is None):
        return []

    ctx = context.lower()
    result = []
    for name, rule in ALLOWED.items():
        if not any(a in ctx for a in rule["aliases"]):
            continue  # not in the retrieved documents
        if not (rule["min_age"] <= p.age <= rule["max_age"]):
            continue
        if rule["avoid_pregnant"] and p.pregnant:
            continue
        if _mentions(p.existing_conditions, rule["avoid_conditions"]):
            continue
        if _mentions(p.allergies, rule["avoid_allergies"]):
            continue
        taking = rule["aliases"] + rule.get("avoid_with", [])
        if _mentions(p.current_medications, taking):
            continue  # already taking it, or a risky combination
        result.append(name)
    return result