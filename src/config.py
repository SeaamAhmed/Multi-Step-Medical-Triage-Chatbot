# src/config.py
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CHROMA_DIR = str(DATA_DIR / "chroma_db")

INTAKE_MODEL = os.getenv("INTAKE_MODEL", "openai/gpt-oss-120b")
MAIN_MODEL = os.getenv("MAIN_MODEL", "gemini-3.8-flash")
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

DISCLAIMER = ("\n\nThis is general information based on our reference documents. "
              "It is not a diagnosis and does not replace a doctor.")