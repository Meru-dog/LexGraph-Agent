"""cross_reference_checker — detect internal inconsistencies across clauses."""

from typing import List

from agents.state import Clause, Inconsistency


def cross_reference_checker(clauses: List[Clause]) -> List[Inconsistency]:
    """Detect conflicting provisions between clauses.

    Phase 2: rule-based heuristics.
    Phase 3: embedding cosine similarity matrix + LLM inconsistency detection.
    """
    inconsistencies: List[Inconsistency] = []

    # Heuristic: find termination clauses that may conflict with payment terms
    termination_clauses = [c for c in clauses if c["type"] == "termination"]
    payment_clauses = [c for c in clauses if c["type"] == "payment"]

    for t in termination_clauses:
        for p in payment_clauses:
            if "immediate" in t["text"].lower() and "30 days" in p["text"].lower():
                inconsistencies.append(
                    Inconsistency(
                        clause_a_id=t["id"],
                        clause_b_id=p["id"],
                        description=(
                            "Termination clause allows immediate termination, but payment "
                            "clause provides 30-day payment window — potential conflict on "
                            "outstanding invoices at termination."
                        ),
                    )
                )

    return inconsistencies
