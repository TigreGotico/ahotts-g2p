"""SAMPA -> IPA mapping tests."""
from ahotts_g2p import SAMPA_TO_IPA


def test_known_mappings():
    assert SAMPA_TO_IPA["g"] == "ɡ"   # LATIN SMALL LETTER SCRIPT G
    assert SAMPA_TO_IPA["tS"] == "tʃ"  # tʃ
    assert SAMPA_TO_IPA["J"] == "ɲ"    # ɲ
    assert SAMPA_TO_IPA["s`"] == "ʂ"   # ʂ
    assert SAMPA_TO_IPA["ts`"] == "tʂ"  # tʂ
    assert SAMPA_TO_IPA["rr"] == "r"
    assert SAMPA_TO_IPA["r"] == "ɾ"    # ɾ


def test_ordered_and_total():
    # ordered dict, plain ASCII vowels map to themselves
    for v in "aeiou":
        assert SAMPA_TO_IPA[v] == v
    # every value is a non-empty string
    assert all(isinstance(v, str) and v for v in SAMPA_TO_IPA.values())


def test_stressed_vowel_keys():
    for v in "aeiou":
        assert SAMPA_TO_IPA["'" + v] == "'" + v
