# -*- coding: utf-8 -*-
"""무엇이 403→200을 뒤집는가. 단계마다 status와 쿠키를 찍는다."""
from playwright.sync_api import sync_playwright

HOME = "https://cgv.co.kr/"
MOVIE = "https://cgv.co.kr/cnm/movieBook/movie"
CINEMA = ("https://cgv.co.kr/cnm/movieBook/cinema"
          "?siteNo=0013&siteNm=%EC%9A%A9%EC%82%B0%EC%95%84%EC%9D%B4%ED%8C%8C%ED%81%AC%EB%AA%B0"
          "&scnYmd=20261006")
API = ("/api/v1/booking/searchSchByMov"
       "?coCd=A420&siteNo=0013&scnYmd=20261006&movNo=30001323&rtctlScopCd=08")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
FETCH = """async p => { try {
  const r = await fetch(p, {headers:{'Accept':'application/json'}});
  const t = await r.text(); let j=null; try{j=JSON.parse(t)}catch(e){}
  return r.status + (j&&j.data ? ' rows='+j.data.length : ' head='+t.slice(0,60));
} catch(e){ return 'jsError '+e } }"""


def cookies(ctx):
    cs = ctx.cookies()
    names = sorted({c["name"] for c in cs})
    cf = [n for n in names if n.startswith("cf") or "clearance" in n.lower()]
    return f"쿠키 {len(cs)}개 cf계열={cf or '없음'}"


def nav(page, ctx, label, url):
    try:
        r = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        st = r.status if r else None
    except Exception as e:
        st = f"예외 {type(e).__name__}"
    print(f"  {label:<34} → {st!s:<16} {cookies(ctx)}", flush=True)
    return st


with sync_playwright() as p:
    br = p.chromium.launch(headless=True,
                           args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])

    print("[실험1] 문서요청만 반복 — 같은 URL 4연타")
    ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()
    for i in range(4):
        nav(page, ctx, f"goto /movie ({i+1}회)", MOVIE)
        page.wait_for_timeout(2000)
    ctx.close()

    print("\n[실험2] 403 페이지에서 API fetch를 먼저 → 그 뒤 문서요청")
    ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()
    nav(page, ctx, "goto / (홈)", HOME)
    print(f"  {'API fetch (403페이지 안에서)':<34} → {page.evaluate(FETCH, API)!s:<16} {cookies(ctx)}", flush=True)
    nav(page, ctx, "goto /movie", MOVIE)
    nav(page, ctx, "goto /cinema", CINEMA)
    ctx.close()

    print("\n[실험3] 문서요청 없이 API fetch만 쓸 수 있는가 (about:blank 기반)")
    ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()
    nav(page, ctx, "goto / (홈)", HOME)
    for i in range(3):
        print(f"  {f'API fetch ({i+1}회)':<34} → {page.evaluate(FETCH, API)!s:<16} {cookies(ctx)}", flush=True)
        page.wait_for_timeout(3000)
    ctx.close()

    print("\n[실험4] 홈 403 뒤 대기만 하고 재시도 (시간이 변수인가)")
    ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()
    nav(page, ctx, "goto /movie", MOVIE)
    page.wait_for_timeout(15000)
    nav(page, ctx, "15초 대기 후 goto /movie", MOVIE)
    ctx.close()

    br.close()
