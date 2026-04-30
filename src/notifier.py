from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

import requests


@dataclass(frozen=True)
class DiscordWebhooks:
    low: str
    mid: str
    high: str


def _color_for_lv(lv: int) -> int:
    if lv >= 4:
        return 0xE53935  # red
    if lv == 3:
        return 0xFB8C00  # orange
    return 0xFDD835  # yellow


def _pick_webhook(webhooks: DiscordWebhooks, lv: int) -> str:
    if lv >= 4:
        return webhooks.high
    if lv == 3:
        return webhooks.mid
    return webhooks.low


def _action_hint(lv: int) -> str:
    if lv >= 4:
        return "既存ロング即時撤退、新規ロング封印"
    if lv == 3:
        return "既存ロング縮小/利確、新規ロング封印（ショートのみ）"
    if lv == 2:
        return "監視強化（追加発言に注意）"
    return "通常運用"


def send_discord(
    *,
    webhooks: DiscordWebhooks,
    lv: int,
    person: str,
    title: str,
    source: str,
    url: str,
    published_at: datetime | None,
    logger: logging.Logger,
    timeout_seconds: float = 5.0,
) -> bool:
    webhook = _pick_webhook(webhooks, lv)
    if not webhook:
        logger.error("Discord Webhook未設定（lv=%s）。通知をスキップします。", lv)
        return False

    headline = f"【FX警戒Lv{lv}】{person}"
    when = published_at.strftime("%Y/%m/%d %H:%M") if published_at else "N/A"

    payload = {
        "username": "fx-alert-tool",
        "embeds": [
            {
                "title": f"**{headline}**",
                "description": f"> {title}",
                "color": _color_for_lv(lv),
                "fields": [
                    {"name": "**推奨アクション**", "value": _action_hint(lv), "inline": False},
                    {"name": "**出典**", "value": f"{source} ({when})", "inline": False},
                    {"name": "**URL**", "value": url, "inline": False},
                ],
            }
        ],
    }

    def _post() -> requests.Response:
        return requests.post(webhook, json=payload, timeout=timeout_seconds)

    try:
        r = _post()
        if 200 <= r.status_code < 300:
            return True
        raise RuntimeError(f"status={r.status_code} body={r.text[:200]}")
    except Exception as e:
        logger.warning("Discord送信失敗。5秒後に1回リトライします: %s", e)
        time.sleep(5)
        try:
            r2 = _post()
            if 200 <= r2.status_code < 300:
                return True
            logger.error("Discord送信失敗（リトライ後）: status=%s body=%s", r2.status_code, (r2.text or "")[:200])
            return False
        except Exception as e2:
            logger.error("Discord送信失敗（リトライ後）: %s", e2)
            return False
