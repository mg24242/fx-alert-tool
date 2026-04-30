from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from collections import Counter

import yaml
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

from .feed_fetcher import FeedSource, fetch_articles
from .filter import evaluate_article
from .notifier import DiscordWebhooks, send_discord
from .state import JST, load_state, mark_notified, prune_state, save_state


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _setup_logger() -> logging.Logger:
    level_name = (os.getenv("LOG_LEVEL") or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    return logging.getLogger("fx-alert-tool")


def _load_yaml_or_die(path: Path, logger: logging.Logger) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("YAML root must be mapping")
        return data
    except Exception as e:
        logger.error("設定ファイル読込失敗: %s (%s)", path, e)
        raise SystemExit(1)


_ENV_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        m = _ENV_PATTERN.match(value.strip())
        if m:
            return os.getenv(m.group(1), "")
        return value
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def main() -> int:
    # ローカル実行時の混乱を避けるため、.envの値で上書きする。
    # GitHub Actionsでは env/secrets が渡されるため、通常 .env は不要。
    load_dotenv(override=True)
    logger = _setup_logger()

    root = _repo_root()
    config_dir = root / "config"

    feeds_cfg = _load_yaml_or_die(config_dir / "feeds.yml", logger)
    keywords_cfg = _load_yaml_or_die(config_dir / "keywords.yml", logger)
    settings_cfg = _expand_env(_load_yaml_or_die(config_dir / "settings.yml", logger))

    state_path = root / str(settings_cfg.get("state", {}).get("notified_file", "state/notified.json"))
    retention_days = int(settings_cfg.get("state", {}).get("retention_days", 7))

    state = load_state(state_path, logger)
    prune_state(state, retention_days)

    discord_cfg = settings_cfg.get("discord", {}) if isinstance(settings_cfg, dict) else {}
    webhooks = DiscordWebhooks(
        low=str(discord_cfg.get("webhook_low", "") or ""),
        mid=str(discord_cfg.get("webhook_mid", "") or ""),
        high=str(discord_cfg.get("webhook_high", "") or ""),
    )

    sources: list[FeedSource] = []
    for item in feeds_cfg.get("feeds", []):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        url = item.get("url")
        enabled = bool(item.get("enabled", True))
        if isinstance(name, str) and isinstance(url, str) and name and url:
            sources.append(FeedSource(name=name, url=url, enabled=enabled))

    now = datetime.now(tz=JST)
    logger.info("monitor start: feeds=%s now=%s", len(sources), now.isoformat())

    notified_count = 0
    scanned_count = 0
    reason_counts: Counter[str] = Counter()

    for src in sources:
        articles = fetch_articles(src, timeout_seconds=10.0, logger=logger)
        scanned_count += len(articles)

        for a in articles:
            res = evaluate_article(
                article_id=a.id,
                title=a.title,
                content=a.content,
                state=state,
                keywords=keywords_cfg,
                settings=settings_cfg,
                logger=logger,
                now=now,
            )
            reason_counts[res.reason] += 1
            if not res.should_notify:
                continue

            assert res.person is not None
            ok = send_discord(
                webhooks=webhooks,
                lv=res.lv,
                person=res.person,
                title=a.title,
                source=a.source,
                url=a.url,
                published_at=a.published_at,
                logger=logger,
                timeout_seconds=5.0,
            )
            if ok:
                mark_notified(
                    state,
                    article_id=a.id,
                    notified_at=now,
                    lv=res.lv,
                    person=res.person,
                )
                notified_count += 1

    save_state(state_path, state)
    top_reasons = ", ".join(f"{k}={v}" for k, v in reason_counts.most_common(8))
    logger.info("filter summary: %s", top_reasons or "no_articles")
    logger.info("monitor done: scanned=%s notified=%s state=%s", scanned_count, notified_count, state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
