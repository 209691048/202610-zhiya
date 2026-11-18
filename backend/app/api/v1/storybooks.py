"""Read-only bookshelf for guardians and scoped child grants."""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Path, Query, Request

from app.api.v1.auth import authorized_db, error

router = APIRouter(prefix="/api/v1")
AgeBand = Literal["AGE_3_4", "AGE_4_5", "AGE_5_6"]
AGES = {"AGE_3_4": (3, 4), "AGE_4_5": (4, 5), "AGE_5_6": (5, 6)}


def version_object(db, row):
    pages = db.execute(
        "SELECT * FROM story_pages WHERE version_id = ? ORDER BY page_no", (row["id"],)
    ).fetchall()
    branches = db.execute(
        "SELECT * FROM story_branches WHERE version_id = ? AND review_status = 'APPROVED' ORDER BY id",
        (row["id"],),
    ).fetchall()
    return {
        "storybookId": row["storybook_id"], "storyVersionId": row["id"],
        "versionNumber": row["version_no"], "title": row["title"], "status": row["status"],
        # No verified, version-bound media resolver exists yet. Never expose seed paths.
        "coverRef": None,
        "pages": [{"pageNumber": p["page_no"], "text": p["body_text"], "imageRef": None,
                   "defaultNextPageNumber": p["default_next_page_number"]} for p in pages],
        "branches": [{"branchId": b["id"], "fromPageNumber": b["from_page_no"],
                      "nextPageNumber": b["next_page_no"], "choiceLabel": b["choice_label"],
                      "reviewStatus": b["review_status"]} for b in branches],
    }


# PUBLISHED is public to authenticated guardians; private versions require ownership.
# Retired versions are available only as reviewed private originals belonging to the guardian.
VISIBLE = """(v.status = 'PUBLISHED' OR
    (v.status = 'APPROVED_PRIVATE' AND b.owner_guardian_id = ?) OR
    (? AND v.status = 'RETIRED' AND b.source_type = 'ORIGINAL'
       AND b.owner_guardian_id = ? AND v.reviewed_by_id IS NOT NULL AND v.reviewed_at IS NOT NULL))"""


@router.get("/storybooks")
def list_storybooks(request: Request, age_band: AgeBand | None = Query(default=None, alias="ageBand"),
                    topic: str | None = Query(default=None, min_length=1, max_length=100),
                    scope: Literal["mine"] | None = None,
                    page: int = Query(default=1, ge=1, le=9007199254740991),
                    page_size: int = Query(default=20, ge=1, le=50, alias="pageSize")):
    try:
        with authorized_db(request) as (db, principal, failure):
            if failure:
                return failure
            if principal.role == "CHILD" and scope == "mine":
                return error(request, 403, "FORBIDDEN", "儿童模式不支持查看个人历史书架")
            conditions = [VISIBLE]
            params = [principal.guardian_id, scope == "mine", principal.guardian_id]
            if principal.role == "CHILD":
                conditions.append("EXISTS (SELECT 1 FROM child_grant_books gb WHERE gb.grant_id = ? AND gb.version_id = v.id)")
                params.append(principal.grant_id)
            if age_band:
                low, high = AGES[age_band]
                conditions.append("v.age_min <= ? AND v.age_max >= ?")
                params.extend((high, low))
            if topic is not None:
                conditions.append("EXISTS (SELECT 1 FROM json_each(v.topics_json) WHERE value = ?)")
                params.append(topic)
            # Avoid exceeding SQLite's signed 64-bit integer range for very large pages.
            offset = min((page - 1) * page_size, 9223372036854775807)
            rows = db.execute(
                "SELECT v.* FROM story_versions v JOIN storybooks b ON b.id = v.storybook_id WHERE "
                + " AND ".join(conditions) + " ORDER BY v.storybook_id, v.version_no DESC LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
            items = [version_object(db, row) for row in rows]
            return {"data": {"items": items, "page": page, "pageSize": page_size}, "requestId": request.state.request_id}
    except sqlite3.Error:
        return error(request, 503, "DEPENDENCY_UNAVAILABLE", "服务暂不可用", retryable=True)


@router.get("/story-versions/{version_id}")
def get_story_version(request: Request, version_id: int = Path(ge=1, le=9007199254740991)):
    try:
        with authorized_db(request) as (db, principal, failure):
            if failure:
                return failure
            grant_filter = (
                "AND EXISTS (SELECT 1 FROM child_grant_books gb WHERE gb.grant_id = ? AND gb.version_id = v.id) "
                if principal.role == "CHILD" else ""
            )
            active_session_filter = (
                "EXISTS (SELECT 1 FROM reading_sessions s WHERE s.version_id = v.id AND s.grant_id = ? "
                "AND s.profile_id = ? AND s.status IN ('CREATED', 'IN_PROGRESS'))"
                if principal.role == "CHILD"
                else "EXISTS (SELECT 1 FROM reading_sessions s JOIN child_profiles p ON p.id = s.profile_id "
                     "WHERE s.version_id = v.id AND p.guardian_id = ? AND s.status IN ('CREATED', 'IN_PROGRESS'))"
            )
            params = (
                (version_id, principal.grant_id, principal.guardian_id, True, principal.guardian_id,
                 principal.grant_id, principal.profile_id)
                if principal.role == "CHILD"
                else (version_id, principal.guardian_id, True, principal.guardian_id, principal.guardian_id)
            )
            row = db.execute(
                "SELECT v.* FROM story_versions v JOIN storybooks b ON b.id = v.storybook_id "
                f"WHERE v.id = ? {grant_filter}AND (" + VISIBLE +
                " OR (v.status = 'RETIRED' AND v.reviewed_by_id IS NOT NULL AND v.reviewed_at IS NOT NULL "
                f"AND b.source_type = 'LIBRARY' AND {active_session_filter}))",
                params,
            ).fetchone()
            if not row:
                return error(request, 404, "RESOURCE_NOT_FOUND", "绘本不可用")
            return {"data": version_object(db, row), "requestId": request.state.request_id}
    except sqlite3.Error:
        return error(request, 503, "DEPENDENCY_UNAVAILABLE", "服务暂不可用", retryable=True)
