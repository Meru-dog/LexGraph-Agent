"""Generate legal domain training data for fine-tuning.

Creates JSONL training examples covering:
- JP/US due diligence analysis
- Contract clause review
- Regulatory compliance questions
- Risk assessment
"""

import json
import os

TRAINING_EXAMPLES = [
    {
        "instruction": "Analyze this contract clause for legal risk: 'The Service Provider retains all intellectual property created during the engagement.'",
        "output": "RISK: HIGH\n\nThis IP assignment clause is highly unfavorable to the client (buyer/licensee).\n\nKey issues:\n1. All IP created during the engagement remains with the Service Provider — client receives no ownership rights\n2. Under US law (work-for-hire doctrine), this is enforceable but unusual in consulting agreements\n3. Under JP law (会社法 Art. 35, 職務発明 特許法 Art. 35), employees' inventions made during employment belong to employer, but contractor arrangements differ\n\nRecommended redline: 'All intellectual property created specifically for Client pursuant to this Agreement shall be assigned to Client upon full payment of fees, with a perpetual license retained by Service Provider for internal use only.'"
    },
    {
        "instruction": "What are the key areas to investigate in a JP M&A due diligence for a technology company?",
        "output": "For a Japanese technology M&A target, prioritize:\n\n1. CORPORATE (§01): Verify 登記簿謄本 (corporate registry), articles of incorporation (定款), board minutes, share register\n2. FINANCIAL (§02): Review 有価証券報告書 (annual report via EDINET), financial statements, audit reports, tax returns (過去3期分)\n3. IP & TECHNOLOGY (§03): Patent/trademark filings, source code ownership, OSS license compliance, cybersecurity posture\n4. EMPLOYMENT (§04): Labor contracts, 就業規則 (work rules), union agreements, key person risk\n5. REGULATORY (§05): 金商法 compliance (if listed), industry-specific licenses (e.g., 電気通信事業法, 個人情報保護法)\n6. CONTRACTS (§06): Major customer/vendor agreements, change-of-control provisions, exclusivity clauses\n7. LITIGATION (§07): Court records, 公正取引委員会 investigations, pending claims\n8. DATA/PRIVACY (§08): 個人情報保護法 compliance, data transfer agreements, breach history"
    },
    {
        "instruction": "A company has filed 5 ad-hoc disclosure reports (臨時報告書) in the past 6 months. What does this indicate?",
        "output": "RISK SIGNAL: HIGH\n\nFive 臨時報告書 (ad-hoc reports) in 6 months is above average and warrants investigation. These reports are required under 金融商品取引法 (FIEA) Art. 24-5 for material events including:\n\n- Changes in management (director/officer appointments/resignations)\n- Material litigation or regulatory investigations\n- Asset disposals or acquisitions exceeding 10% of total assets\n- Changes to capital structure (capital increases, share buybacks)\n- Bankruptcy of major subsidiaries or affiliates\n\nDue diligence recommendation:\n1. Obtain all 5 reports from EDINET and classify each by event type\n2. Flag any regulatory investigations or litigation disclosures for legal review\n3. Assess whether management turnover is a red flag for governance issues\n4. Cross-reference with board minutes and press releases for consistency\n5. Verify no undisclosed material events exist between filings"
    },
    {
        "instruction": "Review this liability clause: 'Neither party shall be liable for any indirect, consequential, or punitive damages, and total liability shall not exceed $5,000 regardless of the nature of the claim.'",
        "output": "RISK: CRITICAL\n\nThis liability cap is extremely unfavorable to the client and may be unenforceable.\n\nIssues:\n1. $5,000 cap is likely insufficient — should be minimum 12 months of contract value\n2. 'Regardless of nature of claim' could exclude liability for willful misconduct and gross negligence — courts in both JP and US often void such broad exclusions\n3. Under JP law (民法 Art. 548-2), unconscionable limitation clauses may be unenforceable as standard contract terms\n4. Under US law, liability caps for gross negligence/fraud are against public policy in most states\n5. No carve-outs for IP infringement, data breach, or confidentiality violations — standard exceptions in well-drafted MSAs\n\nRecommended redline: 'Total liability shall not exceed the greater of (a) fees paid in the 12 months preceding the claim or (b) $100,000. This limitation shall not apply to: (i) willful misconduct; (ii) gross negligence; (iii) IP infringement; (iv) data breaches; or (v) confidentiality violations.'"
    },
    {
        "instruction": "What financial metrics should be analyzed from SEC 10-K filings during M&A due diligence?",
        "output": "Key financial metrics from 10-K analysis:\n\nPROFITABILITY:\n- Revenue growth CAGR (3-5 year trend)\n- Gross margin and operating margin trends\n- EBITDA and adjusted EBITDA (watch for aggressive add-backs)\n- Net income and EPS (diluted)\n\nLIQUIDITY & SOLVENCY:\n- Current ratio and quick ratio\n- Cash and equivalents vs. current liabilities\n- Free cash flow (OCF minus capex)\n- Debt/EBITDA leverage ratio (>4x = elevated risk)\n\nRED FLAGS:\n- Revenue recognition policy changes (ASC 606 restatements)\n- Significant related-party transactions (Item 13)\n- Going concern qualifications in auditor's report\n- Material weaknesses in internal controls (SOX 302/404)\n- Goodwill impairments (may signal overvaluation of prior acquisitions)\n- Significant off-balance sheet obligations (operating leases under ASC 842)\n\nFOR JAPANESE TARGETS (有価証券報告書):\n- 連結 vs 単体 financials (consolidated vs standalone)\n- Pension/退職給付債務 obligations\n- 持合い株式 (cross-shareholding) value and concentration risk"
    },
    {
        "instruction": "Explain the key differences between JP and US termination provisions in employment agreements.",
        "output": "JP vs US Employment Termination — Key Differences:\n\nJAPAN (労働契約法・労働基準法):\n1. STRONG employee protections — termination requires 'objectively reasonable grounds' (労働契約法 Art. 16)\n2. 30 days advance notice required or payment in lieu (労働基準法 Art. 20)\n3. 整理解雇 (layoffs for business reasons) requires 4 elements: business necessity, exhaustion of alternatives, reasonable selection criteria, good-faith negotiation\n4. Probationary termination (試用期間) easier but still requires reasonable grounds after 14+ days\n5. Employment tribunals (労働審判) relatively fast (3 hearings typically)\n\nUSA (varies by state):\n1. At-will employment in most states — can terminate for any non-discriminatory reason\n2. Exceptions: WARN Act (60 days notice for mass layoffs 100+ employees), Title VII, ADEA, ADA\n3. California: stricter — WARN Act applies at 75 employees, stronger wrongful termination claims\n4. Severance: no statutory requirement but contract/policy drives expectations\n5. Non-compete enforceability varies significantly by state (void in CA, limited in MA, IL)\n\nDD IMPLICATION: For JP acquisitions, assume higher employment cost and longer restructuring timeline. Budget for 退職加算金 (severance premium) of 3-24 months salary for key employees."
    },
]


def generate_data(output_path: str = "fine_tune/data/legal_qa.jsonl", extra_examples: int = 0) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    examples = TRAINING_EXAMPLES[:]
    with open(output_path, "w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"Generated {len(examples)} training examples → {output_path}")


if __name__ == "__main__":
    generate_data()
