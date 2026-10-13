from django.urls import path

from apps.web import views

app_name = "web"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.login_page, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="sw"),
    path("offline/", views.offline, name="offline"),
    path("install/", views.install_guide, name="install"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("grid/", views.grid, name="grid"),
    path("menu/", views.menu, name="menu"),
    path("timezone/", views.set_timezone, name="timezone"),
    path("categories/", views.categories, name="categories"),
    path("starters/", views.starters, name="starters"),
    path("export/", views.export, name="export"),
    path("account/delete/", views.account_delete, name="account_delete"),
    path("events/new/", views.event_new, name="event_new"),
    path("events/<uuid:event_id>/", views.event_detail, name="event_detail"),
    path("events/<uuid:event_id>/edit/", views.event_edit, name="event_edit"),
    path("events/<uuid:event_id>/remove/", views.event_remove, name="event_remove"),
    path("events/<uuid:event_id>/restore/", views.event_restore, name="event_restore"),
    path("events/<uuid:event_id>/move/", views.event_move, name="event_move"),
    path("events/<uuid:event_id>/record/", views.record, name="record"),
    path("events/<uuid:event_id>/record-sheet/", views.record_sheet, name="record_sheet"),
    path("logs/<uuid:log_id>/undo/", views.undo, name="undo"),
    path("logs/<uuid:log_id>/edit/", views.log_edit_sheet, name="log_edit"),
    path("logs/<uuid:log_id>/delete/", views.log_delete, name="log_delete"),
]
