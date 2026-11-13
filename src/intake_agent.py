# src/intake_agent.py
import json
import logging
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.config import INTAKE_MODEL
from src.schemas import PatientIntake
from src.prompts import INTAKE_SYSTEM_PROMPT, EXTRACTION_PROMPT
from src.utils import reply_text

chat_llm = ChatGroq(model=INTAKE_MODEL, temperature=0.4, max_retries=6)
extract_llm = ChatGroq(
    model=INTAKE_MODEL,
    temperature=0,
    max_retries=6,
    model_kwargs={"response_format": {"type": "json_object"}},
)

SCHEMA_TEXT = (
    PatientIntake().model_dump_json()
    + "\nAllowed values: sex = male|female|other|unknown; "
      "severity = mild|moderate|severe|unknown; "
      "progression = better|same|worse|unknown. "
      "Lists hold short strings. Ages and scores are integers."
)

GREETING = ("Hello! I'm here to help you understand what to do about a health "
            "concern. What's bothering you today?")


def _parse_patient(response) -> PatientIntake:
    """Pull the JSON object out of the reply and validate it."""
    text = reply_text(response)
    start, end = text.find("{"), text.rfind("}")
    return PatientIntake.model_validate_json(text[start:end + 1])


def _merge(old: PatientIntake, new: PatientIntake) -> PatientIntake:
    """Keep earlier answers if the model forgets them in a later update."""
    merged = new.model_dump()
    for key, old_val in old.model_dump().items():
        if key == "intake_complete":
            continue
        if merged[key] is None and old_val is not None:
            merged[key] = old_val
        elif merged[key] == [] and old_val not in (None, []):
            merged[key] = old_val
    return PatientIntake(**merged)


def _next_topic(d: PatientIntake):
    """The next thing to ask about, or None when intake is finished."""
    if not d.chief_complaint:
        return "what is bothering them (their main problem)"
    if not d.symptoms:
        return "what symptoms they are feeling"
    if d.age is None:
        return "their age"
    if d.sex is None:
        return "their sex (male, female or other)"
    if d.sex == "female" and d.pregnant is None and 12 <= d.age <= 55:
        return "whether they could be pregnant"
    if not d.onset and not d.duration:
        return "when it started"
    if d.severity is None and d.severity_score_0_10 is None:
        return "how bad it is, on a scale of 0 to 10"
    if d.progression is None:
        return "whether it is getting better, staying the same or getting worse"
    if d.associated_symptoms is None:
        return "any other symptoms they have noticed"
    if d.existing_conditions is None:
        return "any existing health conditions"
    if d.current_medications is None:
        return "any medicines or supplements they take now"
    if d.allergies is None:
        return "any allergies"
    return None


def _is_complete(d: PatientIntake) -> bool:
    return _next_topic(d) is None


def _derive_severity(d: PatientIntake) -> None:
    """If we have a 0-10 score but no word, derive the word."""
    s = d.severity_score_0_10
    if d.severity in (None, "unknown") and s is not None:
        d.severity = "mild" if s <= 3 else "moderate" if s <= 6 else "severe"


class IntakeAgent:
    def __init__(self):
        self.history = [AIMessage(content=GREETING)]
        self.data = PatientIntake()

    def _transcript(self):
        return "\n".join(
            f"{'Assistant' if isinstance(m, AIMessage) else 'User'}: {m.content}"
            for m in self.history
        )

    def step(self, user_text: str) -> str:
        self.history.append(HumanMessage(content=user_text))

        # 1) update the JSON from the conversation so far
        try:
            resp = extract_llm.invoke(EXTRACTION_PROMPT.format(
                conversation=self._transcript(), schema=SCHEMA_TEXT))
            self.data = _merge(self.data, _parse_patient(resp))
        except Exception as e:
            logging.warning("Extraction failed, keeping previous data: %s", e)

        _derive_severity(self.data)
        self.data.intake_complete = _is_complete(self.data)

        # 2) write the next friendly message
        if self.data.intake_complete:
            reply = ("Thank you, that's everything I need. "
                     "Let me look at this for you. Please wait a moment.")
        else:
            sys = INTAKE_SYSTEM_PROMPT.format(next_topic=_next_topic(self.data))
            try:
                reply = reply_text(chat_llm.invoke([SystemMessage(content=sys), *self.history]))
            except Exception as e:
                logging.warning("Chat call failed: %s", e)
                self.history.pop()  # forget this message so the user can resend it
                return "Sorry, I had a short delay. Could you say that again?"

        self.history.append(AIMessage(content=reply))
        return reply


if __name__ == "__main__":
    from src.safety import check_red_flags, check_crisis, EMERGENCY_MSG, CRISIS_MSG

    agent = IntakeAgent()
    print("Bot:", GREETING)
    try:
        while not agent.data.intake_complete:
            msg = input("You: ")
            if msg.strip().lower() in ("quit", "exit"):
                break
            crisis = check_crisis(msg)
            if crisis:
                agent.data.red_flags_reported = crisis
                print("Bot:", CRISIS_MSG)
                break
            flags = check_red_flags(msg)
            if flags:
                agent.data.red_flags_reported = flags
                print("Bot:", EMERGENCY_MSG)
                break
            print("Bot:", agent.step(msg))
    except (KeyboardInterrupt, EOFError):
        print()
    print(agent.data.model_dump_json(indent=2))