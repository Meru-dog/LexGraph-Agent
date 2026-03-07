"""JP legal dataset loader for QLoRA fine-tuning.

Sources:
    - JLawText      — 500 examples — 会社法 · 金商法 statutes  (legalscape/jlawtext)
    - e-Gov API     — 400 examples — Current Japanese laws via elaws.e-gov.go.jp
    - JCourts       — 300 examples — Corporate case law (legalscape/jcourts)
    - Courts.go.jp  — 200 examples — Supreme Court decisions (via JCourts fallback)
    - FSA Guidance  — 200 examples — FSA regulatory guidance (synthetic from e-Gov)
    - JP Synthetic  — 200 examples — Contract Q&A pairs
    Total: ~1,800 examples
"""

from __future__ import annotations

import random
import time
from typing import List


def load_jlawtext(max_examples: int = 500) -> List[dict]:
    """Load JLawText JP statute Q&A dataset."""
    from datasets import load_dataset

    results = []
    try:
        ds = load_dataset("legalscape/jlawtext", split="train")
        for ex in ds:
            question = ex.get("question") or ex.get("input") or ex.get("text", "")
            answer = ex.get("answer") or ex.get("output") or ex.get("label", "")
            if not question or not answer:
                continue
            results.append({"question": str(question)[:800], "answer": str(answer)[:1200]})
            if len(results) >= max_examples:
                break
    except Exception as e:
        print(f"[jp_loader] JLawText load failed: {e}")
        # Generate synthetic statute Q&A from Companies Act articles
        results = _synthetic_companies_act_qa(max_examples)
    return results


def load_jcourts(max_examples: int = 500) -> List[dict]:
    """Load JCourts Japanese corporate case law dataset.

    Combines JCourts (300) + Courts.go.jp equivalent (200) as unified source.
    """
    from datasets import load_dataset

    results = []
    try:
        ds = load_dataset("legalscape/jcourts", split="train")
        for ex in ds:
            question = ex.get("question") or ex.get("input", "")
            answer = ex.get("answer") or ex.get("output", "")
            if not question or not answer:
                continue
            results.append({"question": str(question)[:800], "answer": str(answer)[:1200]})
            if len(results) >= max_examples:
                break
    except Exception as e:
        print(f"[jp_loader] JCourts load failed: {e}")
        results = _synthetic_case_law_qa(max_examples)
    return results


def load_egov_api(max_examples: int = 400) -> List[dict]:
    """Fetch Japanese statutes from e-Gov Law API and convert to Q&A pairs.

    API: https://elaws.e-gov.go.jp/api/1/lawlists/1 (all laws)
    Verify ToS at: https://elaws.e-gov.go.jp/apitop/
    """
    import httpx

    results = []
    law_numbers = [
        # Companies Act (会社法) — Act No. 86 of 2005
        "417AC0000000086",
        # Financial Instruments and Exchange Act (金融商品取引法)
        "323AC0000000025",
        # Civil Code (民法)
        "129AC0000000089",
        # Labor Standards Act (労働基準法)
        "322AC0000000049",
        # Act on Protection of Personal Information (個人情報保護法)
        "415AC0000000057",
    ]

    for law_number in law_numbers:
        if len(results) >= max_examples:
            break
        try:
            url = f"https://elaws.e-gov.go.jp/api/1/lawdata/{law_number}"
            response = httpx.get(url, timeout=15)
            if response.status_code != 200:
                continue

            data = response.json()
            law_full_text = _extract_egov_text(data)
            if not law_full_text:
                continue

            # Split into articles and create Q&A pairs
            articles = _split_into_articles(law_full_text)
            law_name = _get_law_name(data)

            for article_num, article_text in articles[:80]:
                if len(results) >= max_examples:
                    break
                if len(article_text.strip()) < 50:
                    continue
                results.append({
                    "question": f"{law_name} 第{article_num}条の内容と法的意義を説明してください。",
                    "answer": f"{law_name}第{article_num}条は次のように規定しています：\n\n{article_text.strip()}\n\nこの条文は、{_generate_article_context(law_name, article_num)}に関する重要な規定です。",
                })
            time.sleep(0.5)  # Rate limiting
        except Exception as e:
            print(f"[jp_loader] e-Gov API failed for {law_number}: {e}")

    if len(results) < max_examples:
        # Supplement with synthetic FSA guidance examples
        results += _synthetic_fsa_qa(max_examples - len(results))

    return results[:max_examples]


