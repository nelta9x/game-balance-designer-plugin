---
name: game-balance-math
description: 게임 밸런스 수학 모델링 및 테이블 설계 지원. Use when requests involve XP/level curves, TTK/EHP tuning, drop-rate weighting, pity or gacha or enhancement expected cost, clear probability, faucet-sink economy, percentile budgeting (p90/p95), or what-if comparisons. Also trigger on player-feel cues: 재미, 지루함, 억까, 속도감, 성장감, 벽, 손맛, 답답함.
---

# 역할 (Role)
게임 밸런스에 필요한 수학적 모델링 참고 자료. 시그모이드, 역수 함수, 가중 랜덤, Pity 시스템 등 다양한 공식을 상황에 맞게 선택한다.

# 사용 맥락 (Usage Context)

**이 스킬의 수학 공식은 테이블 데이터 설계를 위한 참고 도구다.**

- 런타임에 `Mathf.Exp()` 등을 직접 호출하는 것이 아님
- 경험치 테이블, 스탯 테이블, 난이도 곡선 등의 **값을 도출할 때** 곡선을 참고
- 최종 결과물은 ScriptableObject에 저장되는 정수/실수 배열

**이 공식들은 참고용이지 절대적인 규칙이 아니다.**

- 플레이어 체감과 게임 특성에 따라 자유롭게 조정 가능
- 시그모이드가 항상 정답은 아님 - 선형, 지수, 커스텀 곡선도 상황에 따라 적합
- 수학적 우아함보다 플레이 테스트 결과가 우선

# 핵심 철학 (Core Philosophy)
"Sigmoid Curves are a Game Designer's Friend" 기반:
1. **자연스러운 성장 (Natural Growth)**: 현실과 만족스러운 게임 성장은 직선이 아닌 S-곡선(느린 시작 → 급격한 성장 → 포화)을 따른다.
2. **소프트 캡 (Soft Caps)**: 하드 리밋(min/max 클램프)은 인위적으로 느껴진다. 점근선(Asymptotic) 곡선이 경계를 더 우아하게 처리한다.
3. **동적 의미 (Dynamic Meaning)**: 값은 플레이어가 가장 활발한 구간(변곡점, Inflection Point)에서 가장 크게 변해야 한다.

# 수학적 프레임워크 (Mathematical Framework)

## 1. 시그모이드/로지스틱 (Sigmoid/Logistic)

**용도**: 소프트 캡, 확률 곡선, S자 성장

$$ f(x) = \frac{L}{1 + e^{-k(x - x_0)}} $$

| 파라미터 | 의미 | 예시 |
|----------|------|------|
| L | 최댓값 (점근선) | 최대 피해감소 80% |
| k | 기울기 (급격함) | 0.1(완만) ~ 1.0(급격) |
| x0 | 중간점 (50% 도달) | 레벨 50에서 절반 효과 |
| x | 입력값 | 레벨, 스탯 차이, 시간 |

**사용 사례**:
- 스탯 → 확률 변환 (명중률, 치명타율)
- 레벨 차이 → 경험치 보정
- 0%/100% 잠김 방지

**주의**: k 민감도. x가 0~100이면 k=0.1, x가 0~1이면 k=10 정도.

---

## 2. 역수 함수 (Inverse/Hyperbolic)

**용도**: 쿨다운 감소, 공격 속도, 하드캡 접근

$$ f(x) = \frac{a}{x + b} + c $$

또는 효율 공식:
$$ \text{효과} = \frac{x}{x + k} $$

| 파라미터 | 의미 |
|----------|------|
| x | 투자량 (쿨감 스탯) |
| k | 반감기 (50% 도달에 필요한 투자량) |

**예시: 쿨다운 감소**
```
쿨감스탯 0   → 감소율 0%
쿨감스탯 100 → 감소율 50%  (k=100일 때)
쿨감스탯 200 → 감소율 66%
쿨감스탯 300 → 감소율 75%
```

**장점**: 아무리 투자해도 100%에 도달 불가 (0초 쿨 방지)

---

## 3. 가중 랜덤 (Weighted Random)

**용도**: 드롭 테이블, 몬스터 스폰, 보상 선택

**기본 공식**:
$$ P(i) = \frac{w_i}{\sum_{j} w_j} $$

| 아이템 | 가중치 | 확률 |
|--------|--------|------|
| 일반 | 70 | 70% |
| 희귀 | 25 | 25% |
| 전설 | 5 | 5% |

**구현 팁**:
- 가중치 합계를 100으로 맞추면 확률 = 가중치
- 런타임: 누적 가중치 배열 + 이진 탐색

