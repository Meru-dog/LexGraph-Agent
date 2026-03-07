"""NER extraction — spaCy with ja_ginza (JP) and en_core_web_trf (US/EN)."""

import re
from typing import List

# Lazy-loaded spaCy models — None until first use
_jp_nlp = None
_en_nlp = None

# CJK Unicode range covers Japanese/Chinese characters
_CJK_RE = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")


def extract_entities(text: str) -> List[dict]:
    """Extract named entities from text using the appropriate spaCy model.

    Returns a list of entity dicts with keys: text, label, start, end, node_type.
    Falls back to empty list if spaCy models are not installed.
    """
    is_japanese = bool(_CJK_RE.search(text))
    nlp = _get_jp_nlp() if is_japanese else _get_en_nlp()
    if nlp is None:
        return []

    doc = nlp(text[:50_000])  # cap at 50k chars to avoid OOM on large docs
    return [
        {
            "text": ent.text,
            "label": ent.label_,
            "start": ent.start_char,
            "end": ent.end_char,
            "node_type": _map_label(ent.label_),
        }
        for ent in doc.ents
        if _map_label(ent.label_) is not None
    ]


def _get_jp_nlp():
    global _jp_nlp
    if _jp_nlp is not None:
        return _jp_nlp
    try:
        import spacy
        _jp_nlp = spacy.load("ja_ginza")
        print("[ner] Loaded ja_ginza")
        return _jp_nlp
    except Exception as e:
        print(f"[ner] ja_ginza not available ({e}), NER skipped for JP text")
        return None


def _get_en_nlp():
    global _en_nlp
    if _en_nlp is not None:
        return _en_nlp
    try:
        import spacy
        _en_nlp = spacy.load("en_core_web_trf")
        print("[ner] Loaded en_core_web_trf")
        return _en_nlp
    except Exception:
        try:
            import spacy
            _en_nlp = spacy.load("en_core_web_sm")
            print("[ner] Loaded en_core_web_sm (fallback)")
            return _en_nlp
        except Exception as e:
            print(f"[ner] No EN spaCy model available ({e}), NER skipped")
            return None


def _map_label(spacy_label: str):
    """Map spaCy entity labels to graph node types. Returns None to skip non-useful labels."""
    label_map = {
        "ORG": "Entity",
        "PERSON": "Entity",
        "LAW": "Statute",
        "GPE": "Entity",
        # JP (GiNZA) labels
        "法人": "Entity",
        "人名": "Entity",
        "法令": "Statute",
        "地名": "Entity",
    }
    return label_map.get(spacy_label)
