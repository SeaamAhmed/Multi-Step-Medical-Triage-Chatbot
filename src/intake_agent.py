# src/intake_agent.py
import json
import re
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

# ---- Estimating answers from the person's own words ----
# Checked from most to least serious: when two words fit, the higher score wins.
SEVERITY_WORDS = [
    (9, r"\bworst\b|unbearable|excruciating|agoni[sz]ing|can'?t (stand|bear|take) it"),
    (8, r"severe|very bad|really bad|terrible|awful|horrible|intense|extreme|strong pain"),
    (3, r"\bnot (that |too |so |very )?bad\b"),
    (6, r"\bbad\b|painful|hurts a lot"),
    (5, r"moderate|medium|manageable|tolerable"),
    (2, r"\bmild\b|slight|minor|barely hurts|a little (pain|ache)"),
]
NEGATED_SEVERE = (r"\bnot (that |too |so |very |really )?"
                  r"(severe|terrible|awful|horrible|unbearable|excruciating|intense|extreme)\b")
SEVERITY_SCORES = {"mild": 2, "moderate": 5, "severe": 8}

NOT_WORSE = r"\b(not|isn'?t|no)\b[^.!?]{0,12}\b(worse|worsen\w*|increas\w*|spread\w*)\b"
WORSE = (r"\b(worse|worsen\w*|increas\w*|more and more|stronger|spreading|intensif\w*|"
         r"escalat\w*|growing)\b")
NOT_BETTER = (r"\b(not|isn'?t|aren'?t|won'?t|doesn'?t|hasn'?t|never)\b[^.!?]{0,15}"
              r"\b(better|improv\w*|eas\w+|decreas\w*|reduc\w*|stop\w*|go(ing)? away|"
              r"fad\w*|subsid\w*|pass\w*|lessen\w*)\b")
SAME = (r"\b(same|unchanged|constant\w*|continuous\w*|persist\w*|still|no change|"
        r"steady|ongoing)\b")
BETTER = r"\b(better|improv\w*|easing|eased|subsiding|fading|decreas\w*|reduc\w*|less|lessen\w*|settling)\b"
PROGRESSION_TEXT = {"better": "getting better", "same": "staying the same",
                    "worse": "getting worse"}


def _score_from_text(text: str):
    """A 0-10 score from words like 'mild' or 'terrible', or None if unclear."""
    t = text.lower()
    if re.search(NEGATED_SEVERE, t):
        return None            # e.g. "not severe": unclear, so the bot asks
    for score, pattern in SEVERITY_WORDS:
        if re.search(pattern, t):
            return score
    return None


def _progression_from_text(text: str):
    """better / same / worse from the person's words, or None if unclear."""
    t = text.lower()
    not_worse = re.search(NOT_WORSE, t)
    t = re.sub(NOT_WORSE, " ", t)
    if re.search(WORSE, t):
        return "worse"         # when in doubt, take the more serious reading
    if not_worse or re.search(NOT_BETTER, t) or re.search(SAME, t):
        return "same"
    if re.search(BETTER, t):
        return "better"
    return None


def _mark(d: PatientIntake, field: str) -> None:
    if field not in d.inferred_fields:
        d.inferred_fields.append(field)


def _infer(d: PatientIntake, text: str) -> None:
    """Fill severity and progression from the person's words. Never overrides an answer."""
    if d.severity_score_0_10 is None:
        score = _score_from_text(text)
        if score is None and d.severity in SEVERITY_SCORES:
            score = SEVERITY_SCORES[d.severity]
        if score is not None:
            d.severity_score_0_10 = score
            _mark(d, "severity_score_0_10")
    if d.progression in (None, "unknown"):
        progression = _progression_from_text(text)
        if progression:
            d.progression = progression
            _mark(d, "progression")


def _inference_note(d: PatientIntake) -> str:
    """One sentence telling the person what we estimated."""
    bits = []
    if "severity_score_0_10" in d.inferred_fields:
        bits.append(f"{d.severity} (about {d.severity_score_0_10} out of 10)")
    if "progression" in d.inferred_fields and d.progression in PROGRESSION_TEXT:
        bits.append(PROGRESSION_TEXT[d.progression])
    if not bits:
        return ""
    return "From what you told me, I noted it as " + " and ".join(bits) + ". "

