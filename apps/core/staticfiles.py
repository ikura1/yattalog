"""本番の静的ファイルの入れ物。

画面のスクリプトは、機能ごとのファイルに分けて、入口（`js/app.js`）から読み込む（決定 070）。
本番ではファイル名に中身のハッシュが入るので、読み込む先の名前も書き換える。
こうしておくと、どのファイルを変えても入口の名前が変わり、開いたままの画面が新しい版に切り替わる。
"""

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ModuleStaticFilesStorage(CompressedManifestStaticFilesStorage):
    support_js_module_import_aggregation = True
