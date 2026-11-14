# src/ingest.py
import re
import shutil
import logging
from pathlib import Path
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from src.config import DATA_DIR, CHROMA_DIR, EMBED_MODEL

logging.getLogger("pypdf").setLevel(logging.ERROR)

# The triage PDF writes the letters f, i, l as odd Chinese/Korean characters.
# These pairs were found with scan_odd.py (counts add up exactly).
_F = chr(0x6600)  # really the letter "f"
FIXES = {
    _F + _F + chr(0x6900): "ffi",
    _F + _F + chr(0x6C00): "ffl",
    _F + chr(0xCF00): "ffi",
    _F + _F: "ff",
    _F + chr(0x6900): "fi",
    _F + chr(0x6C00): "fl",
    chr(0xFB00): "ff", chr(0xFB01): "fi", chr(0xFB02): "fl",
    chr(0xFB03): "ffi", chr(0xFB04): "ffl",
    chr(0x96): "-",    # hidden dash, as in "1-12 mo"
    chr(0x2DB): "'",   # garbled apostrophe, as in "child's"
}
BROKEN = {_F, chr(0x6900), chr(0x6C00), chr(0xCF00)}

MED = re.compile(
    r"\b(mg|mcg|dose|doses|dosage|tablet|tablets|capsule|capsules|paracetamol|"
    r"acetaminophen|ibuprofen|aspirin|antibiotic|antibiotics|analgesic|"
    r"antihistamine|antacid)\b", re.I)


def clean_text(text: str) -> str:
    for broken, fixed in FIXES.items():
        text = text.replace(broken, fixed)
    return re.sub(r"[ \t]+", " ", text)


def load_documents():
    docs = []
    for source_type in ["triage", "medical"]:
        loaded = PyPDFDirectoryLoader(str(DATA_DIR / source_type)).load()
        kept = 0
        for d in loaded:
            text = clean_text(d.page_content)
            if len(text.strip()) < 40:  # skip empty or near-empty pages
                continue
            d.page_content = text
            d.metadata["source_type"] = source_type
            d.metadata["source_name"] = Path(str(d.metadata.get("source", ""))).name
            d.metadata["page_number"] = int(d.metadata.get("page", 0)) + 1  # PDF viewer numbering
            d.metadata["medicine_dense"] = len(MED.findall(text)) >= 5
            docs.append(d)
            kept += 1
        print(f"{source_type}: {len(loaded)} pages loaded, {kept} kept")
    return docs


def build_db():
    docs = load_documents()
    if not docs:
        raise SystemExit("No documents found. Check data/triage and data/medical.")

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=120
    ).split_documents(docs)
    print("Total chunks:", len(chunks))
    print("Chunks from medicine-heavy pages:", sum(c.metadata["medicine_dense"] for c in chunks))
    print("Chunks still containing broken characters:",
          sum(any(ch in c.page_content for ch in BROKEN) for c in chunks))

    shutil.rmtree(CHROMA_DIR, ignore_errors=True)  # start fresh, so no duplicates
    emb = HuggingFaceEmbeddings(model_name=EMBED_MODEL)
    db = Chroma(persist_directory=CHROMA_DIR, embedding_function=emb)
    for i in range(0, len(chunks), 500):
        db.add_documents(chunks[i:i + 500])
        print(f"  indexed {min(i + 500, len(chunks))} / {len(chunks)}")
    print("Vector DB saved to", CHROMA_DIR)


if __name__ == "__main__":
    build_db()