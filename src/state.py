from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo

    JST = ZoneInfo("Asia/Tokyo")
except Exception:
    # Windows等でtzdataが無い場合のフォールバック（固定UTC+9）
    JST = timezone(timedelta(hours=9), name="JST")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _now_jst() -> datetime:
    return datetime.now(tz=JST)


@dataclass
class NotifiedArticle:
    id: str
    notified_at: str
    lv: int
    person: str


def empty_state() -> dict[str, Any]:
    return {
        "notified_articles": [],
        "last_notification_per_person": {},
    }


def load_state(path: Path, logger: logging.Logger) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("state root must be object")
        data.setdefault("notified_articles", [])
        data.setdefault("last_notification_per_person", {})
        if not isinstance(data["notified_articles"], list):
            data["notified_articles"] = []
        if not isinstance(data["last_notification_per_person"], dict):
            data["last_notification_per_person"] = {}
        return data
    except FileNotFoundError:
        return empty_state()
    except Exception as e:
        logger.warning("ステートファイル読込失敗: %s（空の状態で開始）", e)
        return empty_state()


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def prune_state(state: dict[str, Any], retention_days: int, *, now: datetime | None = None) -> None:
    if retention_days <= 0:
        return

    now = now or _now_jst()
    threshold = now - timedelta(days=retention_days)

    kept: list[dict[str, Any]] = []
    for item in state.get("notified_articles", []):
        if not isinstance(item, dict):
            continue
        dt = _parse_dt(item.get("notified_at"))
        if dt is None:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=JST)
        if dt >= threshold:
            kept.append(item)
    state["notified_articles"] = kept


def is_already_notified(state: dict[str, Any], article_id: str) -> bool:
    for item in state.get("notified_articles", []):
        if isinstance(item, dict) and item.get("id") == article_id:
            return True
    return False


def get_last_notified_at(state: dict[str, Any], person: str) -> datetime | None:
    raw = state.get("last_notification_per_person", {}).get(person)
    dt = _parse_dt(raw)
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    return dt


def mark_notified(
    state: dict[str, Any],
    *,
    article_id: str,
    notified_at: datetime,
    lv: int,
    person: str,
) -> None:
    if notified_at.tzinfo is None:
        notified_at = notified_at.replace(tzinfo=JST)
    iso = notified_at.isoformat()
    state.setdefault("notified_articles", []).append(
        {
            "id": article_id,
            "notified_at": iso,
            "lv": int(lv),
            "person": person,
        }
    )
    state.setdefault("last_notification_per_person", {})[person] = iso
