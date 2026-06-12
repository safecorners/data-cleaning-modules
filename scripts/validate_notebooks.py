#!/usr/bin/env python
"""노트북 검증 스크립트.

프로젝트 루트의 모든 .ipynb 를 위에서부터 끝까지 실행해서 결과를 분류한다.

  ✅ PASS     — 모든 셀이 에러 없이 실행됨
  ⚠️ NO_DATA  — 외부 CSV 부재(FileNotFoundError)로만 실패 → 데이터를 받으면 통과 예상
  ❌ ERROR    — 그 외 실제 실행 오류

사용법:
  uv run python scripts/validate_notebooks.py            # 전체
  uv run python scripts/validate_notebooks.py M12 C04    # 이름에 해당 문자열이 들어간 것만
  uv run python scripts/validate_notebooks.py --timeout 300

종료 코드: ❌ ERROR 가 하나라도 있으면 1, 아니면 0.
(NO_DATA 는 데이터 미동봉이 원인이라 실패로 치지 않음)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError

ROOT = Path(__file__).resolve().parent.parent

PASS, NO_DATA, ERROR = "PASS", "NO_DATA", "ERROR"
ICON = {PASS: "✅", NO_DATA: "⚠️ ", ERROR: "❌"}

# 외부 데이터 부재로만 발생하는, 실패로 치지 않을 예외들
DATA_MISSING_MARKERS = ("FileNotFoundError", "No such file or directory")


def run_notebook(path: Path, kernel: str, timeout: int) -> tuple[str, str]:
    """노트북 하나를 실행하고 (상태, 한 줄 메시지)를 돌려준다."""
    nb = nbformat.read(path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name=kernel,
        allow_errors=False,
        # 상대경로 read_csv 가 프로젝트 루트 기준으로 동작하도록
        resources={"metadata": {"path": str(ROOT)}},
    )
    try:
        client.execute()
        return PASS, "모든 셀 실행 완료"
    except CellExecutionError as exc:
        text = str(exc)
        if any(marker in text for marker in DATA_MISSING_MARKERS):
            return NO_DATA, "외부 CSV 없음 (read_csv 실패)"
        # 에러 종류 한 줄만 추려서 보여주기
        last = ""
        for line in text.strip().splitlines():
            line = line.strip()
            if line and ("Error" in line or "Exception" in line):
                last = line
        return ERROR, last or "실행 오류 (상세는 노트북 직접 실행으로 확인)"
    except Exception as exc:  # 커널 시작 실패 등
        return ERROR, f"{type(exc).__name__}: {exc}".splitlines()[0][:120]


def main() -> int:
    ap = argparse.ArgumentParser(description="노트북 일괄 실행 검증")
    ap.add_argument("filters", nargs="*", help="파일명에 포함될 문자열(여러 개 가능). 없으면 전체.")
    ap.add_argument("--kernel", default="python3", help="사용할 Jupyter 커널 (기본: python3 = venv 커널)")
    ap.add_argument("--timeout", type=int, default=180, help="셀당 타임아웃(초), 기본 180")
    args = ap.parse_args()

    notebooks = sorted(p for p in ROOT.glob("*.ipynb"))
    if args.filters:
        notebooks = [p for p in notebooks if any(f in p.name for f in args.filters)]

    if not notebooks:
        print("실행할 노트북이 없습니다.")
        return 0

    print(f"검증 대상 {len(notebooks)}개 (커널: {args.kernel}, 타임아웃: {args.timeout}s)\n")

    results: list[tuple[str, str, str]] = []
    for path in notebooks:
        print(f"  실행 중… {path.name}", flush=True)
        status, msg = run_notebook(path, args.kernel, args.timeout)
        results.append((status, path.name, msg))

    width = max(len(name) for _, name, _ in results)
    counts = {PASS: 0, NO_DATA: 0, ERROR: 0}
    print("\n" + "=" * (width + 40))
    print("결과 요약")
    print("=" * (width + 40))
    for status, name, msg in results:
        counts[status] += 1
        print(f"{ICON[status]} {name.ljust(width)}  {msg}")
    print("=" * (width + 40))
    print(
        f"✅ 통과 {counts[PASS]}   "
        f"⚠️  데이터없음 {counts[NO_DATA]}   "
        f"❌ 오류 {counts[ERROR]}"
    )

    return 1 if counts[ERROR] else 0


if __name__ == "__main__":
    sys.exit(main())
