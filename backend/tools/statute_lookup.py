"""statute_lookup — direct article fetch from Neo4j, with e-Gov API fallback for JP."""

import re
from typing import Optional


def statute_lookup(article_ref: str, jurisdiction: str) -> Optional[dict]:
    """Fetch a specific statutory provision by article reference.

    Lookup order:
      1. Neo4j Provision node (exact article_no match)
      2. e-Gov API (JP only) — live HTTP fetch
      3. Returns None if not found
    """
    # Try Neo4j first
    result = _neo4j_lookup(article_ref, jurisdiction)
    if result:
        return result

    # JP fallback: e-Gov API
    if jurisdiction in ("JP", "JP+US"):
        result = _egov_lookup(article_ref)
        if result:
            return result

    return None


def _neo4j_lookup(article_ref: str, jurisdiction: str) -> Optional[dict]:
    try:
        from graph.neo4j_client import neo4j_client
        if not neo4j_client._driver:
            return None
        rows = neo4j_client.run_query(
            """
            MATCH (s:Statute)-[:HAS_PROVISION]->(p:Provision)
            WHERE (p.article_no = $article_ref OR p.node_id = $article_ref)
              AND s.jurisdiction = $jurisdiction
            RETURN s.title AS statute_title, s.jurisdiction AS jurisdiction,
                   p.article_no AS article_no, p.text AS text, p.section AS section
            LIMIT 1
            """,
            {"article_ref": article_ref, "jurisdiction": jurisdiction},
        )
        if rows:
            r = rows[0]
            return {
                "source": "neo4j",
                "statute": r.get("statute_title", ""),
                "article_no": r.get("article_no", article_ref),
                "text": r.get("text", ""),
                "section": r.get("section", ""),
                "jurisdiction": r.get("jurisdiction", jurisdiction),
            }
    except Exception as e:
        print(f"[statute_lookup] Neo4j error: {e}")
    return None


def _egov_lookup(article_ref: str) -> Optional[dict]:
    """Query e-Gov elaws API for Japanese statute text.

    API: https://laws.e-gov.go.jp/api/1/lawdata/{law_id}
    We identify law codes by matching known prefixes in article_ref.
    """
    try:
        import httpx

        # Map common statute names to e-Gov law IDs
        LAW_IDS = {
            "会社法": "412AC0000000086",
            "金融商品取引法": "323AC0000000025",
            "金商法": "323AC0000000025",
            "民法": "129AC0000000089",
            "商法": "132AC0000000048",
            "労働基準法": "322AC0000000049",
        }

        law_id = None
        for name, lid in LAW_IDS.items():
            if name in article_ref:
                law_id = lid
                break

        if not law_id:
            return None

        # Fetch law XML from e-Gov
        url = f"https://laws.e-gov.go.jp/api/1/lawdata/{law_id}"
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code != 200:
            return None

        # Extract article number from ref (e.g. "Art. 355" → "355")
        m = re.search(r"(\d+(?:\.\d+)?)", article_ref)
        article_no = m.group(1) if m else ""

        return {
            "source": "egov",
            "statute": next(k for k, v in LAW_IDS.items() if v == law_id),
            "article_no": article_no,
            "text": f"[e-Gov source — see https://laws.e-gov.go.jp/law/{law_id}]",
            "jurisdiction": "JP",
            "law_id": law_id,
        }
    except Exception as e:
        print(f"[statute_lookup] e-Gov API error: {e}")
        return None
