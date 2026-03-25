# 메타 광고 주간 성과 분석 봇 (Meta Ads Weekly Report Bot)

## 개요

메타(Facebook/Instagram) 광고의 주요 지표를 자동으로 분석하고, 주간별 성과 추이를 **고객사가 이해하기 쉬운 언어**로 텍스트 리포트를 자동 생성하는 봇입니다.

> 주간 광고 예산 70만 ~ 100만원 이상 집행 기준으로, 광고가 어떻게 돌아가고 있는지 명확하게 파악하고 고객사에 신뢰 있게 보고하는 것을 목적으로 합니다.

---

## 분석 지표 정의

| 지표 | 영문 | 쉬운 설명 |
|------|------|-----------|
| **CPA** | Cost Per Action | 구매 1건을 만들어내는 데 든 비용. 낮을수록 효율적 |
| **CPC** | Cost Per Click | 광고를 1번 클릭하는 데 든 비용. 낮을수록 좋음 |
| **CTR** | Click-Through Rate | 광고를 본 사람 중 클릭한 비율(%). 높을수록 광고 소재가 매력적 |
| **CPM** | Cost Per 1,000 Impressions | 1,000명에게 광고를 보여주는 데 든 비용. 경쟁 강도 반영 |
| **ROAS** | Return On Ad Spend | 광고비 1원당 발생한 매출. 예: ROAS 300% = 100원 투자 → 300원 매출 |
| **노출수** | Impressions | 광고가 화면에 표시된 총 횟수 |
| **도달수** | Reach | 광고를 실제로 본 순 사람 수 |
| **전환수** | Conversions | 구매, 회원가입 등 목표 행동을 완료한 횟수 |

---

## 봇 구조 설계

```
[데이터 수집]
    ↓
Meta Marketing API → 주간 지표 데이터 추출
    ↓
[데이터 분석]
    ↓
전주 대비 변화율 계산 → 이상 감지(급락/급등) → 인사이트 추출
    ↓
[리포트 생성]
    ↓
GPT / Claude API → 마케팅 언어로 텍스트 자동 생성
    ↓
[전달]
    ↓
슬랙 / 이메일 / 카카오톡 채널 발송
```

---

## 주간 리포트 자동 생성 로직

### 1. 데이터 수집 (Meta Marketing API)

```python
import requests
from datetime import datetime, timedelta

def get_weekly_insights(ad_account_id: str, access_token: str) -> dict:
    """
    메타 광고 계정에서 이번 주 / 지난 주 지표를 가져옵니다.
    """
    today = datetime.today()
    this_week_end = today.strftime("%Y-%m-%d")
    this_week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    last_week_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    last_week_end = (today - timedelta(days=8)).strftime("%Y-%m-%d")

    fields = "spend,impressions,reach,clicks,ctr,cpc,cpm,actions,cost_per_action_type"
    base_url = f"https://graph.facebook.com/v19.0/{ad_account_id}/insights"

    params_this = {
        "fields": fields,
        "time_range": f'{{"since":"{this_week_start}","until":"{this_week_end}"}}',
        "access_token": access_token,
        "level": "account",
    }
    params_last = {
        **params_this,
        "time_range": f'{{"since":"{last_week_start}","until":"{last_week_end}"}}',
    }

    this_week = requests.get(base_url, params=params_this).json()["data"][0]
    last_week = requests.get(base_url, params=params_last).json()["data"][0]

    return {"this_week": this_week, "last_week": last_week}
```

---

### 2. 지표 분석 및 인사이트 추출

