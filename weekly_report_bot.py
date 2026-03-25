# -*- coding: utf-8 -*-
"""
메타 광고 주간 성과 리포트 자동 생성 봇
========================================
구글 스프레드시트에서 브랜드별 일별 데이터를 읽어와
주간 단위로 묶고, 전주 대비 추이를 분석하여
고객사가 이해하기 쉬운 리포트를 자동 생성합니다.
"""

import gspread
import json
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from collections import defaultdict

# ============================================================
# 1. Google Sheets 연결
# ============================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SPREADSHEET_ID = "1MgqPG7eKlBHLq4uyyE_aXsggW0Z91m-ZVHM6rn1WBzA"


def connect():
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


# ============================================================
# 2. 데이터 읽기 & 주간 집계
# ============================================================
def to_num(val):
    """쉼표, %, 공백 등을 처리하여 숫자 변환"""
    if isinstance(val, (int, float)):
        return val
    s = str(val).replace(",", "").replace("%", "").strip()
    if not s or s == " ":
        return 0
    try:
        return float(s)
    except ValueError:
        return 0


def get_week_label(year, month, day):
    """날짜로부터 ISO 주차(월요일 기준) 라벨 생성"""
    try:
        d = datetime(int(year), int(month), int(day))
        iso = d.isocalendar()
        # 해당 주의 월요일 ~ 일요일 구하기
        monday = d - timedelta(days=d.weekday())
        sunday = monday + timedelta(days=6)
        return f"W{iso[1]:02d} ({monday.strftime('%m/%d')}~{sunday.strftime('%m/%d')})"
    except:
        return None


def read_brand_data(spreadsheet, brand_name):
    """브랜드 시트에서 일별 데이터를 읽어 주간 단위로 집계"""

    ws = spreadsheet.worksheet(brand_name)
    rows = ws.get_all_values()

    if len(rows) < 2:
        return []

    header = rows[0]
    data_rows = rows[1:]

    # 주간별 데이터 집계
    weekly = defaultdict(lambda: {
        "days": 0,
        "비용": 0, "노출": 0, "클릭": 0, "진성DB": 0,
        "dates": [],
        "특이사항": [],
    })

    for row in data_rows:
        if len(row) < 14:
            continue

        year, month, day = row[0], row[1], row[2]
        if not year or not month or not day:
            continue

        week_label = get_week_label(year, month, day)
        if not week_label:
            continue

        cost = to_num(row[6])      # 비용(일)
        impressions = to_num(row[7])  # 노출(일)
        clicks = to_num(row[8])    # 클릭(일)
        db = to_num(row[5])        # 진성DB

        if cost == 0 and impressions == 0 and clicks == 0:
            continue  # 빈 행 스킵

        w = weekly[week_label]
        w["days"] += 1
        w["비용"] += cost
        w["노출"] += impressions
        w["클릭"] += clicks
        w["진성DB"] += db
        w["dates"].append(f"{month}/{day}")

        # 특이사항
        if len(row) > 14 and row[14].strip():
            w["특이사항"].append(f"{month}/{day}: {row[14].strip()}")

    # 주간 지표 계산
    result = []
    for week_label in sorted(weekly.keys()):
        w = weekly[week_label]
        cost = w["비용"]
        impressions = w["노출"]
        clicks = w["클릭"]
        db = w["진성DB"]

        cpm = (cost / impressions * 1000) if impressions > 0 else 0
        cpc = (cost / clicks) if clicks > 0 else 0
        ctr = (clicks / impressions * 100) if impressions > 0 else 0
        cpa = (cost / db) if db > 0 else 0

        result.append({
            "주차": week_label,
            "운영일수": w["days"],
            "비용": round(cost),
            "노출": round(impressions),
            "클릭": round(clicks),
            "진성DB": round(db),
            "CPM": round(cpm),
            "CPC": round(cpc),
            "CTR": round(ctr, 2),
            "CPA": round(cpa),
            "특이사항": w["특이사항"],
        })

    return result


