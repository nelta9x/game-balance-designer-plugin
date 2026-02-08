# Game Balance Designer Plugin

게임 밸런스 설계 및 분석을 위한 Claude Code 플러그인입니다.

## 기능

### game-balance-designer 에이전트

범용적 게임 밸런스 설계 에이전트입니다. 경험치/난이도/드롭률/스탯 등 게임 수치 분석과 디자인을 전문적으로 수행합니다.

**핵심 역량:**
- 진행/경험치 시스템 (Linear, Power, Exponential, Sigmoid, Piecewise)
- 전투 난이도 설계 (TTK, EHP 기반)
- 드롭/경제 시스템 (Diminishing Returns, Pity, Weighted Random)
- 콘텐츠-수치 동기화 검증

**설계 철학:**
- No Magic Numbers: 모든 수치에 근거 제시
- Systems Thinking: 변경의 파급 효과 분석
- Player Experience First: 수학은 도구, 목표는 플레이어 몰입

### game-balance-math 스킬

게임 밸런스에 필요한 수학적 모델링 참고 자료입니다.

- 시그모이드/로지스틱 곡선 (소프트 캡, 확률 변환)
- 역수 함수 (쿨다운 감소, 공격 속도)
- 가중 랜덤 (드롭 테이블, 보상 선택)
- Pity 시스템 (선형/소프트/토큰형)
- 구간별 함수 (세밀한 구간별 규칙)

## 프로젝트 구조

```
game-balance-designer-plugin/
├── .claude-plugin/
│   ├── plugin.json          # 플러그인 메타데이터
│   └── marketplace.json     # 마켓플레이스 등록 정보
├── agents/
│   └── game-balance-designer.md
├── skills/
│   └── game-balance-math/
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── ttk_ehp_calculator.py
│       │   ├── economy_flow_simulator.py
│       │   ├── enhancement_cost_simulator.py
│       │   └── clear_probability_tuner.py
│       └── references/
│           ├── experience-tables.md
│           ├── intent-curve-one-pager.md
│           ├── growth-intent-curve-playbook.md
│           ├── fun-quant-thinking.md
│           ├── drop-tables.md
│           ├── diminishing-returns.md
│           ├── pity-systems.md
│           ├── curve-genre-tempo.md
│           ├── combat-ttk-ehp.md
│           ├── economy-faucet-sink.md
│           ├── encounter-clear-probability.md
│           └── enhancement-expected-cost.md
├── tests/
│   └── golden-prompts/
│       ├── game-balance-designer-golden-prompts.json
│       ├── run_golden_checks.py
│       ├── sample-responses/
│       │   ├── A01~A10.md
│       │   ├── D01~D08.md
│       │   ├── T01~T10.md
│       │   └── X01~X06.md
│       └── README.md
├── README.md
└── .gitignore
```

## 사용 방법

### 1분 진입 (처음 쓰는 경우)

가장 자주 쓰는 시나리오 3개만 먼저 잡으면 바로 실전에 쓸 수 있습니다.

| 상황 | 먼저 볼 문서 | 바로 던질 요청 예시 |
|------|-------------|--------------------|
| 레벨업 템포가 이상함 | `skills/game-balance-math/references/experience-tables.md` | "레벨 1~50 경험치 테이블을 20분 세션 기준으로 재설계해줘" |
| 전투가 너무 길거나 짧음 | `skills/game-balance-math/references/combat-ttk-ehp.md` | "보스 2페이즈 목표 TTK 60초로 HP 역산해줘" |
| 강화/가챠 체감이 나쁨 | `skills/game-balance-math/references/enhancement-expected-cost.md` | "강화 +0->+10 기대비용과 p90 비용 계산해줘" |

추가로, 경제 수지 점검이 필요하면 `skills/game-balance-math/references/economy-faucet-sink.md`를 먼저 열어 `Faucet/Sink/TTE`를 기준으로 본다.

### 에이전트 호출

밸런스 분석/설계 요청 시 game-balance-designer 에이전트가 자동으로 호출됩니다.

**예시 요청:**
- "현재 경험치 테이블 분석해줘"
- "몬스터 밸런스 검토해줘"
- "스테이지 난이도 곡선 설계해줘"
- "레벨업이 너무 느려"