```python
def analyze_metrics(data: dict) -> dict:
    """
    이번 주 vs 지난 주 지표를 비교하고 변화율과 인사이트를 추출합니다.
    """
    tw = data["this_week"]
    lw = data["last_week"]

    def rate_of_change(current, previous):
        if float(previous) == 0:
            return 0
        return round((float(current) - float(previous)) / float(previous) * 100, 1)

    analysis = {
        "spend":       {"this": float(tw["spend"]),       "last": float(lw["spend"])},
        "impressions": {"this": int(tw["impressions"]),   "last": int(lw["impressions"])},
        "reach":       {"this": int(tw["reach"]),         "last": int(lw["reach"])},
        "clicks":      {"this": int(tw["clicks"]),        "last": int(lw["clicks"])},
        "ctr":         {"this": float(tw["ctr"]),         "last": float(lw["ctr"])},
        "cpc":         {"this": float(tw["cpc"]),         "last": float(lw["cpc"])},
        "cpm":         {"this": float(tw["cpm"]),         "last": float(lw["cpm"])},
    }

    # 전환수(구매) 추출
    def extract_purchase(actions):
        for a in actions or []:
            if a["action_type"] == "purchase":
                return int(a["value"])
        return 0

    def extract_cpa(cost_per_action):
        for a in cost_per_action or []:
            if a["action_type"] == "purchase":
                return float(a["value"])
        return 0

    analysis["purchases"] = {
        "this": extract_purchase(tw.get("actions")),
        "last": extract_purchase(lw.get("actions")),
    }
    analysis["cpa"] = {
        "this": extract_cpa(tw.get("cost_per_action_type")),
        "last": extract_cpa(lw.get("cost_per_action_type")),
    }

    # 변화율 계산
    for key in analysis:
        analysis[key]["change"] = rate_of_change(
            analysis[key]["this"], analysis[key]["last"]
        )

    # 인사이트 플래그
    insights = []

    if analysis["ctr"]["change"] <= -15:
        insights.append({
            "type": "warning",
            "metric": "CTR",
            "message": "광고 소재 피로도 의심 — 소재 교체 또는 새로운 후킹 문구 테스트 권장",
        })
    elif analysis["ctr"]["change"] >= 20:
        insights.append({
            "type": "positive",
            "metric": "CTR",
            "message": "광고 소재 반응이 좋아졌습니다 — 해당 소재 예산 증액 고려",
        })

    if analysis["cpa"]["change"] >= 20:
        insights.append({
            "type": "warning",
            "metric": "CPA",
            "message": "구매 1건당 비용이 상승했습니다 — 타겟 오디언스 재검토 또는 랜딩페이지 전환율 점검 필요",
        })
    elif analysis["cpa"]["change"] <= -15:
        insights.append({
            "type": "positive",
            "metric": "CPA",
            "message": "구매 효율이 개선되었습니다 — 현재 타겟 세팅과 소재 조합 유지 권장",
        })

    if analysis["cpm"]["change"] >= 20:
        insights.append({
            "type": "caution",
            "metric": "CPM",
            "message": "광고 경쟁이 치열해졌습니다(CPM 상승) — 입찰 전략 및 오디언스 범위 재검토 필요",
        })

    if analysis["cpc"]["change"] >= 20:
        insights.append({
            "type": "warning",
            "metric": "CPC",
            "message": "클릭 비용이 올랐습니다 — 광고 품질 점수 개선 또는 소재 A/B 테스트 권장",
        })

    return {"metrics": analysis, "insights": insights}
```

---

### 3. 텍스트 리포트 자동 생성

