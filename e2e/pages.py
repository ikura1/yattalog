"""E2E テストで、画面の部品を探すための道具。"""


def tile(page):
    return page.locator("#grid .tile", has_text="シーツ交換")