# ============================================================
# 3. 주간 추이 분석 & 인사이트 추출
# ============================================================
def analyze_trend(weekly_data):
    """전주 대비 변화율 계산 + 인사이트 추출"""

    if len(weekly_data) < 2:
        return None

    curr = weekly_data[-1]
    prev = weekly_data[-2]

    metrics = {
        "비용": {"좋은방향": "lower", "단위": "원"},
        "노출": {"좋은방향": "higher", "단위": "회"},
        "클릭": {"좋은방향": "higher", "단위": "회"},
        "진성DB": {"좋은방향": "higher", "단위": "건"},
        "CPM": {"좋은방향": "lower", "단위": "원"},
        "CPC": {"좋은방향": "lower", "단위": "원"},
        "CTR": {"좋은방향": "higher", "단위": "%"},
        "CPA": {"좋은방향": "lower", "단위": "원"},
    }

    changes = {}
    good_points = []
    bad_points = []

    for key, meta in metrics.items():
        c_val = curr[key]
        p_val = prev[key]

        if p_val == 0:
            pct = 0
        else:
            pct = round((c_val - p_val) / p_val * 100, 1)

        changes[key] = {"현재": c_val, "전주": p_val, "변화율": pct}

        is_good = (
            (meta["좋은방향"] == "lower" and pct < 0) or
            (meta["좋은방향"] == "higher" and pct > 0)
        )

        if abs(pct) >= 5:
            if is_good:
                good_points.append((key, pct, meta))
            else:
                bad_points.append((key, pct, meta))

    return {
        "현재주차": curr,
        "전주": prev,
        "changes": changes,
        "good": good_points,
        "bad": bad_points,
    }


# ============================================================
# 4. 리포트 텍스트 생성
# ============================================================
def generate_report(brand_name, weekly_data, analysis):
    """고객사용 주간 리포트 생성 - 카톡/슬랙 복붙용 실무 스타일"""

    lines = []
    curr = analysis["현재주차"]
    prev = analysis["전주"]
    changes = analysis["changes"]

    # 주차 날짜 범위 추출 (예: W12 (03/16~03/22) → 3/16~3/22)
    week_label = curr["주차"]
    date_range = week_label.split("(")[1].rstrip(")") if "(" in week_label else ""

    # ── 인사 & 제목 ──
    lines.append(f"안녕하세요, {brand_name} 전주 광고데이터 공유드립니다.")
    lines.append("")

    # ── 1. 전주 데이터 ──
    lines.append(f"📊 전주 데이터 (*{date_range})")
    lines.append(f"- 지출 비용 : {curr['비용']:,}원")
    lines.append(f"- CTR : {curr['CTR']}%")
    lines.append(f"- CPC : {curr['CPC']:,}원")
    lines.append(f"- DB : {curr['진성DB']}건")
    if curr['진성DB'] > 0:
        prev_cpa = prev['CPA'] if prev['진성DB'] > 0 else 0
        if prev_cpa > 0:
            lines.append(f"- CPA (전환당 비용) : {curr['CPA']:,}원 (전주 {prev_cpa:,}원)")
        else:
            lines.append(f"- CPA (전환당 비용) : {curr['CPA']:,}원")
    else:
        lines.append(f"- CPA (전환당 비용) : DB 0건으로 산출 불가")
    lines.append("")

    # ── 2. 운영 인사이트 ──
    lines.append("🔍 운영 인사이트")

    insight_num = 1
    # 긍정적 변화 인사이트
    if analysis["good"]:
        for key, pct, meta in analysis["good"]:
            lines.append(f"① {_insight_good(key, pct, changes[key], curr, prev)}" if insight_num == 1
                        else f"② {_insight_good(key, pct, changes[key], curr, prev)}" if insight_num == 2
                        else f"③ {_insight_good(key, pct, changes[key], curr, prev)}")
            insight_num += 1
            if insight_num > 3:
                break

    # 부정적 변화도 인사이트로 (단, 원인 분석 형태로)
    if analysis["bad"] and insight_num <= 3:
        for key, pct, meta in analysis["bad"]:
            if key in ("비용",):  # 비용 증가는 운영일수 차이일 수 있으므로 스킵
                continue
            lines.append(f"② {_insight_bad(key, pct, changes[key], curr, prev)}" if insight_num == 2
                        else f"③ {_insight_bad(key, pct, changes[key], curr, prev)}")
            insight_num += 1
            if insight_num > 3:
                break

    if insight_num == 1:
        lines.append("① 전반적으로 전주와 유사한 수준을 유지하며 안정적으로 운영되었습니다.")

    lines.append("")

    # ── 3. 향후 운영 방향 ──
    lines.append("🚀 향후 운영 방향")
    strategies = _suggest_strategy_v2(analysis, curr, prev)
    markers = ["①", "②", "③"]
    for i, s in enumerate(strategies[:3]):
        lines.append(f"{markers[i]} {s}")
    lines.append("")

    # ── 4. 특이사항 ──
    if curr["특이사항"]:
        lines.append("📌 특이사항")
        for note in curr["특이사항"]:
            lines.append(f"• {note}")
        lines.append("")

    # ── 5. 주간 추이 테이블 (최근 4주) ──
    lines.append("📈 최근 주간 추이")
    recent = weekly_data[-4:] if len(weekly_data) >= 4 else weekly_data
    for w in recent:
        cpa_str = f"{w['CPA']:,}원" if w['진성DB'] > 0 else "-"
        lines.append(
            f"  {w['주차']}: 비용 {w['비용']:,}원 / DB {w['진성DB']}건 / "
            f"CPC {w['CPC']:,}원 / CTR {w['CTR']}% / CPA {cpa_str}"
        )

    return "\n".join(lines)


