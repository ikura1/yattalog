# 利用規約とプライバシーポリシー

本文は、アプリが表示するテンプレートが正（決定 041）。

- 利用規約：`templates/web/legal/terms.html`（`/terms/`）
- プライバシーポリシー：`templates/web/legal/privacy.html`（`/privacy/`）
- 問い合わせ先（両方に出る）：`templates/web/legal/_contact.html`

運営者名・制定日・改定日・問い合わせ先は `config/settings.py` で決める（`OPERATOR_NAME`、`LEGAL_DATE`、`TERMS_REVISED`、`PRIVACY_REVISED`、`FEEDBACK_URL`、`CONTACT_FORM_URL`）。

## 変えるとき
1. テンプレートを直す
2. 日付と版をそろえる（登録時に、同意した版として記録している）
   - 規約を変えたら `TERMS_REVISED` と `TERMS_VERSION`（2026-10-19 に、免責・禁止事項・変更の通知を見直して改定。`LEGAL_DATE` は制定日なので変えない）
   - ポリシーを変えたら `PRIVACY_REVISED` と `PRIVACY_VERSION`（2026-10-13 にアクセス解析で改定、決定 047。2026-10-17 に実績と、問い合わせフォーム（Google フォーム）の委託で改定、決定 063）
3. 機能を足して、取得する情報・委託先・保存期間が変わるときは、**機能を出す前に**ポリシーを直す
   - 例：アクセス解析（決定 047、Umami を外部送信に書いた）、写真（Cloudflare R2 が委託先に加わる）、位置情報（#56。いまは「取得しません」と書いている）、エラー監視（#24）

## 確かめたこと
- 運営者の管理用アカウント（Google、GitHub、Neon）の2段階認証（ポリシーの「安全管理措置」に書いた）：2026-10-19 に Yuki さんが確認

## まだ確かめていないこと
- 専門家の確認は受けていない。一般公開の前に受けることをすすめる
- 個人が活動名（ikura1）で運営者を表示し、氏名と住所を「請求があれば開示」とする扱いでよいか
- Neon の運営会社の正式な名称（ポリシーには「Neon（Databricks, Inc.）」と書いた）
- Neon のバックアップ（履歴）の保持期間（ポリシーには「30日以内に削除」と書いた。#26）
- アクセスログの保存場所（ポリシーには「シンガポール」と書いた）。Cloud Logging の `_Default` バケットは、設定を変えていなければ場所が global になる
- Google から受け取る情報は、ポリシー 2章の項目（ID、メールアドレス、表示名）だけを保存している（`adapters.GOOGLE_KEPT_FIELDS`）。scope やプロバイダを足すときは、こことポリシーを一緒に直す
