#!/usr/bin/env python3
"""
CGV 취소표 감시기 (GitHub Actions용)

지정한 날짜·지점·영화의 특정 회차에 빈자리가 생기면 푸시 알림.
CGV는 Cloudflare 봇 차단이 걸려 있어 일반 HTTP 요청은 403이 떨어진다.
그래서 Playwright로 Chromium을 띄우고 페이지 컨텍스트 안에서
내부 API(/api/v1/booking/searchSchByMov)를 fetch 한다.

조회 전용. 좌석 선택·결제는 하지 않는다.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, Error as PWError

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")
KST = ZoneInfo("Asia/Seoul")

HOME = "https://cgv.co.kr/"
BOOK_URL = "https://cgv.co.kr/cnm/movieBook/movie"
API_PATH = (
    "/api/v1/booking/searchSchByMov"
    "?coCd=A420&siteNo={site}&scnYmd={ymd}&movNo={mov}&rtctlScopCd=08"
)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

LOOP_MINUTES = int(os.environ.get("LOOP_MINUTES", "14"))
POLL_SECONDS = max(int(os.environ.get("POLL_SECONDS", "60")), 60)  # 하한 강제


def log(msg: str) -> None:
    stamp = datetime.now(KST).strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", flush=True)


def hhmm(t: str) -> str:
    """CGV는 '1430', 심야는 '2500'(=익일 01:00) 형태로 준다."""
    if not t:
        return "??:??"
    t = t.zfill(4)
    h, m = int(t[:2]), t[2:]
    return f"{h - 24:02d}:{m}(익일)" if h >= 24 else f"{h:02d}:{m}"


# ─────────────────────────────────────────────
# 알림 — ntfy / 텔레그램 중 설정된 쪽으로
# ─────────────────────────────────────────────
def push(title: str, body: str, click: str = BOOK_URL) -> None:
    sent = False

    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
        req = urllib.request.Request(
            f"{server}/{topic}",
            data=body.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "5",
                "Tags": "ticket",
                "Click": click,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                sent = True
        except (urllib.error.URLError, OSError) as e:
            log(f"!! ntfy 실패: {e}")

    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        payload = json.dumps({
            "chat_id": chat_id,
            "text": f"<b>{title}</b>\n\n{body}\n\n<a href=\"{click}\">예매 페이지 열기</a>",
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15):
                sent = True
        except (urllib.error.URLError, OSError) as e:
            log(f"!! 텔레그램 실패: {e}")

    if not sent:
        log(f"[알림채널 없음] {title} | {body}")


# ─────────────────────────────────────────────
# 조회
# ─────────────────────────────────────────────
def fetch(page, site: str, mov: str, ymd: str) -> dict:
    return page.evaluate(
        """async ({site, mov, ymd, path}) => {
            const url = path.replace('{site}', site)
                            .replace('{ymd}', ymd)
                            .replace('{mov}', mov);
            try {
                const res = await fetch(url, {headers: {'Accept': 'application/json'}});
                if (!res.ok) return {error: 'HTTP ' + res.status};
                const j = await res.json();
                if (j.statusCode !== 0)
                    return {error: j.statusMessage || ('statusCode ' + j.statusCode)};
                return {rows: (j.data || []).map(s => ({
                    scnsNo: s.scnsNo,
                    scnsNm: s.scnsNm,
                    expoScnsNm: s.expoScnsNm,
                    fmt: s.movkndDsplNm,
                    start: s.scnsrtTm,
                    free: parseInt(s.frSeatCnt, 10),
                    total: parseInt(s.stcnt, 10),
                    movNm: s.movNm,
                    siteNm: s.siteNm,
                }))};
            } catch (e) {
                return {error: String(e)};
            }
        }""",
        {"site": site, "mov": mov, "ymd": ymd, "path": API_PATH},
    )


def pick_targets(rows: list, cfg: dict) -> dict:
    """{시작시각: row} — 관심 회차만 골라낸다."""
    match = (cfg.get("screen_match") or "").upper()
    wanted = set(cfg.get("target_times") or [])
    out = {}

    for s in rows:
        hay = " ".join([
            s.get("scnsNm") or "",
            s.get("expoScnsNm") or "",
            s.get("fmt") or "",
        ]).upper()
        if match and match not in hay:
            continue

        start = (s.get("start") or "").zfill(4)
        if wanted and start not in wanted:
            continue

        out[start] = s

    return out


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
def main() -> int:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log(f"!! config.json 읽기 실패: {e}")
        return 2

    if not cfg.get("movNo"):
        log("!! config.json 의 movNo 가 비어 있다. README 참고해서 채울 것.")
        return 2

    stop_at = cfg.get("stop_after")
    if stop_at:
        try:
            if datetime.now(KST) > datetime.fromisoformat(stop_at):
                log("감시 종료 시각이 지났다. 아무것도 하지 않는다.")
                return 0
        except ValueError:
            log("!! stop_after 형식이 잘못됨 — 무시하고 진행")

    site = cfg["siteNo"]
    mov = cfg["movNo"]
    ymd = cfg["scnYmd"]
    cooldown = int(cfg.get("alert_cooldown_sec", 600))

    last_alert: dict[str, float] = {}
    deadline = time.time() + LOOP_MINUTES * 60
    fails = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA,
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1440, "height": 900},
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = ctx.new_page()

        try:
            # 콜드 세션 첫 요청 403을 재시도로 흡수한다 (cgv_net 참고)
            goto_ok(page, HOME, log=log)
            head = page.evaluate(
                "document.body ? document.body.innerText.slice(0,200) : ''"
            )
            if "비정상적으로" in head or "이용이 제한" in head:
                raise RuntimeError("Cloudflare 차단 페이지에 걸림")
        except (PWError, NavBlocked, RuntimeError) as e:
            log(f"!! 초기 접속 실패: {e}")
            push("⚠️ CGV 감시기 접속 실패", str(e))
            return 1

        log(f"감시 시작 — {cfg.get('label')} / {ymd} / "
            f"{cfg.get('target_times')} / {POLL_SECONDS}초 주기 / {LOOP_MINUTES}분간")

        while time.time() < deadline:
            res = fetch(page, site, mov, ymd)

            if "error" in res:
                fails += 1
                log(f"조회 실패({fails}): {res['error']}")
                if fails == 3:
                    push("⚠️ CGV 감시기 조회 실패",
                         f"3회 연속 실패\n{res['error']}\nAPI가 바뀌었을 수 있음")
            else:
                fails = 0
                targets = pick_targets(res.get("rows", []), cfg)

                if not targets:
                    log("대상 회차 미발견 — movNo/날짜/시간/IMAX 조건 확인 필요")
                else:
                    now = time.time()
                    for start, s in sorted(targets.items()):
                        free, total = s["free"], s["total"]
                        log(f"{hhmm(start)}  잔여 {free}/{total}석")

                        if free < 1:
                            continue
                        if now - last_alert.get(start, 0) < cooldown:
                            continue

                        last_alert[start] = now
                        d = ymd
                        push(
                            f"🎟 취소표 {free}석 — {s.get('movNm') or cfg.get('movNm')}",
                            f"{s.get('siteNm') or cfg.get('siteNm')} "
                            f"{s.get('expoScnsNm') or s.get('scnsNm')}\n"
                            f"{d[:4]}-{d[4:6]}-{d[6:]} {hhmm(start)}\n"
                            f"잔여 {free}/{total}석",
                        )
                        log(f">>> 알림 발송: {hhmm(start)} {free}석")

            remain = deadline - time.time()
            if remain <= 0:
                break
            time.sleep(min(POLL_SECONDS, remain))

        ctx.close()
        browser.close()

    log("이번 실행 종료 — 다음 스케줄이 이어받는다")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
