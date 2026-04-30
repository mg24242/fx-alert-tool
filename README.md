# fx-alert-tool

要人発言（為替・介入関連）をRSSから自動検知し、Lv判定してDiscordに通知するツールです。  
仕様は `KNOWLEDGE.md` の第6章「要人発言監視ツールの仕様書」に準拠しています。

## 使い方（ローカル実行）

### 前提

- Python 3.11+

### セットアップ

```bash
python -m venv .venv
# Windows(PowerShell)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`.env` にDiscord Webhook URLとログレベルを設定してください。

### 実行

```bash
python -m src.main
```

## 初期セットアップ手順（6-12 準拠）

### Step 1: Discordサーバーとチャンネル作成

1. Discordアプリで新規サーバー作成（自分専用、テンプレートは「ゲーミング」等で可）
2. 以下の3チャンネルを作成
   - `#fx-alert-low`（Lv2用）
   - `#fx-alert-mid`（Lv3用）
   - `#fx-alert-high`（Lv4-5用）
3. 各チャンネルでWebhookを作成
   - チャンネル右クリック → 「チャンネルの編集」 → 「連携サービス」 → 「ウェブフック」 → 「新しいウェブフック」
   - URLをコピー
4. `#fx-alert-low` のプッシュ通知設定をOFFに、他はONに（モバイル）

### Step 2: GitHubリポジトリ設定（Secrets）

1. リポジトリのSettings → Secrets and variables → Actions に以下を登録
   - `DISCORD_WEBHOOK_LOW`
   - `DISCORD_WEBHOOK_MID`
   - `DISCORD_WEBHOOK_HIGH`

### Step 3: 動作確認

1. GitHub Actions の `Run workflow` から手動実行
2. ログを見て、各フィードからの取得が成功しているか確認
3. テスト用に意図的にマッチするキーワードを `config/keywords.yml` に追加してDiscord通知が来るか確認
4. 確認できたらテスト用キーワードを削除

### Step 4: 運用開始

- 5分ごとに自動実行される
- 1週間運用して、通知数が多すぎ/少なすぎを観察
- `config/keywords.yml` を編集してチューニング

## テスト

```bash
pytest
```