# ── 인사이트 설명 헬퍼 함수들 ──

def _explain_good(key, pct, change):
    """기존 호환용"""
    return _insight_good(key, pct, change, {}, {})


def _explain_bad(key, pct, change):
    """기존 호환용"""
    return _insight_bad(key, pct, change, {}, {})


def _insight_good(key, pct, change, curr, prev):
    """긍정 인사이트 - 마케터 실무 톤"""
    explains = {
        "비용": f"광고비 효율화 : 전주 대비 {abs(pct)}% 절감하면서도 핵심 성과 지표를 유지하고 있습니다.",
        "노출": f"노출 확대 : 노출수가 {abs(pct)}% 증가하여 더 많은 잠재 고객에게 브랜드가 도달하고 있습니다.",
        "클릭": f"클릭 반응 상승 : 클릭수가 {abs(pct)}% 증가했습니다. 현재 소재가 타겟 고객의 관심을 효과적으로 끌고 있습니다.",
        "진성DB": f"DB 확보 성과 향상 : 진성 DB가 {abs(pct)}% 증가했습니다. 전환 퍼널이 잘 작동하고 있으며, 실제 관심 있는 고객 유입이 늘었습니다.",
        "CPM": f"노출 단가 절감 : CPM이 {abs(pct)}% 감소하여 같은 예산으로 더 넓은 도달이 가능해졌습니다.",
        "CPC": f"클릭 단가 절감 : CPC가 전주 {change['전주']:,}원 → {change['현재']:,}원으로 {abs(pct)}% 감소했습니다. 소재 효율이 높아지고 있습니다.",
        "CTR": f"클릭률 개선 : CTR이 {change['전주']}% → {change['현재']}%로 상승했습니다. 광고 소재의 매력도가 높아지고 있습니다.",
        "CPA": f"전환 효율 개선 : CPA가 전주 {change['전주']:,}원 → {change['현재']:,}원으로 {abs(pct)}% 감소했습니다. 더 적은 비용으로 DB를 확보하고 있습니다.",
    }
    return explains.get(key, f"{key}가 긍정적으로 변화했습니다.")


