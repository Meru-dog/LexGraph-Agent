"""US legal dataset loader for QLoRA fine-tuning.

Sources:
    - CUAD             — 600 examples — US commercial contracts, 41 clause types
    - Edgar-Corpus     — 300 examples — 10-K, 8-K, proxy filings
    - LegalBench       — 400 examples — legal reasoning tasks
    - CaseHOLD         — 200 examples — federal court holding selection
    - ContractNLI      — 150 examples — contract clause NLI
    - BillSum          — 150 examples — congressional bills
    Total: ~1,800 examples
"""

from __future__ import annotations

import random
from typing import List


def load_cuad(max_examples: int = 600) -> List[dict]:
    """Load CUAD contract understanding dataset.

    Tries theatricusproject/cuad then falls back to synthetic contract examples.
    """
    from datasets import load_dataset

    results = []
    for cuad_path in ("theatticusproject/cuad", "cuad", "malduwais/cuad"):
        try:
            ds = load_dataset(cuad_path, split="train")
            for ex in ds:
                q = ex.get("question", "")
                answers = ex.get("answers", {}).get("text", [])
                if not q or not answers:
                    continue
                context = ex.get("context", "")[:1200]
                answer = answers[0]
                results.append({
                    "question": f"Contract clause analysis: {q}\n\nContract excerpt:\n{context}",
                    "answer": (
                        f"Clause identification: {answer}\n\n"
                        f"This clause is relevant because it directly addresses {q.lower().rstrip('?')}."
                    ),
                })
                if len(results) >= max_examples:
                    break
            if results:
                return results
        except Exception as e:
            print(f"[us_loader] CUAD path '{cuad_path}' failed: {e}")

    print("[us_loader] CUAD unavailable — using synthetic contract examples")
    return _synthetic_contract_qa(max_examples)


