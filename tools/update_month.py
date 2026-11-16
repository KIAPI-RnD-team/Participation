#!/usr/bin/env python3
"""월별 참여현황을 index.html 의 MONTHS 배열에 반영한다.

사용법 (저장소 폴더에서):
    pip install openpyxl cryptography
    python tools/update_month.py "<엑셀 경로>" 2026-12 "인건비관리(26년) 261210 · 12월 변경"

· 엑셀의 「참여율」 시트만 읽는다. 이름·직급·과제별 참여율(%)·과제책임자만 뽑고,
  금액이 들어 있는 다른 시트(인건비·사업비 등)는 열지 않는다.
· 같은 key(예: 2026-11)가 이미 있으면 그 달 덩어리를 바꾸고, 없으면 맨 뒤에 붙인다.
· index.html 이 비밀번호로 잠겨 있으면 비밀번호를 물어보고(또는 환경변수 PAGE_PASSWORD),
  풀어서 고친 뒤 같은 비밀번호로 다시 잠근다.
· 엑셀 파일은 저장소에 넣지 않는다(.gitignore 에 막혀 있음). 엑셀은 저장소 폴더 밖에 둘 것.
"""
import json, re, sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pagecrypt  # noqa: E402

INDEX = Path(__file__).resolve().parent.parent / "index.html"
# 시트 직급과 다르게 표기하는 인원
ROLE_OVERRIDE = {"김봉섭": "실장"}
# 시트 블록 이름 → 페이지 표기. None 이면 건너뜀.
DEPT = {"경영기획": "경영기획", "PG운영본부": "PG운영본부", "전략기획": "전략기획",
        "시험평가": "시험평가", "기업지원": "기업지원", "신규인력": None}
# 여러 블록에 중복 기재됐을 때 맞는 본부 (2026-08-18 확인)
DEPT_OVERRIDE = {"양영호": "기업지원"}
# 시트 과제명이 바뀌었을 때 페이지에서 쓸 이름
RENAME = {"(과)데이터최적화": "(과)데이터복원"}
NOTE_WHERE = {"기업": "기업지원", "시험": "시험평가본부"}

J = lambda v: json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def extract(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb["참여율"].iter_rows(values_only=True))
    hdr = rows[4]
    cols = [(j, RENAME.get(hdr[j], hdr[j])) for j in range(3, len(hdr))
            if isinstance(hdr[j], str) and hdr[j].startswith("(")]
    order = [n for _, n in cols]
    pi = {n: rows[7][j] for j, n in cols}
    kind = {n: rows[5][j] for j, n in cols}
    dept, people, outside, notes = None, [], {}, {}
    for r in rows[10:]:
        if isinstance(r[0], str) and r[0].strip():
            k = re.sub(r"\s", "", r[0])
            if k.startswith("*"):
                break
            dept = DEPT.get(k, k)
        name = r[1]
        if not isinstance(name, str) or dept is None:
            continue
        projs = [(n, round(r[j] * 100)) for j, n in cols
                 if isinstance(r[j], (int, float)) and r[j]]
        if not projs:
            continue
        if dept == "전략기획":
            people.append({"name": name, "role": ROLE_OVERRIDE.get(name, r[2]),
                           "total": float(sum(p for _, p in projs)),
                           "projects": [{"name": n, "pct": p} for n, p in projs]})
            if len(r) > 31 and isinstance(r[31], str):
                notes[name] = r[31]
        else:
            d = DEPT_OVERRIDE.get(name, dept)
            for n, p in projs:
                lst = outside.setdefault(n, [])
                if not any(m["name"] == name for m in lst):
                    lst.append({"name": name, "role": r[2], "pct": p, "dept": d})
    people.sort(key=lambda x: x["name"])
    outside = {n: outside[n] for n in order if n in outside}
    return order, pi, kind, people, outside, notes