def _insight_bad(key, pct, change, curr, prev):
    """부정 인사이트 - 원인 분석 + 해결 방향 제시"""
    explains = {
        "비용": f"비용 증가 모니터링 : 전주 대비 {abs(pct)}% 증가했으나, 성과 지표와 함께 종합적으로 판단이 필요합니다.",
        "노출": f"노출 감소 원인 파악 필요 : 노출수가 {abs(pct)}% 감소했습니다. 예산 소진 패턴이나 타겟 피로도를 점검하겠습니다.",
        "클릭": f"클릭 반응 둔화 : 클릭수가 {abs(pct)}% 감소했습니다. 소재 피로도가 생겼을 가능성이 있어 신규 소재 투입을 검토합니다.",
        "진성DB": f"DB 확보량 감소 : 진성 DB가 전주 대비 {abs(pct)}% 줄었습니다. 랜딩페이지 전환 동선과 폼 이탈률을 점검하겠습니다.",
        "CPM": f"경쟁 심화에 따른 CPM 상승 : CPM이 {abs(pct)}% 상승했습니다. 동일 타겟 내 경쟁 광고가 증가했을 수 있으며, 타겟 세분화로 대응하겠습니다.",
        "CPC": f"클릭 단가 상승 : CPC가 전주 {change['전주']:,}원 → {change['현재']:,}원으로 {abs(pct)}% 상승했습니다. 소재 교체와 타겟 최적화를 통해 단가를 낮추겠습니다.",
        "CTR": f"클릭률 하락 : CTR이 {change['전주']}% → {change['현재']}%로 하락했습니다. 소재에 대한 피로도가 생겼을 수 있어 새로운 크리에이티브를 테스트하겠습니다.",
        "CPA": f"전환 단가 상승 주의 : CPA가 전주 {change['전주']:,}원 → {change['현재']:,}원으로 {abs(pct)}% 상승했습니다. 전환 최적화 캠페인 세팅과 리타겟팅 비중 조정을 검토하겠습니다.",
    }
    return explains.get(key, f"{key}가 부정적으로 변화했습니다. 원인 분석 후 개선 방향을 제시하겠습니다.")


def _suggest_strategy(analysis):
    """기존 호환용"""
    return _suggest_strategy_v2(analysis, {}, {})


def _suggest_strategy_v2(analysis, curr, prev):
    """마케터 실무 톤의 전략 제안"""
    strategies = []
    bad_keys = [key for key, _, _ in analysis["bad"]]
    good_keys = [key for key, _, _ in analysis["good"]]

    # 긍정적 요소 강화 전략
    if "CPC" in good_keys or "CTR" in good_keys:
        strategies.append(
            "고효율 소재 베리에이션 : 현재 성과가 좋은 소재의 디자인 포맷을 다양화하여 "
            "소재 피로도를 낮추고 전환율을 유지하겠습니다."
        )

    if "CPA" in good_keys or "진성DB" in good_keys:
        strategies.append(
            "전환 캠페인 예산 확대 : 현재 DB 확보 효율이 좋으므로 전환 캠페인에 "
            "예산을 집중하여 DB 볼륨을 확대하겠습니다."
        )

    # 부정적 요소 개선 전략
    if "CPC" in bad_keys or "CTR" in bad_keys:
        strategies.append(
            "신규 소재 투입 및 A/B 테스트 : 소재 피로도를 해소하기 위해 "
            "새로운 컨셉의 크리에이티브를 제작하고 성과를 비교 테스트하겠습니다."
        )

    if "CPA" in bad_keys or "진성DB" in bad_keys:
        strategies.append(
            "전환 퍼널 최적화 : 랜딩페이지 CTA 위치, 폼 간소화, 로딩 속도를 점검하고 "
            "리타겟팅 비중을 높여 전환율을 개선하겠습니다."
        )

    if "CPM" in bad_keys:
        strategies.append(
            "타겟 오디언스 재설정 : 경쟁이 덜한 세그먼트를 발굴하고, "
            "유사 타겟(Lookalike) 확장으로 효율적인 노출을 확보하겠습니다."
        )

    if not strategies:
        strategies.append(
            "현재 전략 유지 + 소재 테스트 병행 : 전반적으로 안정적인 성과를 보이고 있어 "
            "기존 세팅을 유지하되, 더 높은 성과를 위해 새로운 소재 변형을 테스트하겠습니다."
        )
        strategies.append(
            "성과 데이터 기반 예산 재배분 : 요일/시간대별 성과를 분석하여 "
            "고효율 구간에 예산을 집중 배분하겠습니다."
        )

    return strategies


