# Golden Prompts

이 폴더는 `game-balance-designer` 에이전트 회귀 검증용 골든 프롬프트 세트를 담는다.

## 파일

- `game-balance-designer-golden-prompts.json`
- `run_golden_checks.py`
- `sample-responses/` (`A01~A09.md`, `D01~D08.md`, `T01~T09.md`, `X01~X02.md`)
- `README.md`

## 자동 실행/채점

### 1) 스모크 체크 (lint + 스크립트 + 샘플 16케이스)

```bash
python3 tests/golden-prompts/run_golden_checks.py \
  --responses-dir tests/golden-prompts/sample-responses \
  --case-ids A01,A02,A07,A08,A09,D01,D02,D07,D08,T01,T02,T07,T08,T09,X01,X02 \
  --check-scripts
```

### 2) 응답 파일로 채점

```bash
python3 tests/golden-prompts/run_golden_checks.py \
  --responses-dir tests/golden-prompts/sample-responses \
  --case-ids A01,A02,A07,A08,A09,D01,D02,D07,D08,T01,T02,T07,T08,T09,X01,X02
```

`sample-responses/`는 기본적으로 전체 28개 케이스(`A01~A09,D01~D08,T01~T09,X01~X02`)를 포함한다.

지원 포맷:
- `--responses-dir`: `A01.md`, `A02.markdown`, `A03.txt` 파일 묶음
- `--responses`: JSON 파일 (`{responses:{...}}`, `{cases:[...]}`, direct map)

### 3) 케이스별 파일 디렉터리 채점

```bash
python3 tests/golden-prompts/run_golden_checks.py \
  --responses-dir tests/golden-prompts/responses
```

파일명 규칙:
- `A01.md`, `A02.markdown`, `A03.txt` (확장자: `.md/.markdown/.txt`)

### 4) 부분 실행

```bash
python3 tests/golden-prompts/run_golden_checks.py --case-ids A01,A02,D03
```

```bash
python3 tests/golden-prompts/run_golden_checks.py \
  --responses-dir tests/golden-prompts/responses \
  --allow-missing-cases
```

`--allow-missing-cases`는 누락 응답을 `SKIP`으로 처리한다.  
`PASS`로 계산되지 않으며, 전체 합격은 최소 1개 이상 평가된 케이스가 있어야 한다.

## 리포트 출력

```bash
python3 tests/golden-prompts/run_golden_checks.py \
  --responses-dir tests/golden-prompts/sample-responses \
  --case-ids A01,A02,A07,A08,A09,D01,D02,D07,D08,T01,T02,T07,T08,T09,X01,X02 \
  --format json \
  --output /tmp/golden-report.json
```

## 종료 코드

- `0`: 전체 합격
- `1`: 품질 기준 미달(섹션/가정/키워드/참조/trait/점수)
- `2`: 실행 오류(입력 파일 형식/파싱/런타임 예외)

## 채점 기준 요약

- 형식: 요청 유형별 필수 섹션 충족 여부
- 가정: 템플릿의 `max_assumptions` 이내 여부
- 키워드: `cases[].required_keywords` 충족 여부
- 참조: `cases[].required_references` 언급 여부
- trait: 템플릿별 품질 조건 충족 여부
- 스크립트: `--check-scripts` 사용 시 `preferred_script` 실행 가능 여부
