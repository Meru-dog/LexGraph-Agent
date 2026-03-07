"""Neo4j seed data — Companies Act (会社法) and FIEA (金融商品取引法) statute nodes.

Run once on startup if the database is empty. Idempotent (uses MERGE).
"""

# ─── JP Statutes ──────────────────────────────────────────────────────────────

JP_STATUTES = [
    {
        "node_id": "jp-ca",
        "title": "会社法",
        "title_en": "Companies Act",
        "jurisdiction": "JP",
        "effective_date": "2006-05-01",
        "source_url": "https://laws.e-gov.go.jp/law/412AC0000000086",
    },
    {
        "node_id": "jp-fiea",
        "title": "金融商品取引法",
        "title_en": "Financial Instruments and Exchange Act (FIEA)",
        "jurisdiction": "JP",
        "effective_date": "1948-04-13",
        "source_url": "https://laws.e-gov.go.jp/law/323AC0000000025",
    },
    {
        "node_id": "jp-cc",
        "title": "民法",
        "title_en": "Civil Code",
        "jurisdiction": "JP",
        "effective_date": "1896-04-27",
        "source_url": "https://laws.e-gov.go.jp/law/129AC0000000089",
    },
]

# ─── Key Provisions ───────────────────────────────────────────────────────────

JP_PROVISIONS = [
    # 会社法 (Companies Act)
    {
        "node_id": "jp-ca-355",
        "statute_id": "jp-ca",
        "article_no": "355",
        "section": "取締役の忠実義務",
        "text": "取締役は、法令及び定款並びに株主総会の決議を遵守し、株式会社のため忠実にその職務を行わなければならない。",
        "text_en": "A director shall observe laws and regulations and the articles of incorporation, and shall perform their duties faithfully for the benefit of the company.",
    },
    {
        "node_id": "jp-ca-423",
        "statute_id": "jp-ca",
        "article_no": "423",
        "section": "役員等の株式会社に対する損害賠償責任",
        "text": "取締役等がその職務を行うについて悪意又は重大な過失があったときは、当該取締役等は、これによって第三者に生じた損害を賠償する責任を負う。",
        "text_en": "When a director etc. has acted in bad faith or with gross negligence in performing their duties, such director etc. shall be liable to compensate for the damage thereby caused to third parties.",
    },
    {
        "node_id": "jp-ca-362",
        "statute_id": "jp-ca",
        "article_no": "362",
        "section": "取締役会の権限等",
        "text": "取締役会は、すべての取締役で組織する。取締役会は、次に掲げる職務を行う。一 取締役会設置会社の業務執行の決定。二 取締役の職務の執行の監督。",
        "text_en": "The board of directors shall consist of all directors. The board of directors shall perform: (i) decisions on execution of operations of the company with board of directors; (ii) supervision of the execution of duties by directors.",
    },
    {
        "node_id": "jp-ca-467",
        "statute_id": "jp-ca",
        "article_no": "467",
        "section": "事業譲渡等の承認等",
        "text": "株式会社は、次に掲げる行為をする場合には、当該行為の効力が生ずる日の前日までに、株主総会の決議によって、当該行為に係る契約の承認を受けなければならない。一 事業の全部の譲渡。",
        "text_en": "When a company takes any of the following actions, it must obtain approval of the relevant contract by resolution of the general shareholders meeting by the day before the effective date: (i) transfer of the whole business.",
    },
    # 金融商品取引法 (FIEA)
    {
        "node_id": "jp-fiea-166",
        "statute_id": "jp-fiea",
        "article_no": "166",
        "section": "会社関係者の禁止行為（インサイダー取引規制）",
        "text": "次の各号に掲げる者は、上場会社等の業務等に関する重要事実を知つた場合には、当該重要事実の公表がされた後でなければ、当該上場会社等の特定有価証券等に係る売買等をしてはならない。",
        "text_en": "Persons listed in the following items shall not make purchase and sale etc. of specified securities etc. of a listed company etc. before the material fact is publicly disclosed.",
    },
    {
        "node_id": "jp-fiea-197",
        "statute_id": "jp-fiea",
        "article_no": "197",
        "section": "虚偽記載等の罪",
        "text": "有価証券届出書に虚偽の記載をした者は、十年以下の懲役若しくは千万円以下の罰金に処し、又はこれを併科する。",
        "text_en": "A person who makes a false statement in a securities registration statement shall be punished by imprisonment with work for not more than 10 years or a fine of not more than ¥10,000,000, or both.",
    },
    # 民法 (Civil Code)
    {
        "node_id": "jp-cc-644",
        "statute_id": "jp-cc",
        "article_no": "644",
        "section": "受任者の注意義務",
        "text": "受任者は、委任の本旨に従い、善良な管理者の注意をもって、委任事務を処理する義務を負う。",
        "text_en": "The mandatory shall process the entrusted business with the care of a prudent manager in accordance with the purport of the mandate.",
    },
]