def _extract_egov_text(data: dict) -> str:
    """Extract article text from e-Gov API response."""
    try:
        law_body = data.get("law", {}).get("lawBody", {})
        main_provision = law_body.get("mainProvision", {})
        # Flatten the nested XML-like structure
        return str(main_provision)[:10000]
    except Exception:
        return ""


def _split_into_articles(text: str) -> list[tuple[str, str]]:
    """Extract article numbers and text from Japanese statute text."""
    import re
    articles = []
    # Match 第N条 patterns
    pattern = re.compile(r"第(\d+)条[　\s]*(.*?)(?=第\d+条|$)", re.DOTALL)
    for match in pattern.finditer(text):
        article_num = match.group(1)
        article_text = match.group(2).strip()[:600]
        if article_text:
            articles.append((article_num, article_text))
    return articles[:100]


def _get_law_name(data: dict) -> str:
    try:
        return data.get("law", {}).get("lawBody", {}).get("lawTitle", "法律")
    except Exception:
        return "法律"


def _generate_article_context(law_name: str, article_num: str) -> str:
    context_map = {
        "会社法": "株式会社の組織・運営・管理",
        "金融商品取引法": "金融商品の取引規制・投資家保護",
        "民法": "私人間の権利義務関係",
        "労働基準法": "労働者の権利保護・労働条件",
        "個人情報保護法": "個人情報の適切な取扱い",
    }
    for key, ctx in context_map.items():
        if key in law_name:
            return ctx
    return "法的権利義務"


