# TypeSafe AI (jev) 시범 사용 프로젝트

[TypeSafe AI](https://typesafe.ai)의 **System One API**를 로컬 PC에서 시험해 보기 위한 구성입니다.
System One은 LLM처럼 자유 텍스트를 생성하는 대신, 입력(**state**)에 대해 **타입이 정해진 질문**을 던지고
**확률이 붙은 타입 답변**을 돌려주는 판단(decision) API입니다.

| 질문 타입 | 입력 | 출력 |
|---|---|---|
| `noul` | 예/아니오 질문 (+ 선택적으로 true/false 설명) | `noul`: 0~1 확률 |
| `choice` | 라벨 집합 `criteria: {label: 설명 \| null}` | `choice`, `confidence`, 라벨별 `probabilities` |
| `score` | 순서가 있는 루브릭 `criteria: [0점 설명, 1점 설명, …]` | 기대값 `score`(정수 사이 가능), `confidence`, `legend`, `probabilities` |

## 시작하기 (로컬)

필요한 것: **Python 3.10 이상** ([python.org](https://www.python.org/downloads/), Windows 는 설치 시 *Add to PATH* 체크).

1. 저장소 받기 — `git clone https://github.com/pavy23/jev_typesafeai_test` 또는 GitHub 의 `<> Code → Download ZIP`
2. 실행 — **Windows: `run.bat` 더블클릭** / macOS·Linux: `./run.sh`
3. 첫 실행에 `TYPESAFE_API_KEY` 를 물어봅니다. 붙여넣고 Enter → `.env` 에 저장(gitignore, 한 번만).
4. 의존성 설치 후 브라우저가 `http://127.0.0.1:8000` 을 엽니다. 창을 닫으면 종료.

키는 내 PC 의 `.env` 와 로컬 서버 프로세스에만 있고 브라우저·GitHub 으로는 가지 않습니다.
회사 망에서 `api.typesafe.ai` 아웃바운드가 막혀 있으면 "Connection error" 가 뜹니다 — 개인망으로 한 번 확인해 보세요.

### 런처 명령

| 명령 (Windows 는 `run.bat …`) | 하는 일 |
|---|---|
| `./run.sh` | 웹 플레이그라운드 |
| `./run.sh demo` | `trial/systemone_demo.py` — ECR 하나에 noul/choice/score 세 질문. `--dry-run` 이면 요청 JSON 만 출력, `--models` 는 사용 가능 모델 |
| `./run.sh triage` | `samples/comment_triage` — 선주 코멘트 8건 라우팅. `--fixture` 오프라인 재생, `--record` 실제 응답 저장 |
| `./run.sh test` | 오프라인 테스트 (mock 서버) |
| `./run.sh shell` | venv 활성화된 셸 |

수동으로 하려면: `python -m venv .venv` → `.venv/bin/pip install -r requirements.txt` → `cp .env.example .env` → `.venv/bin/python webapp/app.py --open`.
키 없이 UI 만 보려면 `webapp/app.py --mock` (무작위 답).

## 웹 플레이그라운드

state 를 넣고 질문 JSON 을 고쳐 가며 실행하면 질문별로 확률 막대가 그려집니다. 예제 3개(선주 코멘트 / 지원 티켓 / ECR) 내장,
`+ noul / + choice / + score` 버튼으로 질문 템플릿 추가, 맨 아래 "원본 응답 JSON" 으로 실제 API 응답 확인.

만져보면 이해가 빠른 것들:
- 선주 코멘트 예제의 `comment.text` 를 "Typo: ACB-2B should read ACB-2A" 로 바꿔 실행 → `beyond_spec` 이 0 에 가깝고 `response_type` 이 `accept_no_cost` 로 가는지
- `discipline` 의 criteria 에서 `cargo_containment` 를 지워보기 → 없는 라벨은 못 고르므로 확률이 `other` 나 엉뚱한 곳으로 몰림 (그래서 `other` 를 항상 둠)
- `impact` 의 단계 설명을 "낮음/중간/높음" 처럼 모호하게 바꿔보기 → 분포가 퍼지는지

## 샘플 애플리케이션

- [`samples/comment_triage/`](samples/comment_triage/README.md) — 선주 코멘트를 기술회신 / VO / 사람검토 트랙으로 라우팅. 코멘트당 1요청·5질문, 비동기 배치, 코드 측 정책 계층(`T_*` 임계값), CSV/MD 리포트.
  `fixtures/answers.json` 은 **손으로 만든 placeholder** 입니다 — `./run.sh triage --record` 로 실제 응답으로 덮어쓴 뒤 임계값을 조정하는 것이 진짜 시작점.

## Claude Code 플러그인 / 스킬

공식 TypeSafe 에이전트 스킬(`typesafe@typesafe-ai`, [typesafe-ai/skills](https://github.com/typesafe-ai/skills))을 두 방식으로 연결해 두었습니다.
- `.claude/settings.json` — 프로젝트 범위 플러그인 선언. 로컬에서 `claude plugin install typesafe@typesafe-ai` 후 `/typesafe:typesafe-ai`
- `.claude/skills/typesafe-ai/` — 같은 SKILL.md 의 고정 사본(v0.5.7, MIT). 어느 세션에서든 `/typesafe-ai`

## 파일

- `run.sh` / `run.bat` — 런처 (venv 생성, 설치, 키 입력, 실행)
- `webapp/` — FastAPI 백엔드 + 단일 HTML 플레이그라운드
- `trial/systemone_demo.py`, `trial/raw_http.sh` — 최소 예제 (SDK / curl)
- `samples/comment_triage/` — 선주 코멘트 라우팅 샘플
- `tests/` — 로컬 mock 서버로 요청 스키마·응답 파싱·정책·웹 백엔드 검증
- `.env.example` — 환경변수 템플릿. **실제 키는 절대 커밋하지 않습니다.**
- `.devcontainer/` — (선택) GitHub Codespaces 에서 돌릴 때의 설정. 아래 참고.

## 검증된 API 계약 (출처)

공식 Python SDK 소스([typesafe-ai/typesafe-sdk-python](https://github.com/typesafe-ai/typesafe-sdk-python), v0.6.0)에서 직접 확인했습니다.
SDK 의 wire 스키마(`_schemas/models.py`)는 `https://api.typesafe.ai/openapi.json` 에서 자동 생성된 것입니다.

- 엔드포인트: `POST https://api.typesafe.ai/v1/systemone`, `GET https://api.typesafe.ai/v1/models`
- 인증: `Authorization: Bearer <TYPESAFE_API_KEY>`
- 요청: `{"state": str|object|array, "model": "jev-latest", "questions": {이름: {"type": "noul"|"choice"|"score", ...}}}`
- 응답: `{"model": str, "answers": {이름: {"type": ..., ...}}, "usage": {"input_tokens", "output_tokens"}}`
- 환경변수: `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`(기본 `https://api.typesafe.ai`), `TYPESAFE_DEFAULT_MODEL`(기본 `jev-latest`)
- SDK 기본값: timeout 10 s, 재시도 2회(408/429/5xx, `Retry-After` 존중)
- 공식 문서: https://docs.typesafe.ai/api , https://docs.typesafe.ai/sdk/python/

## 나중에 배포할 때

이 앱의 무게중심은 **Python 서버**(키를 들고 TypeSafe 를 대신 호출)라, 서버를 그대로 올릴 수 있는 곳을 고릅니다.

| 상황 | 선택 |
|---|---|
| 지금 코드 그대로, 가장 빨리 | **Render** (또는 Railway, Fly.io). 무료 인스턴스는 15분 유휴 후 잠들고 첫 접속에 ~1분 |
| 회사 인프라(AWS/Azure/사내 k8s) | **Dockerfile** 추가 → 컨테이너로. 이식성 최고 |
| 프론트를 크게 키우고 JS 팀 중심 | 그때 Netlify/Vercel + JS 백엔드(`@typesafe-ai/sdk`)로 재작성 |

- **Netlify** 는 정적 호스팅 + JS/Go 서버리스 함수라 Python 서버를 그대로 못 올립니다 — 백엔드를 TS 로 다시 짜야 함.
- **Vercel Hobby(무료)** 는 비상업 용도 제한이 있으니 회사 업무면 약관 확인.
- 공통: 키는 플랫폼 secret 으로(`TYPESAFE_API_KEY`), 접근 제어는 `PLAYGROUND_PASSWORD`(시연용 Basic auth) → 사내 SSO/Cloudflare Access 로 교체,
  응답의 `usage` 토큰을 기록해 비용 추적.

## 현재 상태 / 다음 할 일

- [x] API 계약 확인, SDK 기반 예제·샘플·웹 플레이그라운드, 오프라인 테스트 10건
- [x] 로컬 런처(`run.bat` / `run.sh`)로 실행 경로 통일
- [ ] 실제 키로 첫 호출 → `./run.sh triage --record` 로 fixture 를 실제 응답으로 교체
- [ ] 실제 분포를 보고 `samples/comment_triage/triage.py` 의 `T_*` 임계값·질문 문구 조정
- [ ] 저장소 Private 전환 (Settings → Danger Zone), API 키 재발급

## 왜 로컬인가 (다른 방법을 검토한 기록)

- **정적 페이지(GitHub Pages 등)**: 불가. `api.typesafe.ai` 가 브라우저 origin 의 CORS preflight 에 `400 "Disallowed CORS origin"` 을
  돌려주는 것을 GitHub Actions 러너에서 확인했습니다. 키를 들고 대신 호출하는 서버 프로세스가 반드시 필요합니다.
- **claude.ai 아티팩트**: 샌드박스가 외부 API 호출을 차단.
- **GitHub Codespaces**: 가능(`.devcontainer/` 유지). 프로필 Settings → Codespaces → Secrets 에 `TYPESAFE_API_KEY` 등록 후
  `<> Code → Codespaces → Create` → 8000 포트 탭. 다른 기기에서도 써야 할 때의 대안.
- **로컬**: 계정·호스팅·CORS 전부 무관, 키가 PC 밖으로 안 나감. 시범 사용에는 이것이 가장 단순합니다.
