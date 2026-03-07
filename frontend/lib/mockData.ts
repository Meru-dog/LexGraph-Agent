import type { DDReport, ClauseAnnotation, DiffLine } from "./types";
import { diffLines } from "./diff";

// ─── DD Agent Mock ─────────────────────────────────────────────────────────────

export const MOCK_DD_REPORT: DDReport = {
  target: "TechCorp KK",
  transaction: "¥2,000,000,000 Investment (Series C)",
  date: "March 2025",
  jurisdiction: "JP + US",
  summary: {
    critical: 1,
    high: 3,
    medium: 4,
    low: 2,
    recommendation:
      "Investment may proceed subject to resolution of the identified critical finding regarding irregular cap table entries and completion of FIEA disclosure review. Recommend 60-day remediation period before closing.",
  },
  sections: [
    {
      num: "01",
      title: "Corporate Records",
      items: [
        {
          status: "critical",
          text: "Cap table irregularities detected: 3 undisclosed share transfers between founders occurring within 12 months prior to filing. Potential violation of Companies Act Art. 128 transfer restrictions.",
        },
        {
          status: "high",
          text: "Articles of Incorporation last amended 2019 — pre-date current governance requirements under revised Companies Act (2021 amendments).",
        },
        {
          status: "ok",
          text: "Corporate registry (登記簿謄本) confirms entity in good standing. No dissolution proceedings.",
        },
        {
          status: "ok",
          text: "Board composition meets statutory minimum. Representative Director properly designated.",
        },
      ],
    },
    {
      num: "02",
      title: "Financial Information",
      items: [
        {
          status: "high",
          text: "FY2023 audit report contains going concern qualification. Auditor: Deloitte Tohmatsu LLC. Revenue ¥1.2B vs expenses ¥1.8B.",
        },
        {
          status: "medium",
          text: "Tax returns for FY2021–2022 indicate underpayment of consumption tax (消費税). Estimated exposure: ¥45M.",
        },
        {
          status: "ok",
          text: "FY2024 interim financials (unaudited) show improved EBITDA margin of 12%.",
        },
      ],
    },
    {
      num: "03",
      title: "Indebtedness",
      items: [
        {
          status: "medium",
          text: "Outstanding loan agreements with MUFG totaling ¥800M. Change of control provision triggers repayment obligation on investment close.",
        },
        {
          status: "ok",
          text: "No outstanding security interests registered in the Pledge Registry (動産・債権譲渡登記).",
        },
        { status: "ok", text: "No bond issuances or convertible notes outstanding." },
      ],
    },
    {
      num: "04",
      title: "Employment & Labor",
      items: [
        {
          status: "medium",
          text: "36-Agreement (三六協定) filed but 3 departments regularly exceeding statutory overtime caps. Potential Labor Standards Act violation.",
        },
        {
          status: "ok",
          text: "Employment agreements reviewed for 47 employees. Standard form contracts used throughout.",
        },
        { status: "ok", text: "Social insurance enrollment confirmed for all employees." },
      ],
    },
    {
      num: "05",
      title: "Real Estate",
      items: [
        {
          status: "ok",
          text: "Tokyo HQ office lease: 5-year term, expires March 2027. Renewal option exercisable 6 months prior.",
        },
        { status: "ok", text: "No real property ownership. All facilities leased." },
      ],
    },
    {
      num: "06",
      title: "Agreements & Contracts",
      items: [
        {
          status: "high",
          text: "Master service agreement with primary customer (60% of revenue) contains non-renewal clause exercisable on 30-days notice. Revenue concentration risk.",
        },
        {
          status: "medium",
          text: "IP license agreement with US counterparty lacks FATA/CFIUS notification provisions for foreign investment.",
        },
        {
          status: "ok",
          text: "Vendor contracts reviewed. No material adverse change provisions triggered by proposed investment.",
        },
      ],
    },
    {
      num: "07",
      title: "Supplier & Customer Information",
      items: [
        {
          status: "medium",
          text: "Top 3 customers represent 78% of ARR. Customer concentration above industry threshold (>50%).",
        },
        {
          status: "ok",
          text: "Supply chain agreements with 12 vendors reviewed. No single-source dependencies identified.",
        },
      ],
    },
    {
      num: "08",
      title: "Legal & Regulatory",
      items: [
        {
          status: "high",
          text: "FIEA (金融商品取引法) compliance review: Company's investor relations materials may constitute unlicensed solicitation under FIEA Art. 28. FSA inquiry risk.",
        },
        {
          status: "medium",
          text: "Data protection: 2 minor APPI (個人情報保護法) incidents reported in 2023. Internal investigation completed but no regulatory filing made.",
        },
        {
          status: "ok",
          text: "No pending litigation. No regulatory enforcement actions. No criminal investigations.",
        },
        {
          status: "ok",
          text: "Intellectual property portfolio: 12 registered patents (JP), 3 pending. No IP disputes.",
        },
      ],
    },
  ],
};

