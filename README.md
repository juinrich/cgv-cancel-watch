# CGV 취소표 감시기

지정한 **지점 · 날짜 · 영화 · 회차**의 잔여 좌석이 1석 이상 생기면 푸시 알림을 보낸다.
GitHub Actions에서 돌기 때문에 내 PC를 켜둘 필요가 없다.

조회 전용이다. 좌석 선택·결제는 하지 않는다. 알림을 받고 **사람이 직접 예매**한다.

## 동작 방식

CGV는 Cloudflare 봇 차단이 걸려 있어 평범한 HTTP 요청은 403이 떨어진다.
그래서 Playwright로 Chromium을 띄우고, **페이지 컨텍스트 안에서** 내부 API를 `fetch` 한다.

```
/api/v1/booking/searchSchByMov?coCd=A420&siteNo=..&scnYmd=..&movNo=..&rtctlScopCd=08
```

Actions cron은 최소 5분 주기에 지연도 잦다. 그래서 **15분마다 깨우고, 한 실행이
내부에서 60초 주기로 14분간 도는** 구조로 사실상 상시 감시에 가깝게 만들었다.
`concurrency.cancel-in-progress: true` 라서 앞선 실행이 멈춰 있어도 새 실행이 넘겨받는다.

| 파일 | 역할 |
|---|---|
| `watch.py` | 감시 본체. 60초 주기 폴링 → 빈자리 발견 시 알림 |
| `resolve_movno.py` | 영화 제목 → `movNo` 탐색기 (최초 1회 실행) |
| `config.json` | 감시 대상 설정 |
| `.github/workflows/watch.yml` | 15분마다 자동 감시 |
| `.github/workflows/resolve.yml` | `movNo 찾기` 수동 실행 버튼 |

## 세팅 순서

### 1. 레포는 반드시 **public** 으로

15분마다 14분씩 돌면 **월 약 40,000분**을 쓴다. private 레포는 Free 2,000분 /
Pro 3,000분이라 이틀이면 바닥난다. public 레포는 Actions가 무료 무제한이다.
설정 파일에 민감정보는 없고 토큰은 전부 Secrets로 가니 public이어도 안전하다.

### 2. Secrets 등록

`Settings → Secrets and variables → Actions → New repository secret`

둘 중 **하나만** 넣어도 되고, 둘 다 넣으면 양쪽으로 다 온다.

| 이름 | 설명 |
|---|---|
| `NTFY_TOPIC` | [ntfy.sh](https://ntfy.sh) 토픽명. 앱 설치 후 같은 토픽 구독. 가입 불필요 |
| `TELEGRAM_TOKEN` | @BotFather로 만든 봇 토큰 |
| `TELEGRAM_CHAT_ID` | 내 chat id (@userinfobot에게 말 걸면 알려준다) |

> ntfy 토픽명은 아는 사람이면 누구나 구독할 수 있다. `cgv-a7f3k9x2` 처럼
> 추측하기 어렵게 지을 것.

### 3. `movNo` 채우기

`config.json`의 `movNo`가 비어 있으면 감시기는 아무것도 하지 않고 바로 종료한다.

`Actions → movNo 찾기 → Run workflow` 에 영화 제목을 입력하고 실행하면,
로그와 푸시 알림으로 `movNo` 목록이 온다. 그 숫자를 `config.json`에 넣고 커밋.

### 4. `config.json` 설정

```json
{
  "label": "오디세이 · 용산 IMAX",
  "siteNo": "0013",
  "siteNm": "CGV 용산아이파크몰",
  "movNo": "",
  "movNm": "오디세이",
  "scnYmd": "20261006",
  "screen_match": "IMAX",
  "target_times": ["1430", "1800"],
  "alert_cooldown_sec": 600,
  "stop_after": "2026-10-06T18:30:00+09:00"
}
```

| 키 | 의미 |
|---|---|
| `siteNo` | 지점 코드 (용산아이파크몰 `0013`) |
| `scnYmd` | 상영일 `YYYYMMDD` |
| `screen_match` | 상영관 이름 부분 일치. 비우면 전체 |
| `target_times` | 관심 회차 시작시각 `HHMM`. 비우면 전체. 심야는 `2500`(=익일 01:00) |
| `alert_cooldown_sec` | 같은 회차 재알림 최소 간격. 알림 폭탄 방지 |
| `stop_after` | 이 시각 넘으면 아무것도 안 하고 종료 (KST ISO8601) |

### 5. 끝나면 워크플로를 끈다

`stop_after`가 지나도 **워크플로 자체는 계속 15분마다 깨어난다.**
영화를 보고 나면 `Actions → CGV 취소표 감시 → ⋯ → Disable workflow`.

## 한계 — 솔직하게

- **초 단위 경쟁에서는 진다.** 인기 IMAX 취소표는 수초 안에 사라진다.
  60초 폴링 + Actions 지연으로는 놓치는 게 정상이다. 이 감시기는
  "운 좋으면 잡는 보조 장치"다. 확실히 잡으려면 로컬 상시 실행이 본선이다.
- Actions cron은 러너가 붐비면 **5~20분 밀린다.** 15분 간격이 지켜지지 않는 구간이 생긴다.
- CGV가 API 경로나 응답 스키마를 바꾸면 조용히 0건이 된다. 그래서 3회 연속
  조회 실패 시 경고 알림을 보낸다. "대상 회차 미발견" 로그가 계속 뜨면
  `movNo`/날짜/`screen_match` 조건을 다시 확인할 것.

## 지켜야 할 선

| 단계 | 허용 |
|---|---|
| 상영시간표 조회 · 모니터링 | ✅ 공개 정보 읽기 |
| 알림 발송 | ✅ |
| 좌석 선택 자동화 | ❌ 좌석 클릭 = 좌석 점유. 결제를 안 해도 면책되지 않는다 |
| 결제 자동화 | ❌ 매크로 |

폴링 주기는 코드에 **60초 하한이 강제**되어 있다(`POLL_SECONDS`). 낮추지 말 것.
로그인·세션 쿠키는 사용하지 않는다. 비로그인 공개 페이지만 조회한다.

## 로컬에서 테스트

```bash
pip install -r requirements.txt
playwright install chromium

# 1회성 짧은 테스트 (3분만 돌림)
LOOP_MINUTES=3 POLL_SECONDS=60 NTFY_TOPIC=내토픽 python watch.py

# movNo 탐색
MOVIE_NAME=오디세이 python resolve_movno.py
```

## 관련 프로젝트

`cgv-open-watcher` — 신규 회차가 **오픈되는 순간**을 감지하는 별도 감시기.
이쪽은 "아직 안 열린 회차"를, 이 레포는 "열렸지만 매진된 회차의 취소표"를 본다.
목적이 달라 레포를 분리했다.
