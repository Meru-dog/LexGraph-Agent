# LexGraph AI — 要件定義書

> **バージョン:** 3.1
> **作成日:** 2026年3月
> **更新日:** 2026年4月
> **ステータス:** 実装完了
> **実装ツール:** Claude Code
> **機密区分:** 社内限定
> **変更点（v3.0→v3.1）:** §12.1 ベースモデルをQwen2.5-1.5B-Instructに更新・Mac MPS対応を明記、§12.5 学習コードを実装済みtrain_lora.pyに刷新、§13.2 evaluate_finetune.pyによるFT前後比較の追記、§21 リポジトリ構成をfine_tune/の実構造に更新

---

## 目次

1. [プロダクト概要](#1-プロダクト概要)
2. [設計方針・制約条件](#2-設計方針制約条件)
3. [技術スタック](#3-技術スタック)
4. [システムアーキテクチャ](#4-システムアーキテクチャ)
5. [フロントエンド要件](#5-フロントエンド要件)
6. [バックエンド・API要件](#6-バックエンドapi要件)
7. [Graph RAG設計](#7-graph-rag設計)
8. [Self-Routeルーター](#8-self-routeルーター)
9. [LangGraphエージェント設計](#9-langgraphエージェント設計)
10. [メタデータ管理](#10-メタデータ管理)
11. [RAGAS評価基盤](#11-ragas評価基盤)
12. [ファインチューニング設計](#12-ファインチューニング設計)
13. [W&B実験管理](#13-wb実験管理)
14. [Neo4j知識グラフスキーマ](#14-neo4j知識グラフスキーマ)
15. [ローカルLLM設計](#15-ローカルllm設計)
16. [データ・ストレージ設計](#16-データストレージ設計)
17. [インフラ・実行環境](#17-インフラ実行環境)
18. [セキュリティ・情報管理](#18-セキュリティ情報管理)
19. [開発フェーズ](#19-開発フェーズ)
20. [リスク・未解決事項](#20-リスク未解決事項)
21. [リポジトリ構成](#21-リポジトリ構成)

---

## 1. プロダクト概要

### 1.1 プロダクト名

**LexGraph AI** — 法律事務所向けAI法律調査・ワークフロー自動化プラットフォーム

### 1.2 解決する課題

日本の法律事務所において、以下の業務は高度な専門知識と大量の時間を要します。

- 日米クロスボーダー取引における法令・判例の横断調査
- M&A・投資案件のデューデリジェンス（DD）レポート作成
- 契約書のリスク分析・修正提案（赤線入れ）

LexGraph AIはこれらを**AIが補助する**ことで、弁護士の業務効率を大幅に向上させます。

### 1.3 コア機能（3つ）

```
① 法律調査チャット
   自然言語で日本法・米国法を横断的に検索
   Graph RAG + ローカルLLMが条文引用付きで回答

② DDエージェント
   「TechCorp KKへの投資DDをお願いします」と入力するだけ
   → CFI形式8セクションのDDレポートを自動生成
   → 弁護士によるレビュー・承認フロー付き

③ 契約書レビューエージェント
   契約書をアップロード
   → AIが弁護士として条項リスクを分析・赤線修正を提案
   → GitHub形式のdiffビューアで変更を確認
```

### 1.4 対象ユーザー

- 日米クロスボーダー取引を扱う法律事務所の弁護士・アソシエイト
- M&Aデューデリジェンスを担当するリーガルチーム
- 契約書のドラフト・交渉を担当するチーム

### 1.5 対象管轄

- **日本法（JP）:** 会社法・金商法・民法・労働法・特許法・FSA規制
- **米国法（US）:** 証券取引法・デラウェア会社法・連邦判例・SEC規制

---

## 2. 設計方針・制約条件

### 2.1 最重要原則：機密情報の外部送信禁止

```
禁止事項:
  依頼者の契約書・案件情報を外部LLM API（OpenAI / Anthropic / Google等）
  に送信してはならない

許可事項:
  ① ローカルLLM（Ollama）による推論 ← 機密文書の処理はこれのみ
  ② GCS / Supabase Storage へのファイル保管
     （Google Driveと同等の法的保護。保管≠LLM処理）
  ③ 公開情報（法令・判例）の取得にクラウドAPIを使用すること
```

**根拠:** 弁護士職務基本規程18条（守秘義務）。GCSはファイルの「保管場所」であり、LLMがデータを「読んで処理する」外部APIとは法的に区別される。

### 2.2 ファインチューニング方針：コスト最適化型

「ファインチューニングを一切しない」ではなく、**「コストと効果を検証しながら必要なものだけ実施する」** 方針を採用する。

```
基本原則:
  ① Graph RAG + プロンプト設計で解決できるものはFTしない
  ② RAGASで品質ギャップが定量的に確認できたものだけFTする
  ③ W&Bで実験を管理し、コスト・効果を可視化してから判断する
  ④ 1回の学習コストを最小化する（QLoRA / 小規模データから開始）
```

**ファインチューニングを実施する対象（優先度順）:**

| 優先度 | 対象 | 理由 | 実施フェーズ |
|---|---|---|---|
| **HIGH** | JP adapter（Swallow-8B + 会社法・金商法） | 日本法律文体・要件事実構造の出力品質 | Phase 4 |
| **HIGH** | US adapter（LLaMA 3.1 + CUAD・LegalBench） | 英語契約書条項分類の精度 | Phase 4 |
| **MEDIUM** | 契約書レビュー特化adapter | 赤線提案の文体品質 | Phase 5（要評価） |
| **LOW** | DD報告書フォーマット adapter | CFI形式出力の一貫性 | Phase 5（要評価） |

**実施しない条件:**

```
以下の場合はFTを中止・延期する:
  → W&BのRAGAS比較でFT前後のFaithfulnessが+5%未満
  → 1回の学習コストが期待品質改善に見合わない
  → Graph RAG改善で同等の品質が達成できた
```

**学習データ方針（公開データのみ使用）:**

Phase 4では依頼者データを一切使わない。公開データセットのみ。

```
US（1,800件）: CUAD(600) + Edgar-Corpus(300) + LegalBench(400)
               + CaseHOLD(200) + ContractNLI(150) + BillSum(150)

JP（1,800件）: JLawText会社法・金商法(500) + e-Gov API(400)
               + JCourts商事判例(300) + Courts.go.jp最高裁(200)
               + FSA規制(200) + JP契約書テンプレート合成(200)
```

### 2.3 段階的実装方針

過剰設計を避け、**動くものを先に作り、必要に応じて複雑化する**。各フェーズに明確な終了条件を設ける。

---

## 3. 技術スタック

| レイヤー | 技術 | 選定理由 |
|---|---|---|
| **フロントエンド** | Next.js 14 (App Router) + Tailwind CSS | App RouterのSSE対応・型安全性 |
| **API** | FastAPI (Python 3.11) | 非同期処理・SSEストリーミング |
| **グラフDB** | Neo4j 5.x (AuraDB or Docker) | 条文間リレーション・多段推論 |
| **ベクトルストア** | Supabase pgvector (MVP) → Weaviate (本番) | Supabase統合・SQL操作 |
| **ローカルLLM** | Qwen3 Swallow 8B RL（Ollama） | 日本語SoTA・Apache 2.0・Thinkingモード |
| **埋め込みモデル** | multilingual-e5-large | 日英統合ベクトル化 |
| **エージェント** | LangGraph | 状態管理・並列実行・human interrupt |
| **NER** | spaCy + ja_ginza (JP) / en_core_web_trf (US) | 固有表現抽出→グラフノード自動生成 |
| **ストレージ** | Supabase Storage（文書）/ GCS（学習データ） | 用途別使い分け |
| **認証・DB** | Supabase Auth + PostgreSQL | JWT・OAuth・pgvector統合 |
| **コンテナ** | Docker Compose (MVP) → Kubernetes (本番) | 再現性・スケール |
| **RAG評価** | RAGAS | Faithfulness自動測定 |
| **実験管理** | W&B（Weights & Biases） | 学習・RAG実験の可視化・比較・コスト管理 |
| **学習フレームワーク** | HuggingFace transformers + peft + trl | QLoRA学習・アダプター管理 |
| **学習インフラ** | Google Colab Pro+（テスト） / Vertex AI A100（本番） | Bootcampクレジット活用 |

---

## 4. システムアーキテクチャ

```
┌──────────────────────────────────────────────────────────────┐
│                      フロントエンド                           │
│           Next.js 14 (App Router) + Tailwind CSS            │
│  [Chat] [DD Agent] [Contract Review] [Knowledge Graph] [Upload]│
└─────────────────────────┬────────────────────────────────────┘
                          │ REST / SSE
┌─────────────────────────▼────────────────────────────────────┐
│                    APIゲートウェイ                            │
│                  FastAPI (Python 3.11)                       │
│        /chat  /upload  /agent/dd  /agent/review  /graph      │
└──────┬──────────────────┬────────────────────┬───────────────┘
       │                  │                    │
┌──────▼──────┐  ┌────────▼───────┐  ┌────────▼──────────────┐
│ Self-Route  │  │ LangGraph      │  │ ローカルLLM層          │
│ ルーター    │  │ エージェント   │  │                       │
│             │  │                │  │ Qwen3 Swallow 8B RL   │
│ ルールベース│  │ ┌────────────┐ │  │ (Ollama / localhost)  │
│ +複雑度判定 │  │ │ DD Agent   │ │  │                       │
│             │  │ └────────────┘ │  │ Thinkingモード:       │
│             │  │ ┌────────────┐ │  │   DDレポート生成      │
│             │  │ │ Contract   │ │  │   契約書レビュー      │
│             │  │ │ Agent      │ │  │                       │
│             │  │ └────────────┘ │  │ Non-thinkingモード:   │
└──────┬──────┘  └────────────────┘  │   通常QA・検索        │
       │                             └───────────────────────┘
┌──────▼──────────────────────────────────────────────────────┐
│                  Graph RAG Engine                           │
│                                                             │
│  HybridRetriever:                                           │
│    ① ベクトル検索 (pgvector/Weaviate, top-k=10)            │
│    ② キーワード検索 (条文番号・固有名詞完全一致)            │
│    ③ グラフ探索 (Neo4j 2ホップBFS)                        │
│    ④ CrossEncoderリランキング                               │
└──────┬──────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                      データ層                                │
│                                                             │
│  Neo4j            │  Supabase pgvector  │  Supabase Storage │
│  (知識グラフ)     │  (ベクトル検索)     │  (文書ファイル)  │
│  法令/判例/概念   │  意味検索インデックス│  PDF/DOCX原本    │
│  リレーション管理 │                     │                   │
└──────┬──────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│              メタデータ管理 + RAGAS評価層                    │
│                                                             │
│  メタデータ:  law_name / article_no / effective_date /      │
│              status(ACTIVE/ARCHIVED) / version / jurisdiction│
│  RAGAS:      Faithfulness / Answer Relevancy /              │
│              Context Precision / Context Recall             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. フロントエンド要件

### 5.1 デザイントークン

```css
/* カラー */
--primary:        #2D4FD6;
--navy:           #1E3A5F;
--accent:         #4F46E5;
--text-primary:   #111827;
--text-secondary: #374151;
--text-muted:     #6B7280;
--border:         #E5E7EB;
--bg-page:        #F5F6F8;
--bg-card:        #FFFFFF;
--bg-subtle:      #F9FAFB;
--indigo-light:   #EEF2FF;

/* リスクカラー */
--critical:  #DC2626;  --critical-bg: #FEF2F2;  --critical-border: #FECACA;
--high:      #EA580C;  --high-bg:     #FFF7ED;  --high-border:     #FED7AA;
--medium:    #D97706;  --medium-bg:   #FEFCE8;  --medium-border:   #FDE68A;
--ok:        #16A34A;  --ok-bg:       #F0FDF4;  --ok-border:       #BBF7D0;
```

```
フォント（Google Fonts）:
  DM Serif Display       → ブランド・レポートタイトル
  IBM Plex Sans 300/400/500/600 → ボディテキスト
  IBM Plex Mono 400/500  → 条文番号・ステータスバッジ・diff表示
```

### 5.2 グローバルレイアウト

```
┌──────────────┬────────────────────────────────────────────┐
│ サイドバー   │  メインコンテンツエリア                    │
│ (220px固定)  │  (flex 1, bg: #F5F6F8)                    │
│              │                                            │
│ LexGraph AI  │  [ページごとのコンテンツ]                 │
│ (DM Serif)   │                                            │
│              │                                            │
│ 💬 Chat      │                                            │
│ 🔍 DD Agent  │                                            │
│ 📄 Contract  │                                            │
│ 🕸  Graph    │                                            │
│ ⬆  Upload   │                                            │
│              │                                            │
│ [管轄バッジ] │                                            │
│ JP / US /    │                                            │
│ JP+US        │                                            │
└──────────────┴────────────────────────────────────────────┘
```

**サイドバー詳細:**

| 要素 | 仕様 |
|---|---|
| 背景 | `#FFFFFF`、右ボーダー `1px #E5E7EB` |
| ナビ・通常 | `#6B7280` テキスト、透明背景、`2px solid transparent` 左ボーダー |
| ナビ・ホバー | `#F1F3F8` 背景 |
| ナビ・アクティブ | `#EEF2FF` 背景、`#2D4FD6` テキスト、`2px solid #2D4FD6` 左ボーダー |
| スクロールバー | 幅5px、`#D1D5DB` サム、`#F1F3F5` トラック、3px radius |

### 5.3 Chatページ（ホーム画面 `/`）

ChatGPT / Claude形式のメッセージスレッド。SSEストリーミングでトークン逐次表示。

| コンポーネント | 仕様 |
|---|---|
| **ページヘッダー** | タイトル「Legal Research Chat」+ サブタイトル。右側にトピックチップ（会社法 / 金商法 / M&A / 契約） |
| **トピックチップ** | クリックで入力欄に「{トピック}について説明してください」を自動入力 |
| **ユーザーバブル** | 右側。`#2D4FD6` 背景、白テキスト、10px radius |
| **AIバブル** | 左側。白背景、`#374151` テキスト、`1px #E5E7EB` ボーダー、shadow |
| **タイピングインジケーター** | `#2D4FD6` の3ドット、CSSアニメーション（0.2s stagger） |
| **入力エリア** | 固定bottom。Textarea（自動リサイズ、最大6行）+ 送信ボタン |
| **キーボード** | Enter送信、Shift+Enter改行 |
| **ルーティング表示** | 「このクエリをDDエージェントに転送しました」等のルーティング結果をAIバブルで表示 |

### 5.4 DD Agentページ（`/dd`）

2カラム構成：左296px固定パネル + 右フレキシブルパネル。

**左パネル:**

| コンポーネント | 仕様 |
|---|---|
| **プロンプト入力** | テキストエリア（84px min-height）。例:「TechCorp KKへの¥2B投資のDDをお願いします」 |
| **管轄トグル** | JP / US / JP+US。アクティブ: `#EEF2FF` 背景、`#4F46E5` テキスト |
| **実行ボタン** | 全幅、`#2D4FD6`。ローディング中は「⟳ Running DD Agent...」 |
| **ワークフローステッパー** | 8ステップ。PENDING（グレー）/ ACTIVE（インディゴ・パルス）/ DONE（チェック）。各ステップ850msで進行 |

**ワークフロー8ステップ:**

| # | ラベル | 詳細 |
|---|---|---|
| 1 | Scope Planning | 取引種別・管轄ルーティング |
| 2 | Corporate Records Review | 法人登記・定款・株主名簿 |
| 3 | Financial Information | 財務諸表・税務申告書 |
| 4 | Indebtedness Review | 借入・担保・保証 |
| 5 | Employment & Labor | 役員・労働協約・三六協定 |
| 6 | Agreements & Contracts | 重要契約・知的財産 |
| 7 | Regulatory & Legal | FSA・訴訟・許認可 |
| 8 | Risk Synthesis & Report | リスクマトリクス集約・レポート生成 |

**右パネル — DDレポート:**

| 要素 | 仕様 |
|---|---|
| **レポートヘッダーカード** | 対象企業名（DM Serif 27px）+ 取引概要 + Export PDF |
| **メタデータグリッド** | 4列: 作成者 / 作成日 / 管轄 / 総件数 |
| **リスクバッジ行** | CRITICAL / HIGH / MEDIUM / LOW / OK の件数ピル |
| **推奨事項** | `#FFFBEB` 背景、`#FDE68A` ボーダー |
| **8セクションアコーディオン** | デフォルト: §01と§08が展開。各行にステータスバッジ（CRITICAL/HIGH/MEDIUM/OK） |
| **免責事項** | 「Attorney Review Required」ウォーニング |

**CFIフォーマット8セクション:**

| # | セクション |
|---|---|
| 01 | 法人登記・組織 |
| 02 | 財務情報 |
| 03 | 負債・借入 |
| 04 | 雇用・労務 |
| 05 | 不動産 |
| 06 | 契約・合意 |
| 07 | 取引先情報 |
| 08 | 法的・規制事項 |

### 5.5 Contract Reviewページ（`/contract`）

**左パネル（296px）:**

| コンポーネント | 仕様 |
|---|---|
| **アップロードゾーン** | `2px dashed #D1D5DB`。ドラッグ&ドロップ + クリック。ホバー: `#2D4FD6` ボーダー |
| **アップロード後** | `#F0FDF4` 背景の成功カード。ファイル名 + 差分件数ピル（+N green / -N red） |
| **条項アノテーション** | 各条項のリスクレベル（HIGH/MEDIUM/LOW）+ 弁護士コメント |
| **Export DOCX** | 全幅、`#2D4FD6`。DOCX tracked changes形式でエクスポート |

**右パネル — Diffビューア:**

| 要素 | 仕様 |
|---|---|
| **ツールバー** | ファイル名 + 「Split / Unified」切替ボタン |
| **Split View** | 2列。左: 「− Original」（`#FEF2F2` ヘッダー）/ 右: 「+ AI Redline」（`#F0FDF4` ヘッダー） |
| **削除行（Split）** | `#FEF2F2` 背景、`3px solid #EF4444` 左ボーダー、`#B91C1C` テキスト |
| **追加行（Split）** | `#F0FDF4` 背景、`3px solid #22C55E` 左ボーダー、`#15803D` テキスト |
| **Unified View** | 1列。`+` プレフィックス（緑）/ `−` プレフィックス（赤）/ 空白（グレー） |
| **フォント** | IBM Plex Mono 12px、1.9 line-height |

### 5.6 Knowledge Graphページ（`/graph`）

- Phase 3まではプレースホルダー表示
- Phase 3以降: Neo4j Bloom embed または D3.js force-directed graph
- フィルターパネル: 管轄・ノード種別・日付範囲

### 5.7 Uploadページ（`/upload`）

| コンポーネント | 仕様 |
|---|---|
| **ドロップゾーン** | `2px dashed #D1D5DB`、対応形式: PDF / DOCX / TXT / HTML、最大50MB |
| **文書種別選択** | 3列グリッド: 法令 / 判例 / 契約書 / 規制 / SEC Filing / その他 |
| **処理ステップ可視化** | テキスト抽出 → チャンク分割 → NER → グラフノード生成 → 埋め込みインデックス（各ステップにスピナー→チェックマーク） |

---

## 6. バックエンド・API要件

### 6.1 基本情報

- **開発URL:** `http://localhost:8000`
- **本番URL:** `https://api.lexgraph.ai`
- **レスポンス形式:** JSON（ストリーミングはSSE）
- **認証:** Bearer JWT（Supabase Auth発行、Phase 6から必須）

### 6.2 エンドポイント一覧

| メソッド | パス | 説明 | Phase |
|---|---|---|---|
| `POST` | `/upload` | 文書取り込み（グラフ + ベクトルストア） | 0 |
| `POST` | `/chat` | Graph RAG法律QA（SSEストリーミング） | 0 |
| `POST` | `/agent/dd` | DDエージェントワークフロー開始 | 2 |
| `GET` | `/agent/dd/{task_id}` | DDタスク状態・部分結果ポーリング | 2 |
| `POST` | `/agent/dd/{task_id}/review` | 弁護士レビュー送信（human checkpoint） | 2 |
| `POST` | `/agent/review` | Contract Review Agent開始 | 2 |
| `GET` | `/agent/review/{task_id}` | レビュータスク状態ポーリング | 2 |
| `POST` | `/agent/review/{task_id}/approve` | 条項承認・赤線送信 | 2 |
| `GET` | `/graph/search` | Neo4jサブグラフ検索 | 1 |
| `GET` | `/graph/node/{id}` | 単一ノード + 隣接ノード取得 | 1 |
| `GET` | `/metadata/status` | メタデータ整合性レポート取得 | 3 |
| `POST` | `/evaluate/ragas` | RAGASテストセット実行 | 2 |
| `GET` | `/health` | ヘルスチェック | 0 |

### 6.3 `POST /chat` スキーマ

```
Request:
  query:        string
  jurisdiction: "JP" | "US" | "auto"
  session_id:   string
  history:      [{role, content}]

Response (SSE stream):
  data: {"token": "..."}           # ストリーミングトークン
  data: {"done": true,
         "citations": [{node_id, type, title, article, url}],
         "route_used": "graph_rag" | "vector_rag",
         "adapter_mode": "thinking" | "non_thinking",
         "latency_ms": 1240}
```

### 6.4 `POST /agent/dd` スキーマ

```
Request:
  prompt:           string
  jurisdiction:     "JP" | "US" | "both"
  document_ids:     string[]
  transaction_type: "M&A" | "investment" | "loan" | "JV" | "other"

Response 202:
  task_id:           string
  status:            "running"
  estimated_seconds: number

GET /{task_id} Response:
  task_id:        string
  status:         "running" | "awaiting_review" | "complete" | "error"
  current_step:   number (1-8)
  step_label:     string
  partial_findings: Finding[]
  report:         DDReport | null
```

### 6.5 DDReport スキーマ

```
DDReport:
  target:       string          # 対象企業名
  transaction:  string          # 取引概要
  date:         string
  jurisdiction: string
  summary:
    critical:       number
    high:           number
    medium:         number
    low:            number
    recommendation: string
  sections: [{
    num:   "01" | ... | "08"
    title: string
    items: [{
      status: "critical" | "high" | "medium" | "ok"
      text:   string
      citation: string | null   # 根拠条文
    }]
  }]
```

### 6.6 `POST /agent/review` スキーマ

```
Request:
  document_id:     string
  jurisdiction:    "JP" | "US"
  contract_type:   "NDA" | "SPA" | "employment" | "license" | "MSA" | "other"
  client_position: "buyer" | "seller" | "licensor" | "licensee" | "other"

GET /{task_id} Response:
  original_text:   string
  reviewed_text:   string
  diff:            [{type: "same"|"added"|"removed", text: string}]
  clause_reviews:  ClauseReview[]
  compliance_flags: ComplianceFlag[]

ClauseReview:
  clause_id:          string
  clause_type:        string
  original_text:      string
  reviewed_text:      string
  risk_level:         "critical" | "high" | "medium" | "low"
  issues:             string[]
  redline_suggestion: string
  applicable_statutes: string[]
  citations:          string[]
```

---

## 7. Graph RAG設計

### 7.1 なぜGraph RAGか

```
通常のRAG（ベクトル検索のみ）:
  「会社法423条」を含むチャンクを返す → 平面的

Graph RAG（グラフ探索付き）:
  会社法423条ノード
    → INTERPRETS → 最判昭和44年判決
    → INTERPRETS → 最判平成22年判決
    → REQUIRES_PROOF_OF → [任務懈怠, 損害, 因果関係, 帰責性]
    → ANALOGOUS_TO → Duty of Care (Delaware) [US]
  → 関連情報を多段推論で網羅的に取得できる
```

### 7.2 ハイブリッド検索（HybridRetriever）

```python
class HybridRetriever:
    async def retrieve(self, query: str, jurisdiction: str) -> list[Node]:

        # Stage 1: ベクトル検索（意味的類似性）
        vector_results = await self.vector_search(query, jurisdiction, top_k=10)

        # Stage 2: キーワード検索（条文番号・固有名詞の完全一致）
        keyword_results = await self.keyword_search(query, jurisdiction)

        # Stage 3: グラフ探索（Neo4j 2ホップBFS）
        anchor_nodes = self.merge_and_deduplicate(vector_results, keyword_results)
        graph_results = await self.graph_traverse(
            anchor_nodes, max_hops=2,
            relation_types=["CITES", "INTERPRETS", "AMENDED_BY",
                           "REQUIRES_PROOF_OF", "ANALOGOUS_TO"]
        )

        # Stage 4: CrossEncoderリランキング
        return self.rerank(query, graph_results, top_k=5)
```

### 7.3 プロンプト設計（LEGAL_SYSTEM_PROMPT）

```
System Prompt（厳守ルール）:
  1. 回答の根拠は「参照条文・判例」セクションの情報のみ
  2. 条文引用は [法令名第X条第Y項] の形式
  3. 参照情報にない事項は「参照情報には記載がない」と明示
  4. 不確実な情報は「〜と解される」と明示

回答構造:
  - 結論（1〜2文）
  - 根拠（条文・判例の引用）
  - 例外・留意事項
  - 関連する未解決の問題（あれば）
```

### 7.4 構造化チャンキング

```
悪い例: 512トークンで機械的に切断 → 条文が途中で切れる

良い例: 条文の論理単位で分割
  法令 → 条 / 項 / 号の単位
  判例 → 事実の概要 / 判旨 / 結論を別チャンク
  契約書 → 条項単位（clause_segmenterが処理）
```

---

## 8. Self-Routeルーター

### 8.1 設計方針

LLMルーターではなく**ルールベース + 複雑度判定**で実装する。

```
理由:
  → ルートが5種類と少ない
  → 法律アプリのクエリパターンは予測可能
  → LLM呼び出しを省略できる（低レイテンシ・低コスト）
```

### 8.2 ルーティング対象（5ルート）

| ルート | トリガー例 | 処理 |
|---|---|---|
| `dd_agent` | 「デューデリジェンス」「DD」「M&A」「投資調査」 | DDエージェント起動 |
| `contract_agent` | 「契約書レビュー」「赤線」「条項リスク」 | ContractエージェントHQRK |
| `direct_answer` | 「ありがとう」「こんにちは」 | LLM直接回答（RAGなし） |
| `graph_rag` | 多段推論が必要なクエリ | Neo4j + ベクトル検索 |
| `vector_rag` | 単純な条文検索 | pgvectorのみ |

### 8.3 複雑度判定

```python
MULTI_HOP_SIGNALS = [
    r"なぜ.*判断",       # 理由・根拠を問う
    r"どのような.*影響", # 波及効果
    r".*との関係",       # 関係性
    r"改正.*前後",       # 時系列比較
    r".*場合.*どうなる", # 仮定の推論
    r".*要件.*すべて",   # 網羅的列挙
]

def estimate_complexity(query: str) -> str:
    if any(re.search(p, query) for p in MULTI_HOP_SIGNALS):
        return "high"   # → graph_rag（Neo4j使用）
    return "low"        # → vector_rag（pgvectorのみ）
```

### 8.4 UI表示

チャット画面でルーティング結果をAIバブルの前に表示する。

```
例:
  「このクエリをDDエージェントに転送しました」
  「グラフ検索（2ホップ）を使用しています」
  ユーザーが手動でルートを上書きできるボタンを表示
```

---

## 9. LangGraphエージェント設計

### 9.1 DDエージェント — ステートスキーマ

```python
class DDState(TypedDict):
    # 入力
    transaction_type: str          # M&A | investment | loan | JV | other
    jurisdiction: str              # JP | US | both
    documents: List[dict]
    prompt: str

    # スコープ計画
    dd_checklist: List[dict]

    # 並列調査結果
    corporate_findings: List[Finding]
    contract_findings:  List[Finding]
    regulatory_findings: List[Finding]

    # 集約
    risk_matrix: RiskMatrix

    # Human Loop
    attorney_notes: str
    approved: bool
    reinvestigation_targets: List[str]

    # 出力
    dd_report: Optional[DDReport]
    messages: List[BaseMessage]
```

### 9.2 DDエージェント — ノードグラフ

```
START
  │
  ▼
scope_planner（取引種別・DDチェックリスト生成）
  │
  ├─Send()─► corporate_reviewer ──────────────┐
  ├─Send()─► contract_reviewer ───────────────┤ 並列実行
  └─Send()─► regulatory_checker ──────────────┘
                                              │ fan-in
                                              ▼
                                   risk_synthesizer
                                              │
                                              ▼
                                   human_checkpoint（interrupt()）
                                              │
                               ┌─────────────┴──────────────┐
                             承認                           差戻し
                               │                             │
                               ▼                             ▼
                       report_generator               re_investigate
                               │                             │
                               ▼                             └──► risk_synthesizer
                             END
```

| ノード | 責務 | 使用ツール |
|---|---|---|
| `scope_planner` | 取引種別・DDチェックリスト生成 | LLM + `jurisdiction_router` |
| `corporate_reviewer` | 法人登記・定款・株主構成 | `graph_search`, `statute_lookup` |
| `contract_reviewer` | 重要契約のリスク分析 | `clause_segmenter`, `risk_classifier` |
| `regulatory_checker` | 法令・規制・訴訟確認 | `graph_search`, `cross_reference_checker` |
| `risk_synthesizer` | リスクマトリクス集約 | LLM synthesis |
| `human_checkpoint` | 弁護士レビュー待機 | `interrupt()` + WebSocket |
| `re_investigate` | 指摘箇所の深掘り調査 | 全ツール |
| `report_generator` | CFI形式レポート生成 | LLM + `report_formatter` |

### 9.3 Contract Review エージェント — ステートスキーマ

```python
class ContractReviewState(TypedDict):
    # 入力
    raw_contract: str
    jurisdiction: str
    contract_type: str
    client_position: str

    # 解析結果
    clauses: List[Clause]

    # 条項別レビュー
    clause_reviews: List[ClauseReview]
    inconsistencies: List[Inconsistency]
    compliance_flags: List[ComplianceFlag]

    # Human Loop
    attorney_redlines: Dict[str, str]    # clause_id → 弁護士修正テキスト
    approved_clauses: List[str]

    # 出力
    redlined_contract: str
    review_report: dict
    messages: List[BaseMessage]
```

### 9.4 Contract Review エージェント — ノードグラフ

```
START → parser → clause_classifier → review_loop
                                           │
                                    cross_ref_checker
                                           │
                                  矛盾あり？─YES─► review_loop
                                           │ NO
                                           ▼
                                    statute_checker（Neo4j条文照合）
                                           │
                                           ▼
                                    human_checkpoint（interrupt()）
                                           │
                                           ▼
                                    redline_generator → END
```

### 9.5 共有ツールレジストリ

```python
# 全エージェントが使う共有ツール（@tool デコレータ）

graph_search(query, jurisdiction, node_types)
    → SubGraph（Neo4j Cypher）

vector_search(query, jurisdiction, top_k=5)
    → List[Chunk]（pgvector / Weaviate）

statute_lookup(article_ref, jurisdiction)
    → Provision（Neo4j直接 + e-Gov APIフォールバック）

risk_classifier(text, context)
    → RiskLevel（Qwen3 Swallow Thinkingモード）

clause_segmenter(text, contract_type)
    → List[Clause]（regex + LLM補正）

cross_reference_checker(clauses)
    → List[Inconsistency]（埋め込み類似度行列）

jurisdiction_router(text)
    → "JP" | "US"（langdetect + 明示タグ）

human_review_interrupt(state, reason)
    → None（LangGraph interrupt() + WebSocket通知）

report_formatter(findings, template)
    → str（LLM + Jinja2）
```

### 9.6 LangGraph状態永続化

| フェーズ | バックエンド | 理由 |
|---|---|---|
| Phase 2（開発） | インメモリ | 設定ゼロ・高速 |
| Phase 5（本番） | PostgreSQL（Supabase） | 永続化・再開可能 |

---

## 10. メタデータ管理

### 10.1 設計原則

**「古い条文を参照してしまう」ミスを防ぐことが最優先。** 法令改正があった場合、旧版条文を自動でARCHIVED状態にする仕組みをPhase 0から組み込む。

### 10.2 必須メタデータフィールド

全ノードに以下のメタデータを付与する。

```python
class NodeMetadata(TypedDict):
    # 識別情報
    node_id:      str          # UUID
    node_type:    str          # Statute | Case | Provision | ...

    # 法的メタデータ
    law_name:     str          # 会社法 / Securities Exchange Act
    article_no:   str | None   # 423 / Section 10(b)
    jurisdiction: str          # JP | US

    # バージョン管理（最重要）
    effective_date:  date      # 施行日
    amended_date:    date | None  # 改正日
    expiry_date:     date | None  # 廃止日
    status:          str       # ACTIVE | ARCHIVED | DRAFT
    version:         int       # 1, 2, 3...（改正のたびにインクリメント）
    superseded_by:   str | None   # 改正後の新ノードID

    # 品質管理
    source_url:      str       # e-Gov / courts.go.jp / HF dataset
    ingested_at:     datetime
    last_verified:   datetime  # 手動確認日
    confidence:      float     # 0.0〜1.0（自動抽出精度）
```

### 10.3 改正管理の自動化

```python
class AmendmentManager:
    """
    法令改正を検知してグラフを自動更新する
    """

    async def check_amendments(self):
        """Phase 6以降: e-Gov APIの差分を定期監視"""
        # e-Gov差分API（月次実行）
        new_versions = await self.egov_client.get_updates(
            since=self.last_check_date
        )

        for new_law in new_versions:
            old_node = await self.neo4j.find_active(new_law.id)
            if old_node:
                # 旧版をARCHIVEDに変更
                await self.neo4j.update_status(old_node.id, "ARCHIVED")
                # AMENDED_BYエッジを追加
                await self.neo4j.add_edge(
                    old_node.id, new_node.id, "AMENDED_BY",
                    {"effective_date": new_law.effective_date}
                )
                # 通知（Slack / メール）
                await self.notify_team(f"法令改正検知: {new_law.name}")
```

### 10.4 整合性チェック（定期実行）

```cypher
-- ① 孤立ノード（どのエッジとも繋がっていない）
MATCH (n)
WHERE NOT (n)--()
RETURN n.node_id, n.law_name, labels(n)

-- ② AMENDED_BY後もACTIVEな旧版条文
MATCH (old)-[:AMENDED_BY]->(new)
WHERE old.status = "ACTIVE"
RETURN old.node_id, old.law_name, old.article_no

-- ③ effective_dateが未来なのにACTIVEなノード
MATCH (n)
WHERE n.status = "ACTIVE"
AND n.effective_date > date()
RETURN n.node_id, n.effective_date

-- ④ 引用関係が欠損している判例
MATCH (c:Case)
WHERE NOT (c)-[:CITES]->(:Statute)
AND c.has_citation = true
RETURN c.node_id, c.docket_no
```

### 10.5 メタデータフィルタ検索

```python
# 有効な条文のみを検索対象にする（ARCHIVEDを除外）
async def vector_search_with_filter(
    query: str,
    jurisdiction: str,
    top_k: int = 10
) -> list[Node]:
    return await self.pgvector.similarity_search(
        query=query,
        filter={
            "jurisdiction": jurisdiction,
            "status": "ACTIVE",           # ARCHIVED除外
            "effective_date": {"lte": date.today()},  # 未施行除外
        },
        top_k=top_k
    )
```

### 10.6 グラフ品質ダッシュボード（Phase 4）

管理画面として実装。以下の指標を表示する。

| 指標 | 内容 |
|---|---|
| ノード総数 | 種別別（Statute / Case / Provision / ...） |
| ARCHIVED比率 | 全体に占める旧版ノードの割合 |
| 孤立ノード数 | エッジ未接続ノード（グラフ品質の指標） |
| 最終改正確認日 | 各法令の最終手動確認日 |
| 未確認ノード数 | `last_verified` が90日以上前のノード |

---

## 11. RAGAS評価基盤

### 11.1 評価する4指標

| 指標 | 内容 | 法律用途での重要度 |
|---|---|---|
| **Faithfulness（忠実性）** | 回答が参照条文・判例に基づいているか | ★★★★★（最重要） |
| **Answer Relevancy（回答関連性）** | クエリに対して回答が的確か | ★★★★☆ |
| **Context Precision（文脈精度）** | 取得チャンクのうち役立った割合 | ★★★☆☆ |
| **Context Recall（文脈再現率）** | 正解に必要な情報が取得できているか | ★★★☆☆ |

### 11.2 目標スコア

| フェーズ | Faithfulness | Answer Relevancy |
|---|---|---|
| Phase 2（初期ベースライン） | > 0.75 | > 0.70 |
| Phase 3（検索品質改善後） | > 0.85 | > 0.80 |
| Phase 4（グラフ強化後） | > 0.90 | > 0.85 |

### 11.3 テストセット

```python
# Phase 2: 20〜30件（手動作成）
# Phase 4: 50〜100件（弁護士資格取得後に拡充）

TEST_CASES = [
    {
        "question": "会社法423条1項の要件は何ですか？",
        "ground_truth": "①取締役がその任務を怠ったこと"
                        "②株式会社に損害が生じたこと"
                        "③任務懈怠と損害の間の因果関係",
    },
    {
        "question": "取締役の善管注意義務と米国のDuty of Careの違いは？",
        "ground_truth": "...",
    },
    # ... 50〜100件
]
```

### 11.4 評価実行（機密データ対応）

```python
class LexGraphEvaluator:

    async def run(self, use_local_llm=True):
        """
        機密データの評価はローカルLLMで実行
        （外部APIに評価データを送らない）
        """
        results = await self._generate_answers()
        dataset = Dataset.from_list(results)

        if use_local_llm:
            # OllamaのQwen3 Swallowで評価
            llm = LangchainOllama(model="qwen3-swallow:8b")
            embeddings = OllamaEmbeddings(model="nomic-embed-text")
        else:
            # 公開データのみの評価時はOpenAI使用可
            llm = ChatOpenAI(model="gpt-4o")
            embeddings = OpenAIEmbeddings()

        scores = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy,
                     context_precision, context_recall],
            llm=llm,
            embeddings=embeddings,
        )
        await self._save_scores(scores)  # Supabaseに記録
        return scores

    def run_regression_test(self, baseline: dict, current: dict):
        """変更前後でFaithfulnessが5%以上下がったらエラー"""
        if current["faithfulness"] < baseline["faithfulness"] - 0.05:
            raise ValueError(
                f"品質劣化検出: Faithfulness "
                f"{baseline['faithfulness']:.2f} → {current['faithfulness']:.2f}"
            )
```

---

## 12. ファインチューニング設計

### 12.1 QLoRA設定

```
ベースモデル（実装済み）:
  デフォルト: Qwen/Qwen2.5-1.5B-Instruct
              （多言語JP/EN対応・約3GB・Mac MPS動作確認済み・非ゲーテッド）
  代替（高性能）: NousResearch/Meta-Llama-3.1-8B-Instruct
                  （より多くのRAMが必要）

量子化方式:
  Mac MPS / CPU: float16（bitsandbytesはApple Silicon非対応のため4-bit不使用）
  CUDA (A100等): QLoRA（4bit NF4 + LoRAアダプター）も利用可

LoRA設定:
  rank (r):      16
  alpha:         32  （alpha/r = 2 が標準）
  dropout:       0.05
  対象モジュール: q_proj, v_proj, k_proj, o_proj

学習フレームワーク:
  HuggingFace transformers + peft + trl (SFTTrainer)
  デバイス自動検出: MPS（Apple Silicon）> CUDA > CPU

ハードウェア:
  ローカル開発: Mac Apple Silicon（MPS・float16）
  テスト:       Google Colab Pro+（A100 40GB・月$10程度）
  本番:         Vertex AI Custom Job A100 40GB（Bootcampクレジット消費）
  推定学習時間: 1アダプターあたり60〜90分
  推定学習コスト: 1回あたり約¥800（A100）
```

### 12.2 学習データ（US: 1,800件）

| データセット | HF ID | 件数 | 内容 | 優先度 |
|---|---|---|---|---|
| CUAD | `cuad` | 600 | 米国商業契約・41条項タイプ | ⭐⭐⭐⭐⭐ |
| Edgar-Corpus | `eloukas/edgar-corpus` | 300 | 10-K・8-K証券届出 | ⭐⭐⭐⭐⭐ |
| LegalBench | `nguha/legalbench` | 400 | 法的推論・契約解釈 | ⭐⭐⭐⭐⭐ |
| CaseHOLD | `casehold` | 200 | 連邦裁判所判決・保持選択 | ⭐⭐⭐⭐ |
| ContractNLI | `contract-nli` | 150 | 契約条項NLI・解釈 | ⭐⭐⭐⭐ |
| BillSum | `billsum` | 150 | 議会法案・規制文書 | ⭐⭐⭐ |

### 12.3 学習データ（JP: 1,800件）

| データセット | 出典 | 件数 | 内容 | 優先度 |
|---|---|---|---|---|
| JLawText | `legalscape/jlawtext` | 500 | 会社法・金商法 | ⭐⭐⭐⭐⭐ |
| e-Gov API | 政府API | 400 | 全省庁現行法令 | ⭐⭐⭐⭐⭐ |
| JCourts | `legalscape/jcourts` | 300 | 商事判例 | ⭐⭐⭐⭐ |
| Courts.go.jp | Webスクレイピング* | 200 | 最高裁判所判例 | ⭐⭐⭐⭐⭐ |
| FSA規制 | 金融庁サイト | 200 | 金融規制 | ⭐⭐⭐⭐ |
| JP契約書テンプレート | 合成データ | 200 | 契約書Q&A | ⭐⭐⭐ |

> \* courts.go.jpのrobots.txtとToS確認が必須。JCourtsを優先。

### 12.4 Instruction形式

```json
{
  "text": "### Instruction:\nあなたは日本法律の専門家です。条文引用を含めて回答してください。\n\n### Input:\n取締役の善管注意義務の根拠条文と要件は？\n\n### Response:\n会社法330条・民法644条により、取締役は善管注意義務を負います。要件は..."
}
```

### 12.5 学習パイプライン（`backend/fine_tune/train_lora.py`）

```bash
# 基本実行（Mac MPS / CPU）
python fine_tune/train_lora.py \
    --base_model Qwen/Qwen2.5-1.5B-Instruct \
    --data_path  fine_tune/data/legal_qa.jsonl \
    --adapter    JP \
    --epochs     3

# RAGAS評価付き（学習前後の品質差分をW&Bに記録）
python fine_tune/train_lora.py \
    --base_model Qwen/Qwen2.5-1.5B-Instruct \
    --adapter JP --eval_ragas
```

```python
# W&B 自動ログの概要（train_lora.py より抜粋）
wandb.init(
    project="lexgraph-finetune",
    name=f"{base_model}-{adapter}-r{lora_rank}-{timestamp}",
    config={
        "base_model": base_model, "adapter": adapter,
        "lora_rank": lora_rank, "lora_alpha": lora_alpha,
        "epochs": epochs, "lr": learning_rate,
        "device": device,   # mps / cuda / cpu
    },
)

# SFTTrainer → report_to="wandb" で損失・LR・grad_normを自動ログ
# 学習後のサマリー
wandb.summary["train_loss"]        = train_result.training_loss
wandb.summary["train_runtime_sec"] = ...
wandb.summary["samples_per_sec"]   = ...

# --eval_ragas 時: 学習前後のRAGASスコアを記録
wandb.log({"eval/before/faithfulness": ..., "eval/after/faithfulness": ...})
wandb.summary["faithfulness_delta"]   = after - before
wandb.summary["faithfulness_improved"] = delta > 0

# LoRAアダプターをArtifactとして保存
artifact = wandb.Artifact("lexgraph-adapter-jp", type="model")
artifact.add_dir(output_dir)
run.log_artifact(artifact)
```

### 12.6 ColabからVertex AIへの移行

コードは共通。パスの切り替えのみ。

```bash
# Colabでのテスト実行（OUTPUT_DIR未設定 → ローカルパス）
python training/finetune_jp.py

# Vertex AIでの本番実行（OUTPUT_DIR設定 → GCSパス）
OUTPUT_DIR=gs://lexgraph-training-2026/adapter_jp \
DATA_PATH=gs://lexgraph-training-2026/data/training_data_jp.jsonl \
python training/finetune_jp.py
```

### 12.7 評価ベンチマーク

| ベンチマーク | 管轄 | 目標値 | W&Bで追跡 |
|---|---|---|---|
| COLIEE Task4（法令含意） | JP | > 70%（ベースLLaMA: 約55%） | `eval/coliee_accuracy` |
| LexGLUE Multi-task | US | macro-F1 > 75% | `eval/lexglue_f1` |
| 社内テストセット（20件） | JP+US | 弁護士ブラインド評価 4/5以上 | `eval/human_score` |

---

## 13. W&B実験管理

### 13.1 プロジェクト構成

W&Bの管理対象を2プロジェクトに分割する。

```
wandb project: lexgraph-finetune
  → ファインチューニング学習ログ
  → 損失曲線・学習率・GPU使用率
  → モデルアダプターのArtifacts管理

wandb project: lexgraph-rag
  → RAGAS評価スコアの履歴
  → RAGパイプライン変更の効果比較
  → 失敗クエリの可視化（W&B Tables）
```

### 13.2 RAG実験管理（`backend/evaluation/ragas_evaluator.py`）

Graph RAGパイプラインの変更（検索手法・チャンクサイズ・グラフホップ数等）の効果をW&Bで定量追跡する。

```bash
# RAGAS評価を実行してW&B lexgraph-rag プロジェクトに記録
python -c "
from evaluation.ragas_evaluator import LexGraphEvaluator
LexGraphEvaluator(pipeline_version='v1', use_wandb=True).run()
"
```

W&Bに記録される内容（`lexgraph-rag` プロジェクト）:

| メトリクス | 説明 |
|---|---|
| `ragas/faithfulness` | 回答がコンテキストに根拠を持つ割合 |
| `ragas/answer_relevancy` | 回答が質問に答えている割合 |
| `ragas/context_precision` | 検索チャンクの有用率 |
| `ragas/context_recall` | ground truthがコンテキストに含まれる割合 |
| `ragas/jp/*` / `ragas/us/*` | 管轄別ブレークダウン |
| `ragas/all_cases` (Table) | 全25件の質問・回答・スコア一覧 |
| `ragas/failures` (Table) | Faithfulness < 0.6 の失敗ケース詳細 |
| `ragas/target/faithfulness_pass` | 目標値（0.75）達成フラグ |

回帰チェック: Faithfulnessが前回比5%超下落した場合は `ValueError` を発生させる。

### 13.2.1 ファインチューニング前後比較（`backend/fine_tune/evaluate_finetune.py`）

ベースモデルとファインチューニング済みモデルを同一条件でRAGAS評価し、改善効果を1つのW&Bランに記録する。

```bash
python fine_tune/evaluate_finetune.py \
    --base_model      qwen2.5:1.5b \
    --finetuned_model lexgraph-legal \
    --version         v1
```

W&Bに記録される内容（`lexgraph-finetune` プロジェクト・`job_type=eval-compare`）:

| メトリクス | 説明 |
|---|---|
| `base/faithfulness` 等 | ベースモデルの4指標 |
| `finetuned/faithfulness` 等 | FTモデルの4指標 |
| `delta/faithfulness` 等 | 差分（プラスが改善） |
| `compare/summary` (Table) | 全指標の base / finetuned / delta 一覧 |
| `compare/base_cases` (Table) | ベースモデルの全件スコア |
| `compare/finetuned_cases` (Table) | FTモデルの全件スコア |
| `finetuned_passes_target` | Faithfulness≥0.75 AND Relevancy≥0.70 のフラグ |

### 13.3 実験比較の例（W&Bで可視化する内容）

```
実験比較（lexgraph-rag プロジェクト）:

run-001  ベクトル検索のみ（pgvector top-k=5）
  faithfulness: 0.71  answer_relevancy: 0.74

run-002  ハイブリッド検索追加（+ キーワード検索）
  faithfulness: 0.83  answer_relevancy: 0.80  ← +0.12 改善

run-003  CrossEncoderリランキング追加
  faithfulness: 0.88  answer_relevancy: 0.85  ← +0.05 改善

run-004  グラフ2ホップ探索追加
  faithfulness: 0.91  answer_relevancy: 0.88  ← +0.03 改善

run-005  JP adapter適用後（FT後モデル）
  faithfulness: 0.93  answer_relevancy: 0.91  ← +0.02 改善

→ 最大の改善はハイブリッド検索（+0.12）
  FTの寄与は+0.02（コスト検討の根拠になる）
```

### 13.4 Artifactsによるモデル管理

```python
# 学習済みアダプターをW&B Artifactsとしてバージョン管理
artifact = wandb.Artifact(
    name="lexgraph-adapter-jp",
    type="model",
    description="JP QLoRA adapter v1 - Swallow-8B",
    metadata={
        "base_model": "Swallow-8b-hf",
        "train_data": "jp_1800",
        "lora_rank":  16,
        "coliee_accuracy": 0.72,
        "faithfulness":    0.91,
    }
)
artifact.add_dir("./adapter_jp")
wandb.log_artifact(artifact)

# 本番デプロイ時に最良バージョンを参照
api = wandb.Api()
artifact = api.artifact("lexgraph-ai/lexgraph-adapter-jp:best")
artifact.download("./adapter_jp")
```

### 13.5 料金

```
W&B 無料プラン（個人）:
  実験記録:  無制限
  ストレージ: 100GB
  Team機能:  なし

LexGraph AIでの用途:
  → 個人プロジェクトのため無料プランで十分
  → RAGASログ（テキストのみ）はストレージ消費が軽微
  → モデルアダプター保管はGCSを使い、W&BにはメタデータのみLog
```

---

## 14. Neo4j知識グラフスキーマ

### 12.1 ノード定義

| ラベル | 主要プロパティ | 管轄 |
|---|---|---|
| `Statute` | law_name, article_no, text, effective_date, status, version | JP / US |
| `Case` | court, docket_no, date, holding, summary, status | JP / US |
| `Provision` | text, parent_statute, article_no, section, paragraph_no | JP / US |
| `LegalConcept` | name, domain, definition, aliases | JP / US / Both |
| `LegalElement` | name, element_type（要件事実用） | JP / US |
| `Entity` | name, entity_type（corp/person/agency） | JP / US |
| `Regulation` | title, issuer, effective_date, text, status | JP / US |
| `Chunk` | text, embedding_id, source_doc_id, token_count, status | JP / US |

### 12.2 リレーションシップ定義

| リレーション | 方向 | 意味 | 優先度 |
|---|---|---|---|
| `CITES` | Case → Case/Statute | 先例引用 | Phase 0 |
| `INTERPRETS` | Case → Provision | 司法解釈 | Phase 0 |
| `AMENDS` | Statute → Statute | 改正関係 | Phase 0 |
| `AMENDED_BY` | Statute → Statute | 改正後の新版へのリンク | Phase 0（メタデータ管理に必須） |
| `IMPLEMENTS` | Regulation → Statute | 委任立法 | Phase 1 |
| `OVERRULES` | Case → Case | 先例変更 | Phase 1 |
| `REQUIRES_PROOF_OF` | Provision → LegalElement | 要件事実 | Phase 3 |
| `GOVERNED_BY` | LegalConcept → Statute | 規律関係 | Phase 3 |
| `INVOLVES` | Case → Entity | 当事者関係 | Phase 3 |
| `ANALOGOUS_TO` | Concept → Concept | 日米概念対応 | Phase 4（要法的レビュー） |
| `CONFLICT_WITH` | Provision → Provision | 条文間競合 | Phase 4 |
| `CHUNK_OF` | Chunk → Statute/Case | チャンクの出典 | Phase 0 |

### 12.3 日米クロスジャリスディクション対応表（Phase 4）

| 日本法概念 | 米国法概念 | 対応類型 | 注意 |
|---|---|---|---|
| 不法行為（民法709条） | Tort / Negligence | 構造的類比 | 立証要件が異なる |
| 取締役の善管注意義務 | Duty of Care (Delaware) | 機能的等価 | 経営判断原則の範囲が異なる |
| 金融商品取引法 | Securities Exchange Act 1934 | 規制的類比 | インサイダー規制の構造が異なる |
| 株主代表訴訟（847条） | Derivative suit | 手続的類比 | 提訴要件が大きく異なる |
| 職務発明（特許法35条） | Work-for-hire (17 USC §101) | 機能的類比 | 仕組みが根本的に異なる |
| 三六協定 | FLSA overtime authorization | 規制的類比 | 差異が非常に大きい |

> ⚠️ ANALOGOUS_TOエッジは意味的類似度だけで自動生成してはならない。弁護士による法的レビューが必須。

### 12.4 サンプルCypherクエリ

```cypher
-- Graph RAGアンカー取得後の2ホップ探索
MATCH (anchor {node_id: $anchor_id})
CALL apoc.path.subgraphAll(anchor, {
    relationshipFilter: "CITES|INTERPRETS|AMENDED_BY|REQUIRES_PROOF_OF",
    maxLevel: 2
})
YIELD nodes, relationships
WHERE ALL(n IN nodes WHERE n.status = "ACTIVE")
RETURN nodes, relationships
LIMIT 50
```

---

## 15. ローカルLLM設計

### 13.1 採用モデル

**Qwen3 Swallow 8B RL**（東京科学大学 + AIST開発）

| 属性 | 内容 |
|---|---|
| 開発元 | 東京科学大学岡崎研究室・AIST |
| ベース | Qwen3 8B + 日本語継続事前学習 + SFT + 強化学習 |
| 日本語性能 | 8BクラスオープンLLMでSoTA（2026年2月時点） |
| ライセンス | Apache 2.0（商用利用・オンプレ配置可） |
| Ollamaサポート | 対応済み |
| RAMへの必要容量 | 約6GB（Q4量子化） |

### 13.2 Thinkingモードの使い分け

```python
# Thinkingモード（複雑な推論 → 精度優先・低速）
THINKING_MODE_TRIGGERS = [
    "dd_agent",         # DDレポート生成
    "contract_agent",   # 契約書レビュー
    "graph_rag",        # 複雑度HIGH判定のクエリ
]

# Non-thinkingモード（単純なQA → 速度優先）
NON_THINKING_MODE_TRIGGERS = [
    "vector_rag",       # 単純な条文検索
    "direct_answer",    # 雑談・挨拶
]

# Ollamaでの切り替え
prompt_thinking     = query + " /think"
prompt_non_thinking = query + " /no_think"
```

### 13.3 OllamaによるローカルAPI

```python
class OllamaClient:
    BASE_URL = "http://localhost:11434"
    MODEL    = "qwen3-swallow:8b"   # Ollamaモデル名

    async def generate(self, prompt: str, thinking: bool = False) -> str:
        suffix = " /think" if thinking else " /no_think"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self.BASE_URL}/api/generate",
                json={
                    "model": self.MODEL,
                    "prompt": prompt + suffix,
                    "stream": False,
                }
            )
            return response.json()["response"]

    async def stream(self, prompt: str, thinking: bool = False):
        """SSEストリーミング（チャットUI用）"""
        ...
```

### 13.4 Macでの推奨設定

```bash
# インストール
brew install ollama

# モデルダウンロード（約5GB）
ollama pull qwen3-swallow:8b

# サーバー起動（バックグラウンド）
ollama serve

# 動作確認
curl http://localhost:11434/api/generate -d '{
  "model": "qwen3-swallow:8b",
  "prompt": "会社法423条1項の要件を説明してください /think",
  "stream": false
}'
```

**Mac RAM使用量（Q4量子化）:**

| 状態 | RAM使用量 |
|---|---|
| 待機中（モデルロード済み） | +5〜6GB |
| 推論中（Non-thinking） | +2〜3GB（一時的） |
| 推論中（Thinking） | +4〜6GB（一時的） |
| Ollamaなし時 | 影響なし（5分後に自動アンロード） |

---

## 16. データ・ストレージ設計

### 14.1 データ分類と保管場所

| データ種別 | 保管場所 | 理由 |
|---|---|---|
| 依頼者がアップロードした契約書・文書 | Supabase Storage | Google Driveと同等の法的保護。LLMには送らない |
| 公開法令・判例テキスト | Neo4j + pgvector | 知識グラフとして管理 |
| 埋め込みベクトル | Supabase pgvector | Supabaseに統合・SQL操作可能 |
| LangGraph状態（エージェント実行中） | PostgreSQL（Supabase） | 永続化・再開可能 |
| RAGASテストセット・評価結果 | Supabase PostgreSQL | 回帰テスト・履歴管理 |
| 学習データ（将来FT時） | GCS | Vertex AIとの連携 |

### 14.2 Supabaseスキーマ（主要テーブル）

```sql
-- 文書管理
CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id),
    file_name   TEXT NOT NULL,
    file_path   TEXT NOT NULL,     -- Supabase Storage path
    doc_type    TEXT,              -- contract / statute / case / other
    jurisdiction TEXT,             -- JP | US
    uploaded_at TIMESTAMPTZ DEFAULT now(),
    processed   BOOLEAN DEFAULT false
);

-- チャンク + ベクトル
CREATE TABLE chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID REFERENCES documents(id),
    text         TEXT NOT NULL,
    embedding    vector(1024),     -- multilingual-e5-large
    source_type  TEXT,             -- Statute | Case | Contract
    law_name     TEXT,
    article_no   TEXT,
    jurisdiction TEXT,
    status       TEXT DEFAULT 'ACTIVE',  -- ACTIVE | ARCHIVED
    effective_date DATE,
    version      INTEGER DEFAULT 1,
    created_at   TIMESTAMPTZ DEFAULT now()
);

-- ベクトル検索インデックス（メタデータフィルタ付き）
CREATE INDEX ON chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- RAGAS評価結果
CREATE TABLE ragas_scores (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluated_at    TIMESTAMPTZ DEFAULT now(),
    pipeline_version TEXT,
    faithfulness     FLOAT,
    answer_relevancy FLOAT,
    context_precision FLOAT,
    context_recall   FLOAT,
    test_count       INTEGER,
    notes            TEXT
);

-- ルーティングログ（Self-Routeデバッグ用）
CREATE TABLE route_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query       TEXT,
    route_used  TEXT,
    confidence  FLOAT,
    latency_ms  INTEGER,
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## 17. インフラ・実行環境

### 15.1 Mac開発環境

```
Mac（Claude Code + Docker Desktop）
  │
  ├── Docker Compose
  │     ├── Neo4j 5.x        (localhost:7474 / bolt:7687)
  │     ├── FastAPI           (localhost:8000)
  │     └── Redis             (LangGraph状態管理・開発時)
  │
  ├── Ollama
  │     └── Qwen3 Swallow 8B (localhost:11434)
  │
  ├── Next.js dev server      (localhost:3000)
  │
  └── Supabase CLI            (ローカルSupabase / localhost:54321)
```

### 15.2 クレジット運用計画

```
現在の残高:
  Free Trial:    ¥36,605（3/22まで・残り数日）← 今すぐテスト実行
  Bootcamp:      ¥33,609（4/24まで）← Phase 4以降の実験に使用
  合計:          ¥70,214

使用方針:
  〜3/22: Free Trial → テストジョブ（T4 GPU / 100steps / 約¥50）
  3/23〜: Bootcamp  → Vertex AI本番ジョブ（将来FT再検討時に使用）

予算アラート設定:
  ¥5,000 / ¥20,000 / ¥50,000 でメール通知
```

### 15.3 docker-compose.yml（主要サービス）

```yaml
services:
  neo4j:
    image: neo4j:5-enterprise
    ports: ["7474:7474", "7687:7687"]
    volumes: ["neo4j_data:/data"]
    environment:
      NEO4J_AUTH: neo4j/lexgraph_password
      NEO4J_PLUGINS: '["apoc"]'

  fastapi:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      NEO4J_URI: bolt://neo4j:7687
      SUPABASE_URL: ${SUPABASE_URL}
      SUPABASE_KEY: ${SUPABASE_KEY}
      OLLAMA_URL: http://host.docker.internal:11434
    depends_on: [neo4j, redis]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

---

## 18. セキュリティ・情報管理

### 16.1 情報管理の原則

```
外部LLM APIへの送信を完全禁止:
  機密文書（依頼者の契約書・案件情報）
  → Ollamaローカル推論のみ

クラウドストレージへの保管は許可:
  → GCS / Supabase Storage はファイル保管であり
    LLMがテキストを読んで処理するわけではない
  → Google Driveと同等の法的保護
  → Googleとの契約（DPA）が適用される

公開情報の取得・学習はクラウドAPIを使用可:
  → e-Gov API / HuggingFace / courts.go.jp
```

### 16.2 認証・アクセス制御（Phase 6）

| 機能 | 実装 |
|---|---|
| 認証 | Supabase Auth（JWT + OAuth） |
| RBAC | PostgreSQL Row Level Security（RLS） |
| 監査ログ | 全API呼び出しのログ記録（Supabase PostgreSQL） |
| セッション管理 | Supabase Auth セッション |

### 16.3 データ保護

```
依頼者文書:
  → Supabase Storage（バケット単位の権限制御）
  → ユーザーごとに分離されたストレージパス
  → 転送時: TLS 1.3
  → 保管時: AES-256暗号化（Supabase標準）

LangGraph実行ログ:
  → 案件情報を含む可能性があるため
    PostgreSQL（Supabase）のRLSで弁護士本人のみアクセス可
```

---

## 19. 開発フェーズ

### Phase 0（Week 1〜4）: インフラ基盤

**目標:** 文書をアップロードしてチャットで回答できる最小構成

```
実装内容:
  ✅ Neo4jスキーマ定義（ノード・エッジ・メタデータフィールド）
  ✅ 文書取り込みパイプライン
       PDF/DOCX → テキスト抽出 → 構造化チャンキング → spaCy NER
       → Neo4jノード生成（AMENDED_BYエッジ含む）
       → multilingual-e5-large埋め込み → pgvectorインデックス
  ✅ 基本Graph RAG（/chatエンドポイント・SSEストリーミング）
  ✅ Qwen3 Swallow 8B OllamaセットアップとLEGAL_SYSTEM_PROMPT実装
  ✅ AMENDED_BY / ARCHIVEDの基本メタデータ管理
  ✅ Docker Compose環境構築

終了条件:
  PDFアップロード → Neo4jにメタデータ付きノード生成
  → /chatで条文引用付き回答が返ってくる
```

### Phase 1（Week 5〜7）: MVP UI

**目標:** 非エンジニアが操作できるUI

```
実装内容:
  ✅ Chatページ（SSEストリーミング・トピックチップ）
  ✅ Uploadページ（処理ステップ可視化）
  ✅ Knowledge Graphページ（プレースホルダー）
  ✅ グローバルレイアウト（サイドバー・デザイントークン）
  ✅ Self-Routeルーター基本実装（5ルート・ルールベース）
  ✅ Self-Routeルーティング結果のUI表示

終了条件:
  UIからクエリ → 適切な処理経路に自動ルーティング
  弁護士が手動介入なしで文書アップロード→QAを完結できる
```

### Phase 2（Week 8〜11）: LangGraphエージェント

**目標:** DDエージェント・Contract Review Agentのend-to-end動作

```
実装内容:
  ✅ DDState / ContractReviewState TypedDict
  ✅ DD Agentグラフ（scope_planner〜report_generator）
  ✅ Contract Review Agentグラフ（parser〜redline_generator）
  ✅ human_checkpoint（interrupt() / resume）
  ✅ WebSocketリアルタイム進捗通知
  ✅ DD Agentページ（ステッパー + CFIレポート）
  ✅ Contract Reviewページ（diffビューア + 条項アノテーション）
  ✅ RAGASテストセット構築（20〜30件）
  ✅ RAGAS評価パイプライン実装（ローカルLLMで評価）
  ✅ Faithfulness > 0.75 のベースライン確立

終了条件:
  両エージェントがend-to-endで動作
  human_checkpoint中断・再開が機能
  RAGAS Faithfulness > 0.75 達成
```

### Phase 3（Week 12〜15）: 検索品質強化

**目標:** Graph RAGの品質を実用水準に引き上げる

```
実装内容:
  ✅ ハイブリッド検索（ベクトル + キーワード + グラフ探索）
  ✅ CrossEncoderリランキング
  ✅ メタデータフィルタ検索（ACTIVE条文のみ）
  ✅ AMENDED_BY自動検出パイプライン
  ✅ 整合性チェック定期実行（孤立ノード・旧版条文）
  ✅ Self-Route複雑度判定の精度向上
  ✅ ルーティングログのSupabase記録
  ✅ RAGAS Faithfulness > 0.85 達成

終了条件:
  RAGAS全指標が前フェーズより改善
  メタデータフィルタ検索が動作
  実際の法令・判例で法的整合性のある出力
```

### Phase 4（Week 16〜20）: グラフ構造強化 + ファインチューニング

**目標:** 多段推論の完全実装 + QLoRAアダプターによる品質向上

```
実装内容（グラフ強化）:
  ✅ REQUIRES_PROOF_OF（要件事実）エッジ
  ✅ CONFLICT_WITH（条文間競合）エッジ
  ✅ ANALOGOUS_TO（日米概念対応）エッジ（要法的レビュー）
  ✅ 要件事実メタデータ（会社法423条→任務懈怠/損害/因果関係）
  ✅ 判例メタデータ充実（確定/未確定・上訴状況）
  ✅ グラフ品質ダッシュボード（管理画面）
  ✅ RAGASテストセット50〜100件に拡充

実装内容（ファインチューニング）:
  ✅ W&Bプロジェクト lexgraph-finetune セットアップ
  ✅ HuggingFaceデータセット取得・Instruction形式変換
  ✅ Google ColabでQLoRAテスト実行（T4 GPU・100steps・¥0）
     → W&Bに損失曲線・パラメータをログ
  ✅ Vertex AI A100で JP adapter本番学習（1,800件・3 epochs・約¥800）
     → W&Bで COLIEE accuracy を自動評価・記録
  ✅ Vertex AI A100で US adapter本番学習（1,800件・3 epochs・約¥800）
     → W&Bで LexGLUE F1 を自動評価・記録
  ✅ adapter_router.py でJP/USアダプター自動切替
  ✅ W&B RAGAS比較: FT前後のFaithfulness差分を可視化
     → 改善が +5% 未満の場合は追加FTを中止
  ✅ CI/CD自動回帰テスト（RAGAS Faithfulness > 0.90）
  ✅ W&B Artifactsにアダプターをバージョン管理

終了条件:
  RAGAS Faithfulness > 0.90 達成
  グラフ品質ダッシュボード稼働
  ANALOGOUS_TOエッジが弁護士レビュー済みで10件以上
  W&BでFT前後の品質比較が定量的に確認できること
  COLIEE Task4 accuracy > 70% (JP adapter)
  LexGLUE macro-F1 > 75% (US adapter)
```

### Phase 5（Week 21〜24）: UX完成

**目標:** 弁護士が開発者なしで全ワークフローを使える

```
実装内容:
  ✅ Self-Route UIの手動上書き機能
  ✅ Export PDF（DDレポート）
  ✅ Export DOCX tracked changes（契約書赤線）
  ✅ Knowledge Graphページ（D3.js可視化）
  ✅ e-Gov API差分監視の手動トリガー（改正通知）

終了条件:
  弁護士が操作マニュアルなしで全ワークフロー完結
```

### Phase 6（Week 25〜30）: 本番化

```
実装内容:
  ✅ Supabase Auth（JWT + OAuth）
  ✅ PostgreSQL RLS（ユーザー間データ分離）
  ✅ 全API監査ログ
  ✅ レート制限
  ✅ 負荷テスト（k6）
  ✅ e-Gov API差分監視の自動化（月次）
  ✅ メタデータ定期監査スケジュール
  ✅ Kubernetes移行（必要に応じて）

終了条件:
  本番デプロイ完了
  セキュリティレビュー通過
```

---

## 20. リスク・未解決事項

### 20.1 リスクレジスター

| リスク | 深刻度 | 対策 |
|---|---|---|
| LLaMAのハルシネーション（条文の誤引用） | 🔴 CRITICAL | Graph RAGで正確な条文を文脈に渡す。RAGASのFaithfulnessで継続監視。回答に必ずNeo4j照合を実施 |
| courts.go.jpスクレイピングの法的リスク | 🟠 HIGH | robots.txt・ToS確認。JCourts HFデータセットを優先使用 |
| エージェントループの非終了 | 🟠 HIGH | 最大反復回数ガード。N回後にhuman checkpointへフォールバック |
| Qwen3 Swallow OllamaモデルのMacローカル推論速度 | 🟡 MEDIUM | Thinkingモードはバックグラウンド非同期処理。ユーザーへの進捗表示で体感速度を改善 |
| メタデータ管理の鮮度低下（法令改正の見落とし） | 🟡 MEDIUM | e-Gov差分監視の自動化（Phase 6）。手動確認90日以上のノードをダッシュボードで可視化 |
| ANALOGOUS_TOエッジの法的精度 | 🟡 MEDIUM | 弁護士資格取得後（2027年）まで自動生成禁止。手動レビュー済みのもののみ追加 |
| LangGraph状態永続化の複雑性 | 🟢 LOW | Phase 2はインメモリ。Phase 5でPostgreSQLに移行 |

### 20.2 未解決の設計判断

| # | 判断事項 | 選択肢 | 推奨 | 期限 |
|---|---|---|---|---|
| 1 | 本番時のNeo4jホスティング | AuraDB（クラウド）vs セルフホスト | AuraDB（運用コスト低） | Phase 5 |
| 2 | Weaviate移行タイミング | pgvectorで継続 vs Phase 5で移行 | pgvectorでPhase 4まで評価 | Phase 4終了時 |
| 3 | ANALOGOUS_TOエッジの生成方法 | 手動のみ vs 半自動（提案→法的レビュー） | 半自動（効率化） | Phase 4 |
| 4 | ファインチューニング再検討 | 永続的になし vs 2027年以降に再評価 | 2027年以降に再評価 | 2027年 |
| 5 | 複数ユーザー対応 | シングルユーザー（個人） vs マルチテナント | Phase 6でRLS実装時に決定 | Phase 6 |

---

## 21. リポジトリ構成

```
lexgraph-ai/
│
├── frontend/                          # Next.js 14
│   ├── app/
│   │   ├── page.tsx                   # Chat（ホーム画面）
│   │   ├── dd/page.tsx                # DD Agent
│   │   ├── contract/page.tsx          # Contract Review
│   │   ├── graph/page.tsx             # Knowledge Graph
│   │   └── upload/page.tsx            # Document Upload
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx
│   │   │   └── PageHeader.tsx
│   │   ├── chat/
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── TypingIndicator.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── RouteIndicator.tsx     # Self-Routeルーティング結果表示
│   │   ├── dd/
│   │   │   ├── DDPromptPanel.tsx
│   │   │   ├── StepProgress.tsx
│   │   │   ├── DDReportHeader.tsx
│   │   │   ├── DDReportSection.tsx    # 8セクションアコーディオン
│   │   │   └── RiskBadge.tsx
│   │   └── contract/
│   │       ├── UploadZone.tsx
│   │       ├── ClauseAnnotationCard.tsx
│   │       ├── DiffViewer.tsx         # Split / Unified
│   │       └── DiffLine.tsx
│   ├── hooks/
│   │   ├── useChat.ts                 # SSEストリーミング
│   │   ├── useDDAgent.ts              # /agent/dd/{id} ポーリング
│   │   ├── useContractReview.ts
│   │   └── useWebSocket.ts            # human checkpoint通知
│   └── lib/
│       ├── api.ts                     # APIクライアント（fetch wrapper）
│       ├── diff.ts                    # diffLines() アルゴリズム
│       ├── router.ts                  # Self-Route クライアント側ロジック
│       └── types.ts                   # 共有TypeScript型
│
├── backend/                           # FastAPI
│   ├── main.py
│   ├── api/routers/
│   │   ├── chat.py                    # POST /chat（SSE）
│   │   ├── upload.py                  # POST /upload
│   │   ├── agent_dd.py
│   │   ├── agent_review.py
│   │   ├── graph.py
│   │   └── evaluate.py                # POST /evaluate/ragas
│   ├── agents/
│   │   ├── dd_agent.py                # LangGraph DDエージェント
│   │   ├── review_agent.py            # LangGraph ContractエージェントHQRK
│   │   └── state.py                   # DDState / ContractReviewState TypedDicts
│   ├── router/
│   │   └── query_router.py            # Self-Routeルーター（ルールベース + 複雑度判定）
│   ├── tools/
│   │   ├── graph_search.py
│   │   ├── vector_search.py
│   │   ├── statute_lookup.py
│   │   ├── risk_classifier.py
│   │   ├── clause_segmenter.py
│   │   ├── cross_reference_checker.py
│   │   ├── jurisdiction_router.py
│   │   └── report_formatter.py
│   ├── ingestion/
│   │   ├── pipeline.py                # オーケストレーション
│   │   ├── chunker.py                 # 構造化チャンキング（条/項/号単位）
│   │   ├── ner.py                     # spaCy NER（ja_ginza / en_core_web_trf）
│   │   ├── embedder.py                # multilingual-e5-large
│   │   └── graph_builder.py           # Neo4jノード・エッジ生成
│   ├── graph/
│   │   ├── neo4j_client.py
│   │   ├── schema.py
│   │   └── cypher_queries.py
│   ├── metadata/
│   │   ├── manager.py                 # AmendmentManager（改正管理）
│   │   ├── integrity_check.py         # 整合性チェッククエリ（4種）
│   │   └── egov_client.py             # e-Gov API差分監視
│   ├── evaluation/
│   │   ├── ragas_evaluator.py         # LexGraphEvaluator + W&Bログ（lexgraph-rag）
│   │   └── test_cases.py              # 25件 JP/US legal QAペア（RAGASテストセット）
│   └── models/
│       ├── ollama_client.py           # Qwen3 Swallow（Thinking/Non-thinking切替）
│       ├── adapter_router.py          # JP/USアダプター選択
│       └── embedding_client.py        # multilingual-e5-large
│
├── fine_tune/                         # ファインチューニングパイプライン
│   ├── train_lora.py                  # QLoRA学習（W&B自動ログ・MPS/CUDA/CPU対応）
│   ├── export_gguf.py                 # LoRAマージ → GGUF変換 → Ollama Modelfile生成
│   ├── evaluate_finetune.py           # ベース vs FTモデルのRAGAS比較（W&B記録）
│   └── generate_training_data.py      # 学習データ生成
│
├── supabase/
│   └── migrations/
│       ├── 001_initial_schema.sql     # documents / chunks / ragas_scores
│       └── 002_route_logs.sql         # ルーティングログ
│
├── .wandb/                            # W&Bローカルキャッシュ（.gitignoreに追加）
├── docker-compose.yml                 # Neo4j + FastAPI + Redis
├── pyproject.toml
├── .env.example                       # WANDB_API_KEY / SUPABASE_URL 等
└── docs/
    ├── 要件定義書.md                   # 本ドキュメント
    └── Architecture.md
```

---

*Document Control: v3.1 — 2026年4月更新。Claude Codeを使って実装すること。ファインチューニングはコスト最適化型で実施（W&Bで管理）。機密文書は外部LLM APIに送信しないこと。*