**희귀도 티어 설계**:
```
일반:희귀:에픽:전설 = 100:10:1:0.1 (로그 스케일)
```

---

## 4. Pity 시스템 (보정 확률)

**용도**: 가챠, 강화, 연속 실패 보호

### 4-1. 선형 Pity
$$ P(n) = \min(P_{base} + ((n-1) \times \Delta), P_{max}) $$

| 시도 | 기본 1% + 1%씩 증가 |
|------|---------------------|
| 1회 | 1% |
| 10회 | 10% |
| 50회 | 50% |
| 100회 | 100% (확정) |

### 4-2. 소프트 Pity (단계별)
```
1~73회:  0.6%
74~89회: 6% (소프트 pity 구간)
90회:    100% (하드 pity)
```

### 4-3. 기대값 계산
연속 실패 후 성공 확률 p의 기대 시도 횟수:
$$ E[X] = \frac{1}{p} $$

5% 확률 → 평균 20회 시도 필요

---

## 5. 구간별 함수 (Piecewise)

**용도**: 세밀한 밸런스 조정, 구간별 다른 규칙

```
f(x) =
  10x           (x < 10)     초반: 빠른 성장
  100 + 5x      (10 ≤ x < 50) 중반: 완만한 성장
  350 + 2x      (x ≥ 50)     후반: 느린 성장
```

**장점**: 수학적 우아함 < 디자이너 의도 정확히 반영
**단점**: 경계에서 불연속 가능, 관리 복잡

**사용 사례**:
- 레벨 구간별 경험치 배율
- 등급별 강화 성공률
- PvP 레이팅 구간별 점수 변동

# 모델 선택 가이드 (Model Selection Guide)

| 상황 | 권장 모델 |
|------|----------|
| 스탯에 소프트 캡 적용 | 시그모이드 |
| 쿨다운/공속 감소 | 역수 함수 |
| 드롭 테이블 설계 | 가중 랜덤 |
| 가챠/강화 실패 보호 | Pity 시스템 |
| 구간별 다른 규칙 | 구간별 함수 |
| 플레이어가 계산 가능해야 함 | 선형 |

# 구현 팁 (Implementation Tips)

## Excel/스프레드시트 공식
```
시그모이드: =L / (1 + EXP(-k * (A1 - x0)))
역수 효율: =A1 / (A1 + k)
가중 랜덤: =SUMPRODUCT((B:B<=RAND()*SUM(C:C))*1) (누적 방식)
```

## Unity (C#)
```csharp
// 시그모이드
float Sigmoid(float x, float L, float k, float x0)
    => L / (1f + Mathf.Exp(-k * (x - x0)));

// 역수 효율 (쿨감 등)
float DiminishingReturn(float x, float k)
    => x / (x + k);

// 가중 랜덤
int WeightedRandom(int[] weights) {
    int total = weights.Sum();
    int roll = Random.Range(0, total);
    for (int i = 0; i < weights.Length; i++) {
        roll -= weights[i];
        if (roll < 0) return i;
    }
    return weights.Length - 1;
}
```

## 주의사항
- 시그모이드 k값: x 스케일에 따라 조정 (0~100이면 k=0.1, 0~1이면 k=10)
- 역수 함수: k가 "50% 도달점"임을 명심
- Pity: 기대값과 최악 케이스 모두 계산해서 공개

# 계산 스크립트 (Scripts)

반복 계산이 필요한 요청(표 재생성, what-if 비교, p90/p95 산출)에서는 아래 스크립트를 우선 사용한다.

| 스크립트 | 용도 | 실행 예시 |
|---|---|---|
| `scripts/ttk_ehp_calculator.py` | DPS/EHP/TTK 계산, 목표 TTK 기반 HP 역산 | `python3 "${CODEX_HOME:-$HOME/.codex}/skills/game-balance-math/scripts/ttk_ehp_calculator.py"` |
| `scripts/economy_flow_simulator.py` | Faucet/Sink/TTE, 패치 전후 재고 추이 시뮬레이션 | `python3 "${CODEX_HOME:-$HOME/.codex}/skills/game-balance-math/scripts/economy_flow_simulator.py"` |
| `scripts/enhancement_cost_simulator.py` | 강화 기대 시도/비용 + p50/p90/p95 계산 | `python3 "${CODEX_HOME:-$HOME/.codex}/skills/game-balance-math/scripts/enhancement_cost_simulator.py"` |
| `scripts/clear_probability_tuner.py` | 로지스틱 클리어율 곡선/역산/재시도 횟수 계산 | `python3 "${CODEX_HOME:-$HOME/.codex}/skills/game-balance-math/scripts/clear_probability_tuner.py"` |