def _synthetic_contract_qa(max_examples: int) -> List[dict]:
    """Synthetic US contract law Q&A as fallback when CUAD is unavailable."""
    qa_pairs = [
        {
            "question": (
                "Contract clause analysis: Does this agreement include a limitation of liability cap?\n\n"
                "Contract excerpt: The total liability of each party under this Agreement "
                "shall not exceed the fees paid in the twelve months preceding the claim."
            ),
            "answer": (
                "Clause identification: The Agreement includes a 12-month fee-based liability cap.\n\n"
                "This clause is relevant because it limits exposure to direct damages. "
                "Under Delaware law, liability cap clauses are generally enforceable unless they "
                "result from gross negligence or willful misconduct. "
                "Restatement (Second) of Contracts §195 limits enforcement of exculpatory clauses "
                "that contravene public policy."
            ),
        },
        {
            "question": (
                "Contract clause analysis: Does this NDA contain a non-solicitation provision?\n\n"
                "Contract excerpt: During the term and for two years thereafter, neither party "
                "shall solicit or hire any employee of the other party."
            ),
            "answer": (
                "Clause identification: The agreement contains a 2-year post-term non-solicitation clause.\n\n"
                "This clause restricts hiring of the counterparty's employees. "
                "Enforceability varies by state: California (Cal. Bus. & Prof. Code §16600) broadly "
                "invalidates such restrictions, while Delaware courts apply a reasonableness test "
                "under the common law. Courts consider geographic scope, duration, and business justification."
            ),
        },
        {
            "question": (
                "Contract clause analysis: Identify the governing law and dispute resolution mechanism.\n\n"
                "Contract excerpt: This Agreement shall be governed by the laws of the State of "
                "Delaware. Any disputes shall be resolved by binding arbitration under AAA rules."
            ),
            "answer": (
                "Clause identification: Delaware governing law with AAA binding arbitration.\n\n"
                "Delaware is a preferred governing law jurisdiction for commercial contracts due to "
                "its well-developed case law (Delaware General Corporation Law). "
                "AAA Commercial Arbitration Rules provide an established framework. "
                "Under the Federal Arbitration Act (9 U.S.C. §2), this arbitration clause is presumptively "
                "enforceable and courts will compel arbitration absent grounds under FAA §§3-4."
            ),
        },
        {
            "question": (
                "Contract clause analysis: Does this MSA contain an IP ownership clause?\n\n"
                "Contract excerpt: All work product, inventions, and deliverables created by "
                "Service Provider under this Agreement shall be considered work-for-hire and "
                "shall be owned exclusively by Client."
            ),
            "answer": (
                "Clause identification: Work-for-hire clause vesting IP in Client.\n\n"
                "Under 17 U.S.C. §101 (Copyright Act), works created by an independent contractor "
                "qualify as 'work for hire' only if: (1) specially ordered/commissioned; and "
                "(2) falls within one of the nine enumerated categories. For software/deliverables "
                "outside those categories, an express assignment is required in addition to work-for-hire language. "
                "This clause should also address patent rights separately under 35 U.S.C. §261."
            ),
        },
        {
            "question": (
                "What are the key requirements for a valid indemnification clause under US law?\n\n"
                "Contract excerpt: Each party shall indemnify, defend, and hold harmless the other "
                "party from any third-party claims arising from its breach of this Agreement."
            ),
            "answer": (
                "This mutual indemnification clause covers third-party claims arising from breach. "
                "Key requirements for enforceability under US law: (1) clear and unequivocal language "
                "(anti-indemnity statutes in some states restrict certain indemnity provisions); "
                "(2) mutual vs. unilateral scope — mutual indemnity is generally viewed favorably; "
                "(3) insurance requirements should be coordinated; (4) IP infringement indemnity is "
                "often negotiated separately. The 'defend' obligation is distinct from 'indemnify' — "
                "it triggers a duty to assume legal defense immediately upon notice of a claim."
            ),
        },
        {
            "question": (
                "Analyze the termination for convenience clause in this SaaS agreement:\n\n"
                "Contract excerpt: Either party may terminate this Agreement for any reason "
                "upon 30 days prior written notice to the other party."
            ),
            "answer": (
                "This is a standard mutual termination for convenience (T4C) clause with 30-day notice. "
                "Under US contract law, T4C clauses are generally enforceable. Key considerations: "
                "(1) Payment obligations upon termination — accrued fees through termination date remain due; "
                "(2) Data return/destruction obligations under any applicable DPA; "
                "(3) Survival clauses — IP, confidentiality, limitation of liability typically survive; "
                "(4) 30 days may be insufficient for enterprise SaaS — 90-180 days is more typical "
                "for material contracts to allow transition. Consider adding a termination for cause "
                "provision with a cure period (typically 30 days)."
            ),
        },
    ]
    result = []
    while len(result) < max_examples:
        result += qa_pairs
    return result[:max_examples]


def load_legalbench(max_examples: int = 400) -> List[dict]:
    """Load LegalBench tasks: contract NLI, unfair terms, and statutory reasoning."""
    from datasets import load_dataset

    results = []
    tasks = [
        ("contract_nli_explicit", "text", "label"),
        ("unfair_tos", "text", "label"),
        ("cuad_affiliate_license_licensee", "text", "label"),
    ]

    for task_name, text_col, label_col in tasks:
        try:
            ds = load_dataset("nguha/legalbench", task_name, split="train")
            for ex in ds:
                text = ex.get(text_col, "")
                label = ex.get(label_col, "")
                hypothesis = ex.get("hypothesis", "")
                if not text:
                    continue
                q = (
                    f"Legal benchmark task ({task_name}):\n\n{text[:800]}"
                    + (f"\n\nHypothesis: {hypothesis}" if hypothesis else "")
                )
                results.append({"question": q, "answer": f"Classification: {label}"})
                if len(results) >= max_examples:
                    return results
        except Exception as e:
            print(f"[us_loader] LegalBench task {task_name} failed: {e}")

    return results[:max_examples]


def load_casehold(max_examples: int = 200) -> List[dict]:
    """Load CaseHOLD federal court holding identification dataset."""
    from datasets import load_dataset

    try:
        ds = load_dataset("casehold/casehold", "all", split="train")
    except Exception as e:
        print(f"[us_loader] CaseHOLD failed: {e}")
        return []

    results = []
    for ex in ds:
        prompt = ex.get("citing_prompt", "")
        label = ex.get("label", 0)
        holding_key = f"holding_{label}"
        correct_holding = ex.get(holding_key, "")
        if not prompt or not correct_holding:
            continue
        results.append({
            "question": (
                f"Based on the following legal context, identify the correct holding:\n\n"
                f"{prompt[:1000]}"
            ),
            "answer": f"The correct holding is: {correct_holding}",
        })
        if len(results) >= max_examples:
            break
    return results


