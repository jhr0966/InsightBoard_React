"""로드맵 엑셀 업로드/정규화/검증/Parquet 저장."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from roadmap.schema import ALL_COLUMNS, COLUMN_MAP, REQUIRED_COLUMNS
from store.paths import roadmap_dir


@dataclass
class IngestResult:
    ok: bool
    errors: list[str]
    row_count: int = 0
    parquet_path: str | None = None
    raw_path: str | None = None


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

    return renamed


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


def ingest_excel(
    fileobj: BinaryIO,
    *,
    sheet_name: str | int = "Master_Table",
    save_raw: bool = True,
) -> IngestResult:
    """엑셀 → 정규화 DataFrame → Parquet 저장. 원본 .xlsx도 별도 보관."""
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

    return IngestResult(
        ok=True,
        errors=[],
        row_count=len(df),
        parquet_path=str(parquet_path),
        raw_path=str(raw_path) if raw_path else None,
    )
