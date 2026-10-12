"""django.contrib.admin の代わりに INSTALLED_APPS に入れる設定（決定 045）。

アプリの読み込みの途中で読まれるので、ここではモデルを import しない。
"""

from django.contrib.admin.apps import AdminConfig


class SecureAdminConfig(AdminConfig):
    default_site = "apps.accounts.admin_site.SecureAdminSite"
