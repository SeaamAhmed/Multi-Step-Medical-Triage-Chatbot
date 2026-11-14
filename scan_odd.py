# scan_odd.py  (diagnostic only)
import re, glob, collections, logging
logging.disable(logging.CRITICAL)
from pypdf import PdfReader

IGNORE = {0x2019, 0x2018, 0x201C, 0x201D, 0x2013, 0x2014, 0x2022, 0x2026, 0xB0, 0xA0}

for path in sorted(glob.glob("data/*/*.pdf")):
    text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages)
    counts, examples = collections.Counter(), {}
    for m in re.finditer(r"[^\x00-\x7f]", text):
        c = m.group()
        if ord(c) in IGNORE:
            continue
        counts[c] += 1
        examples.setdefault(c, text[max(0, m.start() - 10): m.end() + 10].replace("\n", " "))
    print("=====", path)
    for c, n in counts.most_common(25):
        print(f"U+{ord(c):04X}", repr(c), n, "times, e.g.", repr(examples[c]))