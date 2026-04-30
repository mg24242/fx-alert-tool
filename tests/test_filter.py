import logging
from datetime import datetime

from src.filter import evaluate_article
from src.state import JST


def test_evaluate_article_happy_path():
    now = datetime(2026, 4, 30, 10, 0, tzinfo=JST)  # 09:00-22:00 の範囲

    state = {"notified_articles": [], "last_notification_per_person": {}}
    keywords = {
        "required_keywords": ["ドル円"],
        "target_persons": {
            "japan": {
                "high_priority": ["片山"],
                "role_keywords": ["財務相"],
            }
        },
        "lv_keywords": {"lv4": ["断固たる"], "lv3": ["準備はできて"], "lv2": ["過度な変動"]},
        "exclude_patterns": ["過去に.*?発言"],
    }
    settings = {
        "time_filter": [
            {"range": "09:00-22:00", "min_lv_to_notify": 2},
            {"range": "22:00-06:00", "min_lv_to_notify": 3},
            {"range": "06:00-09:00", "min_lv_to_notify": 4},
        ],
        "cooldown": {"default_minutes": 60, "bypass_for_lv4": True},
    }

    logger = logging.getLogger("test")

    res = evaluate_article(
        article_id="id-1",
        title="【ドル円】片山財務相 断固たる措置を示唆",
        content="",
        state=state,
        keywords=keywords,
        settings=settings,
        logger=logger,
        now=now,
    )

    assert res.should_notify is True
    assert res.lv == 4
    assert res.person == "片山"