# ============================================================
# 5. 메인 실행
# ============================================================
def generate_report_v2_compact(brand_name, weekly_data, analysis):
    """시안 B: 간결한 카톡 공유용 (짧고 핵심만)"""

    lines = []
    curr = analysis["현재주차"]
    prev = analysis["전주"]
    changes = analysis["changes"]
    week_label = curr["주차"]
    date_range = week_label.split("(")[1].rstrip(")") if "(" in week_label else ""

    lines.append(f"[{brand_name}] 주간 광고 리포트 ({date_range})")
    lines.append("")
    lines.append(f"💰 비용 {curr['비용']:,}원")
    lines.append(f"📩 DB {curr['진성DB']}건 | CPA {curr['CPA']:,}원" if curr['진성DB'] > 0 else f"📩 DB 0건")
    lines.append(f"👆 CPC {curr['CPC']:,}원 | CTR {curr['CTR']}%")
    lines.append("")

    # 전주 비교 한줄 요약
    summary_parts = []
    for key, pct, _ in analysis["good"][:2]:
        summary_parts.append(f"{key} ↑{abs(pct)}%")
    for key, pct, _ in analysis["bad"][:2]:
        summary_parts.append(f"{key} ↓{abs(pct)}%" if pct < 0 else f"{key} ↑{abs(pct)}%")

    if summary_parts:
        lines.append(f"vs 전주: {' / '.join(summary_parts)}")
        lines.append("")

    # 핵심 한줄 인사이트
    if analysis["good"]:
        key, pct, _ = analysis["good"][0]
        lines.append(f"✅ {_insight_good(key, pct, changes[key], curr, prev)}")
    if analysis["bad"]:
        key, pct, _ = analysis["bad"][0]
        lines.append(f"⚠️ {_insight_bad(key, pct, changes[key], curr, prev)}")
    lines.append("")

    # 한줄 방향
    strategies = _suggest_strategy_v2(analysis, curr, prev)
    if strategies:
        lines.append(f"🚀 {strategies[0]}")

    return "\n".join(lines)


