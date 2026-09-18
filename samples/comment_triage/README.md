# Sample: 선주 코멘트(Owner Comment) 자동 분류·라우팅

도면/사양서에 대한 선주 코멘트를 받아 **Jev 가 판단**하고 **코드가 규칙을 적용**해 세 트랙으로 나눕니다.

| 트랙 | 의미 |
|---|---|
| `technical_reply` | 사양 범위 내 — 담당 설계 부서가 기술 회신 |
| `variation_order` | 사양 초과 — 견적·공정 영향 산정 후 VO 트랙 |
| `human_review` | 거절 후보이거나 모델 확신이 낮음 — 사람이 먼저 판단 |

## 구조 (스킬 지침 적용)

1. **State** — 코멘트 본문 + 인용된 사양 조항의 **정확한 원문(코드로 lookup)** + 계약 규칙 요약. 모델에게 계약을 "기억"시키지 않습니다.
2. **Questions** — 한 요청에 독립 질문 5개 (API 내부에서 병렬 실행, 서로 답을 못 봄):
   `discipline`(choice) · `beyond_spec`(noul) · `class_reapproval`(noul) · `impact`(score 0–3) · `response_type`(choice). 모든 choice 에 `other` 포함.
3. **Policy** — `triage.py` 상단 `T_*` 임계값. 추론을 다시 돌리지 않고 바꿀 수 있음. "거절은 항상 사람 승인", "낮은 확신은 사람에게" 같은 조건은 가중합에 섞지 않고 별도 규칙.
4. **Output** — 콘솔 표 + `out/triage.csv` + `out/triage.md`.

## 실행

```bash
python samples/comment_triage/triage.py --fixture          # 오프라인 재생 (fixtures/answers.json)
python samples/comment_triage/triage.py --dry-run OC-002   # 요청 JSON 확인
python samples/comment_triage/triage.py --record           # 실제 호출 + 응답을 fixture 로 저장
python samples/comment_triage/triage.py                    # 실제 호출
```

> **`fixtures/answers.json` 은 손으로 만든 placeholder 입니다 — Jev 의 실제 답이 아닙니다.**
> 파이프라인이 오프라인에서도 돌아가도록 wire 스키마 그대로 만든 것이며, `--record` 로 실제 응답으로 덮어쓰세요.
> 그 뒤 `T_*` 임계값을 실제 분포에 맞춰 조정하는 것이 이 샘플의 진짜 시작점입니다.

`comments.json` / `contract_baseline.json` 의 프로젝트·조항은 모두 가상의 예시입니다.
