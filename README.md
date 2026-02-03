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
│       └── references/
│           ├── experience-tables.md
│           ├── drop-tables.md
│           ├── diminishing-returns.md
│           ├── pity-systems.md
│           └── curve-genre-tempo.md
├── README.md
└── .gitignore
```

## 사용 방법

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
| 문제 해결 | "레벨업이 너무 느려" | 문제 정의, 가정, 원인 분석, 해결 방안, 파급 효과 |

### 스킬 참조

에이전트가 자동으로 game-balance-math 스킬을 참조하여 수학적 모델을 적용합니다. `/game-balance-math` 명령으로 직접 스킬을 호출할 수도 있습니다.

## 포함된 참고 자료

| 파일 | 참고 상황 | 내용 |
|------|----------|------|
| `experience-tables.md` | XP/성장 곡선 | 선형/지수/다항식/구간별 경험치 테이블 예시 |
| `drop-tables.md` | 드롭/가중치 | 가중치, 희귀도 티어, 조건부 드롭, 쿠폰 수집가 문제 |
| `diminishing-returns.md` | 수익 체감/소프트캡 | 쿨감, 공속, 방어력, 치명타 수확체감 예시 |
| `pity-systems.md` | 가챠/강화 보정 | 선형/소프트/지수 Pity, 토큰형, 기대값 계산 |
| `curve-genre-tempo.md` | 곡선 선택 | 곡선-장르/템포 매핑과 선택 질문 |

## 라이선스

MIT License
