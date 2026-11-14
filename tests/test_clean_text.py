# tests/test_clean_text.py
from src.ingest import clean_text

F = chr(0x6600)


def test_fixes_ligatures():
    assert clean_text("strati" + F + chr(0x6900) + "cation") == "stratification"
    assert clean_text("sta" + F + F) == "staff"
    assert clean_text("re" + F + chr(0x6C00) + "ect") == "reflect"
    assert clean_text("sta" + F + chr(0xCF00) + "ng") == "staffing"


def test_fixes_hidden_dash():
    assert clean_text("1" + chr(0x96) + "12 mo") == "1-12 mo"


def test_normal_text_unchanged():
    assert clean_text("A mild headache") == "A mild headache"