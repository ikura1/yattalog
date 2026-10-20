"""画面（Django テンプレート＋htmx）。処理はすべてサービス層に任せる（決定 027）。

機能ごとにファイルを分けている。URL（apps/web/urls.py）からは、ここを通して呼ぶ。
"""

from apps.web.views.account import account_delete, export, settings_sheet
from apps.web.views.achievements import achievement_share, achievements
from apps.web.views.events import (
    EMOJIS,
    categories,
    category_edit,
    category_new,
    event_detail,
    event_edit,
    event_move,
    event_new,
    event_remove,
    event_restore,
)
from apps.web.views.home import archived, grid, home, menu, set_timezone, starters
from apps.web.views.records import log_delete, log_edit_sheet, record, record_sheet, share_sheet, undo
from apps.web.views.review import review
from apps.web.views.site import (
    install_guide,
    login_page,
    logout_view,
    manifest,
    offline,
    privacy,
    service_worker,
    terms,
)

__all__ = [
    "EMOJIS",
    "account_delete",
    "archived",
    "achievement_share",
    "achievements",
    "categories",
    "category_edit",
    "category_new",
    "event_detail",
    "event_edit",
    "event_move",
    "event_new",
    "event_remove",
    "event_restore",
    "export",
    "grid",
    "home",
    "install_guide",
    "log_delete",
    "log_edit_sheet",
    "login_page",
    "logout_view",
    "manifest",
    "menu",
    "offline",
    "privacy",
    "record",
    "record_sheet",
    "review",
    "service_worker",
    "set_timezone",
    "settings_sheet",
    "share_sheet",
    "starters",
    "terms",
    "undo",
]
