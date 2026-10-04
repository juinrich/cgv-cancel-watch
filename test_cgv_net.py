# -*- coding: utf-8 -*-
"""콜드 세션 403 재시도 로직 검증 (네트워크 불필요)."""
import sys
from cgv_net import goto_ok, NavBlocked


class FakeResponse:
    def __init__(self, status): self.status = status


class FakePage:
    """statuses 를 순서대로 돌려주는 가짜 page."""
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []
        self.slept = 0

    def goto(self, url, **kw):
        self.calls.append(url)
        s = self.statuses.pop(0)
        if isinstance(s, Exception):
            raise s
        return FakeResponse(s)

    def wait_for_timeout(self, ms):
        self.slept += ms


def check(name, cond):
    print(("  OK   " if cond else "  FAIL ") + name)
    return cond


def main():
    ok = True

    # 1. Actions에서 관측된 실제 패턴: 첫 요청 403, 두 번째 200
    p = FakePage([403, 200])
    ok &= check("403 → 200 이면 통과하고 200을 돌려준다",
                goto_ok(p, "https://cgv.co.kr/") == 200)
    ok &= check("그 경우 goto를 2번 호출한다", len(p.calls) == 2)
    ok &= check("재시도 사이에 대기한다", p.slept > 0)

    # 2. 처음부터 200이면 재시도하지 않는다 (로컬 환경)
    p = FakePage([200])
    ok &= check("처음부터 200이면 1번만 호출한다",
                goto_ok(p, "x") == 200 and len(p.calls) == 1)

    # 3. 계속 403이면 추측 메시지 대신 status를 담은 예외를 던진다
    p = FakePage([403, 403, 403, 403])
    try:
        goto_ok(p, "x", tries=4)
        ok &= check("전부 403이면 NavBlocked를 던진다", False)
    except NavBlocked as e:
        ok &= check("전부 403이면 NavBlocked를 던진다", True)
        ok &= check("예외 메시지에 실제 status 403이 들어있다", "403" in str(e))
    ok &= check("tries 횟수만큼만 시도한다", len(p.calls) == 4)

    # 4. 예외가 나도 남은 횟수만큼 재시도한다
    p = FakePage([RuntimeError("timeout"), 200])
    ok &= check("goto 예외 후에도 재시도해 통과한다", goto_ok(p, "x") == 200)

    # 5. Actions 실측 최악 패턴: 403이 길게 이어진 뒤 통과 (예열 구간)
    p = FakePage([403, 403, 403, 403, 403, 200])
    ok &= check("403 5연속 뒤 200도 버틴다 (기본 tries로)",
                goto_ok(p, "x") == 200)

    # 6. required=False 면 끝까지 막혀도 예외 없이 status를 돌려준다
    #    (watch.py 는 진입 실패해도 루프의 API fetch 재시도로 복구 가능하므로
    #     여기서 죽으면 안 된다 — 1차 수정이 watch.py 를 망가뜨린 지점)
    p = FakePage([403] * 10)
    try:
        r = goto_ok(p, "x", tries=10, required=False)
        ok &= check("required=False 면 예외 대신 403을 돌려준다", r == 403)
    except NavBlocked:
        ok &= check("required=False 면 예외 대신 403을 돌려준다", False)

    # 7. 재시도 간격이 점점 늘어난다 (고정 2초로는 예열을 못 버텀)
    p = FakePage([403, 403, 403, 200])
    goto_ok(p, "x")
    ok &= check("백오프가 누적 대기 6초를 넘는다", p.slept > 6000)

    print("\n결과:", "전부 통과" if ok else "실패 있음")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