def load_edgar(max_examples: int = 300) -> List[dict]:
    """Load EDGAR SEC filing corpus (10-K/8-K summaries).

    Converts risk factor disclosures into legal analysis Q&A pairs.
    """
    from datasets import load_dataset

    results = []
    try:
        # eloukas/edgar-corpus has annual reports by year
        ds = load_dataset("eloukas/edgar-corpus", "year_2020", split="train", trust_remote_code=False)
        for ex in ds:
            section = ex.get("section_1A", "") or ex.get("section_7", "")
            if not section or len(section) < 200:
                continue
            excerpt = section[:800]
            results.append({
                "question": (
                    f"Analyze the following SEC 10-K filing excerpt for legal risk factors "
                    f"and regulatory compliance issues:\n\n{excerpt}"
                ),
                "answer": (
                    f"This SEC disclosure addresses material risk factors as required under "
                    f"Regulation S-K Item 503. Key legal considerations include: regulatory compliance "
                    f"obligations, material uncertainty disclosures, and forward-looking statement safe harbors "
                    f"under the Private Securities Litigation Reform Act of 1995."
                ),
            })
            if len(results) >= max_examples:
                break
    except Exception as e:
        print(f"[us_loader] EDGAR load failed: {e}")
    return results


def load_contract_nli(max_examples: int = 150) -> List[dict]:
    """Load ContractNLI — natural language inference on contract clauses."""
    from datasets import load_dataset

    results = []
    try:
        ds = load_dataset("kiddothe2b/contract-nli", split="train", trust_remote_code=False)
        for ex in ds:
            premise = ex.get("premise", "")
            hypothesis = ex.get("hypothesis", "")
            label = ex.get("label", "")
            if not premise or not hypothesis:
                continue
            label_map = {0: "Entailment", 1: "Contradiction", 2: "Not mentioned"}
            label_text = label_map.get(label, str(label))
            results.append({
                "question": (
                    f"Contract clause: {premise[:600]}\n\n"
                    f"Hypothesis: {hypothesis}\n\n"
                    f"Does the contract clause entail, contradict, or not address the hypothesis?"
                ),
                "answer": (
                    f"{label_text}. "
                    f"{'The clause directly supports this obligation.' if label == 0 else 'The clause conflicts with or does not support this obligation.' if label == 1 else 'This obligation is not addressed in the clause.'}"
                ),
            })
            if len(results) >= max_examples:
                break
    except Exception as e:
        print(f"[us_loader] ContractNLI load failed: {e}")
    return results


def load_billsum(max_examples: int = 150) -> List[dict]:
    """Load BillSum congressional bill summarization dataset."""
    from datasets import load_dataset

    try:
        ds = load_dataset("billsum", split="train")
    except Exception as e:
        print(f"[us_loader] BillSum failed: {e}")
        return []

    results = []
    for ex in ds:
        text = ex.get("text", "")
        summary = ex.get("summary", "")
        title = ex.get("title", "Congressional Bill")
        if not text or not summary:
            continue
        results.append({
            "question": (
                f"Explain the legal implications and regulatory scope of the following "
                f"legislative text ({title}):\n\n{text[:800]}"
            ),
            "answer": (
                f"Legislative analysis: {summary}\n\n"
                f"This legislation creates legal obligations under federal statutory law. "
                f"Key compliance considerations include implementation timelines, enforcement mechanisms, "
                f"and interaction with existing regulatory frameworks."
            ),
        })
        if len(results) >= max_examples:
            break
    return results


