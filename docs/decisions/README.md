# 決定記録（Decision Records）

仕様や設計の「なぜそう決めたか」を、1件1ファイルで残す。

- ファイル名：`NNN-短いタイトル.md`（連番）
- 一度書いた記録は書き換えない。方針を変えるときは新しい記録を追加し、古い記録の状態を「置き換え済み（→ NNN）」にする

## テンプレート

```markdown
# NNN. タイトル

- 日付：YYYY-MM-DD
- 状態：決定 / 置き換え済み（→ NNN）

## 背景
## 決定
## 理由
## 影響・トレードオフ
```

## 一覧

| No. | タイトル | 状態 |
|---|---|---|
| 001 | [TimeTask を Yattalog として作り直す](001-rebuild-as-yattalog.md) | 決定 |
| 002 | [一般公開する](002-public-release.md) | 決定 |
| 003 | [スマホ中心・PWA で作る](003-mobile-first-pwa.md) | 決定 |
| 004 | [v1 は個人用、共有は将来に備える](004-personal-first-sharing-later.md) | 決定 |
| 005 | [デプロイ先は Render と Cloudflare R2](005-hosting-render-r2.md) | 決定（アプリと DB は 033 で置き換え） |
| 006 | [記録はタップで即記録、長押しで詳細入力](006-tap-and-long-press.md) | 決定（010 で具体化） |
| 007 | [目安の間隔（期限）は持たせない](007-no-target-interval.md) | 決定 |
| 008 | [ホームの並び順は手動](008-manual-ordering.md) | 決定（010 で具体化） |
| 009 | [はじめて使うときはテンプレートから選ぶ](009-onboarding-templates.md) | 決定 |
| 010 | [ホームは Streaks 風のアイコングリッドにする](010-streaks-style-grid.md) | 決定 |
| 011 | [イベント詳細の統計はカレンダー・記録回数・平均間隔の3つ](011-event-stats.md) | 決定（018 で拡張） |
| 012 | [過去の日付で記録できるようにし、時刻は任意にする](012-past-date-logging.md) | 決定（保存形式は 023 で置き換え） |
| 013 | [カテゴリを1つだけ持たせ、ホームのタブで切り替える](013-categories-as-tabs.md) | 決定 |
| 014 | [毎日続いているイベントに連続記録バッジを出す](014-streak-badge.md) | 決定（015 で拡張） |
| 015 | [連続記録の単位をイベントごとに選べるようにする](015-streak-unit-per-event.md) | 決定 |
| 016 | [ログインは Google アカウントのみにする](016-google-login-only.md) | 決定 |
| 017 | [SNS へのシェアは「シェア画像＋共有シート」で行う](017-share-image-via-share-sheet.md) | 決定 |
| 018 | [イベント詳細に「よくやる時期」（月別の棒グラフ）を追加する](018-seasonal-chart.md) | 決定 |
| 019 | [API を前提に作り、MCP サーバーは v1.x で公開する](019-api-first-mcp-later.md) | 決定（027 で具体化） |
| 020 | [実績バッジを入れる（失うものは作らない）](020-achievements.md) | 決定 |
| 021 | [データの書き出し（ZIP）と退会時の完全削除に対応する](021-export-and-deletion.md) | 決定 |
| 022 | [v1 ではオフラインでの記録に対応しない](022-no-offline-logging-in-v1.md) | 決定 |
| 023 | [タイムゾーンはユーザーごとに持ち、時刻なしの記録は日付で保存する](023-per-user-timezone.md) | 決定（保存形式は 026 で置き換え） |
| 024 | [写真は端末で縮小し、1ユーザー1GBまでとする](024-photo-limits.md) | 決定（029 で補強） |
| 025 | [サーバーは Django（＋ Django Ninja）で作る](025-tech-stack-django.md) | 決定 |
| 026 | [すべての記録に「記録した日の日付」を持たせ、後から変えない](026-log-local-date.md) | 決定 |
| 027 | [処理はサービス層にまとめ、画面と API の両方から呼ぶ](027-service-layer.md) | 決定 |
| 028 | [記録は端末で ID を作って送り、画面は先に更新する](028-optimistic-logging.md) | 決定 |
| 029 | [写真はサーバーでも検証して作り直し、書き出しの CSV は無害化する](029-server-side-validation.md) | 決定 |
| 030 | [α・β・一般公開の3段階でリリースする](030-staged-release.md) | 決定 |
| 031 | [ホーム画面への追加（PWA）を案内する](031-pwa-install-guide.md) | 決定 |
| 032 | [データモデルの基本方針](032-data-model.md) | 決定 |
| 033 | [試験運用は Cloud Run ＋ Neon（無料プラン）で動かす](033-cloud-run-neon-for-trial.md) | 決定 |
| 034 | [今日の記録は「さっき」「N時間」で表示する](034-elapsed-hours-today.md) | 決定 |
| 035 | [アイコンはすべての絵文字から選べるようにする（キーボードで入力）](035-any-emoji-icon.md) | 決定 |
| 036 | [カテゴリに絵文字を付けられるようにする（任意）](036-category-emoji.md) | 決定 |
| 037 | [レート制限はアプリの中で、インスタンスごとに数える](037-rate-limit-in-app.md) | 決定 |
| 038 | [β は先着20人。登録できる人数に上限を設ける](038-user-cap-for-beta.md) | 決定 |
| 039 | [写真が入るまで、書き出しはその場で作って返す](039-export-on-request.md) | 決定 |
| 040 | [写真が入るまで、退会はその場で全データを消す](040-delete-account-immediately.md) | 決定 |
| 041 | [規約とポリシーをアプリで表示し、問い合わせ先を公開と非公開の2つに分ける](041-legal-pages-and-contact.md) | 決定 |
| 042 | [テンプレートは、空のホームにそのまま出す](042-starters-on-empty-home.md) | 決定 |
| 043 | [アプリのアイコンを決め、ホーム画面への追加を案内する](043-app-icon-and-install-guide.md) | 決定 |
| 044 | [写真は β に入れず、反応を見てから決める](044-photos-after-beta.md) | 決定 |
| 045 | [管理画面は、決めたメールアドレスと2段階認証で守る](045-admin-with-2fa.md) | 決定 |