def parse_months(html):
    """index.html 의 각 달 덩어리 위치와 PROJECT_PI·OUTSIDE 값을 읽는다."""
    start = html.index("const MONTHS=[\n") + len("const MONTHS=[\n")
    end = html.index("\n\nlet CUR", start)
    body = html[start:end]  # 마지막 달은 "...}];" 로 끝남
    blocks = []
    for m in re.finditer(r'\{key:"(\d{4}-\d\d)".*?(?=\n\{key:|\Z)', body, re.S):
        blk = m.group(0)
        def grab(k):
            s = re.search(r"\n " + k + r":(.*?),?\n", blk).group(1).rstrip(",")
            return json.loads(re.sub(r'([{,])(\w+):', r'\1"\2":', s))
        blocks.append({"key": m.group(1), "span": (start + m.start(), start + m.end()),
                       "PROJECT_PI": grab("PROJECT_PI"), "OUTSIDE": grab("OUTSIDE")})
    return blocks


def main(xlsx, key, src):
    html = INDEX.read_text(encoding="utf-8")
    locked = pagecrypt.is_locked(html)
    if locked:  # 비밀번호로 풀어서 고친 뒤 같은 비밀번호로 다시 잠근다
        pw, salt = pagecrypt.password(), pagecrypt.salt_of(html)
        html = pagecrypt.decrypt(html, pw)
    order, pi, kind, people, outside, notes = extract(xlsx)
    blocks = parse_months(html)
    prev = [b for b in blocks if b["key"] < key] or blocks
    prev = prev[-1]
    # 과제책임자: 시트 8행이 비어 있으면(0) 전달 값을 그대로 쓴다. lead 는 전달 값 유지.
    project_pi = {}
    for n in order:
        old = prev["PROJECT_PI"].get(n, {})
        name = pi[n] if isinstance(pi[n], str) and pi[n] else old.get("pi", "")
        lead = old.get("lead", 1 if kind[n] == "주관" else 0)
        project_pi[n] = {"pi": name, "lead": lead}
    # 합계 100% 미만 사유: 시트 비고(+10%(기업)) 우선, 없으면 전달 값
    out_alloc = {}
    for p in people:
        if p["total"] >= 100:
            continue
        m = re.match(r"\+(\d+)%\((\S+?)\)", notes.get(p["name"], ""))
        if m:
            out_alloc[p["name"]] = {"pct": int(m.group(1)), "where": NOTE_WHERE.get(m.group(2), m.group(2))}
        elif p["name"] in prev["OUTSIDE"]:
            out_alloc[p["name"]] = prev["OUTSIDE"][p["name"]]
    # 전달 순서 유지
    out_alloc = {k: out_alloc[k] for k in sorted(out_alloc, key=lambda k: (k not in prev["OUTSIDE"], list(prev["OUTSIDE"]).index(k) if k in prev["OUTSIDE"] else 0))}
    month = int(key[5:])
    block = (
        f'{{key:"{key}",label:"{month}월",period:"{key[:4]}년 {month}월",src:"{src}",\n'
        f" SHEET_ORDER:{J(order)},\n"
        f" // 전략기획본부 참여율 시트 밖에 배정된 인원 (합계 100% 미만의 사유)\n"
        f" OUTSIDE:{J(out_alloc)},\n"
        f" PROJECT_PI:{J(project_pi)},\n"
        f" // 같은 과제에 참여하는 타 본부 인원 — {src} · 참여율 시트 전 본부 블록\n"
        f" OUTSIDE_MEMBERS:{J(outside)},\n"
        f" PEOPLE:{J(people)}}}"
    )
    same = [b for b in blocks if b["key"] == key]
    if same:
        a, b = same[0]["span"]
        last = html[a:b].endswith("];")
        html = html[:a] + block + ("];" if last else ",") + html[b:]
    else:
        a, b = blocks[-1]["span"]
        assert html[a:b].endswith("}];")
        html = html[:b - 1] + ",\n" + block + "];" + html[b:]
    # 제목의 (N월) 표기를 최신 달로
    latest = max([x["key"] for x in blocks] + [key])
    html = re.sub(r"<title>(.*?)\(\d+월\)</title>", rf"<title>\1({int(latest[5:])}월)</title>", html, count=1)
    if locked:
        html = pagecrypt.encrypt(html, pw, salt)
    INDEX.write_text(html, encoding="utf-8")
    print(f"{key} 반영: 전략기획 {len(people)}명, 과제 {len(order)}개")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
