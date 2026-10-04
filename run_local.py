#!/usr/bin/env python3
"""이 PC에서 상시 실행하는 런처.

왜 필요한가:
  GitHub Actions 의 cron 은 best-effort 라서 */15 같은 짧은 주기는 부하 시
  그냥 건너뛴다. 실제로 2026-10-04 에 schedule 이벤트가 28분간 한 번도
  발화하지 않았다(전부 수동 실행이었음). 10/6 당일을 그 스케줄러에
  맡기기엔 불안하므로, 집 IP 에서 끊기지 않고 돌린다.
  집 IP 는 Cloudflare 예열(403)도 겪지 않는다 — 첫 요청부터 200.

알림 채널:
  비밀값을 이 레포로 복사하지 않는다. 이미 검증된 cgv-open-watcher 의
  config.yaml 에서 런타임에 읽어 환경변수로만 넘긴다.
  (--notify-config 로 경로 변경 가능)
"""

import argparse
import io
import os
import sys

DEFAULT_NOTIFY_CONFIG = os.path.join(
    os.path.expanduser("~"), "Downloads", "cgv-open-watcher", "config.yaml")


def load_telegram(path):
    """config.yaml 에서 텔레그램 토큰/chat_id 를 읽는다. 실패하면 (None, None)."""
    try:
        import yaml
    except ImportError:
        print("!! pyyaml 이 없다. 알림 설정을 읽을 수 없다.")
        return None, None
    try:
        with io.open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except OSError as e:
        print(f"!! 알림 설정을 못 읽었다: {e}")
        return None, None
    tg = cfg.get("telegram") or {}
    token = tg.get("token")
    chat = tg.get("chat_id")
    if chat is not None:
        # config.yaml 에 따옴표가 섞여 들어간 값이 있어 정리한다
        chat = str(chat).strip().strip("'\"")
    return (token or None), (chat or None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--notify-config", default=DEFAULT_NOTIFY_CONFIG,
                    help="텔레그램 설정이 든 config.yaml 경로")
    ap.add_argument("--poll", type=int, default=60, help="조회 주기(초). 하한 60")
    ap.add_argument("--hours", type=float, default=72,
                    help="최대 실행 시간. config 의 stop_after 가 먼저 오면 그때 끝난다")
    args = ap.parse_args()

    token, chat = load_telegram(args.notify_config)
    if token and chat:
        os.environ["TELEGRAM_TOKEN"] = token
        os.environ["TELEGRAM_CHAT_ID"] = chat
        print(f"알림 채널: 텔레그램 (설정 출처 {args.notify_config})")
    else:
        print("!! 텔레그램 설정을 못 찾았다 — 알림 없이 로그만 남긴다")

    # ntfy 도 쓰고 싶으면 환경변수로 넘기면 된다 (watch.py 가 둘 다 지원)
    if os.environ.get("NTFY_TOPIC"):
        print("알림 채널: ntfy 도 함께 사용")

    os.environ["POLL_SECONDS"] = str(max(args.poll, 60))
    os.environ["LOOP_MINUTES"] = str(int(args.hours * 60))

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import watch
    return watch.main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n사용자 중단")
        sys.exit(0)
