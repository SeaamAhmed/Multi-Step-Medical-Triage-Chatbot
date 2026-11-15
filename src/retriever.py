# src/retriever.py
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from src.config import CHROMA_DIR, EMBED_MODEL
from src.schemas import PatientIntake

_emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
_db = Chroma(persist_directory=CHROMA_DIR, embedding_function=_emb)


def build_query(p: PatientIntake) -> str:
    parts = [
        p.chief_complaint or "",
        ", ".join(p.symptoms or []),
        ", ".join(p.associated_symptoms or []),
        p.duration or "",
        p.severity or "",
    ]
    return " ".join(x for x in parts if x)


NOISE_WORDS = ("ORGANIZATIONS", "PERIODICALS", "BOOKS")  # resource lists, not content


def _clean_results(docs, k):
    """Drop resource lists and near-duplicate chunks, then keep the top k."""
    seen, out = set(), []
    for d in docs:
        text = d.page_content
        key = " ".join(text.split())[:40].lower()
        if key in seen or any(w in text for w in NOISE_WORDS):
            continue
        seen.add(key)
        out.append(d)
    return out[:k]


def retrieve(p: PatientIntake, k_triage: int = 3, k_medical: int = 4):
    q = build_query(p)
    triage = _db.similarity_search(q, k=k_triage + 3, filter={"source_type": "triage"})
    medical = _db.similarity_search(q, k=k_medical + 4, filter={"source_type": "medical"})
    return _clean_results(triage, k_triage), _clean_results(medical, k_medical)


if __name__ == "__main__":
    tests = {
        "adult sore throat": PatientIntake(
            age=48, chief_complaint="sore throat", symptoms=["sore throat", "fever"],
            duration="3 days", severity="moderate"),
        "headache": PatientIntake(
            age=44, chief_complaint="headache", symptoms=["headache"],
            duration="since morning", severity="moderate"),
        "teen tummy ache": PatientIntake(
            age=15, chief_complaint="my tummy hurts", symptoms=["stomach pain"],
            duration="since yesterday", severity="mild"),
    }
    for name, patient in tests.items():
        print("\n" + "#" * 70)
        print(name, "| query:", build_query(patient))
        triage, medical = retrieve(patient)
        for label, docs in [("TRIAGE", triage), ("MEDICAL", medical)]:
            print("=====", label)
            for d in docs:
                m = d.metadata
                print(f"{m.get('source_name')} p.{m.get('page_number')} "
                      f"medicine_dense={m.get('medicine_dense')}")
                print("    ", d.page_content[:200].replace("\n", " "))