def _synthetic_companies_act_qa(max_examples: int) -> List[dict]:
    """Synthetic Q&A pairs based on key Companies Act provisions."""
    qa_pairs = [
        {
            "question": "会社法第355条に定める取締役の忠実義務とはどのようなものですか？",
            "answer": "会社法第355条は、取締役に対し「法令及び定款並びに株主総会の決議を遵守し、株式会社のため忠実にその職務を行わなければならない」と定めています（忠実義務）。この忠実義務は、善管注意義務（民法第644条）と並ぶ取締役の基本的義務であり、取締役が自己または第三者の利益を会社の利益に優先させてはならないことを意味します。違反した場合、取締役は会社法第423条に基づき損害賠償責任を負います。",
        },
        {
            "question": "会社法上の利益相反取引（第356条）の規制内容を説明してください。",
            "answer": "会社法第356条は、取締役が会社と取引をしようとする場合（直接取引）または取締役が第三者のために会社と取引をしようとする場合（間接取引）に、取締役会の承認が必要であることを規定しています。承認を受けなかった取引は、会社は第三者に対して無効を主張できますが、善意の第三者には対抗できません。また、取引後は重要な事実を取締役会に報告する義務があります（同条第2項）。",
        },
        {
            "question": "株主代表訴訟（会社法第847条）の制度と要件を説明してください。",
            "answer": "株主代表訴訟は、取締役・監査役等の役員が会社に損害を与えた場合に、株主が会社に代わって訴訟を提起できる制度です（会社法第847条）。要件は：①6ヶ月前から引き続き株式を保有していること（公開会社の場合）、②会社に対して書面で提訴請求をすること、③会社が60日以内に訴訟を提起しないこと、です。勝訴した場合、弁護士費用等を会社に請求できます（同条第6項）。非公開会社では保有期間要件はありません。",
        },
        {
            "question": "金融商品取引法（FIEA）第166条のインサイダー取引規制について説明してください。",
            "answer": "金融商品取引法第166条は、会社関係者（役員・従業員等）が、その職務上知り得た重要事実（業績の重要な変動、M&A、重要な訴訟等）が公表される前に、当該会社の有価証券の取引を行うことを禁止しています。違反した場合、5年以下の懲役もしくは500万円以下の罰金、または両方が科されます（第197条の2）。「重要事実」の判断基準は、投資者の投資判断に著しい影響を与える事実かどうかです。",
        },
        {
            "question": "会社法における取締役の善管注意義務（第330条・民法第644条）の具体的内容は？",
            "answer": "会社法第330条は取締役と会社の関係に民法の委任規定を準用しており、民法第644条により取締役は「善良な管理者の注意義務」（善管注意義務）を負います。これは、取締役の地位・職種に応じて要求される標準的な注意義務であり、単なる自己の財産に対する注意より高い水準が求められます。具体的には、①十分な情報収集・調査、②合理的な判断プロセス、③法令・定款の遵守が要求されます。最高裁は、取締役の経営判断については一定の裁量を認めていますが、著しく不合理な判断は義務違反となります。",
        },
        {
            "question": "三六協定（労働基準法第36条）の締結要件と法的効果を説明してください。",
            "answer": "三六協定（36協定）とは、使用者が時間外労働・休日労働を命じるために、労働基準法第36条に基づき労働者の過半数代表との書面による協定を締結し、労働基準監督署に届け出ることで成立します。協定なく時間外労働をさせた場合、6ヶ月以下の懲役または30万円以下の罰金が科されます（第119条）。2019年の法改正により、時間外労働の上限規制が強化され、原則として月45時間・年360時間が上限となりました（特別条項付き協定でも年720時間が絶対的上限）。",
        },
        {
            "question": "個人情報保護法（APPI）における「要配慮個人情報」の取扱い規制を説明してください。",
            "answer": "個人情報保護法（令和2年改正）における「要配慮個人情報」とは、人種、信条、社会的身分、病歴、犯罪歴、身体・精神障害等、その取扱いによって本人に不当な差別・偏見が生じる可能性のある個人情報です（第2条第3項）。取得には本人の同意が原則必要であり（第20条第2項）、第三者提供も原則禁止です（第27条第2項）。オプトアウト手続による第三者提供も認められません。違反には個人情報保護委員会による是正勧告・命令、および100万円以下の罰金が科されます（第178条）。",
        },
        {
            "question": "外国為替及び外国貿易法（外為法）における対内直接投資規制の概要を説明してください。",
            "answer": "外為法（外国為替及び外国貿易法）は、安全保障等の観点から、外国投資家が指定業種（防衛、原子力、航空、宇宙、サイバーセキュリティ、半導体等）の国内企業に1%以上の出資をする場合に、原則として事前届出を義務付けています（第26条）。2019年の法改正により対象業種が大幅に拡大され、IT・通信、メディア等も追加されました。届出後、審査期間（通常30日、延長可）内に投資の中止・変更を命じられる可能性があります。米国のCFIUS制度と比較すると、審査の透明性・予測可能性において改善が進んでいます。",
        },
    ]

    result = []
    while len(result) < max_examples:
        result += qa_pairs
    return result[:max_examples]


