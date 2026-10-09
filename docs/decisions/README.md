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
| 005 | [デプロイ先は Render と Cloudflare R2](005-hosting-render-r2.md) | 決定 |
| 006 | [記録はタップで即記録、長押しで詳細入力](006-tap-and-long-press.md) | 決定 |
| 007 | [目安の間隔（期限）は持たせない](007-no-target-interval.md) | 決定 |
| 008 | [ホームの並び順は手動](008-manual-ordering.md) | 決定 |
| 009 | [はじめて使うときはテンプレートから選ぶ](009-onboarding-templates.md) | 決定 |