// ─── Contract Review Mock ─────────────────────────────────────────────────────

const MOCK_ORIGINAL = `SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of January 1, 2025, between LexTech Solutions Inc. ("Service Provider") and Global Corp Ltd. ("Client").

§1. SERVICES
Service Provider shall provide software development and consulting services as specified in Schedule A. Services will be delivered within 30 days of each milestone.

§2. PAYMENT TERMS
Client shall pay Service Provider USD 50,000 per month. Payment is due within 30 days of invoice. Late payments accrue interest at 5% per annum.

§3. INTELLECTUAL PROPERTY
All work product created under this Agreement shall be owned exclusively by Service Provider until full payment is received. Client receives a non-exclusive license to use deliverables.

§4. TERMINATION
Either party may terminate this Agreement with 30 days written notice. Service Provider may terminate immediately upon Client's material breach.

§5. LIABILITY
Service Provider's total liability shall not exceed the amount paid in the preceding 3 months. Neither party shall be liable for indirect or consequential damages.

§6. GOVERNING LAW
This Agreement is governed by the laws of the State of Delaware, without regard to conflict of law provisions.`;

const MOCK_REVIEWED = `SERVICE AGREEMENT

This Service Agreement ("Agreement") is entered into as of January 1, 2025, between LexTech Solutions Inc. ("Service Provider") and Global Corp Ltd. ("Client").

§1. SERVICES
Service Provider shall provide software development and consulting services as specified in Schedule A, which may be updated by mutual written consent. Services will be delivered within 30 days of each milestone, subject to Client providing timely feedback within 5 business days.

§2. PAYMENT TERMS
Client shall pay Service Provider USD 50,000 per month. Payment is due within 30 days of invoice. Late payments accrue interest at 2% per annum, not to exceed the maximum rate permitted by applicable law.

§3. INTELLECTUAL PROPERTY
All work product created under this Agreement shall be owned exclusively by Client upon full payment of all amounts due. Service Provider retains no rights to Client's confidential information or deliverables after project completion.

§4. TERMINATION
Either party may terminate this Agreement with 60 days written notice. Service Provider may terminate immediately upon Client's material breach that remains uncured for 15 business days following written notice.

§5. LIABILITY
Service Provider's total liability shall not exceed the total amount paid in the preceding 12 months. Neither party shall be liable for indirect or consequential damages, except in cases of willful misconduct or gross negligence.

§6. GOVERNING LAW
This Agreement is governed by the laws of the State of Delaware, without regard to conflict of law provisions. Any disputes shall be resolved through binding arbitration under AAA Commercial Rules.`;

export const MOCK_DIFF: DiffLine[] = diffLines(MOCK_ORIGINAL, MOCK_REVIEWED);

export const MOCK_CLAUSE_ANNOTATIONS: ClauseAnnotation[] = [
  {
    clauseRef: "§1",
    title: "SERVICES",
    risk: "ok",
    notes: "Added mutual consent requirement for scope changes and feedback SLA for Client.",
  },
  {
    clauseRef: "§2",
    title: "PAYMENT",
    risk: "ok",
    notes: "Reduced interest rate from 5% to 2% p.a., capped at statutory maximum.",
  },
  {
    clauseRef: "§3",
    title: "INTELLECTUAL PROPERTY",
    risk: "high",
    notes:
      "Original clause vests IP in Service Provider — revised to vest in Client on full payment. Critical change for Client's position.",
  },
  {
    clauseRef: "§4",
    title: "TERMINATION",
    risk: "medium",
    notes: "Extended notice period from 30 to 60 days. Added cure period for breach termination.",
  },
  {
    clauseRef: "§5",
    title: "LIABILITY",
    risk: "medium",
    notes:
      "Extended liability cap from 3 to 12 months. Added willful misconduct carve-out — consistent with Delaware case law.",
  },
  {
    clauseRef: "§6",
    title: "GOVERNING LAW",
    risk: "medium",
    notes: "Added binding arbitration clause under AAA Commercial Rules.",
  },
];

// ─── Chat Mock Responses ──────────────────────────────────────────────────────

