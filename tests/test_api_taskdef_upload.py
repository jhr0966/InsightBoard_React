"""api.routers.taskdefs — 엑셀 업로드(ingest) + api.routers.opportunities."""
from __future__ import annotations

import io

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _excel_bytes() -> bytes:
    raw = pd.DataFrame([
        {"팀": "가공팀", "부서": "가공부", "분류(Lv1)": "실행분과",
         "소분류(Lv2)": "구조내업", "공정(Lv3)": "전처리", "작업": "강재선별",
         "세부 작업": "크레인", "작업 정의": "", "SWS 표준번호": "SC0-1", "SWS명": "강재 하역"},
        {"팀": "가공팀", "부서": "가공부", "분류(Lv1)": "실행분과",
         "소분류(Lv2)": "구조내업", "공정(Lv3)": "가공", "작업": "절단",
         "세부 작업": "절단", "작업 정의": "", "SWS 표준번호": "SC0-2", "SWS명": "절단 작업"},
    ])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        raw.to_excel(w, sheet_name="Master_Table", index=False)
    return buf.getvalue()


def test_upload_ingests_roadmap():
    files = {"file": ("master.xlsx", _excel_bytes(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = client.post("/api/taskdefs/upload", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["row_count"] == 2
    # 골격 행(작업 정의 JSON 없음)은 per-task task_defs_db 로는 skip,
    # 로드맵 데이터셋(매칭/기회용)에는 적재된다.
    from roadmap import query
    assert len(query.load_latest()) == 2


def test_upload_rejects_bad_excel():
    files = {"file": ("bad.xlsx", b"not really excel", "application/octet-stream")}
    r = client.post("/api/taskdefs/upload", files=files)
    assert r.status_code == 422


def test_opportunities_empty_ok():
    # 데이터 없으면 빈 배열(에러 X)
    assert client.get("/api/opportunities").json() == []
