"""roadmap.task_def_json — v1.0 `org_meta` 확장 (PR-2)."""
from __future__ import annotations

import json

import pytest

from roadmap import task_def_json as tdj
from roadmap.task_def_json import (
    ORG_META_KEYS,
    ORG_META_REQUIRED,
    SCHEMA_VERSION,
    TaskDefJsonError,
    ingest_org_meta,
    org_meta_of,
    validate_task_def_json,
)


# ── 상수 sanity ──────────────────────────────────────────

def test_schema_constants_exposed():
    assert SCHEMA_VERSION == "1.0"
    assert "team" in ORG_META_KEYS and "dept" in ORG_META_KEYS
    assert "lv1" in ORG_META_KEYS and "lv3" in ORG_META_KEYS
    assert ORG_META_REQUIRED == ("team", "dept")


# ── ingest_org_meta ──────────────────────────────────────

def test_ingest_org_meta_adds_org_meta_and_version_to_existing_json():
    src = json.dumps({
        "process_id": "PNL-SEL-001",
        "process_name": "판넬 선별",
        "objectives": ["BOM 수입 검수"],
    })
    out = ingest_org_meta(src, {
        "team": "가공팀", "dept": "판넬조립부",
        "division": "구조내업", "process": "판넬",
        "task": "선별", "sub_task": "선별",
    })
    obj = json.loads(out)
    assert obj["org_meta"]["team"] == "가공팀"
    assert obj["org_meta"]["dept"] == "판넬조립부"
    assert obj["org_meta"]["process"] == "판넬"
    assert obj["version"] == "1.0"
    # 기존 필드 보존
    assert obj["process_id"] == "PNL-SEL-001"
    assert obj["objectives"] == ["BOM 수입 검수"]


def test_ingest_org_meta_starts_from_empty_when_input_blank():
    out = ingest_org_meta("", {"team": "가공팀", "dept": "D1"}, process_id="X1")
    obj = json.loads(out)
    assert obj["process_id"] == "X1"
    assert obj["org_meta"]["team"] == "가공팀"
    assert obj["version"] == "1.0"


def test_ingest_org_meta_starts_from_empty_when_input_invalid_json():
    out = ingest_org_meta("not json {{", {"team": "T", "dept": "D"})
    obj = json.loads(out)
    assert obj["org_meta"] == {"team": "T", "dept": "D"}


def test_ingest_org_meta_overwrites_process_id_when_arg_given():
    src = json.dumps({"process_id": "OLD-ID", "x": 1})
    out = ingest_org_meta(src, {"team": "T", "dept": "D"}, process_id="NEW-ID")
    assert json.loads(out)["process_id"] == "NEW-ID"


def test_ingest_org_meta_preserves_existing_version_if_present():
    src = json.dumps({"process_id": "X", "version": "1.5"})
    out = ingest_org_meta(src, {"team": "T", "dept": "D"})
    assert json.loads(out)["version"] == "1.5"


def test_ingest_org_meta_strips_whitespace_and_drops_empty_values():
    out = ingest_org_meta("", {
        "team": "  가공팀  ",
        "dept": "판넬조립부",
        "division": "   ",  # empty → drop
        "process": "판넬",
        "lv1": "",          # empty → drop
    })
    meta = json.loads(out)["org_meta"]
    assert meta["team"] == "가공팀"
    assert meta["process"] == "판넬"
    assert "division" not in meta
    assert "lv1" not in meta


def test_ingest_org_meta_ignores_unknown_keys():
    out = ingest_org_meta("", {
        "team": "T", "dept": "D",
        "random_key": "값", "process_id": "이건 무시",
    })
    meta = json.loads(out)["org_meta"]
    assert "random_key" not in meta
    assert "process_id" not in meta  # ORG_META_KEYS 에 없음


def test_ingest_org_meta_rejects_missing_team():
    with pytest.raises(TaskDefJsonError, match="team"):
        ingest_org_meta("", {"dept": "D"})


def test_ingest_org_meta_rejects_missing_dept():
    with pytest.raises(TaskDefJsonError, match="dept"):
        ingest_org_meta("", {"team": "T"})


def test_ingest_org_meta_rejects_non_dict_org_meta():
    with pytest.raises(TaskDefJsonError, match="object"):
        ingest_org_meta("", ["not", "a", "dict"])  # type: ignore[arg-type]


# ── org_meta_of ─────────────────────────────────────────

def test_org_meta_of_extracts_only_known_keys():
    js = json.dumps({
        "process_id": "X",
        "org_meta": {
            "team": "T", "dept": "D", "junk": "ignored",
            "division": "구조내업",
        },
    })
    meta = org_meta_of(js)
    assert meta == {"team": "T", "dept": "D", "division": "구조내업"}


def test_org_meta_of_returns_empty_on_missing_or_invalid():
    assert org_meta_of(None) == {}
    assert org_meta_of("") == {}
    assert org_meta_of("not json") == {}
    assert org_meta_of(json.dumps([1, 2])) == {}
    assert org_meta_of(json.dumps({"process_id": "X"})) == {}  # no org_meta
    # org_meta 가 list 인 경우
    assert org_meta_of(json.dumps({"org_meta": [1]})) == {}


# ── validate_task_def_json ──────────────────────────────

def test_validate_accepts_well_formed():
    js = ingest_org_meta(
        json.dumps({"process_id": "X1"}),
        {"team": "T", "dept": "D"},
    )
    obj = validate_task_def_json(js)
    assert obj["process_id"] == "X1"
    assert obj["org_meta"]["team"] == "T"


def test_validate_rejects_missing_process_id():
    js = json.dumps({"org_meta": {"team": "T", "dept": "D"}})
    with pytest.raises(TaskDefJsonError, match="process_id"):
        validate_task_def_json(js)


def test_validate_rejects_invalid_or_empty():
    with pytest.raises(TaskDefJsonError):
        validate_task_def_json("")
    with pytest.raises(TaskDefJsonError, match="invalid JSON"):
        validate_task_def_json("{{not json")
    with pytest.raises(TaskDefJsonError, match="object"):
        validate_task_def_json(json.dumps(["list"]))


def test_validate_rejects_missing_required_org_meta_fields():
    js = json.dumps({"process_id": "X", "org_meta": {"dept": "D"}})
    with pytest.raises(TaskDefJsonError, match="team"):
        validate_task_def_json(js)


def test_validate_rejects_whitespace_only_process_id():
    """Codex P2 — whitespace-only process_id 가 truthy 로 통과되면 안 됨."""
    for bad in ("   ", "\t", "\n", " \t\n "):
        js = json.dumps({
            "process_id": bad,
            "org_meta": {"team": "T", "dept": "D"},
        })
        with pytest.raises(TaskDefJsonError, match="process_id"):
            validate_task_def_json(js)


def test_validate_rejects_non_string_process_id():
    for bad in (123, None, [], {}):
        js = json.dumps({
            "process_id": bad,
            "org_meta": {"team": "T", "dept": "D"},
        })
        with pytest.raises(TaskDefJsonError, match="process_id"):
            validate_task_def_json(js)
