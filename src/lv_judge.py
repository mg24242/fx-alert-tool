from __future__ import annotations


def judge_lv(title: str, content: str, keywords: dict) -> int:
    """
    記事のタイトルと本文からLvを判定する。
    タイトルマッチを優先（重要発言は見出しに入るため）。
    強いキーワードが優先（Lv4 > Lv3 > Lv2）。
    """
    title = title or ""
    content = content or ""

    lv_keywords = keywords.get("lv_keywords", keywords)

    # タイトル優先で判定
    for lv in [4, 3, 2]:
        for kw in lv_keywords.get(f"lv{lv}", []):
            if kw and kw in title:
                return lv

    # タイトルになければ本文を見る
    for lv in [4, 3, 2]:
        for kw in lv_keywords.get(f"lv{lv}", []):
            if kw and kw in content:
                return lv

    # どれにもマッチしなければLv1（通常）
    return 1
