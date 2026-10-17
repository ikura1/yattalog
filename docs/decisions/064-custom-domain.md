# 064. 独自のドメイン yattalog.ikura1.dev で出す

- 日付：2026-10-17
- 状態：決定（切り替えの途中。下の手順を参照）

## 背景
これまでは Cloud Run の URL（`yattalog-332057063162.asia-southeast1.run.app`）で出していた。覚えにくく、後からドメインを変えるとホーム画面に追加したアプリとログインがやり直しになるので、β を開く前に決める（#13）。Yuki さんが持っている `ikura1.dev`（Squarespace）のサブドメインを使う。

## 決定
- ドメインは **`yattalog.ikura1.dev`**
- つなぎ方は **Cloud Run のドメインの紐づけ**（`gcloud beta run domain-mappings`）。無料で、証明書も Google が自動で出す
  - 正式な方法（ロードバランサー）は月 2,000〜3,000円ほどかかり、予算（月 1,000円、決定 052）を超える。紐づけは Google の「プレビュー」だが、β では十分。困ったら、無料の Firebase Hosting を前に置く方法に移る
- DNS（Squarespace）は、`yattalog` の CNAME を `ghs.googlehosted.com` に向ける。Squarespace の「転送（Domain Forwarding）」は使わない（転送すると、アドレス欄が run.app に変わる）
- 古いホスト（run.app）に来た人は、同じ道のりのまま新しいドメインへ 301 で送る（`apps/core/canonical.py`）。寄せ先は GitHub の Variable `CANONICAL_HOST`
  - 送るのは GET と HEAD だけ。POST を 301 で送ると中身が消えるので、開いたままの画面からの記録は、古いホストのまま受ける
  - `/health` は送らない（死活監視）

## 切り替えの手順
1. [x] Search Console で `ikura1.dev` の持ち主を確認する（gcloud にログインしているアカウントで）
2. [x] Cloud Run にドメインをつなぐ（`gcloud beta run domain-mappings create --service yattalog --domain yattalog.ikura1.dev --region asia-southeast1`）
3. [ ] Squarespace：`yattalog` の転送を消し、CNAME `ghs.googlehosted.com` を足す → 証明書の発行を待つ（15分〜24時間）
4. [x] GitHub の Variable `DJANGO_ALLOWED_HOSTS` に `yattalog.ikura1.dev` を足す（次のデプロイから効く）
5. [ ] Google ログイン：OAuth クライアントに、承認済みの JavaScript 生成元 `https://yattalog.ikura1.dev` と、リダイレクト URI `https://yattalog.ikura1.dev/accounts/google/login/callback/` を足す。同意画面の承認済みドメインに `ikura1.dev` を足す（古い run.app の分は、しばらく残す）
6. [ ] 新しいドメインで、ログイン・記録ができることを確かめる
7. [ ] GitHub の Variable `CANONICAL_HOST` に `yattalog.ikura1.dev` を入れて、デプロイし直す（ここから古いホストの人を送り始める）
8. [ ] 死活監視（Variable `APP_URL`）、Umami のサイトのドメイン、Search Console をそろえる

## 影響・トレードオフ
- ホーム画面に追加したアプリは、新しいドメインでは別のアプリになる。追加し直し、ログインし直しになる（β の前なので、いまは Yuki さんだけ）
- 古い投稿のリンク（run.app）は、転送で新しいドメインに届く
