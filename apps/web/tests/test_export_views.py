"""データの書き出しの画面（SPEC 3.11.2、決定 039）。"""


def test_ログインしていなければ書き出せない(client, db):
    r = client.post("/export/")
    assert r.status_code == 302 and "/login/" in r["Location"]


def test_書き出しは_POST_だけ(client_in):
    assert client_in.get("/export/").status_code == 405


def test_書き出すと_自分のデータの_ZIP_がダウンロードされる(client_in, event):
    import io
    import zipfile

    r = client_in.post("/export/")

    assert r.status_code == 200 and r["Content-Type"] == "application/zip"
    assert r["Content-Disposition"] == 'attachment; filename="yattalog-20261010.zip"'
    assert "no-store" in r["Cache-Control"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        assert sorted(z.namelist()) == ["data.json", "events.csv", "logs.csv"]
        assert "シーツ交換" in z.read("events.csv").decode("utf-8")


def test_メニューから書き出せる(client_in):
    body = client_in.get("/menu/").content.decode()
    assert 'action="/export/"' in body and "データを書き出す" in body
