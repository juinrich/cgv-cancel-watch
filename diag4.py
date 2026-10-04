# -*- coding: utf-8 -*-
"""403 발생률 측정. 문서요청 10회 + API fetch 20회."""
from playwright.sync_api import sync_playwright
MOVIE = "https://cgv.co.kr/cnm/movieBook/movie"
API = ("/api/v1/booking/searchSchByMov"
       "?coCd=A420&siteNo=0013&scnYmd=20261006&movNo=30001323&rtctlScopCd=08")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
FETCH = """async p => { try {
  const r = await fetch(p, {headers:{'Accept':'application/json'}});
  if (!r.ok) return 'HTTP'+r.status;
  const j = await r.json();
  return j.statusCode===0 ? 'OK'+(j.data?j.data.length:0) : 'code'+j.statusCode;
} catch(e){ return 'ERR' } }"""

with sync_playwright() as p:
    br = p.chromium.launch(headless=True, args=["--no-sandbox"])
    ctx = br.new_context(user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul")
    page = ctx.new_page()

    doc = []
    for i in range(10):
        try:
            r = page.goto(MOVIE, wait_until="domcontentloaded", timeout=45000)
            doc.append(r.status if r else 0)
        except Exception:
            doc.append(-1)
        page.wait_for_timeout(1500)
    print("문서요청 10회:", doc)
    print(f"  → 403 {doc.count(403)}회 / 200 {doc.count(200)}회")

    api = []
    for i in range(20):
        api.append(page.evaluate(FETCH, API))
        page.wait_for_timeout(1500)
    print("API fetch 20회:", " ".join(api))
    bad = sum(1 for a in api if not a.startswith("OK"))
    print(f"  → 실패 {bad}회 / 성공 {20-bad}회  (실패율 {bad*5}%)")
    ctx.close(); br.close()
