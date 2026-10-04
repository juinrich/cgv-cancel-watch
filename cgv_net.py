# -*- coding: utf-8 -*-
"""CGV 접속 공통 로직.

GitHub Actions IP에서 관측된 사실 (2026-10-04, 진단 2회로 확인):
  콜드 세션의 **첫 요청**은 경로와 무관하게 Cloudflare가 403으로 걷어찬다.
  그 403 페이지에서 Cloudflare 비콘(/cdn-cgi/rum)이 실행되며 세션이 풀리고,
  **두 번째 요청부터는 같은 URL도 200**으로 통과한다.
  (집 IP에서는 첫 요청부터 200이라 재현되지 않는다.)

따라서 진입 goto는 반드시 재시도해야 한다. 한 번만 호출하면
"차단당했다"고 오판하게 된다 — 실제로는 한 번 더 안 해본 것일 뿐이다.
"""


class NavBlocked(RuntimeError):
    """재시도를 모두 소진했는데도 진입에 실패했을 때."""


def goto_ok(page, url, tries=4, wait_until="domcontentloaded",
            timeout=45000, sleep_ms=2000, log=None):
    """200대/300대를 받을 때까지 goto를 재시도하고 최종 status를 돌려준다.

    실패 시 NavBlocked 를 던지며, 메시지에 **실제 관측값**(status/제목)을 담는다.
    추측성 원인("Cloudflare에 막혔거나...")을 쓰지 않는 것이 요점이다.
    """
    attempts = []

    for i in range(1, tries + 1):
        try:
            res = page.goto(url, wait_until=wait_until, timeout=timeout)
            status = res.status if res is not None else None
            if status is None or status < 400:
                if i > 1 and log:
                    log(f"진입 성공 ({i}번째 시도, HTTP {status})")
                return status
            attempts.append(f"{i}차 HTTP {status}")
            if log:
                log(f"진입 {i}/{tries} 실패: HTTP {status} — 콜드 세션 예열 후 재시도")
        except Exception as e:                      # 타임아웃 등
            attempts.append(f"{i}차 {type(e).__name__}")
            if log:
                log(f"진입 {i}/{tries} 실패: {type(e).__name__} — 재시도")

        if i < tries:
            page.wait_for_timeout(sleep_ms)

    detail = ""
    try:
        detail = f" | 마지막 페이지 제목={page.title()!r}"
    except Exception:
        pass

    raise NavBlocked(f"{url} 진입 실패 — " + ", ".join(attempts) + detail)