def _synthetic_securities_qa(max_examples: int) -> List[dict]:
    """Synthetic US securities and corporate law Q&A."""
    qa_pairs = [
        {
            "question": "Explain the materiality standard for SEC disclosure under Rule 10b-5.",
            "answer": (
                "Under SEC Rule 10b-5 (17 C.F.R. §240.10b-5), materiality is defined by the "
                "Supreme Court in TSC Industries v. Northway (1976): information is material if "
                "there is a 'substantial likelihood that a reasonable shareholder would consider "
                "it important' in making an investment decision. For merger negotiations, Basic Inc. "
                "v. Levinson (1988) established a probability/magnitude test: materiality depends "
                "on the probability the transaction will occur and the anticipated magnitude of the "
                "event. Failure to disclose material information in SEC filings (Form 10-K, 8-K, "
                "proxy statements) may give rise to Section 10(b) liability and SEC enforcement action."
            ),
        },
        {
            "question": "What are the Section 16 short-swing profit recovery rules under the Securities Exchange Act of 1934?",
            "answer": (
                "Section 16 of the Securities Exchange Act of 1934 (15 U.S.C. §78p) imposes "
                "reporting and disgorgement obligations on 'insiders' (directors, officers, and >10% "
                "beneficial owners of registered equity securities). Key rules: "
                "(1) Section 16(a): Insiders must report beneficial ownership changes on Forms 3, 4, and 5. "
                "(2) Section 16(b): Short-swing profits from any purchase and sale (or sale and purchase) "
                "of the issuer's equity within any 6-month period are recoverable by the issuer. "
                "Liability is strict — intent to profit is irrelevant. Rule 16b-3 exempts certain "
                "equity compensation plan transactions from short-swing profit recovery."
            ),
        },
        {
            "question": "Describe the business judgment rule under Delaware corporate law.",
            "answer": (
                "The business judgment rule (BJR) is a rebuttable presumption under Delaware law "
                "that directors of a corporation acted on an informed basis, in good faith, and in "
                "the honest belief that the action was in the best interests of the company. "
                "(Smith v. Van Gorkom, 488 A.2d 858 (Del. 1985)). To rebut the BJR, a plaintiff must "
                "show: (1) gross negligence in the decision-making process; (2) bad faith; or "
                "(3) self-interest/conflict. Once rebutted, the burden shifts to directors to prove "
                "entire fairness (fair dealing + fair price). Revlon duties arise when a company is "
                "in the Revlon zone (sale of the company or break-up), requiring directors to maximize "
                "short-term stockholder value. Unocal scrutiny applies to defensive measures."
            ),
        },
        {
            "question": "Explain Hart-Scott-Rodino (HSR) Act pre-merger notification requirements.",
            "answer": (
                "The Hart-Scott-Rodino Antitrust Improvements Act of 1976 (15 U.S.C. §18a) requires "
                "parties to certain M&A transactions to notify the FTC and DOJ before closing if "
                "statutory thresholds are met. 2024 thresholds: Size of transaction >$119.5M; "
                "Size of person: either the acquirer or target must meet the $23.9M/$239M asset/sales tests. "
                "After filing, a 30-day waiting period applies (15 days for cash tender offers). "
                "Agencies may issue a Second Request to extend review. "
                "Failure to file carries civil penalties up to $50,120 per day of violation. "
                "Exemptions include acquisitions of foreign assets outside the US with limited nexus."
            ),
        },
        {
            "question": "What constitutes insider trading under Dirks v. SEC (1983)?",
            "answer": (
                "In Dirks v. SEC, 463 U.S. 646 (1983), the Supreme Court held that a tippee's "
                "liability for insider trading depends on whether the tipper breached a fiduciary "
                "duty for personal benefit, and whether the tippee knew or should have known of "
                "that breach. The 'personal benefit' test: a tipper benefits if they receive "
                "something of value, or if the disclosure was a gift to a trading relative or friend. "
                "United States v. Newman (2d Cir. 2014) heightened the personal benefit standard, "
                "requiring a concrete, objective benefit. However, Salman v. United States (2016) "
                "clarified that a gift of confidential information to a trading relative or friend "
                "satisfies the personal benefit test, even without a financial quid pro quo."
            ),
        },
        {
            "question": "Explain the Caremark standard for director oversight liability in Delaware.",
            "answer": (
                "The Caremark standard (In re Caremark Int'l Derivative Litigation, 698 A.2d 959 "
                "(Del. Ch. 1996)) establishes when directors face liability for failing to implement "
                "and monitor a compliance program. A successful Caremark claim requires showing: "
                "(1) directors knew they were not discharging their fiduciary obligations; or "
                "(2) directors acted in bad faith by consciously disregarding their duty to be informed. "
                "Mere negligence in oversight is insufficient. Stone v. Ritter (Del. 2006) reaffirmed "
                "that Caremark claims require showing bad faith — the most difficult theory of director "
                "liability. Post-COVID, Delaware courts have become more receptive to Caremark claims "
                "involving systematic compliance failures (e.g., Marchand v. Barnhill (2019))."
            ),
        },
        {
            "question": "What are the key terms in a standard M&A merger agreement (SPA)?",
            "answer": (
                "A standard US M&A Stock Purchase Agreement (SPA) contains: "
                "(1) Representations and Warranties: seller reps on organization, capitalization, "
                "financial statements, absence of material adverse change (MAC clause), IP, litigation; "
                "(2) Covenants: pre-closing conduct of business in ordinary course, no-shop/no-talk "
                "restrictions, regulatory approvals (HSR, CFIUS if foreign buyer); "
                "(3) Conditions to Closing: accuracy of reps (bring-down standard), no MAC, "
                "required consents, regulatory clearances; "
                "(4) Indemnification: survival periods (typically 12-18 months for general reps, "
                "longer for fundamental reps and fraud), baskets (deductible vs. first-dollar), caps; "
                "(5) Termination: MAC termination right, outside date (typically 6-12 months), "
                "reverse termination fee for buyer breach. "
                "Sandbagging provisions (pro-buyer: knowledge at closing does not limit indemnity rights) "
                "are heavily negotiated."
            ),
        },
        {
            "question": "Analyze CFIUS review requirements for foreign investment in the US under FIRRMA.",
            "answer": (
                "The Foreign Investment Risk Review Modernization Act of 2018 (FIRRMA) significantly "
                "expanded CFIUS jurisdiction under 50 U.S.C. §4565. Key provisions: "
                "(1) Mandatory declarations required for foreign government-controlled investors "
                "acquiring any interest in TID US businesses (Technology, Infrastructure, Data); "
                "(2) Expanded jurisdiction to cover non-controlling investments in TID businesses "
                "that afford access to material non-public technical information, board rights, "
                "or involvement in substantive decision-making; "
                "(3) Real estate transactions near military installations now covered; "
                "(4) Review timeline: 30-day initial review + 45-day investigation + 15-day Presidential review; "
                "(5) Penalties: up to $250,000 per violation or transaction value for material misstatements. "
                "Comparable to Japan's FEFTA regime, but CFIUS has broader discretion and no bright-line exemptions."
            ),
        },
    ]
    result = []
    while len(result) < max_examples:
        result += qa_pairs
    return result[:max_examples]