export function getMockChatResponse(input: string): string {
  const lower = input.toLowerCase();

  if (lower.includes("会社法") || lower.includes("companies act")) {
    return `Under the **Japanese Companies Act** (会社法, Act No. 86 of 2005), directors are subject to the duty of care (善管注意義務) under **Art. 330** read together with Civil Code **Art. 644**.

Key obligations include:

1. **Duty of Care (Art. 330 / Civil Code Art. 644)** — Directors must perform their duties with the care of a good manager (善良な管理者の注意義務).
2. **Duty of Loyalty (Art. 355)** — Directors must follow laws, articles of incorporation, and shareholder resolutions in good faith.
3. **Conflict of Interest (Art. 356)** — Competing transactions require board approval and disclosure.

**Relevant provisions:**
- Companies Act Art. 355 (忠実義務)
- Companies Act Art. 423 (損害賠償責任)
- Civil Code Art. 644 (善管注意義務)`;
  }

  if (lower.includes("金商法") || lower.includes("fiea") || lower.includes("securities")) {
    return `The **Financial Instruments and Exchange Act** (金融商品取引法 / FIEA, Act No. 25 of 1948, as amended) is Japan's primary securities regulation statute, broadly analogous to the US Securities Exchange Act of 1934.

**Key regulatory requirements:**

1. **Disclosure Obligations (Art. 4, 24)** — Securities offerings require registration and periodic disclosure filings to the FSA.
2. **Prohibition on Insider Trading (Art. 166)** — Trading based on material non-public information is prohibited.
3. **Solicitation Rules (Art. 28–29)** — Financial instruments business requires FSA registration.
4. **Cross-border applicability** — Foreign issuers distributing securities in Japan are subject to FIEA disclosure requirements.

**Comparable US framework:** Securities Act of 1933 + Securities Exchange Act of 1934 + Reg S-K/S-X disclosure rules.`;
  }

  if (lower.includes("m&a") || lower.includes("merger") || lower.includes("acquisition")) {
    return `**M&A in Japan — Regulatory Framework Overview**

Key statutes governing Japanese M&A transactions:

1. **Companies Act (会社法)** — Merger procedures (Art. 748–816), share exchange/transfer (Art. 767–774), company split (Art. 757–766).
2. **FIEA (金融商品取引法)** — Tender offer rules (Art. 27-2 to 27-22) for listed company acquisitions above 5% threshold requiring mandatory TOB.
3. **Act on Prohibition of Private Monopolization (独占禁止法)** — JFTC merger notification required for transactions above statutory thresholds.
4. **Foreign Exchange Act (外為法 / FEFTA)** — Foreign investment notification for designated industries (defense, semiconductors, media, utilities).

**US parallel framework:** Hart-Scott-Rodino Act (antitrust), Williams Act (tender offers), CFIUS (foreign investment review under FIECA 2018).`;
  }

  if (lower.includes("contract")) {
    return `**Contract Law — JP/US Comparative Overview**

**Japanese Law (民法 / Civil Code):**
- General contract principles: Civil Code Art. 521–548
- Offer and acceptance: Art. 522–527
- Consideration equivalent: 約因 concept not required in Japanese law (unlike common law)
- Good faith obligation (信義則): Civil Code Art. 1(2) — pervasive good faith duty in contract performance

**US Law (Common Law / UCC):**
- Common law governs service contracts; UCC Article 2 governs goods
- Offer, acceptance, consideration required for enforceable contract
- Parol evidence rule limits extrinsic evidence of contract terms
- Implied covenant of good faith in all contracts (Restatement 2d Contracts §205)

**Key differences for cross-border drafting:**
1. Japanese courts more likely to imply obligations from good faith (信義則)
2. US contracts require explicit consideration recitals
3. Liquidated damages clauses enforceable in Japan (Art. 420) if not penal; US requires reasonable estimate`;
  }

  return `**Graph RAG Response — Legal Research**

Based on the knowledge graph traversal across **JP and US legal corpora**, here is a synthesized response:

Your query touches on principles found across multiple interconnected legal nodes in the graph. The relevant statutory framework depends on the specific jurisdiction and transaction context.

**JP Jurisdiction nodes activated:**
- 民法 (Civil Code) — foundational obligations
- 会社法 (Companies Act) — corporate governance
- 金融商品取引法 (FIEA) — securities regulation

**US Jurisdiction nodes activated:**
- Delaware General Corporation Law
- Securities Exchange Act of 1934
- Uniform Commercial Code

For a more precise response, please specify:
1. The jurisdiction (JP / US / cross-border)
2. The transaction type (M&A, investment, contract, litigation)
3. The specific legal question or article reference

*Powered by LexGraph Agent — Graph RAG + Gemini 1.5 Pro (JP/US)*`;
}
