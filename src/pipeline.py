# src/pipeline.py
"""One chat session: safety gate first, then intake, then guidance, then conversation."""
import re

from src.intake_agent import IntakeAgent, GREETING
from src.safety import check_red_flags, check_crisis, EMERGENCY_MSG, CRISIS_MSG
from src.retriever import retrieve
from src.medicines import ALLOWED
from src.guidance_agent import answer, follow_up, is_dose_question, DOSE_MSG, ERROR_MSG

INVITE = "\n\nIf you have any questions about this, feel free to ask me."
ALLERGY_RE = re.compile(r"allerg|reaction to|can'?t take|cannot take", re.I)


class ChatSession:
    def __init__(self):
        self.agent = IntakeAgent()
        self.stage = "intake"   # intake | followup | emergency | crisis
        self.guidance = ""
        self.triage, self.medical = [], []
        self.history = []

    @property
    def greeting(self) -> str:
        return GREETING

    @property
    def patient(self):
        return self.agent.data

    def _out(self, reply: str) -> dict:
        return {"reply": reply, "stage": self.stage,
                "patient": self.patient.model_dump()}

    def _guidance(self) -> str:
        try:
            self.triage, self.medical = retrieve(self.patient)
            self.guidance = answer(self.patient, self.triage, self.medical)
            return self.guidance + INVITE
        except Exception:
            self.guidance = ERROR_MSG
            return ERROR_MSG

    def _note_new_info(self, message: str):
        """Save a newly mentioned medicine allergy so the allow-list respects it."""
        if ALLERGY_RE.search(message):
            text = message.lower()
            found = [a for info in ALLOWED.values() for a in info["aliases"] if a in text]
            if found:
                self.patient.allergies = list(self.patient.allergies or []) + found

    def _followup(self, message: str) -> str:
        self._note_new_info(message)
        if is_dose_question(message):
            reply = DOSE_MSG
        else:
            reply = follow_up(self.patient, self.guidance, self.history,
                              message, self.triage, self.medical)
        self.history += [f"Person: {message}", f"Assistant: {reply}"]
        self.history = self.history[-10:]
        return reply

    def send(self, message: str) -> dict:
        message = (message or "").strip()
        if not message:
            return self._out("Please type a message.")

        # 1. Safety gate: runs on EVERY message, before anything else.
        crisis = check_crisis(message)
        if crisis:
            self.patient.red_flags_reported = crisis
            self.stage = "crisis"
            return self._out(CRISIS_MSG)
        flags = check_red_flags(message)
        if flags:
            self.patient.red_flags_reported = flags
            self.stage = "emergency"
            return self._out(EMERGENCY_MSG)

        # 2. After an emergency/crisis, keep showing the safety message.
        if self.stage == "emergency":
            return self._out(EMERGENCY_MSG)
        if self.stage == "crisis":
            return self._out(CRISIS_MSG)

        # 3. After the guidance, talk with the person.
        if self.stage == "followup":
            return self._out(self._followup(message))

        # 4. Intake interview; when code says it is complete, give guidance.
        reply = self.agent.step(message)
        if self.patient.intake_complete:
            reply = reply + "\n\n" + self._guidance()
            self.stage = "followup"
        return self._out(reply)


if __name__ == "__main__":
    session = ChatSession()
    print("Bot:", session.greeting)
    print("(type 'new' for a new chat, 'quit' to exit)")
    try:
        while True:
            msg = input("You: ")
            if msg.strip().lower() in ("quit", "exit"):
                break
            if msg.strip().lower() == "new":
                session = ChatSession()
                print("Bot:", session.greeting)
                continue
            result = session.send(msg)
            print("Bot:", result["reply"])
    except (KeyboardInterrupt, EOFError):
        print()