```python
def generate_report_text(analysis: dict, brand_name: str = "고객사") -> str:
    """
    분석 결과를 바탕으로 고객사에게 전달할 주간 리포트 텍스트를 생성합니다.
    """
    m = analysis["metrics"]
    insights = analysis["insights"]

    # 이모지 방향 표시
    def arrow(change):
        if change > 0:
            return f"▲ {abs(change)}%"
        elif change < 0:
            return f"▼ {abs(change)}%"
        return "→ 변동 없음"

    def good_bad(metric, change):
        """지표별로 오르면 좋은지 / 내리면 좋은지 판단"""
        higher_is_better = {"ctr", "purchases", "reach", "impressions"}
        lower_is_better = {"cpa", "cpc", "cpm"}
        if metric in higher_is_better:
            return "개선" if change > 0 else ("하락" if change < -5 else "유지")
        elif metric in lower_is_better:
            return "개선" if change < 0 else ("악화" if change > 5 else "유지")
        return ""

    report = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 {brand_name} | 메타 광고 주간 성과 리포트
━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 분석 기간: 이번 주 vs 지난 주 비교

【 광고비 집행 현황 】
  · 이번 주 집행 금액: {m['spend']['this']:,.0f}원
  · 지난 주 집행 금액: {m['spend']['last']:,.0f}원
  · 변화: {arrow(m['spend']['change'])}

【 광고 도달 및 노출 】
  · 노출수 (광고가 화면에 표시된 횟수)
    이번 주: {m['impressions']['this']:,}회 / 지난 주: {m['impressions']['last']:,}회  {arrow(m['impressions']['change'])}
  · 도달수 (실제로 본 순 사람 수)
    이번 주: {m['reach']['this']:,}명 / 지난 주: {m['reach']['last']:,}명  {arrow(m['reach']['change'])}

【 클릭 성과 】
  · CTR (클릭률) — 광고를 본 사람 중 클릭한 비율
    이번 주: {m['ctr']['this']:.2f}% / 지난 주: {m['ctr']['last']:.2f}%  {arrow(m['ctr']['change'])}  [{good_bad('ctr', m['ctr']['change'])}]
  · CPC (클릭당 비용)
    이번 주: {m['cpc']['this']:,.0f}원 / 지난 주: {m['cpc']['last']:,.0f}원  {arrow(m['cpc']['change'])}  [{good_bad('cpc', m['cpc']['change'])}]

【 광고 경쟁 강도 】
  · CPM (1,000명에게 노출하는 데 드는 비용)
    이번 주: {m['cpm']['this']:,.0f}원 / 지난 주: {m['cpm']['last']:,.0f}원  {arrow(m['cpm']['change'])}  [{good_bad('cpm', m['cpm']['change'])}]

【 전환 성과 (가장 중요!) 】
  · 구매 건수
    이번 주: {m['purchases']['this']:,}건 / 지난 주: {m['purchases']['last']:,}건  {arrow(m['purchases']['change'])}  [{good_bad('purchases', m['purchases']['change'])}]
  · CPA (구매 1건당 광고비)
    이번 주: {m['cpa']['this']:,.0f}원 / 지난 주: {m['cpa']['last']:,.0f}원  {arrow(m['cpa']['change'])}  [{good_bad('cpa', m['cpa']['change'])}]

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 이번 주 인사이트 & 개선 방향
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    if not insights:
        report += "\n  ✅ 이번 주 전반적인 지표가 안정적으로 유지되고 있습니다. 현재 세팅을 유지하며 소재 다양화를 준비할 것을 권장합니다.\n"
    else:
        for i, ins in enumerate(insights, 1):
            icon = {"warning": "⚠️", "positive": "✅", "caution": "🔶"}.get(ins["type"], "📌")
            report += f"\n  {i}. {icon} [{ins['metric']}] {ins['message']}\n"

    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 다음 주 액션 플랜
━━━━━━━━━━━━━━━━━━━━━━━━━━

{_generate_action_plan(analysis)}

━━━━━━━━━━━━━━━━━━━━━━━━━━
※ 본 리포트는 메타 광고 데이터를 기반으로 자동 생성되었습니다.
   세부 분석이나 전략 미팅은 담당 매니저에게 문의해주세요.
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return report


def _generate_action_plan(analysis: dict) -> str:
    """인사이트를 기반으로 다음 주 액션 플랜을 생성합니다."""
    m = analysis["metrics"]
    plans = []

    # 소재 피로도 감지
    if m["ctr"]["change"] <= -15:
        plans.append("  1. 새로운 광고 소재(이미지/영상) 최소 2~3개 제작 및 A/B 테스트 진행")
        plans.append("     → 현재 CTR이 하락 중이므로 소재 신선도 회복이 시급합니다")

    # CPA 상승 시
    if m["cpa"]["change"] >= 20:
        plans.append("  2. 구매 전환이 낮은 오디언스 세그먼트 제외 또는 교체")
        plans.append("     → 랜딩페이지 로딩 속도, 구매 버튼 위치 등 UX도 함께 점검 권장")

    # CPM 상승 시
    if m["cpm"]["change"] >= 20:
        plans.append("  3. 유사 타겟(Lookalike) 비율 확대 또는 관심사 타겟 재구성")
        plans.append("     → 경쟁 심화 구간을 피해 도달 효율을 높이는 방향으로 조정")

    # 성과 좋을 때
    if m["cpa"]["change"] <= -15 and m["purchases"]["change"] >= 10:
        plans.append("  ✅ 현재 성과가 좋습니다. 예산을 10~20% 증액하여 모멘텀을 유지하는 것을 검토해보세요")

    if not plans:
        plans.append("  · 현재 세팅 유지 + 신규 소재 1~2개 테스트 준비")
        plans.append("  · 경쟁사 광고 모니터링 병행 권장")

    return "\n".join(plans)
```