def generate_report_v3_detailed(brand_name, weekly_data, analysis):
    """시안 C: 상세 보고서형 (고객사 미팅/이메일용)"""

    lines = []
    curr = analysis["현재주차"]
    prev = analysis["전주"]
    changes = analysis["changes"]
    week_label = curr["주차"]
    date_range = week_label.split("(")[1].rstrip(")") if "(" in week_label else ""

    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  [{brand_name}] META 광고 주간 성과 보고서")
    lines.append(f"  리포트 기간: {date_range}")
    lines.append(f"  작성일: {datetime.now().strftime('%Y년 %m월 %d일')}")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    # 1. 성과 요약
    lines.append("1️⃣ 성과 요약")
    lines.append("┌─────────────────────────────────────┐")
    lines.append(f"│ 지출 비용  │ {curr['비용']:>12,}원          │")
    lines.append(f"│ 노출수     │ {curr['노출']:>12,}회          │")
    lines.append(f"│ 클릭수     │ {curr['클릭']:>12,}회          │")
    lines.append(f"│ 진성 DB    │ {curr['진성DB']:>12,}건          │")
    lines.append(f"│ CTR        │ {curr['CTR']:>11}%          │")
    lines.append(f"│ CPC        │ {curr['CPC']:>12,}원          │")
    lines.append(f"│ CPM        │ {curr['CPM']:>12,}원          │")
    cpa_val = f"{curr['CPA']:>12,}원" if curr['진성DB'] > 0 else "        산출불가"
    lines.append(f"│ CPA        │ {cpa_val}          │")
    lines.append("└─────────────────────────────────────┘")
    lines.append("")

    # 2. 전주 대비 변화
    lines.append("2️⃣ 전주 대비 변화")
    key_metrics = [
        ("비용", "지출 비용", "원"), ("진성DB", "진성 DB", "건"),
        ("CPC", "CPC", "원"), ("CTR", "CTR", "%"),
        ("CPM", "CPM", "원"), ("CPA", "CPA", "원"),
    ]
    for key, label, unit in key_metrics:
        c = changes[key]
        pct = c["변화율"]
        arrow = "▲" if pct > 0 else "▼" if pct < 0 else "─"
        sign = "+" if pct > 0 else ""
        if unit == "%":
            lines.append(f"  {arrow} {label}: {c['전주']}{unit} → {c['현재']}{unit} ({sign}{pct}%)")
        else:
            lines.append(f"  {arrow} {label}: {c['전주']:,}{unit} → {c['현재']:,}{unit} ({sign}{pct}%)")
    lines.append("")

    # 3. 인사이트
    lines.append("3️⃣ 운영 인사이트")
    insight_num = 1
    for key, pct, meta in analysis["good"][:2]:
        lines.append(f"  {insight_num}. ✅ {_insight_good(key, pct, changes[key], curr, prev)}")
        insight_num += 1
    for key, pct, meta in analysis["bad"][:2]:
        if key == "비용":
            continue
        lines.append(f"  {insight_num}. ⚠️ {_insight_bad(key, pct, changes[key], curr, prev)}")
        insight_num += 1
    if insight_num == 1:
        lines.append("  1. 전반적으로 안정적인 성과를 유지하고 있습니다.")
    lines.append("")

    # 4. 향후 운영 방향
    lines.append("4️⃣ 향후 운영 방향")
    strategies = _suggest_strategy_v2(analysis, curr, prev)
    for i, s in enumerate(strategies[:3], 1):
        lines.append(f"  {i}. {s}")
    lines.append("")

    # 5. 특이사항
    if curr["특이사항"]:
        lines.append("5️⃣ 특이사항")
        for note in curr["특이사항"]:
            lines.append(f"  • {note}")
        lines.append("")

    # 6. 주간 추이
    lines.append("6️⃣ 주간 추이")
    for w in weekly_data:
        cpa_str = f"CPA {w['CPA']:,}원" if w['진성DB'] > 0 else "CPA -"
        lines.append(
            f"  {w['주차']}"
        )
        lines.append(
            f"    비용 {w['비용']:,}원 / DB {w['진성DB']}건 / "
            f"CPC {w['CPC']:,}원 / CTR {w['CTR']}% / {cpa_str}"
        )
    lines.append("")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"  CrowedSlave 자동 리포트")
    lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# ============================================================
# 5. 메인 실행
# ============================================================
def main():
    print("\n🚀 메타 광고 주간 리포트 봇 시작!\n")

    spreadsheet = connect()
    print("✅ 구글 스프레드시트 연결 완료\n")

    brand = "뵈르뵈르"

    print(f"📊 [{brand}] 데이터를 읽는 중...")
    weekly_data = read_brand_data(spreadsheet, brand)

    if not weekly_data:
        print("❌ 데이터가 없습니다.")
        return

    print(f"✅ {len(weekly_data)}주차 데이터 수집 완료\n")

    analysis = analyze_trend(weekly_data)
    if not analysis:
        print("❌ 분석에는 최소 2주 데이터가 필요합니다.")
        return

    # ── 3가지 시안 출력 ──
    print("=" * 60)
    print("  📋 시안 A: 실무 공유용 (카톡/슬랙)")
    print("=" * 60)
    report_a = generate_report(brand, weekly_data, analysis)
    print(report_a)

    print("\n\n")
    print("=" * 60)
    print("  📋 시안 B: 간결 요약형 (빠른 공유용)")
    print("=" * 60)
    report_b = generate_report_v2_compact(brand, weekly_data, analysis)
    print(report_b)

    print("\n\n")
    print("=" * 60)
    print("  📋 시안 C: 상세 보고서형 (미팅/이메일용)")
    print("=" * 60)
    report_c = generate_report_v3_detailed(brand, weekly_data, analysis)
    print(report_c)

    # 파일 저장
    today = datetime.now().strftime('%Y%m%d')
    for label, report in [("A_실무공유", report_a), ("B_간결요약", report_b), ("C_상세보고", report_c)]:
        filename = f"report_{brand}_{today}_{label}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report)
    print(f"\n📁 3개 시안 파일 저장 완료!")


if __name__ == "__main__":
    main()
