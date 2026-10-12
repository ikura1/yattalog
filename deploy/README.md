# デプロイ（Cloud Run ＋ Neon、決定 033）

試験運用（α・β）の構成。月額はほぼ0円（無料枠の範囲）。

```
スマホ ──HTTPS──▶ Cloud Run（シンガポール、使われていないときは0台）──▶ Neon PostgreSQL（AWS シンガポール、無料プラン）
                     ▲
GitHub（main に入る）──▶ GitHub Actions：イメージを作る → マイグレーション → デプロイ
```

## 初回だけやること

### 1. Neon
1. https://neon.com で無料アカウントを作り、プロジェクトを作る（リージョン：**AWS Asia Pacific (Singapore)**）
2. 「Connection string」で **Pooled connection** を選び、接続文字列（`postgresql://...-pooler...?sslmode=require`）を控える

### 2. Google Cloud のプロジェクト
1. 新しいプロジェクトを作り、請求先アカウントを紐づける（無料枠内でも必要）
2. **予算アラート**を設定する（例：月 ¥500 で通知）。「お支払い → 予算とアラート」
3. ダッシュボードの「プロジェクト番号」（数字）を控える

### 3. Google ログイン用の OAuth クライアント
1. 「API とサービス → OAuth 同意画面」を設定する（ユーザーの種類：外部、公開ステータス：テスト中。テストユーザーに自分のアドレスを追加）
2. 「認証情報 → 認証情報を作成 → OAuth クライアント ID」（種類：ウェブ アプリケーション）
3. 承認済みのリダイレクト URI に次を入れる（`<プロジェクト番号>` は 2-3. で控えた数字）
   ```
   https://yattalog-<プロジェクト番号>.asia-southeast1.run.app/accounts/google/login/callback/
   ```
4. 表示された**クライアント ID** と**クライアントシークレット**を控える

### 4. 初期設定のスクリプト
Cloud Shell（コンソール右上の `>_`）で流す。途中で Neon の接続文字列と、3. のクライアントシークレットを聞かれる。
```sh
git clone https://github.com/ikura1/yattalog && cd yattalog
bash deploy/gcp-setup.sh <PROJECT_ID>
```
何度流しても大丈夫（作成済みのものはそのまま使う）。

### 5. GitHub
`gcp-setup.sh` の最後に表示された値（`GOOGLE_CLIENT_ID` は 3. で控えたもの）を、リポジトリの **Settings → Secrets and variables → Actions → Variables** に登録する。
登録したら Actions の「Deploy」を手動で実行する（以後は main にマージするたびに自動でデプロイされる）。

## 管理者を作る・管理画面に入る（決定 045）
管理画面に入れるのは、決めたメールアドレスの人が、Google でログインし、さらに2段階認証を通したときだけ。パスワードは使わない。

### 管理者にする（初回だけ）
1. GitHub の **Settings → Secrets and variables → Actions → Secrets** タブで、`ADMIN_EMAILS` という名前の **Secret** を作り、管理者にする Google アカウントのメールアドレスを入れる
   - Variables ではなく **Secrets** に入れる（リポジトリが公開で、Actions のログも公開されるため。Secret はログで伏せられる）
   - 複数にするときは、空白で区切る
2. Actions の「Deploy」を手動で実行する（または、次に main へマージされるのを待つ）

### 管理画面に入る
1. 管理画面の URL を調べる（推測しにくい値にしてある）。手元のターミナルで：
   ```sh
   echo "https://yattalog-<プロジェクト番号>.asia-southeast1.run.app/$(gcloud secrets versions access latest --secret django-admin-url --project <PROJECT_ID>)/"
   ```
2. アプリに Google でログインした状態で、その URL を開く
3. **はじめてのとき**：2段階認証の登録画面が出る。スマホの認証アプリ（Google Authenticator、1Password など）に登録し、6桁のコードを入れる
   - 登録用の鍵は、このときしか表示されない
4. **2回目から**：6桁のコードを入れるだけ。ブラウザを変えたり、ログインし直したりすると、もう一度コードが要る

### 管理者をやめさせる・スマホをなくしたとき
- やめさせる：`ADMIN_EMAILS` から外してデプロイする。すぐに入れなくなる
- 認証アプリを入れたスマホをなくした：データベース（Neon のコンソール）で、`otp_totp_totpdevice` のその人の行を消す。次に開いたときに、登録し直しになる

### 管理画面でできること
ユーザーの一覧（メールアドレス、登録日、イベント数、記録数）、利用の停止、アカウントの削除（その人のデータもすべて消える）。
記録やイベントの中身を見る画面は、用意していない。

## 監視
死活監視・毎朝の報告・Error Reporting の通知。設定と、Claude への頼み方は `docs/operations.md`（決定 046）。

## 費用を抑えるための設定
- Cloud Run：最小0台・最大2台、リクエストを処理している間だけ課金
- Artifact Registry：イメージは新しい5つだけを残す（無料枠0.5GBに収める）
- Neon：無料プラン（1GB、5分使わないと休止）

## 将来
- 写真（β）：Cloudflare R2（決定 005・024）
- 利用者が増えて待ち時間が気になったら：Cloud Run の最小インスタンスを1にする、または Render などの常時起動に移す
