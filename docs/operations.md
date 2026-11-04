# 運用（監視と改善）

本番の様子に気づき、Claude に確かめてもらい、直すまでの手順。なぜこの形にしたかは決定 046。

## 自動で動いているもの
| 名前 | いつ | 何をする | 異常のとき |
|---|---|---|---|
| Uptime（`.github/workflows/uptime.yml`） | 1時間ごと | `/health` が 200 を返すか（DB には触れない） | Issue「本番に繋がらない（死活監視）」（ラベル `ops`）と Discord |
| Ops report（`.github/workflows/ops-report.yml`） | 毎朝 9:07・手動 | 直近24時間のリクエストとエラーをまとめてサマリーに出す | エラーの種類ごとに Issue「本番のエラー：…」（`ops`）と Discord（題名と回数だけ） |
| Error Reporting（Google Cloud） | 常に | 例外を種類ごとにまとめる | 新しい種類が出たらメール |
| 予算アラート（Google Cloud） | 常に | 月 ¥500 を超えそうか | メール |

Issue はリポジトリの通知で Yuki さんにも届く。Claude は同じ Issue を見る。
Discord の知らせ（決定 067）は Secret `OPS_WEBHOOK_URL` があるときだけ送る。送るのは `apps/core/ops_notify.py`。

## Claude への頼み方
プロジェクトのチャットで、次のように頼む。

| 頼み方 | Claude がすること |
|---|---|
| 「本番を見て」 | Ops report を手動で実行し（直近24時間）、要点と気になる点を返す。直すべきものは Issue にする |
| 「この1週間の本番をふりかえって」 | 期間を 168 時間にして同じことをする。遅い経路や 429 の傾向から、改善の候補を出す |
| 「#NN を直して」 | Issue と報告から場所を絞り、テストで再現してから直して PR を出す。CI が通ったら知らせる |
| 「デプロイを確かめて」 | Deploy の実行結果と新しいリビジョンを確かめ、Ops report を短い期間で流して、エラーが出ていないかを見る |
| 「`ops` の Issue を片付けて」 | 開いている `ops` の Issue を見て、直せるものは PR に、様子見のものは理由を書いて残す |

マージは今までどおり Yuki さんが行う。マージの後、Claude はデプロイと Ops report で直ったことを確かめてから Issue を閉じる。

### Claude から見えないもの
Claude が見られるのは、伏せた報告（経路の形、回数、例外の種類、自前のコードの位置）だけ。
エラーのメッセージが手がかりになるときは、Yuki さんが Error Reporting の画面で見て、**利用者のデータを除いて**要点を伝える。

## 報告で伏せるもの（リポジトリが公開のため）
`apps/core/ops_report.py` が伏せる。変えるときはテスト（`apps/core/tests/test_ops_report.py`）を先に足す。
- 経路の ID・数字・クエリ → `<id>` など。知らない経路（管理画面など）→ `/<その他>`
- エラーの本文と例外のメッセージ → 捨てる
- Cloud Logging の生のデータ → ランナーのファイルにだけ書いて、使い終わったら消す

## 初回の設定
2026-10-19 に、1・2・4 を済ませた（読むだけのアカウント `yattalog-ops` を Claude が gcloud で作り、Variable `GCP_OPS_SA` を登録。Ops report の成功を確認）。3 の Error Reporting の通知は Yuki さんが画面で行う。

1. **読むだけのアカウントを作る**：Cloud Shell で
   ```sh
   cd yattalog && git pull
   bash deploy/gcp-setup.sh yattalog-511302
   ```
   作成済みのものはそのまま使われ、秘密の値も聞かれない。最後に `GCP_OPS_SA` が表示される
2. **GitHub に登録する**：Settings → Secrets and variables → Actions → Variables に `GCP_OPS_SA` を足す
3. **Error Reporting の通知を入れる**：Google Cloud のコンソール →「Error Reporting」→「通知を構成」で、メールの通知チャネル（自分のアドレス）を選ぶ
4. 確かめる：Actions の「Ops report」を手動で実行し、サマリーが出ることを見る（Claude に「本番を見て」と頼んでもよい）

5. **Discord の通知を入れる**（決定 067）
   1. Discord で自分だけのサーバーを作り、通知用のチャンネル（例：`#yattalog-ops`）を作る
   2. チャンネルの設定 →「連携サービス」→「ウェブフック」→「新しいウェブフック」→「ウェブフック URL をコピー」
   3. GitHub の Settings → Secrets and variables → Actions → **Secrets** に `OPS_WEBHOOK_URL` として登録する（URL は書き込みの鍵なので、チャットや Issue には貼らない）
   4. 確かめる：Actions の「Ops report」を手動で実行し、「Discord にテストの知らせを送る」に印を付ける（Claude に「通知を確かめて」と頼んでもよい）。ふだんは、エラーがあったときだけ送る

`APP_URL` は `https://yattalog.ikura1.dev`（2026-10-19、決定 064）。

独自のドメインにしてから、自動の探索（`/.git`、`/actuator`、`/wp-json` など）が来ていて、4xx（ほとんど 404）が多く出る。証明書の公開の記録にドメインが載るためで、どれも 404 を返すだけなので、気にしなくてよい。

## 費用
増えない。公開リポジトリの Actions は無料。Cloud Logging の読み出し・Error Reporting・1日24回の `/health` は無料枠に収まる。`/health` は DB に触れないので、Neon の計算時間も使わない。
