# scan_pdfs.py  (diagnostic only)
import re, glob, collections, logging
logging.disable(logging.CRITICAL)
from pypdf import PdfReader

ODD = re.compile(r"[\u4e00-\u9fff]+")
MED = re.compile(
    r"\b(mg|mcg|dose|doses|dosage|tablet|tablets|capsule|capsules|paracetamol|"
    r"acetaminophen|ibuprofen|aspirin|antibiotic|antibiotics|analgesic|"
    r"antihistamine|antacid)\b", re.I)


def ranges(nums):
    out, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append((start, prev))
            start = prev = n
    if start is not None:
        out.append((start, prev))
    return ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in out)


for path in glob.glob("data/*/*.pdf"):
    reader = PdfReader(path)
    print("=====", path, "| pages:", len(reader.pages))
    odd = collections.Counter()
    context = {}
    med_pages = []
    for i, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        for m in ODD.finditer(text):
            odd[m.group()] += 1
            context.setdefault(m.group(), text[max(0, m.start() - 8): m.end() + 8].replace("\n", " "))
        if len(MED.findall(text)) >= 5:
            med_pages.append(i)
    print("odd character runs and an example:")
    for run, count in odd.most_common(10):
        print("  ", repr(run), count, "times, e.g.", repr(context[run]))
    print("pages with 5 or more medicine/dose words:", ranges(med_pages) or "none")