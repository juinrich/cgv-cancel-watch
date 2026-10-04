# -*- coding: utf-8 -*-
"""잔여석 기록과 '증가' 감지.

왜 증가만 보는가:
  잔여석이 0이 아니어도(예: 624석 중 50석 남음) 그 자체는 뉴스가 아니다.
  의미 있는 신호는 **잔여석이 늘어난 순간** — 누군가 취소했다는 뜻이다.
  'free >= 1 이면 알림' 으로는 50석 남은 회차에서 쿨다운마다 영원히 울린다.

왜 파일에 남기는가:
  GitHub Actions 실행은 15분짜리 토막으로 끊긴다. 기록을 남기지 않으면
  매 실행의 첫 조회가 기준선이 되어, 실행 사이에 생긴 취소표를 놓친다.
"""

import json
import os
from datetime import datetime


def load(path):
    """기록을 읽는다. 없거나 깨졌으면 빈 dict — 감시기를 멈추지 않는다."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def save(path, state):
    """기록을 쓴다. 상위 디렉터리가 없으면 만든다."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)          # 중간에 끊겨도 반쪽 파일이 남지 않는다


def rising(prev, cur):
    """[(회차, 이전잔여, 현재잔여)] — 잔여석이 늘어난 회차만.

    prev 에 없는 회차(처음 보는 회차)는 기준선만 잡고 알리지 않는다.
    """
    out = []
    for key in sorted(cur):
        before = prev.get(key)
        if before is None:
            continue
        after = cur[key]
        if after > before:
            out.append((key, before, after))
    return out


def expired(stop_after, now):
    """감시 종료 시각이 지났으면 True.

    watch.py 는 원래 시작 시점에만 stop_after 를 확인했다. Actions 처럼
    15분 토막으로 끊길 때는 그걸로 충분했지만, 로컬에서 상시 실행하면
    종료 시각이 지나도 계속 돌기 때문에 루프 안에서도 확인해야 한다.

    값이 없거나 형식이 깨졌으면 False — 감시를 멋대로 멈추지 않는다.
    (멈춰야 할 때 안 멈추는 쪽이, 돌아야 할 때 멈추는 쪽보다 낫다.)
    """
    if not stop_after:
        return False
    try:
        limit = datetime.fromisoformat(str(stop_after))
    except (TypeError, ValueError):
        return False
    return now > limit
