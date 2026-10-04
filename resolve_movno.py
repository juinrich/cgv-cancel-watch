#!/usr/bin/env python3
"""
movNo 자동 탐색기

CGV 예매 페이지를 실제 브라우저로 열고, 페이지가 주고받는 모든 JSON 응답에서
{movNo, movNm} 쌍을 긁어모아 출력한다.
API 경로 이름을 몰라도 되고, 개발자도구도 필요 없다.

GitHub Actions의 'movNo 찾기' 워크플로를 수동 실행하면
로그와 푸시 알림으로 목록을 받아볼 수 있다.
"""

import json
import os
import re
import urllib.request
import urllib.error

from playwright.sync_api import sync_playwright

from cgv_net import goto_ok, NavBlocked

BOOK_URL = "https://cgv.co.kr/cnm/movieBook/movie"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 찾고 싶은 영화 (부분 일치, 공백·하이픈 무시). 비우면 전체 출력.
WANT = os.environ.get("MOVIE_NAME", "오디세이")


def norm(s: str) -> str:
    return re.sub(r"[\s\-·:]", "", s or "").lower()


def walk(obj, found: dict) -> None:
    """중첩 JSON 어디에 있든 movNo+movNm 쌍을 찾아낸다."""
    if isinstance(obj, dict):
        no = obj.get("movNo")
        nm = obj.get("movNm") or obj.get("movNmKor") or obj.get("movieNm")
        if no and nm:
            found[str(no)] = str(nm)
        for v in obj.values():
            walk(v, found)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, found)


def push(text: str) -> None:
    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"{server}/{topic}",
                    data=text.encode("utf-8"),
                    headers={"Title": "movNo 탐색 결과".encode("utf-8")},
                    method="POST",
                ),
                timeout=15,
            )
        except (urllib.error.URLError, OSError):
            pass

    token = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=json.dumps({"chat_id": chat, "text": text}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=15,
            )
        except (urllib.error.URLError, OSError):
            pass


def main() -> int:
    found: dict[str, str] = {}
    diag: dict = {"all": 0, "json": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul",
            viewport={"width": 1440, "height": 900},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = ctx.new_page()

        def on_response(res):
            diag["all"] += 1
            ct = (res.headers or {}).get("content-type", "")
            if "json" not in ct.lower():
                return
            diag["json"] += 1
            try:
                walk(res.json(), found)
            except Exception:
                pass

        page.on("response", on_response)

        # Cloudflare 예열 구간(초반 403)을 재시도로 흡수한다 (cgv_net 참고).
        # 진입에 성공해도 예열 중이면 하위 API 응답이 403이 섞여 0건이 될 수 있으므로,
        # 수집 결과가 비면 페이지를 다시 읽는다.
        for attempt in range(1, 4):
            goto_ok(page, BOOK_URL, wait_until="networkidle", timeout=60000,
                    log=lambda m: print(m, flush=True))
            page.wait_for_timeout(5000)   # 늦게 오는 응답까지 수집
            if found:
                break
            print(f"수집 0건 — 페이지 재읽기 {attempt}/3", flush=True)
            page.wait_for_timeout(4000)

        diag["title"] = page.title()
        diag["html"] = len(page.content())

        ctx.close()
        browser.close()

    if not found:
        # 추측하지 않는다 — 관측값만 적는다.
        msg = (f"movNo 0건. 페이지는 열렸으나(제목={diag.get('title')!r}, "
               f"HTML {diag.get('html')}바이트) JSON 응답 {diag.get('json')}건에 "
               f"movNo/movNm 쌍이 없었음. 응답 총 {diag.get('all')}건.")
        print(msg)
        push(msg)
        return 1

    lines = [f"{no}  {nm}" for no, nm in sorted(found.items(), key=lambda x: x[1])]
    print(f"\n발견한 영화 {len(found)}편\n" + "\n".join(lines))

    hits = [f"{no}  {nm}" for no, nm in found.items() if norm(WANT) in norm(nm)]
    if hits:
        out = f"'{WANT}' 검색 결과\n\n" + "\n".join(hits) + \
              "\n\n위 숫자를 config.json 의 movNo 에 넣으세요."
    else:
        out = f"'{WANT}' 와 일치하는 영화 없음\n\n전체 목록:\n" + "\n".join(lines[:30])

    print("\n" + "=" * 40 + "\n" + out)
    push(out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except NavBlocked as e:
        print(f"CGV 진입 실패: {e}")
        push(f"CGV 진입 실패: {e}")
        raise SystemExit(1)
