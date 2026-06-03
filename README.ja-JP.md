# WizTree CLI Agent

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/wiztree-cli-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](#ライセンス)
[![Tests](https://img.shields.io/badge/tests-366%20passed-brightgreen.svg)](#テスト)

<p align="center">
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.zh-CN.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README.fr-FR.md">🇫🇷 Français</a> &nbsp;|&nbsp;
  <a href="README.de-DE.md">🇩🇪 Deutsch</a> &nbsp;|&nbsp;
  <b><a href="README.ja-JP.md">🇯🇵 日本語</a></b> &nbsp;|&nbsp;
  <a href="README.ru-RU.md">🇷🇺 Русский</a>
</p>

> **WizTree CLI Agent** は、AI を活用したインテリジェントなディスククリーンアップアシスタントです。WizTree CLI ツールをラップし、複数の LLM プロバイダーを統合したルーティングシステムにより、安全で人間と対話しながらのファイルクリーンアップを実現します。

---

## 目次

- [プロジェクト概要](#プロジェクト概要)
- [主な機能](#主な機能)
- [スクリーンショット](#スクリーンショット)
- [クイックスタート](#クイックスタート)
- [アーキテクチャ](#アーキテクチャ)
- [LLM Router](#llm-router)
- [設定](#設定)
- [テスト](#テスト)
- [ライセンス](#ライセンス)

---

## プロジェクト概要

WizTree CLI Agent は、**Scanner**（スキャン）→ **Analyzer**（分析）→ **Safety**（安全）の3段階ワークフローで構成される、AI 駆動のディスククリーンアップツールです。

WizTree の MFT（Master File Table）高速スキャン機能を活用してファイルシステムを瞬時に分析し、LLM（大規模言語モデル）またはルールエンジンを用いて削除可能なファイルを特定します。削除前には多層的な安全チェックを実施し、ユーザーの明示的な確認を得てから実行します。

### 主な設計思想

- **AI First, Rule Fallback**: LLM が利用可能な場合はインテリジェントな分析を、不可能な場合はルールエンジンによる確実な分析を提供
- **Safety by Design**: システムパスの保護、監査ログ、確認ダイアログの多層防御
- **Multi-Provider 耐障害性**: 6つの LLM プロバイダーをサポートし、障害発生時に自動フェイルオーバー
- **Lazy Initialization**: API キーがなくてもアプリケーションは完全に動作可能

---

## 主な機能

### コア機能（v1.0.0）

- **WizTree CLI 統合** — MFT スキャンによる超高速ディスク分析。CSV 出力をパースしてファイル情報を構造化
- **AI 分析** — LLM によるインテリジェントなファイル分析。どのファイルが安全に削除できるかを識別
- **LLM Router** — 6つのプロバイダーを統合したマルチプロバイダールーター。障害耐性とコスト最適化を実現
- **ルールエンジン** — 10 の定義済みクリーンアップルール。API キー不要で動作し、LLM 不能時のフェールバックとして機能
- **ストリーミング JSON パーサー** — AI 分析結果をリアルタイム表示
- **リスクレベル評価** — 各削除推奨ファイルに LOW / MEDIUM / HIGH / CRITICAL のリスクレベルを付与
- **安全な削除** — send2trash 経由でファイルをごみ箱に移動。誤削除からの復元が可能
- **Treemap 可視化** — Squarified Treemap アルゴリズムによるファイルサイズ分布の視覚化（Brus らのアルゴリズム、サードパーティ不要）
- **セキュリティ機構** — パスブラックリスト、監査ログ、確認ダイアログによる多層防御
- **多言語対応** — 日本語と英語のインターフェース切り替えに対応

### v1.1.0 — UI モダナイゼーション

- **モダンテーマシステム** — ダークテーマ / ライトテーマの切り替え、プロフェッショナルな UI デザイン
- **スムーズプログレスバー** — 60fps アニメーションによる滑らかな進捗表示
- **レスポンシブレイアウト** — ウィンドウサイズに追従するアダプティブデザイン
- **統計情報カード** — ファイル数、総サイズ、スキャン時間をリアルタイム表示

### v1.2.0 — セキュリティ + テーマ + インタラクション

- **安全な資格情報ストレージ** — API キーを keyring 経由で OS の資格情報管理機能に保存（Windows DPAPI / macOS Keychain / Linux Secret Service）
- **6 種類のダークテーマ** — Steam Dark / Catppuccin Mocha / OLED Black / GitHub Dark / Nord / Dracula。動的切り替え対応
- **5 つのキーボードショートカット** — Ctrl+S（スキャン）/ Ctrl+R（タブ更新）/ Ctrl+L（クリア）/ Ctrl+,（設定）/ Esc（キャンセル）
- **ドラッグ＆ドロップ** — フォルダをウィンドウにドロップして即座にスキャン開始（tkinterdnd2 対応、非利用時は自動的に機能を無効化）
- **監査履歴と復元** — すべての破壊的操作を SQLite に記録。History タブからファイル削除 / 移動を復元可能
- **Diff プレビュー** — 削除実行前にファイルサイズ・更新日時・削除警告を表示
- **Pure-Python Squarified Treemap** — サードパーティライブラリ不要の Bruls ら (2000) Algorithm 4 実装
- **3 段階カスケード設定** — ビルトイン初期値 → `~/.wiztree-cli-agent/config.json` → 実行時オーバーライド
- **LLM Models & Prompts タブ** — GUI からモデルカタログの閲覧とプロンプト編集が可能
- **ステータスバー** — スキャン中 / 分析中 / 準備完了 / エラー状態を表示

### v1.3.0 — UX 改善

- **スケルトンスクリーン** — ローディング中にプレースホルダー UI を表示し、知覚パフォーマンスを向上
- **テーマ切り替えコールバック** — テーマ変更時に全コンポーネントを自動更新
- **ttk スタイル統合** — Treeview、Progressbar、Combobox などがテーマに追従

### v1.4.0 — パフォーマンス最適化

- **仮想スクロール TreeView** — 10万件以上のファイルリストをメモリ効率的に表示
- **`__slots__` メモリ最適化** — `FileInfo` のメモリ使用量を約 60% 削減
- **スキャンキャッシュ** — 1時間の TTL 付きキャッシュで同一ターゲットの再スキャンを高速化
- **ストリーミング CSV パーサー** — 巨大な CSV をメモリに全て読み込まずに逐次処理

### v1.5.0 — CLI 拡張 + 動的ルーティング

- **LatencyProbe** — バックグラウンドスレッドで各 Provider のレイテンシを定期的にプローブ（P50 / P95 / 平均値を計測）
- **WeightedRouter** — レイテンシ・成功率・コストに基づく動的ウェイトルーティング
- **batch_chat** — 複数の LLM リクエストを並列実行（ThreadPoolExecutor 使用）
- **RequestCoalescer** — 同一内容の同時リクエストを自動マージして API コールを節約
- **CLI スクリプト化** — `--quiet` / `--json` / `--no-color` フラグ、プロフェッショナルな終了コード（`EXIT_SUCCESS`=0 / `EXIT_ERROR`=1 / `EXIT_WARNING`=2）
- **CLI バッチスキャン** — `--batch` / `--batch-file` で複数ターゲットを連続スキャン
- **JSON / CSV エクスポート** — スキャン結果と分析結果のファイル出力
- **OutputFormatter** — 統一された出力フォーマッタ（JSON / CSV / ヒューマンリーダブル / カラー出力）
- **366 件の統合テスト** — 全 6 ステージをカバーする包括的な回帰テストスイート

---

## スクリーンショット

![WizTree CLI Agent](docs/screenshot.png)

---

## クイックスタート

### インストール

```bash
# 依存関係のインストール
pip install -r requirements.txt
```

### 実行方法

```bash
# CLI モード（API キー不要 — ルールエンジンで動作）
python app.py --cli

# 対話モード
python cli.py --interactive

# スキャンして分析
python cli.py --scan "C:\Users" --analyze

# GUI モード（tkinter が必要）
python app.py

# バッチスキャン（複数ターゲット）
python cli.py --batch "C:\Users,D:\Data" --export-json results.json

# スクリプト化モード（終了コード対応）
python cli.py --scan "C:\Temp" --analyze --quiet --json --no-color
```

> **ヒント**: API キーがなくてもアプリケーションは完全に動作します。LLM が利用できない場合は、自動的にルールエンジン（10 の定義済みルール）にフォールバックします。

### 簡単な使用例

```python
from src.scanner import WizTreeScanner
from src.analyzer import RuleEngine
from src.safety import ComprehensiveSafetyManager

# 1. スキャン
scanner = WizTreeScanner(wiztree_path="W:\\WizTree\\WizTree64.exe")
scan_result = scanner.scan("C:\\Users", ScanOptions())

# 2. 分析（ルールエンジン）
engine = RuleEngine()
recommendations, warnings = engine.analyze_files(scan_result.files)

# 3. 安全チェック
safety = ComprehensiveSafetyManager()
safe_files = safety.validate(recommendations)
```

---

## アーキテクチャ

### 全体アーキテクチャ図

```
┌──────────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                              │
│                                                                  │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│    │ Scanner  │───▶│ Analyzer │───▶│  Safety  │                 │
│    │ スキャン  │    │ 分析     │    │ 安全     │                 │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘                 │
│         │               │               │                        │
│         ▼        ┌──────┴──────┐        ▼                        │
│    ┌─────────┐  ▼             ▼   ┌──────────┐                  │
│    │WizTree  │ ┌──────────┐ ┌────┐ │Blocklist │                  │
│    │  CLI    │ │ LLMRouter│ │Rule│ │ AudLog   │                  │
│    │  MFT    │ │ 6Prov.   │ │Eng │ │ FileValid│                  │
│    │  高速   │ │ 4戦略     │ │10規則│ │ Confirm   │                  │
│    └─────────┘ │ Circuit  │ └────┘ └──────────┘                  │
│                │ Breaker  │                                       │
│                │ Latency  │                                       │
│                │  Probe   │                                       │
│                │ Weighted │                                       │
│                │  Router  │                                       │
│                └──────────┘                                       │
└──────────────────────────────────────────────────────────────────┘
```

### データフロー

```
ユーザー入力（CLI / GUI）
    │
    ▼
Scanner ──▶ WizTree CLI ──▶ CSV 出力 ──▶ FileInfo[]
    │
    ▼
Analyzer ──▶ LLMRouter（API キーがある場合）
    │            ├── LatencyProbe（レイテンシプローブ）
    │            ├── WeightedRouter（動的重み付けルーティング）
    │            ├── CircuitBreaker（障害検出）
    │            └── RequestCoalescer（リクエストマージ）
    │         OR RuleEngine（フォールバック、API キー不要）
    │
    ▼
Safety ──▶ Blocklist（ブラックリスト）──▶ FileValidator（検証）
    │                                          │
    ▼                                          ▼
ユーザー確認ダイアログ ──▶ send2trash（ソフト削除）──▶ 監査ログ
```

### モジュール構造

```
wiztree-cli-agent/
├── app.py                          # GUI エントリポイント
├── cli.py                          # CLI エントリポイント（スクリプト化、バッチ対応）
├── build.py                        # PyInstaller ビルドスクリプト
├── requirements.txt                # Python 依存関係
├── config/
│   └── llm_config.json             # LLM Router 設定
├── docs/                           # ドキュメント
│   └── screenshot.png              # スクリーンショット
├── src/
│   ├── __init__.py                 # パッケージ定義、__version__ = "1.5.0"
│   ├── scanner/                    # スキャナーモジュール
│   │   ├── interface.py            # ScannerInterface（抽象基底クラス）
│   │   ├── wiztree_scanner.py      # WizTreeScanner（WizTree CLI ラッパー）
│   │   ├── path_validator.py       # PathValidator（パス検証）
│   │   ├── scan_progress.py        # ScanProgress（進捗管理）
│   │   ├── deep_search.py          # DeepSearcher（深層検索）
│   │   └── options.py              # ScanOptions（スキャンオプション）
│   ├── analyzer/                   # アナライザーモジュール
│   │   ├── interface.py            # AnalyzerInterface（抽象基底クラス）
│   │   ├── llm_analyzer.py         # LLMAnalyzer（LLM 分析）
│   │   ├── llm_router.py           # LLMRouter v1.5.0（動的ルーティング）
│   │   ├── rule_engine.py          # RuleEngine（10 定義済みルール）
│   │   ├── json_parser.py          # StreamingJsonParser（ストリーミング JSON）
│   │   ├── model_catalog.py        # ModelCatalog（OpenRouter モデルカタログ）
│   │   └── prompt_store.py         # PromptStore（プロンプト管理）
│   ├── safety/                     # セーフティモジュール
│   │   ├── interface.py            # SafetyInterface（抽象基底クラス）
│   │   ├── blocklist.py            # Blocklist（38 保護システムパス）
│   │   ├── audit_logger.py         # AuditLogger（SQLite 監査ログ + 復元）
│   │   ├── file_validator.py       # FileValidator（ファイル検証）
│   │   └── confirm_dialog.py       # ConfirmDialog（確認ダイアログ）
│   ├── ui/                         # UI モジュール
│   │   ├── main_window.py          # メインウィンドウ
│   │   ├── settings_dialog.py      # 設定ダイアログ
│   │   ├── keybindings.py          # キーボードショートカット
│   │   ├── config_panel.py         # 設定パネル
│   │   ├── results_view.py         # 結果ビュー
│   │   ├── file_table.py           # ファイル操作テーブル
│   │   ├── components/             # UI コンポーネント
│   │   │   ├── treemap_view.py     # Treemap 可視化
│   │   │   ├── squarify.py         # Squarified アルゴリズム
│   │   │   ├── drill_down.py       # Treemap ドリルダウン
│   │   │   ├── virtual_treeview.py # 仮想スクロール TreeView
│   │   │   ├── skeleton.py         # スケルトンスクリーン
│   │   │   └── status_bar.py       # ステータスバー
│   │   ├── tabs/                   # タブページ
│   │   │   ├── diff_preview.py     # Diff プレビュー
│   │   │   ├── history_tab.py      # 監査履歴
│   │   │   ├── models_tab.py       # モデルブラウザ
│   │   │   └── prompts_tab.py      # プロンプトエディタ
│   │   ├── themes/                 # テーマ
│   │   │   └── modern_theme.py     # 6 テーマ管理
│   │   └── animations/             # アニメーション
│   │       └── smooth_progress.py  # 60fps プログレスバー
│   ├── models/                     # データモデル
│   │   ├── file_info.py            # FileInfo（__slots__ 最適化）
│   │   ├── scan_result.py          # ScanResult
│   │   └── analysis_result.py      # AnalysisResult / RiskLevel
│   └── utils/                      # ユーティリティ
│       ├── config_loader.py        # 3 段階カスケード設定ローダー
│       └── credential_store.py     # OS keyring 資格情報ストレージ
└── tests/                          # テスト（約 30 ファイル）
    ├── test_integration_v150.py    # v1.5.0 統合テスト
    ├── test_router_v150.py         # v1.5.0 ルーターテスト
    ├── test_router.py              # ルーターテスト
    ├── test_scanner.py             # スキャナーテスト
    ├── test_analyzer.py            # アナライザーテスト
    ├── test_safety.py              # セーフティテスト
    ├── test_export.py              # エクスポートテスト
    └── ...                         # 他 20+ テストファイル
```

---

## LLM Router

LLM Router は、統一された大規模言語モデル API ゲートウェイ層です。複数の LLM プロバイダーを管理し、状況に応じて最適なプロバイダーを自動選択します。

### サポートされている Provider

| Provider | 環境変数 | 無料モデル | 特徴 |
|----------|---------|-----------|------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | deepseek-v4-flash | 中国本土から直接接続可能、高コストパフォーマンス、100万トークンコンテキスト |
| **OpenAI** | `OPENAI_API_KEY` | — | GPT-4o-mini / GPT-4o、マルチモーダル（Vision）対応 |
| **Anthropic** | `ANTHROPIC_API_KEY` | — | Claude 3 Haiku / Claude 3.5 Sonnet、高度な推論能力 |
| **OpenRouter** | `OPENROUTER_API_KEY` | gemini-2.0-flash-exp:free | 300+ モデルを集約するゲートウェイ、フェイルバックに最適 |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | DeepSeek-V3, Qwen2.5-7B | 中国国内の無料モデルプロバイダー |
| **Ollama** | 不要（ローカル） | llama3.2, qwen2.5 | ローカル実行、完全無料、インターネット不要 |

### ルーティング戦略

| 戦略 | 説明 | 使用シナリオ |
|------|------|-------------|
| `cost`（コスト優先） | 最も安いモデルを選択 | 予算が限られている場合 |
| `latency`（レイテンシ優先） | 最も応答の速い Provider を選択 | 素早い応答が必要な場合 |
| `fallback`（フォールバック） | 自動的に利用可能な Provider に切り替え | 高可用性が求められる場合 |
| `manual`（手動） | 特定の Provider を指定 | 明示的にプロバイダーを選びたい場合 |

### v1.5.0 新機能 — 動的ルーティング

#### LatencyProbe（レイテンシプローブ）

バックグラウンドのデーモンスレッドが定期的に各 Provider に最小リクエスト（1トークン）を送信し、レイテンシを計測します。

- スライディングウィンドウ（直近 20 サンプル）で統計を管理
- P50 / P95 / 平均値 / 成功率を提供
- スレッドセーフな設計

```python
from src.analyzer.llm_router import LLMRouter, RoutingStrategy

router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash",
    enable_probe=True,       # レイテンシプローブを有効化
    probe_interval=30,       # 30秒間隔でプローブ
)
```

#### WeightedRouter（動的ウェイトルーター）

レイテンシ・成功率・コストの3軸で各 Provider の総合スコアを計算し、確率的に選択します。

```python
from src.analyzer.llm_router import WeightedRouter

router = WeightedRouter(
    strategy=RoutingStrategy.COST,
    enable_probe=True,
    weights={"latency": 0.4, "success": 0.4, "cost": 0.2},
)
```

スコア計算式:

```
score = w_latency × f(レイテンシ) + w_success × f(成功率) + w_cost × f(コスト)
```

#### バッチ並列リクエスト

```python
from src.analyzer.llm_router import batch_chat, BatchRequest

results = batch_chat(router, [
    BatchRequest(messages=[{"role": "user", "content": "ファイル分析1"}]),
    BatchRequest(messages=[{"role": "user", "content": "ファイル分析2"}]),
    BatchRequest(messages=[{"role": "user", "content": "ファイル分析3"}]),
], max_workers=4)
```

#### RequestCoalescer（リクエストマージャー）

同一内容の同時リクエストを SHA-256 ハッシュで識別し、最初のリクエストのみ実際に API を呼び出し、後続はその結果を共有します。

```python
from src.analyzer.llm_router import RequestCoalescer

coalescer = RequestCoalescer(router)
# 同一メッセージの並列リクエスト → 1回だけ API 呼び出し
```

### Circuit Breaker（断路器）

各 Provider にはサーキットブレーカーが実装されており、連続失敗を検出して自動的に通信を遮断します。

| 状態 | 説明 |
|------|------|
| **CLOSED** | 正常動作中 |
| **OPEN** | 3回連続失敗で遮断。60秒後に HALF_OPEN へ |
| **HALF_OPEN** | 試験的に1リクエストを許可。成功すれば CLOSED、失敗すれば OPEN に戻る |

---

## 設定

### API キーの設定

```bash
# DeepSeek（推奨）
set DEEPSEEK_API_KEY=sk-your-key

# OpenAI
set OPENAI_API_KEY=sk-your-key

# Anthropic
set ANTHROPIC_API_KEY=sk-ant-your-key

# OpenRouter
set OPENROUTER_API_KEY=sk-your-key

# SiliconFlow
set SILICONFLOW_API_KEY=sk-your-key

# Ollama（ローカル — API キー不要）
```

> **v1.2.0 からの新機能**: GUI（設定 → 資格情報）から安全に API キーを保存できます。キーは OS の資格情報管理機能（Windows DPAPI / macOS Keychain / Linux Secret Service）に暗号化されて保存されます。

### 設定ファイル

設定は3段階のカスケード方式で管理されます:

1. **ビルトイン初期値** — `config/llm_config.json`
2. **ユーザー設定** — `~/.wiztree-cli-agent/config.json`（初回起動時に自動移行）
3. **実行時オーバーライド** — プログラム内からの変更

```json
{
  "strategy": "fallback",
  "default_model": "deepseek-v4-flash",
  "timeout": 30,
  "max_retries": 2,
  "providers": [
    {
      "name": "deepseek",
      "base_url": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "priority": 1,
      "models": [
        {
          "id": "deepseek-v4-flash",
          "context_window": 1000000,
          "cost_input": 0.14,
          "cost_output": 0.28
        }
      ]
    }
  ]
}
```

### WizTree の設定

| 項目 | 説明 |
|------|------|
| デフォルトパス | `W:\WizTree\WizTree64.exe` |
| カスタムパス | GUI または CLI で任意のパスを指定可能 |

---

## テスト

### テスト実行

```bash
# 全テスト実行
pytest tests/ -v

# 特定のテストファイルを実行
pytest tests/test_scanner.py -v

# v1.5.0 統合テスト
pytest tests/test_integration_v150.py -v

# v1.5.0 ルーターテスト
pytest tests/test_router_v150.py -v

# LLM Router デモ
python tests/demo_router.py
```

### テストカバレッジ

| バージョン | テスト数 | 対象 |
|-----------|---------|------|
| v1.0.0 | 68 ユニットテスト | 全コアモジュール |
| v1.1.0 | +4 UI テスト | メインウィンドウ、FileTable、ResultsView、プログレスバー |
| v1.2.0 | +30 統合テスト（5シナリオ × 6ステージ） | テーマ、キーバインド、ドラッグ＆ドロップ、監査、Diff、Treemap |
| v1.3.0 | +6 テスト | スケルトンスクリーン、テーマ切り替え |
| v1.4.0 | +12 テスト | 仮想スクロール、メモリ最適化、スキャンキャッシュ、CSV ストリーミング |
| v1.5.0 | +60 テスト | ルーター動的機能、CLI スクリプト化、バッチスキャン、エクスポート |
| **合計** | **366 合格、116 スキップ** | |

### テストカテゴリ

- **ユニットテスト**: 各モジュールの個別機能を網羅的にテスト
- **統合テスト**: スキャナー → アナライザー → セーフティのエンドツーエンドフロー
- **LLM Router テスト**: LatencyProbe、WeightedRouter、batch_chat、RequestCoalescer の動的機能
- **CLI テスト**: 終了コード、出力フォーマット、バッチモード
- **エクスポートテスト**: JSON / CSV 出力の正確性
- **パフォーマンステスト**: 仮想スクロール、メモリ使用量、キャッシュ効率
- **UI テスト**: テーマ切り替え、キーボードショートカット、ドラッグ＆ドロップ
- **安全テスト**: ブラックリスト、監査ログ、ファイル検証、確認ダイアログ

---

## ライセンス

MIT License

Copyright (c) 2026 WizTree CLI Agent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## 貢献

Issue と Pull Request は大歓迎です。大きな変更を加える前に、まず Issue を開いて議論してください。

1. このリポジトリをフォーク
2. 機能ブランチを作成（`git checkout -b feature/amazing-feature`）
3. 変更をコミット（`git commit -m 'Add amazing feature'`）
4. ブランチにプッシュ（`git push origin feature/amazing-feature`）
5. Pull Request を作成

---

*この README は WizTree CLI Agent v1.5.0 に対応しています。*
