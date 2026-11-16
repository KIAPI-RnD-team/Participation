#!/usr/bin/env python3
"""페이지 전체를 비밀번호로 암호화/복호화한다.

index.html 에는 암호문과 비밀번호 입력 화면만 들어가고, 이름·참여율 같은 내용은
비밀번호가 맞아야 브라우저 안에서 풀린다 (PBKDF2-SHA256 + AES-256-GCM).
비밀번호는 저장소 어디에도 저장하지 않는다.

사용법 (저장소 폴더에서, pip install cryptography):
    python tools/pagecrypt.py decrypt page.plain.html     # index.html → 평문 (디자인 수정용)
    python tools/pagecrypt.py encrypt page.plain.html     # 평문 → index.html
    python tools/pagecrypt.py repass                       # 비밀번호 변경
비밀번호는 Dashboard 와 같다. 환경변수 PAGE_PASSWORD, 또는 GATE_CONF(Dashboard 의
gate_conf.json 경로)가 있으면 그것을 쓰고, 없으면 입력을 받는다.
평문 파일(page.plain.html)은 .gitignore 에 막혀 있으니 커밋되지 않는다. 작업 후 지워도 된다.
"""
import base64, getpass, json, os, re, sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

INDEX = Path(__file__).resolve().parent.parent / "index.html"
SHELL = Path(__file__).resolve().parent / "lock_shell.html"
ITER = 310_000
MARK = re.compile(r'var VAULT = (\{.*?\});')

b64 = lambda b: base64.b64encode(b).decode()


def _key(pw, salt, it):
    return PBKDF2HMAC(hashes.SHA256(), 32, salt, it).derive(pw.encode("utf-8"))


def is_locked(html):
    return bool(MARK.search(html))


def salt_of(locked_html):
    return base64.b64decode(json.loads(MARK.search(locked_html).group(1))["salt"])


def encrypt(plain_html, pw, salt=None):
    # salt 를 유지하면 「이 기기에서 기억하기」 한 사람은 월별 갱신 뒤에도 다시 입력하지 않아도 된다.
    salt, iv = salt or os.urandom(16), os.urandom(12)
    ct = AESGCM(_key(pw, salt, ITER)).encrypt(iv, plain_html.encode("utf-8"), None)
    payload = json.dumps({"v": 1, "it": ITER, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)})
    shell = SHELL.read_text(encoding="utf-8")
    return shell.replace("__PAYLOAD__", payload)


def decrypt(locked_html, pw):
    p = json.loads(MARK.search(locked_html).group(1))
    key = _key(pw, base64.b64decode(p["salt"]), p["it"])
    try:
        return AESGCM(key).decrypt(base64.b64decode(p["iv"]), base64.b64decode(p["ct"]), None).decode("utf-8")
    except Exception:
        sys.exit("비밀번호가 맞지 않습니다.")


def password(confirm=False, prompt="페이지 비밀번호: "):
    pw = os.environ.get("PAGE_PASSWORD")
    if pw:
        return pw
    conf = os.environ.get("GATE_CONF")  # Dashboard 게이트 설정 파일(gate_conf.json) 경로
    if conf and not confirm:
        return json.load(open(conf, encoding="utf-8"))["password"]
    pw = getpass.getpass(prompt)
    if confirm and getpass.getpass("한 번 더: ") != pw:
        sys.exit("두 비밀번호가 다릅니다.")
    if not pw:
        sys.exit("비밀번호가 비어 있습니다.")
    return pw


def main(argv):
    if len(argv) < 1 or argv[0] not in ("encrypt", "decrypt", "repass"):
        sys.exit(__doc__)
    cmd = argv[0]
    if cmd == "decrypt":
        out = Path(argv[1] if len(argv) > 1 else "page.plain.html")
        out.write_text(decrypt(INDEX.read_text(encoding="utf-8"), password()), encoding="utf-8")
        print(f"평문 저장: {out}  (커밋 금지, 작업 후 삭제 권장)")
    elif cmd == "encrypt":
        src = Path(argv[1] if len(argv) > 1 else "page.plain.html")
        html = src.read_text(encoding="utf-8")
        if is_locked(html):
            sys.exit("이미 암호화된 파일입니다.")
        INDEX.write_text(encrypt(html, password(confirm=True)), encoding="utf-8")
        print("index.html 암호화 완료")
    else:
        plain = decrypt(INDEX.read_text(encoding="utf-8"), password(prompt="현재 비밀번호: "))
        os.environ.pop("PAGE_PASSWORD", None)
        INDEX.write_text(encrypt(plain, password(confirm=True, prompt="새 비밀번호: ")), encoding="utf-8")
        print("비밀번호 변경 완료")


if __name__ == "__main__":
    main(sys.argv[1:])
