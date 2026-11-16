# 매달 참여현황 갱신 방법

1. 새 달 「인건비관리」 엑셀은 PC의 `3.인건비` 폴더에 그대로 둔다. **저장소 폴더로 복사하지 않는다.**
2. 저장소 폴더에서 실행한다.

   ```
   pip install openpyxl
   python tools/update_month.py "<엑셀 전체 경로>" 2026-12 "인건비관리(26년) 261210 · 12월 변경"
   ```

   - 두 번째 값은 달(key), 세 번째 값은 페이지에 보이는 출처 문구.
   - 같은 달이 이미 있으면 덮어쓰고, 없으면 새 달 탭을 추가한다.
3. `git diff` 로 바뀐 사람·참여율만 확인하고 PR을 올린다.

스크립트는 엑셀의 「참여율」 시트에서 이름·직급·과제별 참여율(%)·과제책임자만 읽는다.
금액(인건비·사업비 등)은 읽지도 페이지에 넣지도 않는다. `.gitignore` 가 엑셀·CSV 파일 커밋을 막는다.

시트와 다르게 표기하는 예외(직급 표기, 중복 기재 인원의 본부, 과제명 변경)는
`update_month.py` 위쪽 `ROLE_OVERRIDE`·`DEPT_OVERRIDE`·`RENAME` 에 모아 두었다.
시트 8행 과제책임자가 비어 있으면(0) 전달 값을 그대로 쓰고, 주관 여부(lead)는 전달 값을 유지한다.

## 접속 비밀번호

`index.html` 은 비밀번호로 암호화돼 있다. 이름·참여율은 비밀번호가 맞아야 브라우저에서 풀린다.
비밀번호는 저장소에 저장하지 않으니 따로 잘 보관할 것 (잊으면 복구 불가 → 엑셀로 다시 만들어야 함).

- 월별 갱신: `update_month.py` 가 실행 중 비밀번호를 물어본다.
- 디자인 수정: `python tools/pagecrypt.py decrypt` → `page.plain.html` 수정 → `python tools/pagecrypt.py encrypt` → `page.plain.html` 삭제
- 비밀번호 변경: `python tools/pagecrypt.py repass` (모든 사람이 새 비밀번호로 다시 입력해야 함)