NEGATIVE = re.compile(
    r"^\s*(no|nope|nah|none|nothing|nil|n/?a|not really|no thanks|no thank you|"
    r"nothing else|none at all|no,? none|i don'?t have any|i have none)\s*[.!]*\s*$", re.I)
LIST_TOPICS = (   # (start of the topic text, the field that holds the answer)
    ("any other symptoms", "associated_symptoms"),
    ("any existing", "existing_conditions"),
    ("any medicines", "current_medications"),
    ("any allergies", "allergies"),
)
TOPIC_HINTS = (   # (start of the topic text, how to word the question)
    ("their sex", "Ask exactly: 'Are you male or female?' Do not mention any other options."),
    ("whether they could be pregnant",
     "Ask kindly: 'Could you be pregnant?' Do not ask about periods or dates."),
    ("how bad it is", "Ask: 'On a scale of 0 to 10, how bad is it?'"),
    ("when it started", "Ask: 'When did it start?'"),
)


def _clean_unknowns(d: PatientIntake) -> None:
    """'unknown' means not known yet, so the bot should still ask."""
    for field in ("sex", "severity", "progression"):
        if getattr(d, field) == "unknown":
            setattr(d, field, None)


def _apply_plain_no(d: PatientIntake, topic, text: str) -> None:
    """A plain 'no' to a list question means an empty list, whatever the model extracted."""
    if topic and NEGATIVE.match(text):
        for start, field in LIST_TOPICS:
            if topic.startswith(start) and getattr(d, field) is None:
                setattr(d, field, [])


def _style_note(topic, first_message: bool) -> str:
    note = ("The question itself must be one polite, friendly sentence of under 20 words. "
            "Never repeat a question the person already answered.")
    if first_message:
        note = ("This is the person's first message. Begin with ONE warm, comforting "
                "sentence that acknowledges what they told you (for example that you are "
                "sorry they feel this way and that you are here to help), then ask your "
                "question. ") + note
    for start, hint in TOPIC_HINTS:
        if topic and topic.startswith(start):
            note += " " + hint
    return note

def _parse_patient(response) -> PatientIntake:
    """Pull the JSON object out of the reply and validate it."""
    text = reply_text(response)
    start, end = text.find("{"), text.rfind("}")
    return PatientIntake.model_validate_json(text[start:end + 1])


def _merge(old: PatientIntake, new: PatientIntake) -> PatientIntake:
    """Keep earlier answers if the model forgets them (or says 'unknown') later."""
    merged = new.model_dump()
    for key, old_val in old.model_dump().items():
        if key == "intake_complete":
            continue
        new_val = merged[key]
        if new_val in (None, "unknown") and old_val not in (None, "unknown"):
            merged[key] = old_val
        elif new_val == [] and old_val not in (None, []):
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

        topic = _next_topic(self.data)      # what the bot's last question was about
        can_infer = topic is not None and not topic.startswith(
            ("any other symptoms", "any existing", "any medicines", "any allergies"))
        guessed = list(self.data.inferred_fields)
        old_score, old_progress = self.data.severity_score_0_10, self.data.progression

        # 1) update the JSON from the conversation so far
        try:
            resp = extract_llm.invoke(EXTRACTION_PROMPT.format(
                conversation=self._transcript(), schema=SCHEMA_TEXT))
            self.data = _merge(self.data, _parse_patient(resp))
        except Exception as e:
            logging.warning("Extraction failed, keeping previous data: %s", e)

        # An explicit new answer replaces an earlier estimate.
        if self.data.severity_score_0_10 != old_score and "severity_score_0_10" in guessed:
            guessed.remove("severity_score_0_10")
        if self.data.progression != old_progress and "progression" in guessed:
            guessed.remove("progression")
        self.data.inferred_fields = guessed

        # 2) clean up, and fill in what the person's own words already tell us
        _clean_unknowns(self.data)
        _apply_plain_no(self.data, topic, user_text)
        _infer(self.data, user_text if can_infer else "")
        _derive_severity(self.data)
        self.data.intake_complete = _is_complete(self.data)

        # 3) write the next friendly message
        if self.data.intake_complete:
            reply = ("Thank you, that's everything I need. "
                     "Let me look at this for you. Please wait a moment.")
        else:
            next_topic = _next_topic(self.data)
            first = sum(isinstance(m, HumanMessage) for m in self.history) == 1
            sys = (INTAKE_SYSTEM_PROMPT.format(next_topic=next_topic)
                   + "\n\n" + _style_note(next_topic, first))
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