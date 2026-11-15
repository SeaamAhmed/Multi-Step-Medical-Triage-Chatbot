"""Looks up the allowed OTC medicines by name, so they can appear in the context."""
from src import retriever

SEARCH_TERMS = {
    "acetaminophen": ["acetaminophen", "paracetamol"],
    "ibuprofen": ["ibuprofen"],
    "antacid": ["antacid"],
    "cetirizine": ["cetirizine"],
}


def _database():
    db = retriever._db
    return db() if callable(db) else db


def medicine_docs(p, k=3):
    """Return pages that mention an allowed medicine, found by name."""
    db = _database()
    found, seen = [], set()
    for names in SEARCH_TERMS.values():
        query = f"{names[0]} {p.chief_complaint or ''}"
        for doc in db.similarity_search(query, k=k):
            text = doc.page_content.lower()
            if not any(n in text for n in names):
                continue
            key = (doc.metadata.get("source_name"), doc.metadata.get("page_number"),
                   doc.page_content[:60])
            if key not in seen:
                seen.add(key)
                found.append(doc)
    return found

def search_docs(query, k=4):
    """Plain search over the whole index (used for follow-up questions)."""
    return _database().similarity_search(query, k=k)