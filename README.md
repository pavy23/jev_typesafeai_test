# TypeSafe AI (jev) 시범 사용 프로젝트

[TypeSafe AI](https://typesafe.ai)의 **System One API**를 시험해 보기 위한 최소 구성입니다.
System One은 LLM처럼 자유 텍스트를 생성하는 대신, 입력(**state**)에 대해 **타입이 정해진 질문**을 던지고
**확률이 붙은 타입 답변**을 돌려주는 판단(decision) API입니다.

| 질문 타입 | 입력 | 출력 |
|---|---|---|
| `noul` | 예/아니오 질문 (+ 선택적으로 true/false 설명) | `noul`: 0~1 확률 |
| `choice` | 라벨 집합 `criteria: {label: 설명 \| null}` | `choice`, `confidence`, 라벨별 `probabilities` |
| `score` | 순서가 있는 루브릭 `criteria: [0점 설명, 1점 설명, …]` | 기대값 `score`(정수 사이 가능), `confidence`, `legend`, `probabilities` |

## 빠른 시작

```bash
uv venv .venv && uv pip install --python .venv/bin/python -e . --group dev   # 또는 pip install typesafe-sdk python-dotenv pytest
cp .env.example .env            # TYPESAFE_API_KEY 를 채움 (.env 는 gitignore 됨)

.venv/bin/python trial/systemone_demo.py --dry-run   # 전송될 JSON 만 출력 (네트워크 없음)
.venv/bin/python trial/systemone_demo.py --models    # 키로 사용 가능한 모델 목록
.venv/bin/python trial/systemone_demo.py             # 실제 호출
.venv/bin/python -m pytest                           # 로컬 mock 서버로 오프라인 검증
```

SDK 없이 확인하려면 `trial/raw_http.sh` (curl) 를 사용하세요.

## Claude Code 플러그인 / 스킬

공식 TypeSafe 에이전트 스킬(`typesafe@typesafe-ai`, [typesafe-ai/skills](https://github.com/typesafe-ai/skills))을 두 가지 방식으로 연결해 두었습니다.

- `.claude/settings.json` — 프로젝트 범위 플러그인 선언(`extraKnownMarketplaces` + `enabledPlugins`). 로컬에서는 `claude plugin install typesafe@typesafe-ai` 후 `/typesafe:typesafe-ai` 로 호출
- `.claude/skills/typesafe-ai/` — 같은 SKILL.md 의 고정 사본(v0.5.7, MIT). 클라우드/새 세션에서도 `/typesafe-ai` 로 바로 사용 가능

## 브라우저에서 바로 써보기 — GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/pavy23/jev_typesafeai_test?quickstart=1&ref=claude/typesafeai-trial-vt2wg9)

설치 없이 GitHub 안에서 실행하는 방법입니다. 포트는 기본이 **Private**(Codespace 소유자만 접근)이라 저장소가 비공개면 완전히 비공개인 웹입니다.

1. **키 등록(1회)**: GitHub → Settings → Codespaces → Secrets → *New secret* → 이름 `TYPESAFE_API_KEY`, 이 저장소에 접근 허용.
   (배지로 만들 때 "recommended secrets" 입력칸이 뜨면 거기 넣어도 됩니다.)
2. 위 배지를 클릭 → Codespace 생성. `.devcontainer/`가 의존성 설치 후 플레이그라운드를 8000 포트에 자동으로 띄우고 브라우저 탭을 엽니다.
3. 키가 없으면 MOCK 모드(무작위 답)로 뜨고 화면 상단에 안내가 나옵니다. 키를 넣은 뒤 Codespace를 Rebuild 하면 LIVE 로 바뀝니다.

탭을 닫아도 Codespace는 살아 있고(유휴 30분 후 자동 정지), 다시 열면 `postStartCommand`가 서버를 재시작합니다.
무료 계정은 월 120 core-hours 까지 무료입니다 — 안 쓸 때는 Stop 해두세요.

## 로컬에서 실행


```bash
cp .env.example .env                 # 키 입력
.venv/bin/python webapp/app.py       # → http://127.0.0.1:8000
.venv/bin/python webapp/app.py --mock   # 키 없이 UI 만 둘러보기 (무작위 답)
```

브라우저에서 state 를 넣고 질문 JSON 을 고쳐 가며 실행하면 질문별로 확률 막대가 그려집니다.
예제 3개(선주 코멘트 / 지원 티켓 / ECR)가 내장돼 있고, `+ noul / + choice / + score` 버튼으로 질문 템플릿을 추가할 수 있습니다.
API 키는 서버(`webapp/app.py`)에만 있고 브라우저로는 가지 않습니다.

## 샘플 애플리케이션

- [`samples/comment_triage/`](samples/comment_triage/README.md) — 선주 코멘트를 기술회신 / VO / 사람검토 트랙으로 라우팅. 코멘트당 1요청·5질문, 비동기 배치, 코드 측 정책 계층, CSV/MD 리포트. `--fixture` 로 오프라인 실행 가능.

## 파일

- `trial/systemone_demo.py` — 조선소 설계변경요청(ECR)을 state 로 넣고 세 가지 타입 질문을 한 번에 묻는 예제
- `trial/raw_http.sh` — 동일 요청의 순수 HTTP(curl) 버전
- `tests/test_mock_systemone.py` — `/v1/systemone` 로컬 mock 으로 요청 스키마·응답 파싱을 검증
- `.env.example` — 환경변수 템플릿. **실제 키는 절대 커밋하지 않습니다.**
- `.devcontainer/` — Codespaces 설정: Python 3.11 이미지, 의존성 설치, 8000 포트 자동 포워딩, 추천 secret `TYPESAFE_API_KEY`
- `webapp/` — FastAPI 백엔드 + 단일 HTML 플레이그라운드

## 검증된 API 계약 (출처)

아래 내용은 공식 Python SDK 소스([typesafe-ai/typesafe-sdk-python](https://github.com/typesafe-ai/typesafe-sdk-python), v0.6.0)에서 직접 확인했습니다.
SDK 의 wire 스키마(`_schemas/models.py`)는 `https://api.typesafe.ai/openapi.json` 에서 자동 생성된 것입니다.

- 엔드포인트: `POST https://api.typesafe.ai/v1/systemone`, `GET https://api.typesafe.ai/v1/models`
- 인증: `Authorization: Bearer <TYPESAFE_API_KEY>`
- 요청 본문: `{"state": str|object|array, "model": "jev-latest", "questions": {이름: {"type": "noul"|"choice"|"score", ...}}}`
- 응답 본문: `{"model": str, "answers": {이름: {"type": ..., ...}}, "usage": {"input_tokens", "output_tokens"}}`
- 환경변수: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`(기본 `https://api.typesafe.ai`), `TYPESAFE_DEFAULT_MODEL`(기본 `jev-latest`)
- SDK 기본값: timeout 10 s, 재시도 2회(408/429/5xx, `Retry-After` 존중)
- 공식 문서: https://docs.typesafe.ai/api , https://docs.typesafe.ai/sdk/python/

> 참고: 이 저장소를 만든 Claude Code 원격 세션의 네트워크 정책은 `*.typesafe.ai` 로의 접속을 차단하고 있어
> (`CONNECT ... 403`), 실제 API 호출은 로컬 환경에서 수행해야 합니다. 요청 스키마와 응답 파싱은 mock 테스트로 검증했습니다.
