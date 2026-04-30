from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import feedparser
import requests

from .state import JST


@dataclass(frozen=True)
class FeedSource:
    name: str
    url: str
    enabled: bool = True


@dataclass(frozen=True)
class Article:
    id: str
    title: str
    content: str
    url: str
    source: str
    published_at: datetime | None = None


def _entry_text(entry: Any) -> str:
    for key in ("summary", "description", "content"):
        val = getattr(entry, key, None)
        if isinstance(val, str) and val.strip():
            return val
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, dict) and isinstance(first.get("value"), str) and first["value"].strip():
                return first["value"]
    return ""


def _entry_id(entry: Any) -> str:
    for key in ("id", "guid", "link"):
        val = getattr(entry, key, None)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _entry_url(entry: Any) -> str:
    link = getattr(entry, "link", None)
    if isinstance(link, str):
        return link
    return ""


def fetch_articles(
    source: FeedSource,
    *,
    timeout_seconds: float = 10.0,
    logger: logging.Logger,
) -> list[Article]:
    if not source.enabled:
        return []

    try:
        resp = requests.get(source.url, timeout=timeout_seconds, headers={"User-Agent": "fx-alert-tool/1.0"})
        if resp.status_code != 200:
            logger.warning("RSS取得失敗（%s）: %s status=%s", source.name, source.url, resp.status_code)
            return []
    except Exception as e:
        logger.warning("RSS取得失敗（%s）: %s (%s)", source.name, source.url, e)
        return []

    parsed = feedparser.parse(resp.text)
    if getattr(parsed, "bozo", False):
        logger.warning("RSSパースエラー（%s）: %s", source.name, getattr(parsed, "bozo_exception", "unknown"))
        return []

    articles: list[Article] = []
    for entry in getattr(parsed, "entries", []) or []:
        article_id = _entry_id(entry)
        url = _entry_url(entry) or article_id
        if not article_id:
            continue
        title = getattr(entry, "title", "") or ""
        content = _entry_text(entry)

        published_at: datetime | None = None
        struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if struct:
            try:
                published_at = datetime(*struct[:6], tzinfo=JST)
            except Exception:
                published_at = None

        articles.append(
            Article(
                id=article_id,
                title=title,
                content=content,
                url=url,
                source=source.name,
                published_at=published_at,
            )
        )

    return articles
