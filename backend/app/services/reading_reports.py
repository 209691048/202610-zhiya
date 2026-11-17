"""Reading report lifecycle: fact summary, out-of-transaction generation and startup recovery.

Rules follow common.reportLifecycle in docs/design/api-contract-v0.4.json:
- the first finish stores a PENDING report holding the fact summary in the same transaction;
- generation runs after commit and only moves a report that is still PENDING;
- on startup, leftover PENDING reports become FAILED without calling the model;
- the service stays unready until startup recovery completes against the active database.
"""

import json
import logging
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

from app.api.v1.auth import connect
from app.core.config import database_path
from app.db.connection import database_ready

logger = logging.getLogger("zhiya.reports")
MAX_SUMMARY_CHARS = 500
SUMMARY_PROMPT = (
    "你是儿童绘本共读助手。请根据给出的阅读事实和已读页面正文，为家长写一段不超过120字的中文共读小结。"
    "只陈述已发生的阅读事实和可在家延续的温和建议，不评价孩子能力，不编造未出现的互动。"
)
_recovery_lock = threading.Lock()
_recovered_paths: set[Path] = set()


def fact_summary(visited_pages: list[int]) -> str:
    pages = list(dict.fromkeys(visited_pages))
    if not pages:
        return "本次共读尚未阅读页面。"
    return "本次共读阅读了第 " + "、".join(str(page) for page in pages) + " 页。"


def report_object(session_id: int, row) -> dict | None:
    if row is None:
        return None
    activities = json.loads(row["activities_json"] or "[]") if row["status"] == "READY" else []
    return {"readingSessionId": session_id, "summary": row["summary"],
            "activities": activities, "status": row["status"]}


def _settle(session_id: int, status: str, summary: str | None = None) -> bool:
    """Conditionally move a PENDING report; never overrides READY/FAILED written elsewhere."""
    now = int(time.time() * 1000)
    with closing(connect()) as db, db:
        if status == "READY":
            cursor = db.execute(
                """UPDATE reading_reports SET status = 'READY', summary = ?, activities_json = '[]',
                   updated_at = ? WHERE session_id = ? AND status = 'PENDING'""",
                (summary, now, session_id))
        else:
            cursor = db.execute(
                """UPDATE reading_reports SET status = 'FAILED', activities_json = '[]', updated_at = ?
                   WHERE session_id = ? AND status = 'PENDING'""",
                (now, session_id))
        return cursor.rowcount == 1


async def generate_report(session_id: int, facts: str, page_texts: list[str], adapter) -> None:
    """Runs after the finish transaction commits. One model attempt at most, no retries."""
    text = ""
    if adapter is not None:
        try:
            from app.schemas.agent import ModelGenerateRequest
            result = await adapter.generate(ModelGenerateRequest(
                system_prompt=SUMMARY_PROMPT,
                context_text="\n".join(page_texts)[:4000],
                user_input=facts,
            ))
            if result.success:
                text = (result.text or "").strip()
        except Exception:  # model or adapter failure is a definite generation failure
            logger.warning("report_generation_failed session_id=%s", session_id)
            text = ""
    try:
        if text and len(text) <= MAX_SUMMARY_CHARS:
            _settle(session_id, "READY", text)
        else:
            _settle(session_id, "FAILED")
    except sqlite3.Error:
        # Left PENDING; startup recovery will settle it to FAILED.
        logger.warning("report_settle_failed session_id=%s", session_id)


def reset_recovery_state() -> None:
    with _recovery_lock:
        _recovered_paths.clear()


def ensure_startup_recovered() -> bool:
    """Run startup PENDING->FAILED recovery once per startup on the active DB; never calls the model."""
    target = database_path().resolve()
    with _recovery_lock:
        if target in _recovered_paths:
            return True
        if not database_ready(target):
            return False
        try:
            with closing(connect(timeout=0.3)) as db, db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    """UPDATE reading_reports SET status = 'FAILED', activities_json = '[]', updated_at = ?
                       WHERE status = 'PENDING'""",
                    (int(time.time() * 1000),))
        except sqlite3.Error:
            logger.warning("report_recovery_failed database_unavailable")
            return False
        _recovered_paths.add(target)
        return True


def recover_pending_reports() -> bool:
    """Single-worker startup recovery called by lifespan before readiness."""
    reset_recovery_state()
    return ensure_startup_recovered()
