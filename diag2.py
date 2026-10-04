# -*- coding: utf-8 -*-
"""watch.py 의 실제 경로만 검증. 환경(로컬 vs Actions) 비교용."""
import json
from playwright.sync_api import sync_playwright

HOME = "https://cgv.co.kr/"
MOVIE = "https://cgv.co.kr/cnm/movieBook/movie"
API = ("/api/v1/booking/searchSchByMov"
       "?coCd=A420&siteNo=0013&scnYmd=20261006&movNo=30001323&rtctlScopCd=08")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

JS = """async (path) => {
  try {
    const res = await fetch(path, {headers: {'Accept': 'application/json'}});
    const txt = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(txt); } catch (e) {}
    return {ok: res.ok, status: res.status,
            statusCode: parsed ? parsed.statusCode : null,
            statusMessage: parsed ? parsed.statusMessage : null,
            rows: parsed && parsed.data ? parsed.data.length : null,
            head: txt.slice(0, 200)};
  } catch (e) { return {jsError: String(e)}; }
}"""

with sync_playwright() as p:
    br = p.chromium.launch(headless=True,
                           args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
    ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul",
                         viewport={"width": 1440, "height": 900})
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
    page = ctx.new_page()

    print("[1] watch.py 진입점: goto", HOME)
    try:
        nav = page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
        print(f"    status={nav.status if nav else None} title={page.title()!r} "
              f"html={len(page.content())}")
    except Exception as e:
        print(f"    예외 {type(e).__name__}: {e}")

    print("[2] watch.py 핵심: 페이지 안에서 좌석 API fetch (movNo=30001323)")
    for i in range(3):
        r = page.evaluate(JS, API)
        print(f"    시도{i+1}: " + json.dumps(r, ensure_ascii=False)[:400])
        page.wait_for_timeout(3000)

    print("[3] 대조군: /movieBook/movie 를 3회 연속 (403 일관성 확인)")
    for i in range(3):
        try:
            nav = page.goto(MOVIE, wait_until="domcontentloaded", timeout=45000)
            print(f"    시도{i+1}: status={nav.status if nav else None} title={page.title()!r}")
        except Exception as e:
            print(f"    시도{i+1}: 예외 {type(e).__name__}")
        page.wait_for_timeout(2000)

    ctx.close(); br.close()
