# scan_otc.py  (diagnostic only)
import logging
from pypdf import PdfReader
logging.disable(logging.CRITICAL)

CANDIDATES = [
    "acetaminophen", "paracetamol", "ibuprofen", "aspirin", "naproxen",
    "antacid", "oral rehydration", "loperamide", "diphenhydramine",
    "cetirizine", "loratadine", "guaifenesin", "dextromethorphan",
    "pseudoephedrine", "lozenge", "simethicone", "calamine", "hydrocortisone",
]

reader = PdfReader("data/medical/Medical Book.pdf")
pages = []
for i, p in enumerate(reader.pages, 1):
    t = (p.extract_text() or "").lower().replace("-\n", "").replace("- ", "")
    pages.append((i, t))

for name in CANDIDATES:
    hits = [i for i, t in pages if name in t]
    print(f"{name:20} {len(hits):3} pages", hits[:8])