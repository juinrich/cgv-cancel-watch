# -*- coding: utf-8 -*-
"""진단 전용. 경계마다 증거를 찍는다. 아무것도 고치지 않는다."""
import json, re, sys, urllib.parse, urllib.request
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

URL_FAIL = "https://cgv.co.kr/cnm/movieBook/movie"
URL_WORK = "https://cgv.co.kr/cnm/movieBook/cinema?" + urllib.parse.urlencode(
    {"siteNo": "0013", "siteNm": "용산아이파크몰", "scnYmd": "20261006"})


def walk(obj, found):
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


print("=" * 70)
print("[경계 A] 브라우저 없이 순수 HTTP GET — IP 차단 여부")
print("=" * 70)
for u in (URL_FAIL, URL_WORK):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read(4000).decode("utf-8", "replace")
            title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S)
            print(f"  {u[:60]}...")
            print(f"    HTTP {r.status} | len={len(body)} | server={r.headers.get('server')} "
                  f"| cf-ray={r.headers.get('cf-ray')}")
            print(f"    title={(title.group(1).strip()[:60] if title else None)!r}")
    except Exception as e:
        print(f"  {u[:60]}... → {type(e).__name__}: {e}")

for label, url in (("실패한 URL (/movieBook/movie)", URL_FAIL),
                   ("작동하는 URL (/movieBook/cinema?쿼리)", URL_WORK)):
    print()
    print("=" * 70)
    print(f"[경계 B·C·D] Playwright — {label}")
    print("=" * 70)
    responses, found = [], {}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul",
                             viewport={"width": 1440, "height": 900})
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        def on_response(res):
            ct = (res.headers or {}).get("content-type", "")
            responses.append((res.status, ct.split(";")[0], res.url))
            if "json" not in ct.lower():
                return
            try:
                walk(res.json(), found)
            except Exception as e:
                responses.append((res.status, f"JSON파싱실패:{type(e).__name__}", res.url))

        page.on("response", on_response)
        try:
            nav = page.goto(url, wait_until="networkidle", timeout=45000)
            print(f"  goto status = {nav.status if nav else None}")
        except Exception as e:
            print(f"  goto 예외: {type(e).__name__}: {e}")
        page.wait_for_timeout(6000)

        print(f"  최종 URL   = {page.url}")
        print(f"  페이지 제목 = {page.title()!r}")
        html = page.content()
        print(f"  HTML 길이  = {len(html)}")
        cf = [m for m in ("Just a moment", "cf-chl", "challenge-platform",
                          "cf_chl_opt", "Attention Required") if m in html or m in page.title()]
        print(f"  Cloudflare 지문 = {cf or '없음'}")
        ctx.close(); br.close()

    print(f"  받은 응답 총 {len(responses)}건")
    js = [r for r in responses if "json" in r[1].lower()]
    print(f"  그중 JSON {len(js)}건:")
    for st, ct, u in js[:20]:
        print(f"    {st} {ct} {u[:110]}")
    if not js:
        print("    (없음) — 비-JSON 응답 상위 12건:")
        for st, ct, u in responses[:12]:
            print(f"    {st} {ct} {u[:110]}")
    print(f"  movNo 발견 = {len(found)}건")
    for no, nm in sorted(found.items(), key=lambda x: x[1])[:40]:
        print(f"    movNo={no}  {nm}")