def load_all_us_datasets(shuffle: bool = True) -> List[dict]:
    """Load and combine all US training datasets (target: ~1,800 examples)."""
    TARGET = 1800

    print("[us_loader] Loading CUAD...")
    data = load_cuad()
    print(f"[us_loader] CUAD: {len(data)} examples")

    print("[us_loader] Loading EDGAR...")
    edgar = load_edgar()
    print(f"[us_loader] EDGAR: {len(edgar)} examples")
    data += edgar

    print("[us_loader] Loading LegalBench...")
    lb = load_legalbench()
    print(f"[us_loader] LegalBench: {len(lb)} examples")
    data += lb

    print("[us_loader] Loading CaseHOLD...")
    ch = load_casehold()
    print(f"[us_loader] CaseHOLD: {len(ch)} examples")
    data += ch

    print("[us_loader] Loading ContractNLI...")
    nli = load_contract_nli()
    print(f"[us_loader] ContractNLI: {len(nli)} examples")
    data += nli

    print("[us_loader] Loading BillSum...")
    bs = load_billsum()
    print(f"[us_loader] BillSum: {len(bs)} examples")
    data += bs

    # Supplement with synthetic data to reach target
    if len(data) < TARGET:
        needed = TARGET - len(data)
        print(f"[us_loader] Supplementing with {needed} synthetic examples...")
        data += _synthetic_securities_qa(needed)

    if shuffle:
        random.shuffle(data)

    print(f"[us_loader] Total US examples: {len(data)}")
    return data[:TARGET]
