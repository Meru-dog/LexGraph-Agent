"""clause_segmenter — split contract text into typed clauses (regex + LLM)."""

import re
from typing import List

from agents.state import Clause

CLAUSE_TYPE_MAP = {
    "services": "services",
    "payment": "payment",
    "intellectual property": "ip",
    "ip": "ip",
    "termination": "termination",
    "liability": "liability",
    "governing law": "governing_law",
    "confidential": "confidentiality",
    "indemnif": "indemnification",
    "warranty": "warranty",
    "dispute": "dispute_resolution",
}

# Pattern matches §N or ARTICLE N or numbered section headers
SECTION_PATTERN = re.compile(
    r"(?:§\d+\.?\s+[A-Z][^\n]+|ARTICLE\s+\d+[^\n]+|\d+\.\s+[A-Z][^\n]+)",
    re.MULTILINE,
)


def clause_segmenter(text: str, contract_type: str) -> List[Clause]:
    """Split contract into typed clauses.

    Phase 2: regex-based structural segmentation.
    Phase 3: add LLM correction pass for semantic boundary refinement.
    """
    sections = list(SECTION_PATTERN.finditer(text))
    clauses: List[Clause] = []

    for i, match in enumerate(sections):
        start = match.start()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        clause_text = text[start:end].strip()
        header = match.group(0).lower()
        clause_type = _classify_type(header)

        clauses.append(
            Clause(
                id=f"clause_{i + 1:02d}",
                type=clause_type,
                text=clause_text,
                position=start,
            )
        )

    return clauses


def _classify_type(header: str) -> str:
    for keyword, clause_type in CLAUSE_TYPE_MAP.items():
        if keyword in header:
            return clause_type
    return "general"