### 에이전트 동작

에이전트는 요청 유형에 따라 다른 형식으로 응답합니다:

| 요청 유형 | 예시 | 출력 형식 |
|----------|------|----------|
| 분석 | "경험치 테이블 분석해줘" | 현황 요약, 가정, 분석, 권장 사항, 검증 방법 |
| 설계 | "경험치 테이블 만들어줘" | 설계 목표, 가정, 제안 수치, 설계 근거, 의존성 경고, 검증 방법 |
| 문제 해결 | "레벨업이 너무 느려" | 문제 정의, 가정, 원인 분석, 해결 방안, 권장안, 파급 효과 |

### 스킬 참조

에이전트가 자동으로 game-balance-math 스킬을 참조하여 수학적 모델을 적용합니다. `/game-balance-math` 명령으로 직접 스킬을 호출할 수도 있습니다.

### 반복 계산 스크립트

반복 계산/시뮬레이션은 아래 스크립트를 사용하면 빠르고 재현 가능합니다.

- `python3 skills/game-balance-math/scripts/ttk_ehp_calculator.py`
- `python3 skills/game-balance-math/scripts/economy_flow_simulator.py`
- `python3 skills/game-balance-math/scripts/enhancement_cost_simulator.py`
- `python3 skills/game-balance-math/scripts/clear_probability_tuner.py`

입력 JSON을 쓰려면 각 스크립트에 `--input <json>`을 추가하세요. 입력이 없으면 내장 샘플로 실행됩니다.

### 골든 프롬프트

에이전트 회귀 품질 검증용 골든 프롬프트 세트는 아래 경로에 있습니다.

- `tests/golden-prompts/game-balance-designer-golden-prompts.json`
- `tests/golden-prompts/run_golden_checks.py`
- `tests/golden-prompts/sample-responses/`
- `tests/golden-prompts/README.md`

구성:
- 총 34개 케이스 (분석/설계/문제 해결/교차 시스템 + 엣지/불완전 입력)
- 요청 유형별 필수 섹션 템플릿
- 케이스별 필수 참조 문서/핵심 키워드/권장 계산 스크립트

## 포함된 참고 자료

| 파일 | 참고 상황 | 내용 |
|------|----------|------|
| `experience-tables.md` | XP/성장 곡선 | 선형/지수/다항식/구간별 경험치 테이블 예시 |
| `intent-curve-one-pager.md` | 빠른 상담/요약 답변 | 의도-모델-리스크-검증 지표 1페이지 요약 |
| `growth-intent-curve-playbook.md` | 체감 의도 기반 조언 | 선형/지수/계단식 선택 사례, 안티패턴, 복구 레버 |
| `fun-quant-thinking.md` | 재미 발상 프레임 | 재미를 절대식이 아니라 가설+관찰 신호로 다루는 기준 |
| `drop-tables.md` | 드롭/가중치 | 가중치, 희귀도 티어, 조건부 드롭, 쿠폰 수집가 문제 |
| `diminishing-returns.md` | 수익 체감/소프트캡 | 쿨감, 공속, 방어력, 치명타 수확체감 예시 |
| `pity-systems.md` | 가챠/강화 보정 | 선형/소프트/지수 Pity, 토큰형, 기대값 계산 |
| `curve-genre-tempo.md` | 곡선 선택 | 곡선-장르/템포 매핑과 선택 질문 |
| `combat-ttk-ehp.md` | 전투 페이싱/난이도 | 기대 DPS, EHP, TTK 목표 밴드, 보스 페이즈 시간 예산 |
| `economy-faucet-sink.md` | 경제 수지/인플레이션 | Faucet/Sink 수지식, TTE, 패치 충격 시뮬레이션 |
| `encounter-clear-probability.md` | 스테이지 클리어율 | 로지스틱 클리어 확률 모델, 목표 확률 역산, 재시도 확률 |
| `enhancement-expected-cost.md` | 강화 기대비용 | 상태전이 기반 기대 시도/비용, 퍼센타일 예산, 보호권 가치 |

## 라이선스

MIT License
