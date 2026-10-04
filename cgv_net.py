# -*- coding: utf-8 -*-
"""CGV 접속 공통 로직.

GitHub Actions IP에서 실측한 사실 (2026-10-04, 진단 4회):

  · Cloudflare는 콜드 세션의 **초반 몇 요청**을 403으로 걷어낸다(예열 구간).
    구간 길이는 불규칙하다 — 0회로 끝나기도 하고 4회 이상 이어지기도 한다.
      문서요청 10연타 실측: 403, 403, 403, 200, 200, 200, 200, 200, 200, 200
  · 예열을 넘기면 안정적이다. 특히 페이지 안에서 쏘는 API fetch는
      searchSchByMov 20연타 실측: 20/20 성공 (실패 0)
  · cf_clearance 류 쿠키는 전 구간 한 번도 발급되지 않았다 — 챌린지가 아니다.
  · 집(가정용) IP에서는 재현되지 않는다. 첫 요청부터 200이다.

따라서:
  1) 진입 goto 는 넉넉히 재시도해야 한다. 4회·2초로는 부족했다(실패 확인).
  2) 진입이 끝내 안 되더라도 죽이면 안 된다. 호출부가 주기적으로 API 를
     재시도하는 구조라면 예열이 그 사이에 풀린다 → required=False 를 쓴다.
  3) 실패 메시지에는 추측을 쓰지 않는다. 관측한 status 를 그대로 남긴다.
"""

# 재시도 간격(ms). 뒤로 갈수록 길어진다 — 예열이 길면 시간이 필요하다.
BACKOFF_MS = (2000, 2500, 3000, 3500, 4000, 5000, 5000, 6000, 6000, 8000)


class NavBlocked(RuntimeError):
    """재시도를 모두 소진했는데도 진입에 실패했을 때 (required=True 인 경우)."""


def goto_ok(page, url, tries=8, wait_until="domcontentloaded",
            timeout=45000, log=None, required=True):
    """200/300대를 받을 때까지 goto 를 재시도하고 최종 status 를 돌려준다.

    required=True  → 끝까지 실패하면 NavBlocked
    required=False → 끝까지 실패해도 마지막 status 를 그대로 돌려준다
    """
    attempts = []
    last_status = None

    for i in range(1, tries + 1):
        try:
            res = page.goto(url, wait_until=wait_until, timeout=timeout)
            last_status = res.status if res is not None else None
            if last_status is None or last_status < 400:
                if i > 1 and log:
                    log(f"진입 성공 ({i}번째 시도, HTTP {last_status})")
                return last_status
            attempts.append(f"{i}차 {last_status}")
            if log:
                log(f"진입 {i}/{tries}: HTTP {last_status} — 예열 대기 후 재시도")
        except Exception as e:                      # 타임아웃 등
            last_status = f"{type(e).__name__}"
            attempts.append(f"{i}차 {last_status}")
            if log:
                log(f"진입 {i}/{tries}: {type(e).__name__} — 재시도")

        if i < tries:
            page.wait_for_timeout(BACKOFF_MS[min(i - 1, len(BACKOFF_MS) - 1)])

    detail = ""
    try:
        detail = f" | 마지막 페이지 제목={page.title()!r}"
    except Exception:
        pass
    msg = f"{url} 진입 실패 — " + ", ".join(attempts) + detail

    if required:
        raise NavBlocked(msg)
    if log:
        log(f"!! {msg}")
        log("   진입은 못 했지만 API 재시도로 복구될 수 있어 계속 진행한다")
    return last_status