def _synthetic_case_law_qa(max_examples: int) -> List[dict]:
    """Synthetic Q&A based on landmark Japanese corporate law cases."""
    qa_pairs = [
        {
            "question": "最高裁が示した取締役の経営判断原則（経営判断の原則）について説明してください。",
            "answer": "日本の裁判所は、取締役の経営判断に対して「経営判断の原則」を適用し、一定の裁量を認めています。最高裁平成22年7月15日判決では、取締役の判断が「著しく不合理」でない限り善管注意義務違反とはならないと示しました。判断基準は：①判断の基礎となった情報収集が合理的か、②判断プロセスが合理的か、③結果としての判断内容が著しく不合理でないか、の3点です。米国デラウェア州法のビジネス・ジャッジメント・ルールに類似しますが、日本では明文規定はなく判例法理として発展しています。",
        },
        {
            "question": "取締役の競業避止義務（会社法第356条第1項第1号）と違反した場合の効果は？",
            "answer": "会社法第356条第1項第1号は、取締役が自己または第三者のために会社の事業の部類に属する取引をしようとする場合、取締役会設置会社では取締役会の承認を要求しています。これが「競業避止義務」です。承認なく競業取引を行った場合、①その取引によって取締役または第三者が得た利益は会社の損害と推定されます（会社法第423条第2項）、②損害賠償責任を負います、③場合によっては解任事由となります。退任後の競業については、会社法上の制限はなく、特約による対応が必要です。",
        },
        {
            "question": "消費者契約法上の不当条項規制について説明してください。",
            "answer": "消費者契約法は、事業者と消費者の情報・交渉力格差を踏まえ、不当な契約条項を無効とします。主な無効条項として：①事業者の損害賠償責任の全部免除条項（第8条）、②消費者の解除権を放棄させる条項（第8条の2）、③消費者に過大な違約金を課す条項（第9条）、④消費者の利益を一方的に害する条項（第10条・一般条項）があります。第10条の適用には、①任意規定より消費者の権利を制限/義務を加重する、②信義則に反して消費者の利益を一方的に害する、の両要件が必要です（最高裁平成23年7月15日判決参照）。",
        },
    ]
    result = []
    while len(result) < max_examples:
        result += qa_pairs
    return result[:max_examples]


def _synthetic_fsa_qa(max_examples: int) -> List[dict]:
    """Synthetic FSA regulatory guidance Q&A."""
    qa_pairs = [
        {
            "question": "金融庁の監督指針における反社会的勢力排除の要求事項を説明してください。",
            "answer": "金融庁の「金融機関等向けの総合的な監督指針」は、金融機関に対し反社会的勢力との関係遮断を求めています。具体的には：①反社会的勢力対応部署の設置、②反社会的勢力に関するデータベースの整備と取引審査での活用、③既存取引先の反社チェック、④契約書への暴力団排除条項の導入、が求められます。反社会的勢力に該当することが判明した場合、当該取引を解消する方針の明確化も必要です。違反した場合、業務改善命令（金融商品取引法第51条等）の対象となり得ます。",
        },
        {
            "question": "FIEA（金融商品取引法）上の適合性の原則（第40条）とは何ですか？",
            "answer": "金融商品取引法第40条の適合性の原則は、金融商品取引業者が顧客の知識・経験・財産状況・投資目的に照らして不適当な勧誘を行ってはならないことを規定しています。最高裁（平成17年7月14日）は、適合性原則への著しい違反は不法行為（民法第709条）上の違法となりうると判示しています。実務上は：①顧客の属性把握（KYC）、②商品リスクの説明義務（第37条の3）、③自己責任原則との均衡が重要です。特に高齢者・投資経験のない顧客への複雑なデリバティブ商品等の勧誘は、違法と判断されるリスクが高くなります。",
        },
    ]
    result = []
    while len(result) < max_examples:
        result += qa_pairs
    return result[:max_examples]


def load_all_jp_datasets(shuffle: bool = True) -> List[dict]:
    """Load and combine all JP training datasets (target: ~1,800 examples)."""
    print("[jp_loader] Loading JLawText...")
    data = load_jlawtext(500)
    print(f"[jp_loader] JLawText: {len(data)} examples")

    print("[jp_loader] Loading e-Gov API statutes...")
    egov = load_egov_api(400)
    print(f"[jp_loader] e-Gov: {len(egov)} examples")
    data += egov

    print("[jp_loader] Loading JCourts case law...")
    courts = load_jcourts(500)
    print(f"[jp_loader] JCourts: {len(courts)} examples")
    data += courts

    # Supplement to reach 1,800 if external datasets unavailable
    target = 1800
    if len(data) < target:
        print(f"[jp_loader] Supplementing with synthetic data ({target - len(data)} examples)...")
        data += _synthetic_companies_act_qa(min(400, target - len(data)))
        data += _synthetic_fsa_qa(min(200, target - len(data)))

    if shuffle:
        random.shuffle(data)

    print(f"[jp_loader] Total JP examples: {len(data)}")
    return data[:target]
