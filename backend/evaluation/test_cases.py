"""RAGAS test cases — 25 JP/US legal QA pairs (Phase 2 baseline set).

Ground truths are based on actual statute text and standard legal doctrine.
Extend to 50–100 cases in Phase 4 after attorney review.
"""

TEST_CASES = [
    # ── 会社法 (Companies Act) ─────────────────────────────────────────────────
    {
        "question": "会社法423条1項の要件は何ですか？",
        "ground_truth": (
            "会社法423条1項の要件は、①取締役等がその任務を怠ったこと（任務懈怠）、"
            "②株式会社に損害が生じたこと、③任務懈怠と損害との間に因果関係があること、"
            "④取締役等に帰責事由（故意または過失）があることです。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "取締役の善管注意義務とは何ですか？",
        "ground_truth": (
            "取締役の善管注意義務は、会社法330条・民法644条に基づき、"
            "取締役が善良な管理者の注意をもって職務を遂行する義務です。"
            "経営判断の原則が適用され、一定の裁量が認められます。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "会社法362条が規定する取締役会の権限は何ですか？",
        "ground_truth": (
            "会社法362条は、取締役会の権限として、①取締役会設置会社の業務執行の決定、"
            "②取締役の職務執行の監督、③代表取締役の選定・解職を規定しています。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "会社法355条の忠実義務の内容を説明してください。",
        "ground_truth": (
            "会社法355条の忠実義務は、取締役が法令・定款・株主総会決議を遵守し、"
            "株式会社のために忠実に職務を行う義務です。"
            "善管注意義務（民法644条）と実質的に同一であるとされています。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "会社法467条が定める事業譲渡の手続きは何ですか？",
        "ground_truth": (
            "会社法467条は、事業の全部譲渡等の行為をする場合には、"
            "効力発生日の前日までに株主総会の特別決議による承認を必要とします。"
        ),
        "jurisdiction": "JP",
    },
    # ── 金融商品取引法 (FIEA) ─────────────────────────────────────────────────
    {
        "question": "金商法166条のインサイダー取引規制の対象者は誰ですか？",
        "ground_truth": (
            "金商法166条の対象者は、①上場会社等の役員・主要株主等の会社関係者、"
            "②情報受領者（第一次情報受領者）です。"
            "重要事実の公表前に特定有価証券等の売買等をすることが禁止されます。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "金商法197条の虚偽記載の罰則は何ですか？",
        "ground_truth": (
            "金商法197条は、有価証券届出書等への虚偽記載に対し、"
            "10年以下の懲役または1,000万円以下の罰金、あるいは両方を科します。"
        ),
        "jurisdiction": "JP",
    },
    # ── 民法 (Civil Code) ──────────────────────────────────────────────────────
    {
        "question": "民法644条の善管注意義務の内容を説明してください。",
        "ground_truth": (
            "民法644条は、受任者が委任の本旨に従い、善良な管理者の注意をもって"
            "委任事務を処理する義務を負うと規定しています。"
            "抽象的軽過失であり、受任者の職業・能力等を考慮した標準的注意が求められます。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "民法709条の不法行為の要件は何ですか？",
        "ground_truth": (
            "民法709条の不法行為の成立要件は、①故意または過失、②権利・法益侵害、"
            "③損害の発生、④因果関係の4つです。"
            "これらが全て充足された場合、加害者は損害賠償責任を負います。"
        ),
        "jurisdiction": "JP",
    },
    # ── Cross-jurisdictional ──────────────────────────────────────────────────
    {
        "question": "日本の取締役の善管注意義務と米国のDuty of Careはどう異なりますか？",
        "ground_truth": (
            "日本の善管注意義務（会社法330条・民法644条）と米国デラウェア州のDuty of Care（DGCL）は"
            "機能的に類似しますが、経営判断原則の適用範囲が異なります。"
            "米国では業務判断原則（Business Judgment Rule）により取締役の裁量が広く認められ、"
            "過失があっても責任を免れる場合があります。"
            "日本でも経営判断原則は認められていますが、立証責任の分配が異なります。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "日本のインサイダー取引規制と米国Rule 10b-5の構造的違いは何ですか？",
        "ground_truth": (
            "日本の金商法166条は類型化規制であり、規制対象者・重要事実・禁止行為を明文で列挙します。"
            "米国のRule 10b-5（証券取引所法10条b項）は包括的詐欺禁止規定であり、"
            "Misappropriation理論による拡張適用が認められています。"
            "日本は刑事処罰に重点、米国はSECによる民事制裁・内部告発制度が発達しています。"
        ),
        "jurisdiction": "JP",
    },
    # ── US Law ────────────────────────────────────────────────────────────────
    {
        "question": "What is the business judgment rule under Delaware law?",
        "ground_truth": (
            "The business judgment rule is a presumption under Delaware law that directors "
            "act on an informed basis, in good faith, and in the honest belief that the action "
            "is in the best interests of the corporation. Courts will not second-guess director "
            "decisions unless the plaintiff shows self-dealing, bad faith, or failure to inform themselves."
        ),
        "jurisdiction": "US",
    },
    {
        "question": "What are the fiduciary duties of directors under the DGCL?",
        "ground_truth": (
            "Under Delaware corporate law, directors owe two primary fiduciary duties: "
            "the duty of care (act on an informed basis with due diligence) and the duty of loyalty "
            "(act in the best interests of the corporation, free from self-interest). "
            "A duty of good faith is sometimes treated as a component of the duty of loyalty."
        ),
        "jurisdiction": "US",
    },
    {
        "question": "What does Section 141 of the DGCL provide?",
        "ground_truth": (
            "Section 141 of the Delaware General Corporation Law provides that the business "
            "and affairs of every corporation shall be managed by or under the direction of a "
            "board of directors. It sets out quorum requirements, written consent procedures, "
            "and allows delegation to committees."
        ),
        "jurisdiction": "US",
    },
    {
        "question": "What is SEC Rule 10b-5?",
        "ground_truth": (
            "SEC Rule 10b-5, promulgated under Section 10(b) of the Securities Exchange Act of 1934, "
            "prohibits fraud and misrepresentation in connection with the purchase or sale of any security. "
            "It is the primary anti-fraud provision used in insider trading cases and securities class actions."
        ),
        "jurisdiction": "US",
    },
    {
        "question": "What are the elements of a Section 10(b) / Rule 10b-5 claim?",
        "ground_truth": (
            "The elements of a Rule 10b-5 claim are: (1) a material misrepresentation or omission, "
            "(2) scienter (intent to deceive or recklessness), (3) connection with the purchase or sale of a security, "
            "(4) reliance, (5) economic loss, and (6) loss causation."
        ),
        "jurisdiction": "US",
    },
    {
        "question": "What is Section 144 of the DGCL about?",
        "ground_truth": (
            "Section 144 of the DGCL addresses interested director transactions. "
            "A contract or transaction involving an interested director is not void or voidable solely "
            "because of the director's interest if: (1) material facts are disclosed and the disinterested "
            "directors approve, (2) shareholders approve, or (3) the transaction is fair to the corporation."
        ),
        "jurisdiction": "US",
    },
    # ── M&A / Transactional ───────────────────────────────────────────────────
    {
        "question": "M&Aにおける表明保証（Representations and Warranties）の機能は何ですか？",
        "ground_truth": (
            "表明保証（Rep & Warranty）は、売主が買主に対して対象会社・事業の状態について"
            "一定の事実を表明・保証する契約条項です。"
            "違反した場合、売主は損害賠償責任（補償条項）を負います。"
            "日本法では、民法の瑕疵担保責任または債務不履行（民法415条）により処理されることもあります。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "株主総会の特別決議の定足数・決議要件は何ですか？",
        "ground_truth": (
            "会社法309条2項により、特別決議は議決権を行使できる株主の議決権の過半数を有する株主が出席し、"
            "出席した株主の議決権の3分の2以上の賛成が必要です。"
            "定款による加重も可能です。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "What is a merger agreement's material adverse change clause?",
        "ground_truth": (
            "A Material Adverse Change (MAC) or Material Adverse Effect (MAE) clause allows a buyer "
            "to terminate a merger agreement if the target suffers a significant negative change between "
            "signing and closing. Delaware courts have rarely found MAEs, requiring sustained, significant "
            "changes affecting the long-term business (not short-term dips). The clause typically contains "
            "carve-outs for general market conditions, industry-wide events, and regulatory changes."
        ),
        "jurisdiction": "US",
    },
    # ── Contract Law ──────────────────────────────────────────────────────────
    {
        "question": "秘密保持契約（NDA）において秘密情報の定義で注意すべき点は何ですか？",
        "ground_truth": (
            "秘密情報の定義では、①対象情報の範囲（書面・口頭・電子データ）、"
            "②秘密指定の方式（書面表示要件の有無）、③除外情報（既に公知の情報、独自開発情報等）を"
            "明確に規定することが重要です。"
            "日本法上、不正競争防止法の営業秘密（2条6項）の要件（秘密管理性・有用性・非公知性）も意識する必要があります。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "What is the limitation of liability clause in a commercial contract?",
        "ground_truth": (
            "A limitation of liability clause caps the maximum damages recoverable by one party from the other, "
            "typically expressed as a multiple of fees paid under the contract or a fixed amount. "
            "Consequential damages exclusions (lost profits, indirect damages) are commonly paired with these clauses. "
            "Under UCC and common law, such clauses are generally enforceable unless unconscionable."
        ),
        "jurisdiction": "US",
    },
    # ── Labor Law ─────────────────────────────────────────────────────────────
    {
        "question": "三六協定（時間外労働・休日労働に関する協定届）の法的根拠は何ですか？",
        "ground_truth": (
            "三六協定は、労働基準法36条に基づき、使用者と労働組合（または労働者の過半数代表者）が"
            "締結・届出することで、法定労働時間（1日8時間・週40時間）を超える時間外労働および"
            "休日労働が法的に許容される協定です。"
            "2019年の改正により、時間外労働の上限規制（原則月45時間・年360時間）が法定化されました。"
        ),
        "jurisdiction": "JP",
    },
    {
        "question": "What is the WARN Act's notice requirement?",
        "ground_truth": (
            "The WARN Act (Worker Adjustment and Retraining Notification Act) requires employers with 100 or more "
            "employees to provide 60 calendar days' advance notice before plant closings or mass layoffs "
            "affecting 50 or more employees. Failure to provide notice results in liability for up to 60 days' "
            "pay and benefits per affected employee."
        ),
        "jurisdiction": "US",
    },
]
