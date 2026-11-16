# src/guidance_agent.py
import re
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from src.config import MAIN_MODEL, DISCLAIMER
from src.prompts import GUIDANCE_PROMPT, FOLLOWUP_PROMPT
from src.schemas import PatientIntake
from src.medicines import ALLOWED, allowed_medicines
from src.utils import reply_text
from src.medicine_search import medicine_docs, search_docs

llm = ChatGoogleGenerativeAI(model=MAIN_MODEL, temperature=0.2, timeout=120, max_retries=2)
chain = ChatPromptTemplate.from_template(GUIDANCE_PROMPT) | llm

followup_chain = ChatPromptTemplate.from_template(FOLLOWUP_PROMPT) | llm

DOSE_MSG = ("I can't give doses, because the right amount depends on the product and "
            "the person. Please follow the instructions on the package label, or ask a "
            "pharmacist or doctor before taking it.")
DOSE_QUESTION_RE = re.compile(
    r"\b(doses?|dosage|dosing|mg|milligrams?)\b"
    r"|\bhow (much|many|often|frequently)\b.*\b(take|taking|tablets?|pills?|capsules?|"
    r"paracetamol|acetaminophen|ibuprofen|medicines?|medications?)\b", re.I)
DOSE_IN_REPLY_RE = re.compile(
    r"\d+(\.\d+)?\s*(mg|milligrams?|ml|g|grams?|tablets?|pills?|capsules?)\b", re.I)


def is_dose_question(message: str) -> bool:
    return bool(DOSE_QUESTION_RE.search(message))


def _unique(docs):
    seen, out = set(), []
    for d in docs:
        key = (d.metadata.get("source_name"), d.metadata.get("page_number"),
               d.page_content[:80])
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out


def drop_allergens(allowed, patient):
    """Remove any allowed medicine the patient has said they are allergic to."""
    allergies = " ".join(patient.allergies or []).lower()
    return [n for n in allowed
            if not any(a in allergies for a in ALLOWED[n]["aliases"])]

NO_CONTEXT_MSG = ("I could not find enough information in my reference documents "
                  "about this. Please speak to a doctor or visit a clinic.")
ERROR_MSG = ("Sorry, I could not prepare guidance right now. Please try again in a "
             "moment. If you feel unwell, please speak to a doctor or visit a clinic.")
MEDICINE_FALLBACK = ("I can share general information, but I can't safely name "
                     "medicines here. Please ask a doctor or pharmacist which medicine "
                     "is right for you. If your symptoms get worse, or you feel very "
                     "unwell, please go to a hospital or call emergency services.")

# Word endings typical of prescription drug names (heuristic safety net)
DRUG_ENDINGS = ("cillin", "triptan", "mycin", "cycline", "floxacin", "azole",
                "statin", "sartan", "olol", "oxetine", "zepam", "codone", "morphine")


def _fmt(docs):
    return "\n\n".join(
        f"[{d.metadata.get('source_name', '?')} p.{d.metadata.get('page_number', '?')}] "
        f"{d.page_content}"
        for d in docs
    )


def _leaks(reply: str, allowed: list, context: str, patient_json: str) -> list:
    """Drug-like words in the reply that come from the documents but are not allowed."""
    ok = {a for name in allowed for a in ALLOWED[name]["aliases"]}
    ok |= set(re.findall(r"[a-z]+", patient_json.lower()))  # the patient's own words
    in_docs = set(re.findall(r"[a-z]+", context.lower()))
    words = set(re.findall(r"[a-z]+", reply.lower()))
    return sorted(w for w in words if w in in_docs and w.endswith(DRUG_ENDINGS) and w not in ok)


def answer(patient: PatientIntake, triage_docs, medical_docs) -> str:
    medical_docs = list(medical_docs) + medicine_docs(patient)
    if not triage_docs and not medical_docs:
        return NO_CONTEXT_MSG + DISCLAIMER

    triage_ctx, medical_ctx = _fmt(triage_docs), _fmt(medical_docs)
    context = triage_ctx + "\n" + medical_ctx
    allowed = drop_allergens(allowed_medicines(patient, context), patient)
    patient_json = patient.model_dump_json()

    inputs = {
        "age": patient.age if patient.age is not None else "unknown",
        "patient_json": patient_json,
        "allowed_medicines": ", ".join(ALLOWED[n]["display"] for n in allowed) or "none",
        "triage_context": triage_ctx or "(none found)",
        "medical_context": medical_ctx or "(none found)",
    }

    try:
        reply = reply_text(chain.invoke(inputs))
        bad = _leaks(reply, allowed, context, patient_json)
        if bad:
            logging.warning("Reply named medicines that are not allowed: %s", bad)
            inputs["allowed_medicines"] += " | NEVER mention: " + ", ".join(bad)
            reply = reply_text(chain.invoke(inputs))
            if _leaks(reply, allowed, context, patient_json):
                reply = MEDICINE_FALLBACK
    except Exception as e:
        logging.warning("Guidance call failed: %s", e)
        return ERROR_MSG

    return reply + DISCLAIMER

def follow_up(patient, guidance, history, message, triage_docs, medical_docs) -> str:
    """Conversational reply after the guidance has been given."""
    medical_docs = _unique(list(medical_docs) + medicine_docs(patient) + search_docs(message))
    triage_ctx, medical_ctx = _fmt(triage_docs), _fmt(medical_docs)
    context = triage_ctx + "\n" + medical_ctx
    allowed = drop_allergens(allowed_medicines(patient, context), patient)
    patient_json = patient.model_dump_json()

    inputs = {
        "age": patient.age if patient.age is not None else "unknown",
        "patient_json": patient_json,
        "allowed_medicines": ", ".join(ALLOWED[n]["display"] for n in allowed) or "none",
        "guidance": guidance,
        "history": "\n".join(history) or "(none yet)",
        "triage_context": triage_ctx or "(none found)",
        "medical_context": medical_ctx or "(none found)",
        "message": message,
    }

    try:
        reply = reply_text(followup_chain.invoke(inputs))
        bad = _leaks(reply, allowed, context, patient_json)
        if bad or DOSE_IN_REPLY_RE.search(reply):
            logging.warning("Follow-up reply broke a rule: %s", bad)
            inputs["allowed_medicines"] += " | NEVER mention: " + ", ".join(bad) if bad else ""
            inputs["message"] = message + "\n(Do not mention any amounts, mg or tablet counts.)"
            reply = reply_text(followup_chain.invoke(inputs))
            if _leaks(reply, allowed, context, patient_json):
                return MEDICINE_FALLBACK
            if DOSE_IN_REPLY_RE.search(reply):
                return DOSE_MSG
    except Exception as e:
        logging.warning("Follow-up call failed: %s", e)
        return ERROR_MSG
    return reply

if __name__ == "__main__":
    from src.retriever import retrieve

    p = PatientIntake(
        age=44, sex="male", chief_complaint="headache", symptoms=["headache"],
        onset="morning", duration="since morning", severity="moderate",
        severity_score_0_10=5, progression="same", associated_symptoms=[],
        existing_conditions=[], current_medications=[], allergies=[],
        intake_complete=True)
    triage, medical = retrieve(p)
    print(answer(p, triage, medical))