# -*- coding: utf-8 -*-
"""잔여석 증가 감지 로직 검증 (네트워크·파일 불필요)."""
import os
import sys
import tempfile

from seat_state import rising, load, save


def check(name, cond):
    print(("  OK   " if cond else "  FAIL ") + name)
    return cond


def main():
    ok = True

    # 처음 관측한 회차는 기준선만 잡고 알리지 않는다.
    # (안 그러면 50석 남은 상태로 켜는 순간 알림이 터진다 — 이번에 실제로 겪은 문제)
    ok &= check("이전 기록이 없으면 알리지 않는다", rising({}, {"1430": 50}) == [])

    # 변화 없음 / 감소는 취소표가 아니다
    ok &= check("같으면 알리지 않는다", rising({"1430": 50}, {"1430": 50}) == [])
    ok &= check("줄어들면 알리지 않는다 (누가 예매한 것)",
                rising({"1430": 50}, {"1430": 47}) == [])

    # 늘어난 것 = 누가 취소한 것 → 이것만 알린다
    ok &= check("늘어나면 (이전, 이후)를 돌려준다",
                rising({"1430": 50}, {"1430": 52}) == [("1430", 50, 52)])

    # 0석에서 풀린 경우도 당연히 증가
    ok &= check("매진에서 1석 풀리면 알린다",
                rising({"1800": 0}, {"1800": 1}) == [("1800", 0, 1)])

    # 여러 회차 동시 처리 — 증가한 것만
    out = rising({"1430": 50, "1800": 10}, {"1430": 51, "1800": 9})
    ok &= check("증가한 회차만 골라낸다", out == [("1430", 50, 51)])

    # 새로 등장한 회차는 기준선만
    ok &= check("새 회차는 기준선만 잡는다",
                rising({"1430": 50}, {"1430": 50, "2100": 3}) == [])

    # 저장/복원 왕복
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sub", "seats.json")
        ok &= check("기록이 없으면 빈 dict", load(p) == {})
        save(p, {"1430": 50})
        ok &= check("저장 후 그대로 읽힌다", load(p) == {"1430": 50})
        ok &= check("하위 디렉터리를 만든다", os.path.exists(p))

    # 깨진 파일이어도 죽지 않는다 (감시기가 멈추면 안 된다)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "seats.json")
        open(p, "w").write("{깨진 json")
        ok &= check("깨진 기록은 빈 dict로 취급", load(p) == {})

    print("\n결과:", "전부 통과" if ok else "실패 있음")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