입력 파일이 있으면 `--input <json>`을 사용하고, 없으면 각 스크립트의 내장 샘플로 바로 실행된다.

# 참고 자료 (References)

참고용 안내:
- 아래 매핑은 절대 규칙이 아니라 시작점이다. 실제 선택은 게임 의도, 세션 길이, 콘텐츠 티어 수, 보상 구조에 따라 달라진다.
- 불확실하면 1~2개의 질문으로 전제를 확인하거나, 가정을 명시하고 진행한다.

아래 표는 참고 상황과 내용을 함께 요약한다.

### 요청-문서 빠른 라우팅

| 요청 신호(의도) | 먼저 볼 문서 | 핵심 산출 |
|---|---|---|
| "레벨업이 느리다/빠르다", "경험치 테이블 설계" | `experience-tables.md` | 레벨 구간별 XP 곡선/레벨업 시간 |
| "빠르게 추천해줘", "요약표로 먼저 알려줘" | `intent-curve-one-pager.md` | 의도-모델-리스크-지표를 1페이지로 제시 |
| "어떤 느낌을 주고 싶다", "선형/지수/계단식 추천" | `growth-intent-curve-playbook.md` | 체감 의도 기반 모델 추천 + 리스크/검증 지표 |
| "재미를 수치로 어떻게 봐야 하지?", "모호한 재미를 검증하고 싶다" | `fun-quant-thinking.md` | 재미를 가설/관찰 신호/실패 조건으로 변환 |
| "드랍률 이상함", "희귀도 확률 조정" | `drop-tables.md` | 가중치/희귀도/조건부 드롭 구조 |
| "쿨감/공속/방어 효율 이상" | `diminishing-returns.md` | 수확 체감 공식과 k값 |
| "가챠/강화 실패 체감이 나쁨" | `pity-systems.md` | pity/천장/중복보호 구조 |
| "장르 템포에 맞는 곡선을 고르고 싶다" | `curve-genre-tempo.md` | 장르-템포별 모델 후보 |
| "전투가 길다/짧다", "보스 체력 역산" | `combat-ttk-ehp.md` | DPS/EHP/TTK 기반 체력 산정 |
| "스테이지 클리어율 목표 설정" | `encounter-clear-probability.md` | 목표 클리어율/재시도 횟수 |
| "재화 인플레/디플레 점검" | `economy-faucet-sink.md` | Faucet-Sink/TTE/패치 충격 |
| "강화 기대비용 계산", "보호권 가치" | `enhancement-expected-cost.md` | 평균/p90/p95 소모량 |

| 파일 | 참고 상황 | 내용 |
|------|----------|------|
| `experience-tables.md` | XP/성장 곡선 | 선형/지수/다항식/구간별 경험치 테이블 예시 |
| `intent-curve-one-pager.md` | 빠른 상담/요약 답변 | 의도-모델-리스크-검증 지표 1페이지 요약 |
| `growth-intent-curve-playbook.md` | 체감 의도 기반 조언 | 선형/지수/계단식 선택 사례, 안티패턴, 복구 레버 |
| `fun-quant-thinking.md` | 재미 지표 발상/검증 | 재미를 절대식이 아니라 가설+관찰 장치로 다루는 프레임 |
| `drop-tables.md` | 드롭/가중치 | 가중치, 희귀도 티어, 조건부 드롭, 쿠폰 수집가 문제 |
| `diminishing-returns.md` | 수익 체감/소프트캡 | 쿨감, 공속, 방어력, 치명타 수확체감 예시 |
| `pity-systems.md` | 가챠/강화 보정 | 선형/소프트/지수 Pity, 토큰형, 기대값 계산 |
| `curve-genre-tempo.md` | 곡선 선택/장르-템포(휴리스틱) | 곡선-장르/템포 매핑과 선택 질문 |
| `combat-ttk-ehp.md` | 전투 페이싱/난이도 | 기대 DPS, EHP, TTK 목표 밴드, 보스 페이즈 시간 예산 |
| `economy-faucet-sink.md` | 경제 수지/인플레이션 | Faucet/Sink 수지식, TTE, 패치 충격 시뮬레이션 |
| `encounter-clear-probability.md` | 스테이지 클리어율 | 로지스틱 클리어 확률 모델, 목표 확률 역산, 재시도 확률 |
| `enhancement-expected-cost.md` | 강화 기대비용 | 상태전이 기반 기대 시도/비용, 퍼센타일 예산, 보호권 가치 |