# ─── US Statutes ──────────────────────────────────────────────────────────────

US_STATUTES = [
    {
        "node_id": "us-dgcl",
        "title": "Delaware General Corporation Law",
        "title_en": "Delaware General Corporation Law (DGCL)",
        "jurisdiction": "US",
        "effective_date": "1899-01-01",
        "source_url": "https://delcode.delaware.gov/title8/",
    },
    {
        "node_id": "us-sa33",
        "title": "Securities Act of 1933",
        "title_en": "Securities Act of 1933",
        "jurisdiction": "US",
        "effective_date": "1933-05-27",
        "source_url": "https://www.govinfo.gov/content/pkg/COMPS-1884/pdf/COMPS-1884.pdf",
    },
    {
        "node_id": "us-sea34",
        "title": "Securities Exchange Act of 1934",
        "title_en": "Securities Exchange Act of 1934",
        "jurisdiction": "US",
        "effective_date": "1934-06-06",
        "source_url": "https://www.govinfo.gov/content/pkg/COMPS-1885/pdf/COMPS-1885.pdf",
    },
]

US_PROVISIONS = [
    {
        "node_id": "us-dgcl-141",
        "statute_id": "us-dgcl",
        "article_no": "141",
        "section": "Board of Directors; Powers; Number; Qualifications; Terms; Compensation",
        "text": "The business and affairs of every corporation organized under this chapter shall be managed by or under the direction of a board of directors, except as may be otherwise provided in this chapter or in its certificate of incorporation.",
    },
    {
        "node_id": "us-dgcl-144",
        "statute_id": "us-dgcl",
        "article_no": "144",
        "section": "Interested Directors and Officers; Quorum",
        "text": "No contract or transaction between a corporation and 1 or more of its directors or officers, or between a corporation and any other corporation, partnership, association, or other organization in which 1 or more of its directors or officers, are directors or officers, or have a financial interest, shall be void or voidable solely for this reason.",
    },
    {
        "node_id": "us-sea34-10b",
        "statute_id": "us-sea34",
        "article_no": "10(b)",
        "section": "Manipulative and Deceptive Devices",
        "text": "It shall be unlawful for any person, directly or indirectly, by the use of any means or instrumentality of interstate commerce or of the mails, or of any facility of any national securities exchange, to use or employ, in connection with the purchase or sale of any security registered on a national securities exchange, any manipulative or deceptive device.",
    },
]

# ─── Legal Concepts ───────────────────────────────────────────────────────────

