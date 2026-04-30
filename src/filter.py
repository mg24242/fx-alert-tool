from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from .lv_judge import judge_lv
from .state import JST, get_last_notified_at, is_already_notified


@dataclass(frozen=True)
class FilterResult:
    should_notify: bool
    lv: int
    person: str | None
    reason: str


def _now_jst() -> datetime:
    return datetime.now(tz=JST)


def flatten_person_keywords(keywords: dict[str, Any]) -> list[str]:
    tp = keywords.get("target_persons", {}) if isinstance(keywords, dict) else {}
    result: list[str] = []
    for country in ("japan", "us"):
        c = tp.get(country, {})
        if not isinstance(c, dict):
            continue
        for key in ("high_priority", "medium_priority", "low_priority", "role_keywords"):
            items = c.get(key, [])
            if isinstance(items, list):
                for s in items:
                    if isinstance(s, str) and s:
                        result.append(s)
    seen: set[str] = set()
    deduped: list[str] = []
    for p in result:
        if p in seen:
            continue
        seen.add(p)
        deduped.append(p)
    return deduped


def passes_required_keywords(text: str, keywords: dict[str, Any]) -> bool:
    required = keywords.get("required_keywords", []) if isinstance(keywords, dict) else []
    if not isinstance(required, list) or not required:
        return True
    return any(isinstance(kw, str) and kw and (kw in text) for kw in required)


def is_excluded(text: str, keywords: dict[str, Any]) -> bool:
    patterns = keywords.get("exclude_patterns", []) if isinstance(keywords, dict) else []
    if not isinstance(patterns, list) or not patterns:
        return False
    for pat in patterns:
        if not isinstance(pat, str) or not pat:
            continue
        try:
            if re.search(pat, text):
                return True
        except re.error:
            continue
    return False


def find_person(title: str, content: str, keywords: dict[str, Any]) -> str | None:
    persons = flatten_person_keywords(keywords)
    hay_title = title or ""
    hay_body = content or ""
    for p in persons:
        if p in hay_title:
            return p
    for p in persons:
        if p in hay_body:
            return p
    return None


def _parse_range(range_str: str) -> tuple[time, time] | None:
    m = re.fullmatch(r"(\d{2}):(\d{2})-(\d{2}):(\d{2})", range_str or "")
    if not m:
        return None
    sh, sm, eh, em = map(int, m.groups())
    return time(sh, sm), time(eh, em)


def _time_in_range(t: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= t < end
    return t >= start or t < end


def min_lv_for_now(settings: dict[str, Any], *, now: datetime | None = None) -> int:
    now = now or _now_jst()
    t = now.timetz().replace(tzinfo=None)
    for rule in settings.get("time_filter", []) if isinstance(settings, dict) else []:
        if not isinstance(rule, dict):
            continue
        parsed = _parse_range(rule.get("range", ""))
        if not parsed:
            continue
        start, end = parsed
        if _time_in_range(t, start, end):
            lv = rule.get("min_lv_to_notify", 2)
            try:
                return int(lv)
            except Exception:
                return 2
    return 2


def in_cooldown(
    state: dict[str, Any],
    person: str,
    cooldown_minutes: int,
    *,
    now: datetime | None = None,
) -> bool:
    if cooldown_minutes <= 0:
        return False
    now = now or _now_jst()
    last = get_last_notified_at(state, person)
    if not last:
        return False
    return now - last < timedelta(minutes=cooldown_minutes)


def evaluate_article(
    *,
    article_id: str,
    title: str,
    content: str,
    state: dict[str, Any],
    keywords: dict[str, Any],
    settings: dict[str, Any],
    logger: logging.Logger,
    now: datetime | None = None,
) -> FilterResult:
    now = now or _now_jst()
    text_all = f"{title}\n{content}"

    # レイヤ0：重複排除
    if is_already_notified(state, article_id):
        return FilterResult(False, 0, None, "duplicate")

    # 除外（過去発言の引用など）
    if is_excluded(text_all, keywords):
        return FilterResult(False, 0, None, "excluded")

    # レイヤ1：必須キーワード
    if not passes_required_keywords(text_all, keywords):
        return FilterResult(False, 0, None, "required_keywords_miss")

    # レイヤ2：人物マッチ
    person = find_person(title, content, keywords)
    if not person:
        return FilterResult(False, 0, None, "person_miss")

    # レイヤ3：強度判定
    lv = judge_lv(title, content, keywords)

    # レイヤ4：時間帯フィルタ
    min_lv = min_lv_for_now(settings, now=now)
    if lv < min_lv:
        return FilterResult(False, lv, person, f"time_filter(min_lv={min_lv})")

    # レイヤ5：クールダウン
    cooldown = settings.get("cooldown", {}) if isinstance(settings, dict) else {}
    default_minutes = int(cooldown.get("default_minutes", 60))
    bypass_for_lv4 = bool(cooldown.get("bypass_for_lv4", True))
    if not (bypass_for_lv4 and lv >= 4):
        if in_cooldown(state, person, default_minutes, now=now):
            return FilterResult(False, lv, person, "cooldown")

    logger.info("フィルタ通過: lv=%s person=%s title=%s", lv, person, (title or "")[:80])
    return FilterResult(True, lv, person, "ok")
