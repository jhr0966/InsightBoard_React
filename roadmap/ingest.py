"""로드맵 엑셀 업로드/정규화/검증/Parquet 저장."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from roadmap.schema import ALL_COLUMNS, COLUMN_MAP, REQUIRED_COLUMNS
from roadmap.task_def_json import assemble_from_columns
from store.paths import roadmap_dir

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    ok: bool
    errors: list[str]
    row_count: int = 0
    parquet_path: str | None = None
    raw_path: str | None = None
    # 정규 JSON 데이터셋 경로 — 작업 정의 전체를 JSON 배열로 보유(재업로드 교체).
    json_path: str | None = None
    # PR-3 — SQLite 동기화 결과 (best-effort; Parquet 저장 성공이 ok 의 기준).
    sqlite_created: int = 0
    sqlite_updated: int = 0
    sqlite_skipped: int = 0
    # 동기화 실패 메시지 — Parquet 은 성공했는데 SQLite 가 실패하면 채워진다.
    # query.load_latest 가 SQLite 를 우선 읽으므로(stale 위험) 호출부가 표면화할 수 있게 (C3).
    sqlite_error: str = ""


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """한국어 헤더를 snake_case로 변환. 알 수 없는 컬럼은 그대로 둔다.

    신버전 엑셀(2026-05+) 호환: lv1/lv2/lv3 가 없고 division/process/task 만
    있으면 자동으로 fallback 채움 — 기존 사용처(보드 ④/⑥, 인사이트, persona
    interest_lv3)가 그대로 동작하도록.

      신엑셀 컬럼 분과 / 공정 / 작업 → division / process / task
      자동 채움    lv1 = division
                  lv2 = process
                  lv3 = task   (lv3 가 비어있을 때만)

    구버전 엑셀은 영향 없음 — lv1/lv2/lv3 가 이미 채워져 있으면 덮어쓰지 않음.
    """
    renamed = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
    # 누락된 선택 컬럼은 빈 값으로 채워 후속 조회 안정화
    for col in ALL_COLUMNS:
        if col not in renamed.columns:
            renamed[col] = ""
    renamed = renamed[list(ALL_COLUMNS)].copy()

    # 신버전 fallback — lv1/lv2/lv3 가 모두 빈 값이고 division/process/task 가
    # 채워진 경우 자동 채움. 부분만 비어있는 혼합 경우는 안전을 위해 건드리지 않음.
    def _is_blank(series: pd.Series) -> bool:
        return bool(series.astype(str).str.strip().eq("").all())

    if _is_blank(renamed["lv1"]) and not _is_blank(renamed["division"]):
        renamed["lv1"] = renamed["division"]
    if _is_blank(renamed["lv2"]) and not _is_blank(renamed["process"]):
        renamed["lv2"] = renamed["process"]
    if _is_blank(renamed["lv3"]) and not _is_blank(renamed["task"]):
        renamed["lv3"] = renamed["task"]

    # flat-column 엑셀(2026-06+) — JSON 열이 없는 행은 개별 컬럼을 task_def_json 으로
    # 조립한다. 이미 task_def_json 이 채워진 행(구 JSON 포맷)은 그대로 둔다.
    # 이 한 단계 덕분에 이후 매칭/보드/SOLA/SQLite 가 포맷에 상관없이 task_def_json
    # 만 읽으면 된다(단일 진입점).
    def _fill_task_def_json(r: pd.Series) -> str:
        existing = str(r.get("task_def_json") or "").strip()
        if existing:
            return existing
        payload = assemble_from_columns(r)
        return json.dumps(payload, ensure_ascii=False) if payload else ""

    renamed["task_def_json"] = renamed.apply(_fill_task_def_json, axis=1)

    return renamed


_GUIDE_MARKERS = ("◀", "▶")


def drop_guide_rows(df: pd.DataFrame) -> pd.DataFrame:
    """안내/배너 행 제거 — 공정정의서_통합 폼 1행(`◀ 계층 구조 ▶` 등 가이드 배너).

    제거 기준(둘 중 하나):
      1) 어떤 셀이든 `◀`/`▶` 마커를 포함 (가이드 배너),
      2) 작업·팀·process_id 가 모두 빈 행 (실데이터가 아님).
    정규화 후 호출 — 컬럼은 코드명(team/task/process_id …).
    """
    if df.empty:
        return df

    def _is_guide(r: pd.Series) -> bool:
        joined = " ".join(str(v) for v in r.values)
        if any(m in joined for m in _GUIDE_MARKERS):
            return True
        ident = [str(r.get(c, "")).strip() for c in ("team", "task", "process_id")]
        return not any(ident)

    mask = df.apply(_is_guide, axis=1)
    return df.loc[~mask].reset_index(drop=True)


def validate(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df.empty:
        errors.append("엑셀에 데이터가 없습니다.")
        return errors
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            errors.append(f"필수 컬럼 누락: {col}")
            continue
        null_count = int(df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum())
        if null_count:
            errors.append(f"필수 컬럼 '{col}'에 빈 값이 {null_count}건 있습니다.")
    return errors


CANONICAL_JSON_NAME = "task_defs.json"


def write_canonical_json(df: pd.DataFrame, out_dir: Path) -> Path:
    """정규화 DataFrame → 작업 정의 JSON 배열을 `task_defs.json` 으로 (원자적) 저장.

    각 행을 `sqlite_sync.row_to_task_def` 로 변환해 org_meta·process_id 가 주입된
    **완성 JSON 객체**를 모은다(= SQLite 에 들어가는 것과 동일). 매 업로드 통째로
    덮어쓰므로 파일 자체가 '교체' 의미의 단일 SOT(React/백엔드 공용 계약).
    """
    from roadmap.sqlite_sync import row_to_task_def

    objects: list[dict] = []
    if df is not None and not df.empty:
        for _, raw in df.iterrows():
            built = row_to_task_def(raw.to_dict())
            if built is None:
                continue
            _pid, json_str = built
            try:
                objects.append(json.loads(json_str))
            except (json.JSONDecodeError, TypeError):
                continue

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / CANONICAL_JSON_NAME
    tmp = path.with_suffix(".json.tmp")
    payload = {
        "schema_version": "1.0",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(objects),
        "task_defs": objects,
    }
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)  # 원자적 교체
    return path


def ingest_excel(
    fileobj: BinaryIO,
    *,
    sheet_name: str | int = "Master_Table",
    save_raw: bool = True,
    to_sqlite: bool = True,
    replace: bool = False,
) -> IngestResult:
    """엑셀 → 정규화 DataFrame → Parquet + 정규 JSON 저장. 원본 .xlsx도 별도 보관.

    to_sqlite=True (기본): Parquet 저장 후 `store.task_defs_db` 에도 행 단위
    UPSERT (best-effort). SQLite 동기화 실패는 ingest 전체를 실패시키지 않는다.

    replace=True (재업로드 교체): SQLite 를 비운 뒤 새 데이터셋으로 채운다 +
    정규 JSON(`task_defs.json`)을 통째로 덮어쓴다 → 직전 업로드에 없던 행이
    남지 않는다("한 번 더 업로드 = 데이터 교체").
    """
    try:
        df_raw = pd.read_excel(fileobj, sheet_name=sheet_name, dtype=str).fillna("")
    except ValueError:
        # 시트명이 다르면 첫 시트로 fallback
        fileobj.seek(0)
        df_raw = pd.read_excel(fileobj, sheet_name=0, dtype=str).fillna("")
    except Exception as e:
        return IngestResult(ok=False, errors=[f"엑셀 읽기 실패: {e}"])

    df = normalize_columns(df_raw)
    # 문자열 strip
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # 안내/배너 행(◀ 계층 구조 ▶ 등) 제거 — 검증 전.
    df = drop_guide_rows(df)

    errs = validate(df)
    if errs:
        return IngestResult(ok=False, errors=errs)

    stamp = _utc_stamp()
    out_dir = roadmap_dir()
    parquet_path = out_dir / f"roadmap_{stamp}.parquet"
    df.to_parquet(parquet_path, index=False)

    raw_path: Path | None = None
    if save_raw:
        try:
            fileobj.seek(0)
            raw_path = out_dir / f"roadmap_{stamp}.xlsx"
            raw_path.write_bytes(fileobj.read())
        except Exception:
            raw_path = None

    # 정규 JSON 데이터셋 — 작업 정의 전체를 JSON 배열로 보유(SQLite/Parquet 와 동일
    # 내용, org_meta·process_id 주입 완료). 업로드마다 통째로 덮어써 '교체' 의미를 만든다.
    json_path: Path | None = None
    try:
        json_path = write_canonical_json(df, out_dir)
    except Exception:
        json_path = None

    result = IngestResult(
        ok=True,
        errors=[],
        row_count=len(df),
        parquet_path=str(parquet_path),
        raw_path=str(raw_path) if raw_path else None,
        json_path=str(json_path) if json_path else None,
    )

    if to_sqlite:
        try:
            from roadmap.sqlite_sync import sync_dataframe

            sync = sync_dataframe(df, source="excel_upload", replace=replace)
            result.sqlite_created = sync.created
            result.sqlite_updated = sync.updated
            result.sqlite_skipped = sync.skipped
        except Exception as exc:  # noqa: BLE001 — SQLite 동기화는 best-effort(Parquet 은 이미 성공)
            # 조용히 삼키면 Parquet 만 갱신되고 SQLite 우선 reader 가 stale 데이터를
            # 읽어 분기됨(C3). 메시지를 result 에 남기고 로깅해 표면화.
            result.sqlite_error = str(exc)
            logger.warning("로드맵 SQLite 동기화 실패(Parquet 은 성공): %s", exc, exc_info=True)

    return result