---

### 4. 실행 엔트리포인트

```python
def run_weekly_report(ad_account_id: str, access_token: str, brand_name: str):
    """메인 실행 함수"""
    print("📡 메타 광고 데이터 수집 중...")
    raw_data = get_weekly_insights(ad_account_id, access_token)

    print("🔍 지표 분석 중...")
    analysis = analyze_metrics(raw_data)

    print("📝 리포트 생성 중...")
    report = generate_report_text(analysis, brand_name)

    print(report)

    # 필요 시 파일 저장
    filename = f"meta_report_{datetime.today().strftime('%Y%m%d')}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n✅ 리포트 저장 완료: {filename}")

    return report


# 실행 예시
if __name__ == "__main__":
    run_weekly_report(
        ad_account_id="act_123456789",
        access_token="YOUR_META_ACCESS_TOKEN",
        brand_name="OO브랜드",
    )
```

---

## 리포트 출력 예시

```
━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 OO브랜드 | 메타 광고 주간 성과 리포트
━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 분석 기간: 이번 주 vs 지난 주 비교

【 광고비 집행 현황 】
  · 이번 주 집행 금액: 876,300원
  · 지난 주 집행 금액: 821,000원
  · 변화: ▲ 6.7%

【 클릭 성과 】
  · CTR (클릭률): 1.82% / 2.34%  ▼ 22.2%  [하락]
  · CPC (클릭당 비용): 412원 / 318원  ▲ 29.6%  [악화]

【 전환 성과 (가장 중요!) 】
  · 구매 건수: 18건 / 24건  ▼ 25.0%  [하락]
  · CPA (구매 1건당 광고비): 48,683원 / 34,208원  ▲ 42.3%  [악화]

━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 이번 주 인사이트 & 개선 방향
━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. ⚠️ [CTR] 광고 소재 피로도 의심 — 소재 교체 또는 새로운 후킹 문구 테스트 권장
  2. ⚠️ [CPA] 구매 1건당 비용이 상승했습니다 — 타겟 오디언스 재검토 또는 랜딩페이지 전환율 점검 필요
  3. ⚠️ [CPC] 클릭 비용이 올랐습니다 — 광고 품질 점수 개선 또는 소재 A/B 테스트 권장
```

---

## 확장 옵션

| 기능 | 설명 |
|------|------|
| **캠페인별 분석** | `level="campaign"` 으로 변경 시 캠페인 단위 분석 가능 |
| **소재별 분석** | `level="ad"` 로 변경 시 광고 소재 단위 성과 비교 |
| **슬랙 자동 발송** | `slack_sdk` 연동으로 매주 월요일 오전 자동 발송 |
| **이메일 발송** | `smtplib` 또는 SendGrid 연동 |
| **Google Sheets 연동** | `gspread` 라이브러리로 시트에 자동 기록 |
| **AI 리포트 고도화** | Claude / GPT API 연동으로 더 자연스러운 문장 생성 |
| **ROAS 분석 추가** | 광고비 대비 매출 효율 지표 추가 |
| **4주 추이 그래프** | `matplotlib`으로 시각화 이미지 첨부 |

---

## 자동 스케줄 실행 (매주 월요일 오전 9시)

```python
# schedule 라이브러리 사용 예시
import schedule
import time

def job():
    run_weekly_report(
        ad_account_id="act_123456789",
        access_token="YOUR_TOKEN",
        brand_name="OO브랜드",
    )

schedule.every().monday.at("09:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

## 필요 패키지

```bash
pip install requests schedule
```

Meta Marketing API 액세스 토큰 발급: [Meta for Developers](https://developers.facebook.com/) > 앱 생성 > Marketing API 권한 요청

---

## 주의사항

- Meta Marketing API는 **시스템 사용자 토큰** 사용을 권장 (만료 없음)
- 전환 데이터는 기여 기간(Attribution Window) 설정에 따라 수치가 달라질 수 있음
- 데이터는 최대 **48시간 지연** 반영될 수 있으므로 집계 기준일 확인 필요
- 광고 계정 ID 형식: `act_` 접두사 포함 (예: `act_123456789`)