CONCEPTS = [
    {
        "node_id": "concept-fiduciary-jp",
        "name": "忠実義務",
        "domain": "Corporate",
        "jurisdiction": "JP",
        "definition": "取締役が会社のために忠実に職務を遂行する義務（会社法355条）",
        "analogous_to": "concept-fiduciary-us",
    },
    {
        "node_id": "concept-fiduciary-us",
        "name": "Fiduciary Duty",
        "domain": "Corporate",
        "jurisdiction": "US",
        "definition": "Duty of directors to act in good faith and in the best interests of the corporation and its shareholders.",
        "analogous_to": "concept-fiduciary-jp",
    },
    {
        "node_id": "concept-insider-jp",
        "name": "インサイダー取引",
        "domain": "Securities",
        "jurisdiction": "JP",
        "definition": "会社関係者による重要事実の公表前の有価証券売買（金商法166条）",
        "analogous_to": "concept-insider-us",
    },
    {
        "node_id": "concept-insider-us",
        "name": "Insider Trading",
        "domain": "Securities",
        "jurisdiction": "US",
        "definition": "Purchase or sale of securities on the basis of material non-public information (SEC Rule 10b-5).",
        "analogous_to": "concept-insider-jp",
    },
]


def seed(client) -> dict:
    """Write all seed data to Neo4j. Idempotent (MERGE). Returns counts."""
    if not client._driver:
        print("[seed] Neo4j not connected — skipping seed")
        return {"skipped": True}

    counts = {"statutes": 0, "provisions": 0, "concepts": 0, "analogies": 0}

    # Seed statutes
    for statute in JP_STATUTES + US_STATUTES:
        client.run_query(
            """
            MERGE (s:Statute {node_id: $node_id})
            SET s.title = $title,
                s.title_en = $title_en,
                s.jurisdiction = $jurisdiction,
                s.effective_date = $effective_date,
                s.source_url = $source_url
            """,
            statute,
        )
        counts["statutes"] += 1

    # Seed provisions + HAS_PROVISION edges
    for prov in JP_PROVISIONS + US_PROVISIONS:
        statute_id = prov.pop("statute_id")
        client.run_query(
            """
            MERGE (p:Provision {node_id: $node_id})
            SET p.article_no = $article_no,
                p.section = $section,
                p.text = $text,
                p.text_en = $text_en
            WITH p
            MATCH (s:Statute {node_id: $statute_id})
            MERGE (s)-[:HAS_PROVISION]->(p)
            """,
            {**prov, "text_en": prov.get("text_en", ""), "statute_id": statute_id},
        )
        prov["statute_id"] = statute_id  # restore
        counts["provisions"] += 1

    # Seed legal concepts
    for concept in CONCEPTS:
        analogous_to = concept.pop("analogous_to", None)
        client.run_query(
            """
            MERGE (lc:LegalConcept {node_id: $node_id})
            SET lc.name = $name,
                lc.domain = $domain,
                lc.jurisdiction = $jurisdiction,
                lc.definition = $definition
            """,
            concept,
        )
        concept["analogous_to"] = analogous_to
        counts["concepts"] += 1

    # Wire ANALOGOUS_TO relationships
    for concept in CONCEPTS:
        if concept.get("analogous_to"):
            client.run_query(
                """
                MATCH (a:LegalConcept {node_id: $from_id})
                MATCH (b:LegalConcept {node_id: $to_id})
                MERGE (a)-[:ANALOGOUS_TO]-(b)
                """,
                {"from_id": concept["node_id"], "to_id": concept["analogous_to"]},
            )
            counts["analogies"] += 1

    # Wire Provision → LegalConcept GOVERNS edges (key relationships)
    GOVERNS_EDGES = [
        ("jp-ca-355", "concept-fiduciary-jp"),
        ("jp-fiea-166", "concept-insider-jp"),
        ("us-dgcl-141", "concept-fiduciary-us"),
        ("us-sea34-10b", "concept-insider-us"),
    ]
    for prov_id, concept_id in GOVERNS_EDGES:
        client.run_query(
            """
            MATCH (p:Provision {node_id: $prov_id})
            MATCH (lc:LegalConcept {node_id: $concept_id})
            MERGE (p)-[:GOVERNS]->(lc)
            """,
            {"prov_id": prov_id, "concept_id": concept_id},
        )

    print(f"[seed] Seeded: {counts}")
    return counts
