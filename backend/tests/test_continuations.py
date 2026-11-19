"""Tests for API-026 story version approvals and API-011 atomic continuation switching (TC-FR17-04/05)."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from app.api.v1.auth import _login_attempts
from app.main import app

SCHEMA = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


@pytest.fixture
def cont_env(tmp_path, monkeypatch):
    db_path = tmp_path / "continuations.sqlite3"
    monkeypatch.setenv("ZHIYA_DB_PATH", str(db_path))
    with closing(sqlite3.connect(db_path)) as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
    _login_attempts.clear()
    with TestClient(app, base_url="https://testserver") as first, TestClient(app, base_url="https://testserver") as second:
        for client, account in ((first, "guardian-one"), (second, "guardian-two")):
            creds = {"account": account, "password": "strong-pass-123"}
            assert client.post("/api/v1/auth/registrations", json=creds).status_code == 201
            assert client.post("/api/v1/auth/sessions", json=creds).status_code == 201
        with closing(sqlite3.connect(db_path)) as db, db:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("INSERT INTO storybooks VALUES (201, 1, 'ORIGINAL', 1)")
            db.execute("""INSERT INTO story_versions
                (id, storybook_id, version_no, title, topics_json, age_min, age_max,
                 license_note, status, reviewed_by_id, reviewed_at, created_at, branching)
                VALUES (301, 201, 1, '小狐狸原创', '["互助"]', 3, 5, '原创授权', 'APPROVED_PRIVATE', 1, 100, 1, 0)""")
            for pno, nxt in ((1, 2), (2, 3), (3, 4), (4, None)):
                db.execute("INSERT INTO story_pages (version_id, page_no, body_text, image_ref, default_next_page_number) VALUES (301, ?, ?, 'none', ?)",
                           (pno, f"v1第{pno}页", nxt))
        h1 = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}
        pid = first.post("/api/v1/child-profiles", headers=h1,
                         json={"ageBand": "AGE_4_5", "preferredMinutes": 15}).json()["data"]["childProfileId"]
        yield first, second, db_path, pid
    _login_attempts.clear()


def _seed_continuation_draft(db_path: Path, version_id: int, version_no: int, src_session_id: int,
                             src_revision: int, src_page: int, prefix: list[int], *,
                             status: str = "PENDING_REVIEW", branching: int = 0, src_version_id: int = 301):
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("""INSERT INTO story_versions
            (id, storybook_id, version_no, title, topics_json, age_min, age_max,
             license_note, status, created_at, source_version_id, source_session_id,
             source_revision, source_page_no, resume_page_no, source_visited_pages_json, branching)
            VALUES (?, 201, ?, '小狐狸续写', '["互助"]', 3, 5, '原创授权', ?, 1, ?, ?, ?, ?, ?, ?, ?)""",
            (version_id, version_no, status, src_version_id, src_session_id, src_revision, src_page,
             len(prefix) + 1, json.dumps(prefix), branching))
        if branching == 0:
            for pno, nxt in ((1, 2), (2, 3), (3, 4), (4, 5), (5, None)):
                db.execute("INSERT INTO story_pages (version_id, page_no, body_text, image_ref, default_next_page_number) VALUES (?, ?, ?, 'none', ?)",
                           (version_id, pno, f"v{version_no}第{pno}页", nxt))
        else:
            for pno, nxt in ((1, 2), (2, 3), (3, None), (4, 5), (5, None)):
                db.execute("INSERT INTO story_pages (version_id, page_no, body_text, image_ref, default_next_page_number) VALUES (?, ?, ?, 'none', ?)",
                           (version_id, pno, f"v{version_no}第{pno}页", nxt))
            db.execute("INSERT INTO story_pages (version_id, page_no, body_text, image_ref, default_next_page_number) VALUES (?, 6, ?, 'none', NULL)",
                       (version_id, f"v{version_no}第6页"))
            db.execute("INSERT INTO story_branches VALUES (901, ?, 3, 4, '去森林', 'PENDING')", (version_id,))
            db.execute("INSERT INTO story_branches VALUES (902, ?, 3, 6, '回家去', 'PENDING')", (version_id,))
        for carried_page, source_page in enumerate(prefix, start=1):
            db.execute(
                """UPDATE story_pages SET body_text = (
                       SELECT body_text FROM story_pages WHERE version_id = ? AND page_no = ?
                   ) WHERE version_id = ? AND page_no = ?""",
                (src_version_id, source_page, version_id, carried_page),
            )


def test_approve_story_version_retires_prior_verifies_dag_and_rejects_invalid(cont_env):
    first, second, db_path, pid = cont_env
    h1 = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}
    h2 = {"X-CSRF-Token": second.cookies["zhiya_csrf"]}

    sid = first.post("/api/v1/reading-sessions", headers=h1, json={
        "childProfileId": pid, "storyVersionId": 301, "mode": "PARENT_CHILD",
    }).json()["data"]["readingSessionId"]
    assert first.post(f"/api/v1/reading-sessions/{sid}/events", headers=h1, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "s1",
    }).status_code == 201
    assert first.post(f"/api/v1/reading-sessions/{sid}/events", headers=h1, json={
        "eventType": "PAGE_CHANGED", "pageNumber": 2, "expectedRevision": 1, "clientEventId": "s2",
    }).status_code == 201

    _seed_continuation_draft(db_path, 302, 2, sid, 2, 2, [1, 2], branching=1)
    # Also add an invalid 3-page draft (303) and a cyclic draft (304) and a WITHDRAWN version (305).
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("""INSERT INTO story_versions
            (id, storybook_id, version_no, title, topics_json, age_min, age_max,
             license_note, status, created_at, branching)
            VALUES (303, 201, 3, '过短草稿', '["互助"]', 3, 5, 'ok', 'PENDING_REVIEW', 1, 0)""")
        for pno, nxt in ((1, 2), (2, 3), (3, None)):
            db.execute("INSERT INTO story_pages (version_id, page_no, body_text, image_ref, default_next_page_number) VALUES (303, ?, 'short', 'none', ?)",
                       (pno, nxt))
        db.execute("""INSERT INTO story_versions
            (id, storybook_id, version_no, title, topics_json, age_min, age_max,
             license_note, status, created_at, branching)
            VALUES (304, 201, 4, '环路草稿', '["互助"]', 3, 5, 'ok', 'PENDING_REVIEW', 1, 0)""")
        for pno, nxt in ((1, 2), (2, 3), (3, 4), (4, 2)):
            db.execute("INSERT INTO story_pages (version_id, page_no, body_text, image_ref, default_next_page_number) VALUES (304, ?, 'loop', 'none', ?)",
                       (pno, nxt))
        db.execute("""INSERT INTO story_versions
            (id, storybook_id, version_no, title, topics_json, age_min, age_max,
             license_note, status, created_at, branching)
            VALUES (305, 201, 5, '撤回版', '["互助"]', 3, 5, 'ok', 'WITHDRAWN', 1, 0)""")

    with TestClient(app, base_url="https://testserver") as anon:
        assert anon.post("/api/v1/story-versions/302/approvals", json={"versionNumber": 2, "reviewedAllBranches": True}).status_code == 401
    assert first.post("/api/v1/story-versions/302/approvals", json={"versionNumber": 2, "reviewedAllBranches": True}).status_code == 403
    assert second.post("/api/v1/story-versions/302/approvals", headers=h2, json={"versionNumber": 2, "reviewedAllBranches": True}).status_code == 404
    assert first.post("/api/v1/story-versions/305/approvals", headers=h1, json={"versionNumber": 5, "reviewedAllBranches": True}).status_code == 404
    assert first.post("/api/v1/story-versions/302/approvals", headers=h1, json={"versionNumber": 2, "reviewedAllBranches": False}).status_code == 422
    assert first.post("/api/v1/story-versions/302/approvals", headers=h1, json={"versionNumber": 1, "reviewedAllBranches": True}).status_code == 409
    assert first.post("/api/v1/story-versions/303/approvals", headers=h1, json={"versionNumber": 3, "reviewedAllBranches": True}).status_code == 422
    assert first.post("/api/v1/story-versions/304/approvals", headers=h1, json={"versionNumber": 4, "reviewedAllBranches": True}).status_code == 422

    approved = first.post("/api/v1/story-versions/302/approvals", headers=h1,
                          json={"versionNumber": 2, "reviewedAllBranches": True})
    assert approved.status_code == 200 and approved.json()["requestId"] == approved.headers["X-Request-ID"]
    adata = approved.json()["data"]
    assert adata["status"] == "APPROVED_PRIVATE"
    assert adata["continuation"] == {
        "sourceReadingSessionId": sid,
        "sourceStoryVersionId": 301,
        "sourceRevision": 2,
        "sourcePageNumber": 2,
        "sourceVisitedPageNumbers": [1, 2],
        "resumePageNumber": 3,
    }
    assert all(b["reviewStatus"] == "APPROVED" for b in adata["branches"])

    # Old version 301 was atomically retired keeping reviewed_at=100, and source session stays IN_PROGRESS.
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT status, reviewed_by_id, reviewed_at FROM story_versions WHERE id = 301").fetchone() == ("RETIRED", 1, 100)
        assert db.execute("SELECT status, revision FROM reading_sessions WHERE id = ?", (sid,)).fetchone() == ("IN_PROGRESS", 2)
    assert [v["storyVersionId"] for v in first.get("/api/v1/storybooks", params={"scope": "mine"}).json()["data"]["items"]] == [302, 301]


def test_continuation_metadata_is_omitted_from_granted_child_books(cont_env):
    guardian, _, db_path, profile_id = cont_env
    headers = {"X-CSRF-Token": guardian.cookies["zhiya_csrf"]}
    sessions_url = "/api/v1/reading-sessions"
    session_body = {"childProfileId": profile_id, "mode": "PARENT_CHILD"}
    source = guardian.post(sessions_url, headers=headers, json={**session_body, "storyVersionId": 301})
    assert source.status_code == 201
    source_id = source.json()["data"]["readingSessionId"]
    started = guardian.post(f"{sessions_url}/{source_id}/events", headers=headers, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "start-source",
    })
    assert started.status_code == 201
    _seed_continuation_draft(db_path, 302, 2, source_id, 1, 1, [1], branching=1)

    detail_url = "/api/v1/story-versions/302"
    shelf_url = "/api/v1/storybooks"
    approved = guardian.post(f"{detail_url}/approvals", headers=headers, json={
        "versionNumber": 2, "reviewedAllBranches": True,
    })
    shelf = guardian.get(shelf_url, params={"scope": "mine"})
    detail = guardian.get(detail_url)
    assert approved.status_code == shelf.status_code == detail.status_code == 200
    parent_detail = detail.json()["data"]
    for book in (approved.json()["data"], shelf.json()["data"]["items"][0], parent_detail):
        assert book["storyVersionId"] == 302
        assert book["sourceStoryVersionId"] == 301
        assert book["continuation"] == {
            "sourceReadingSessionId": source_id,
            "sourceStoryVersionId": 301,
            "sourceRevision": 1,
            "sourcePageNumber": 1,
            "sourceVisitedPageNumbers": [1],
            "resumePageNumber": 2,
        }

    session = guardian.post(sessions_url, headers=headers, json={**session_body, "storyVersionId": 302})
    assert session.status_code == 201
    session_id = session.json()["data"]["readingSessionId"]
    grant = guardian.put(f"{sessions_url}/{session_id}/mode-settings", headers=headers, json={
        "mode": "CHILD_SOLO", "allowedStoryVersionIds": [302], "timeLimitSeconds": 600,
    })
    assert grant.status_code == 200
    assert grant.json()["data"]["allowedStoryVersionIds"] == [302]

    child_shelf = guardian.get(shelf_url)
    child_detail = guardian.get(detail_url)
    assert child_shelf.status_code == child_detail.status_code == 200
    [shelf_book] = child_shelf.json()["data"]["items"]
    for book in (shelf_book, child_detail.json()["data"]):
        assert book["storyVersionId"] == 302
        assert "continuation" not in book
        assert "sourceStoryVersionId" not in book
        assert book["pages"] == parent_detail["pages"]
        assert [page["text"] for page in book["pages"][:2]] == ["v1第1页", "v2第2页"]
        assert book["branches"] == parent_detail["branches"]
        assert [branch["reviewStatus"] for branch in book["branches"]] == ["APPROVED", "APPROVED"]


@pytest.mark.parametrize("continuation", [
    pytest.param({"sourceReadingSessionId": None}, id="one-null"),
    pytest.param({"sourceReadingSessionId": None, "expectedRevision": None, "clientRequestId": None}, id="all-null"),
    pytest.param({"sourceReadingSessionId": 1, "expectedRevision": None, "clientRequestId": "switch"}, id="mixed"),
])
def test_create_reading_session_rejects_explicit_null_continuation_fields(cont_env, continuation):
    guardian, _, db_path, profile_id = cont_env
    headers = {"X-CSRF-Token": guardian.cookies["zhiya_csrf"]}
    with closing(sqlite3.connect(db_path)) as db:
        before = db.execute("SELECT COUNT(*) FROM reading_sessions").fetchone()
        response = guardian.post("/api/v1/reading-sessions", headers=headers, json={
            "childProfileId": profile_id, "storyVersionId": 301, "mode": "PARENT_CHILD", **continuation,
        })
        assert response.status_code == 422
        assert db.execute("SELECT COUNT(*) FROM reading_sessions").fetchone() == before


def test_continuation_switch_tc_fr17_04_and_idempotency(cont_env):
    first, second, db_path, pid = cont_env
    h1 = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}
    h2 = {"X-CSRF-Token": second.cookies["zhiya_csrf"]}

    sid1 = first.post("/api/v1/reading-sessions", headers=h1, json={
        "childProfileId": pid, "storyVersionId": 301, "mode": "PARENT_CHILD",
    }).json()["data"]["readingSessionId"]
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "e1",
    }).status_code == 201
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "PAGE_CHANGED", "pageNumber": 2, "expectedRevision": 1, "clientEventId": "e2",
    }).status_code == 201

    _seed_continuation_draft(db_path, 302, 2, sid1, 2, 2, [1, 2], branching=1)
    assert first.post("/api/v1/story-versions/302/approvals", headers=h1,
                      json={"versionNumber": 2, "reviewedAllBranches": True}).status_code == 200

    switch_body = {
        "childProfileId": pid,
        "storyVersionId": 302,
        "mode": "PARENT_CHILD",
        "sourceReadingSessionId": sid1,
        "expectedRevision": 2,
        "clientRequestId": "switch-001",
    }
    assert second.post("/api/v1/reading-sessions", headers=h2, json=switch_body).status_code == 404

    simultaneous = Barrier(2, timeout=5)

    def switch():
        simultaneous.wait()
        return first.post("/api/v1/reading-sessions", headers=h1, json=switch_body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(switch) for _ in range(2)]
        replayed, switched = sorted(
            (pending.result() for pending in requests), key=lambda response: response.status_code,
        )
    assert switched.status_code == 201 and switched.json()["requestId"] == switched.headers["X-Request-ID"]
    sdata = switched.json()["data"]
    sid2 = sdata["readingSessionId"]
    assert sid2 != sid1
    assert sdata == {
        "readingSessionId": sid2,
        "storyVersionId": 302,
        "sourceReadingSessionId": sid1,
        "startPageNumber": 3,
        "carriedPrefixPageCount": 2,
        "currentPage": 3,
        "visitedPageNumbers": [1, 2, 3],
        "mode": "PARENT_CHILD",
        "status": "IN_PROGRESS",
        "revision": 1,
        "expiresAt": None,
    }

    # Old session is FINISHED(CONTINUED) with fact report, and new session can choose branch at page 3.
    old_view = first.get(f"/api/v1/reading-sessions/{sid1}").json()["data"]
    assert old_view["session"]["status"] == "FINISHED"
    assert old_view["report"]["status"] == "READY" and "第 1、2 页" in old_view["report"]["summary"]
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT end_reason FROM reading_sessions WHERE id = ?", (sid1,)).fetchone()[0] == "CONTINUED"

    # Concurrent same-key replay returns 200 for the original successor.
    assert replayed.status_code == 200 and replayed.json()["data"] == sdata
    assert replayed.json()["requestId"] == replayed.headers["X-Request-ID"] != switched.json()["requestId"]
    with closing(sqlite3.connect(db_path)) as db:
        successors = db.execute(
            "SELECT id FROM reading_sessions WHERE source_reading_session_id = ?", (sid1,),
        ).fetchall()
        reports = db.execute("SELECT session_id FROM reading_reports WHERE session_id = ?", (sid1,)).fetchall()
        starts = db.execute(
            "SELECT id FROM interaction_events WHERE session_id = ? AND event_type = 'STARTED'", (sid2,),
        ).fetchall()
        assert successors == [(sid2,)]
        assert reports == [(sid1,)]
        assert len(starts) == 1
        assert db.execute("SELECT COUNT(*) FROM request_executions WHERE scope_type = 'SESSION_CREATE'").fetchone() == (1,)

    # A changed body conflicts with the original key. A new key reports the completed switch.
    assert first.post("/api/v1/reading-sessions", headers=h1,
                      json={**switch_body, "expectedRevision": 3}).json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    repeat_switch_body = {**switch_body, "clientRequestId": "switch-002"}
    already_switched = first.post("/api/v1/reading-sessions", headers=h1, json=repeat_switch_body)
    assert already_switched.status_code == 409
    assert already_switched.json()["error"]["code"] == "CONTINUATION_ALREADY_SWITCHED"
    replayed_failure = first.post("/api/v1/reading-sessions", headers=h1, json=repeat_switch_body)
    assert replayed_failure.status_code == 409
    assert replayed_failure.json()["error"] == already_switched.json()["error"]

    chosen = first.post(f"/api/v1/reading-sessions/{sid2}/branches", headers=h1, json={
        "branchId": 901, "expectedRevision": 1, "clientEventId": "b-cont",
    })
    assert chosen.status_code == 201 and chosen.json()["data"]["currentPage"] == 4
    assert chosen.json()["data"]["visitedPageNumbers"] == [1, 2, 3, 4]

    other_failure = first.post("/api/v1/reading-sessions", headers=h1, json={
        **switch_body, "sourceReadingSessionId": sid2, "clientRequestId": "switch-003",
    })
    assert other_failure.status_code == 409
    assert other_failure.json()["error"]["code"] == "SESSION_CONFLICT"

    # Deleting source session clears its ID and preserves successor recovery metadata.
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute(
            "SELECT status FROM request_executions WHERE scope_type = 'SESSION_CREATE' AND client_request_id = ?",
            ("switch-002",),
        ).fetchone() == ("FAILED",)
    assert first.delete(f"/api/v1/reading-sessions/{sid1}", headers=h1).status_code == 204
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute(
            "SELECT status FROM request_executions WHERE scope_type = 'SESSION_CREATE' AND client_request_id = ?",
            ("switch-002",),
        ).fetchone() is None
        assert db.execute(
            "SELECT status FROM request_executions WHERE scope_type = 'SESSION_CREATE' AND client_request_id = ?",
            ("switch-003",),
        ).fetchone() == ("FAILED",)
    restored = first.get(f"/api/v1/reading-sessions/{sid2}").json()["data"]["session"]
    assert "sourceReadingSessionId" not in restored
    assert restored["storyVersionId"] == 302
    assert restored["currentPage"] == 4
    assert restored["startPageNumber"] == 3
    assert restored["carriedPrefixPageCount"] == 2


def test_continuation_switch_stale_snapshot_and_atomic_rollback_tc_fr17_05(cont_env):
    first, _, db_path, pid = cont_env
    h1 = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}

    sid1 = first.post("/api/v1/reading-sessions", headers=h1, json={
        "childProfileId": pid, "storyVersionId": 301, "mode": "PARENT_CHILD",
    }).json()["data"]["readingSessionId"]
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "e1",
    }).status_code == 201
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "PAGE_CHANGED", "pageNumber": 2, "expectedRevision": 1, "clientEventId": "e2",
    }).status_code == 201

    _seed_continuation_draft(db_path, 302, 2, sid1, 2, 2, [1, 2], branching=0)
    assert first.post("/api/v1/story-versions/302/approvals", headers=h1,
                      json={"versionNumber": 2, "reviewedAllBranches": True}).status_code == 200

    # Simulate DB write failure mid-switch: entire transaction rolls back so source session stays intact.
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("""CREATE TRIGGER fail_switch_insert BEFORE INSERT ON reading_sessions
            WHEN NEW.source_reading_session_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'simulated db write failure'); END;""")
    switch_body = {
        "childProfileId": pid,
        "storyVersionId": 302,
        "mode": "PARENT_CHILD",
        "sourceReadingSessionId": sid1,
        "expectedRevision": 2,
        "clientRequestId": "switch-fail",
    }
    failed = first.post("/api/v1/reading-sessions", headers=h1, json=switch_body)
    assert failed.status_code == 503 and failed.json()["error"]["retryable"] is False
    with closing(sqlite3.connect(db_path)) as db, db:
        assert db.execute("SELECT status, end_reason, revision FROM reading_sessions WHERE id = ?", (sid1,)).fetchone() == (
            "IN_PROGRESS", None, 2,
        )
        assert db.execute("SELECT COUNT(*) FROM reading_sessions").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM request_executions WHERE scope_type = 'SESSION_CREATE'").fetchone()[0] == 0
        db.execute("DROP TRIGGER fail_switch_insert")

    # Advance source session to page 3 (revision=3): stale snapshot at revision=2 now returns 409 without closing source.
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "PAGE_CHANGED", "pageNumber": 3, "expectedRevision": 2, "clientEventId": "e3",
    }).status_code == 201
    stale = first.post("/api/v1/reading-sessions", headers=h1, json=switch_body)
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "CONTINUATION_STALE"
    assert first.get(f"/api/v1/reading-sessions/{sid1}").json()["data"]["session"]["status"] == "IN_PROGRESS"
    # Source session can still continue to page 4 normally.
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "PAGE_CHANGED", "pageNumber": 4, "expectedRevision": 3, "clientEventId": "e4",
    }).status_code == 201


def test_continuation_switch_from_branched_source_renumbers_carried_prefix(cont_env):
    first, _, db_path, pid = cont_env
    h1 = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("UPDATE story_versions SET branching = 1 WHERE id = 301")
        db.execute("INSERT INTO story_branches VALUES (801, 301, 1, 3, '走近路', 'APPROVED')")
    sid1 = first.post("/api/v1/reading-sessions", headers=h1, json={
        "childProfileId": pid, "storyVersionId": 301, "mode": "PARENT_CHILD",
    }).json()["data"]["readingSessionId"]
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "b1",
    }).status_code == 201
    assert first.post(f"/api/v1/reading-sessions/{sid1}/branches", headers=h1, json={
        "branchId": 801, "expectedRevision": 1, "clientEventId": "b2",
    }).status_code == 201
    # Source visited [1, 3]; continuation maps carried prefix to 1..2 and resumes at page 3.
    _seed_continuation_draft(db_path, 306, 2, sid1, 2, 3, [1, 3], branching=0)
    approval_path = "/api/v1/story-versions/306/approvals"
    approval_body = {"versionNumber": 2, "reviewedAllBranches": True}
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("UPDATE story_pages SET body_text = 'v1第2页' WHERE version_id = 306 AND page_no = 2")

    rejected = first.post(approval_path, headers=h1, json=approval_body)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
    with closing(sqlite3.connect(db_path)) as db, db:
        assert db.execute("SELECT status FROM story_versions WHERE id = 301").fetchone() == ("APPROVED_PRIVATE",)
        assert db.execute("SELECT status FROM story_versions WHERE id = 306").fetchone() == ("PENDING_REVIEW",)
        db.execute("UPDATE story_pages SET body_text = 'v1第3页' WHERE version_id = 306 AND page_no = 2")

    approved = first.post(approval_path, headers=h1, json=approval_body)
    assert approved.status_code == 200
    assert [p["text"] for p in approved.json()["data"]["pages"][:2]] == ["v1第1页", "v1第3页"]
    switched = first.post("/api/v1/reading-sessions", headers=h1, json={
        "childProfileId": pid, "storyVersionId": 306, "mode": "PARENT_CHILD",
        "sourceReadingSessionId": sid1, "expectedRevision": 2, "clientRequestId": "switch-branched",
    })
    assert switched.status_code == 201
    data = switched.json()["data"]
    assert data["visitedPageNumbers"] == [1, 2, 3]
    assert data["carriedPrefixPageCount"] == 2 and data["startPageNumber"] == 3
    old_report = first.get(f"/api/v1/reading-sessions/{sid1}").json()["data"]["report"]
    assert "第 1、3 页" in old_report["summary"]


@pytest.mark.parametrize("ending", ["finish", "switch"])
def test_continuation_first_page_event_reuses_creation_key_and_report_counts_new_pages(cont_env, monkeypatch, ending):
    first, _, db_path, pid = cont_env
    monkeypatch.setattr(app.state, "model_adapter", None, raising=False)
    headers = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}
    sessions = "/api/v1/reading-sessions"
    created = first.post(sessions, headers=headers, json={
        "childProfileId": pid, "storyVersionId": 301, "mode": "PARENT_CHILD",
    })
    assert created.status_code == 201
    source_id = created.json()["data"]["readingSessionId"]
    source = f"{sessions}/{source_id}"
    assert first.post(f"{source}/events", headers=headers, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "start-source",
    }).status_code == 201
    _seed_continuation_draft(db_path, 302, 2, source_id, 1, 1, [1])
    assert first.post("/api/v1/story-versions/302/approvals", headers=headers, json={
        "versionNumber": 2, "reviewedAllBranches": True,
    }).status_code == 200

    request_key = "continuation-request"
    switched = first.post(sessions, headers=headers, json={
        "childProfileId": pid, "storyVersionId": 302, "mode": "PARENT_CHILD",
        "sourceReadingSessionId": source_id, "expectedRevision": 1, "clientRequestId": request_key,
    })
    assert switched.status_code == 201
    successor_id = switched.json()["data"]["readingSessionId"]
    successor = f"{sessions}/{successor_id}"
    page_event = {
        "eventType": "PAGE_CHANGED", "pageNumber": 3, "expectedRevision": 1, "clientEventId": request_key,
    }
    advanced = first.post(f"{successor}/events", headers=headers, json=page_event)
    assert advanced.status_code == 201
    assert first.get(successor).json()["data"]["session"]["visitedPageNumbers"] == [1, 2, 3]
    replayed = first.post(f"{successor}/events", headers=headers, json=page_event)
    assert replayed.status_code == 200 and replayed.json()["data"] == advanced.json()["data"]

    assert first.delete(source, headers=headers).status_code == 204
    if ending == "finish":
        finished = first.post(f"{successor}/completions", headers=headers, json={
            "reason": "USER_FINISH", "expectedRevision": 2, "clientEventId": "finish-successor",
        })
        assert finished.status_code == 200
    else:
        _seed_continuation_draft(db_path, 303, 3, successor_id, 2, 3, [1, 2, 3], src_version_id=302)
        assert first.post("/api/v1/story-versions/303/approvals", headers=headers, json={
            "versionNumber": 3, "reviewedAllBranches": True,
        }).status_code == 200
        next_switch = first.post(sessions, headers=headers, json={
            "childProfileId": pid, "storyVersionId": 303, "mode": "PARENT_CHILD",
            "sourceReadingSessionId": successor_id, "expectedRevision": 2, "clientRequestId": "next-continuation",
        })
        assert next_switch.status_code == 201
    report = first.get(successor).json()["data"]["report"]
    assert report["summary"] == "本次共读阅读了第 2、3 页。"


def test_approval_enforces_backend_safety_freezes_media_and_handles_dependency_recovery(cont_env, tmp_path, monkeypatch):
    from io import BytesIO
    from PIL import Image

    first, second, db_path, pid = cont_env
    h1 = {"X-CSRF-Token": first.cookies["zhiya_csrf"]}
    media_root = tmp_path / "media"
    media_root.mkdir()
    monkeypatch.setenv("ZHIYA_MEDIA_ROOT", str(media_root))

    def make_png(color: tuple[int, int, int]) -> bytes:
        buf = BytesIO()
        Image.new("RGB", (4, 4), color).save(buf, format="PNG")
        return buf.getvalue()

    green_png = make_png((0, 200, 0))
    red_png = make_png((200, 0, 0))
    (media_root / "resume.png").write_bytes(green_png)

    sid1 = first.post("/api/v1/reading-sessions", headers=h1, json={
        "childProfileId": pid, "storyVersionId": 301, "mode": "PARENT_CHILD",
    }).json()["data"]["readingSessionId"]
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "STARTED", "pageNumber": 1, "expectedRevision": 0, "clientEventId": "m1",
    }).status_code == 201
    assert first.post(f"/api/v1/reading-sessions/{sid1}/events", headers=h1, json={
        "eventType": "PAGE_CHANGED", "pageNumber": 2, "expectedRevision": 1, "clientEventId": "m2",
    }).status_code == 201

    _seed_continuation_draft(db_path, 307, 2, sid1, 2, 2, [1, 2], branching=1)
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("UPDATE story_pages SET image_ref = 'resume.png' WHERE version_id = 307 AND page_no = 3")
        db.execute("UPDATE story_pages SET body_text = '请模仿危险操作玩火' WHERE version_id = 307 AND page_no = 3")

    # Even with reviewedAllBranches=True, backend safety check blocks unsafe text with 422.
    unsafe = first.post("/api/v1/story-versions/307/approvals", headers=h1,
                        json={"versionNumber": 2, "reviewedAllBranches": True})
    assert unsafe.status_code == 422 and unsafe.json()["error"]["code"] == "VALIDATION_ERROR"

    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("UPDATE story_pages SET body_text = '安全续写第3页' WHERE version_id = 307 AND page_no = 3")
        db.execute("UPDATE story_branches SET choice_label = '询问家庭地址' WHERE id = 901")
    unsafe_branch = first.post("/api/v1/story-versions/307/approvals", headers=h1,
                               json={"versionNumber": 2, "reviewedAllBranches": True})
    assert unsafe_branch.status_code == 422 and unsafe_branch.json()["error"]["code"] == "VALIDATION_ERROR"

    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("UPDATE story_branches SET choice_label = '去森林' WHERE id = 901")

    # Missing media root during API-026 returns retryable 503 and rolls back status/retirement.
    offline_root = tmp_path / "media-offline"
    media_root.rename(offline_root)
    dep_fail = first.post("/api/v1/story-versions/307/approvals", headers=h1,
                          json={"versionNumber": 2, "reviewedAllBranches": True})
    assert dep_fail.status_code == 503 and dep_fail.json()["error"]["retryable"] is True
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT status FROM story_versions WHERE id = 307").fetchone()[0] == "PENDING_REVIEW"
        assert db.execute("SELECT status FROM story_versions WHERE id = 301").fetchone()[0] == "APPROVED_PRIVATE"
    offline_root.rename(media_root)

    approved = first.post("/api/v1/story-versions/307/approvals", headers=h1,
                          json={"versionNumber": 2, "reviewedAllBranches": True})
    assert approved.status_code == 200
    p3 = next(p for p in approved.json()["data"]["pages"] if p["pageNumber"] == 3)
    assert p3["imageRef"] == "asset-307-page-3"

    # Mutate source image file after approval: pinned snapshot keeps original green PNG bytes.
    (media_root / "resume.png").write_bytes(red_png)
    assert first.get("/api/v1/media/asset-307-page-3").content == green_png
    assert second.get("/api/v1/media/asset-307-page-3").status_code == 404

    # Temporarily move blobs directory before API-011 switch: resume_page media verification fails closed with retryable 503.
    blobs_dir = db_path.parent / f".{db_path.name}.media_pins" / "blobs"
    blobs_offline = tmp_path / "blobs-offline"
    blobs_dir.rename(blobs_offline)
    switch_req = {
        "childProfileId": pid, "storyVersionId": 307, "mode": "PARENT_CHILD",
        "sourceReadingSessionId": sid1, "expectedRevision": 2, "clientRequestId": "switch-media-307",
    }
    media_503 = first.post("/api/v1/reading-sessions", headers=h1, json=switch_req)
    assert media_503.status_code == 503 and media_503.json()["error"]["retryable"] is True
    assert first.get(f"/api/v1/reading-sessions/{sid1}").json()["data"]["session"]["status"] == "IN_PROGRESS"

    blobs_offline.rename(blobs_dir)
    switched = first.post("/api/v1/reading-sessions", headers=h1, json=switch_req)
    assert switched.status_code == 201
    sid2 = switched.json()["data"]["readingSessionId"]

    # Withdrawing target version blocks SESSION_CREATE replay with 404.
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("UPDATE story_versions SET status = 'WITHDRAWN' WHERE id = 307")
    assert first.post("/api/v1/reading-sessions", headers=h1, json=switch_req).status_code == 404
    with closing(sqlite3.connect(db_path)) as db, db:
        db.execute("UPDATE story_versions SET status = 'APPROVED_PRIVATE' WHERE id = 307")
    assert first.post("/api/v1/reading-sessions", headers=h1, json=switch_req).status_code == 200

    # Deleting continuation session cleans up its SESSION_CREATE idempotency row.
    assert first.delete(f"/api/v1/reading-sessions/{sid2}", headers=h1).status_code == 204
    with closing(sqlite3.connect(db_path)) as db:
        assert db.execute("SELECT COUNT(*) FROM request_executions WHERE scope_type = 'SESSION_CREATE'").fetchone()[0] == 0
