"""
메타 광고 주간 성과 분석 봇 - Google Sheets 연동
=================================================
구글 스프레드시트에서 메타 광고 데이터를 읽어와
주간별 성과 추이를 분석하고 리포트를 자동 생성합니다.
"""

import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
import os
from datetime import datetime

# ============================================================
# 1. 환경변수 로드
# ============================================================
load_dotenv()

GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
DATA_SHEET_NAME = os.getenv("DATA_SHEET_NAME", "메타광고_주간데이터")
REPORT_SHEET_NAME = os.getenv("REPORT_SHEET_NAME", "주간리포트")


# ============================================================
# 2. Google Sheets 연결
# ============================================================
def connect_google_sheets():
    """Google Sheets API 연결"""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    try:
        creds = Credentials.from_service_account_file(
            GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        print("✅ Google Sheets 연결 성공!")
        return spreadsheet
    except FileNotFoundError:
        print("❌ credentials.json 파일을 찾을 수 없습니다.")
        print("   → google_sheets_setup.md 가이드를 참고해서 서비스 계정 키를 다운로드하세요.")
        return None
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return None


# ============================================================
# 3. 데이터 읽기
# ============================================================
def read_weekly_data(spreadsheet):
    """스프레드시트에서 주간 광고 데이터 읽기"""

    try:
        sheet = spreadsheet.worksheet(DATA_SHEET_NAME)
        all_data = sheet.get_all_records()

        if not all_data:
            print("⚠️ 데이터가 비어있습니다. 스프레드시트에 데이터를 먼저 입력해주세요.")
            return []

        print(f"📊 총 {len(all_data)}주차 데이터를 불러왔습니다.")
        return all_data

    except gspread.exceptions.WorksheetNotFound:
        print(f"❌ '{DATA_SHEET_NAME}' 시트를 찾을 수 없습니다.")
        print(f"   → 스프레드시트에 '{DATA_SHEET_NAME}' 이름의 시트를 만들어주세요.")
        return []


# ============================================================
# 4. 주간 성과 분석
# ============================================================
def analyze_weekly_performance(data):
    """주간 성과를 분석하고 인사이트 추출"""

    if len(data) < 2:
        return {
            "current": data[-1] if data else {},
            "changes": {},
            "insights": ["데이터가 2주 이상 필요합니다. 다음 주부터 비교 분석이 가능합니다."],
            "improvements": [],
        }

    current = data[-1]   # 이번 주
    previous = data[-2]  # 지난 주

    # ---- 주요 지표 변화율 계산 ----
    metrics = {
        "광고비(원)": {"direction": "lower", "label": "광고비"},
        "CPC": {"direction": "lower", "label": "클릭당 비용(CPC)"},
        "CTR(%)": {"direction": "higher", "label": "클릭률(CTR)"},
        "CPM": {"direction": "lower", "label": "노출 비용(CPM)"},
        "CPA": {"direction": "lower", "label": "전환당 비용(CPA)"},
        "ROAS(%)": {"direction": "higher", "label": "광고 수익률(ROAS)"},
        "전환수": {"direction": "higher", "label": "전환수"},
        "클릭수": {"direction": "higher", "label": "클릭수"},
        "노출수": {"direction": "higher", "label": "노출수"},
    }

    changes = {}
    insights = []
    improvements = []

    for key, meta in metrics.items():
        cur_val = _to_number(current.get(key, 0))
        prev_val = _to_number(previous.get(key, 0))

        if prev_val == 0:
            change_pct = 0
        else:
            change_pct = round((cur_val - prev_val) / prev_val * 100, 1)

        changes[key] = {
            "current": cur_val,
            "previous": prev_val,
            "change_pct": change_pct,
            "label": meta["label"],
            "direction": meta["direction"],
        }

        # ---- 인사이트 & 개선점 추출 ----
        is_good = (
            (meta["direction"] == "lower" and change_pct < 0) or
            (meta["direction"] == "higher" and change_pct > 0)
        )

        if abs(change_pct) >= 10:  # 10% 이상 변동 시 주목
            if is_good:
                insights.append(
                    f"✅ {meta['label']}이(가) 전주 대비 {abs(change_pct)}% {'감소' if change_pct < 0 else '증가'}했습니다. "
                    f"긍정적인 변화입니다!"
                )
            else:
                insights.append(
                    f"⚠️ {meta['label']}이(가) 전주 대비 {abs(change_pct)}% {'증가' if change_pct > 0 else '감소'}했습니다. "
                    f"주의가 필요합니다."
                )
                improvements.append(_suggest_improvement(key, change_pct))

    return {
        "current": current,
        "previous": previous,
        "changes": changes,
        "insights": insights if insights else ["이번 주는 전반적으로 안정적인 성과를 유지했습니다."],
        "improvements": improvements,
    }


def _to_number(val):
    """문자열/숫자를 숫자로 변환 (쉼표 포함 처리)"""
    if isinstance(val, (int, float)):
        return val
    try:
        return float(str(val).replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return 0


def _suggest_improvement(metric_key, change_pct):
    """지표별 개선 방향 제안"""

    suggestions = {
        "CPC": (
            "💡 클릭당 비용 개선 방안:\n"
            "   - 광고 소재(이미지/영상)를 새롭게 교체해보세요\n"
            "   - 타겟 오디언스를 좀 더 세분화해서 관심도 높은 고객에게 노출해보세요\n"
            "   - 광고 문구의 CTA(행동유도)를 더 명확하게 수정해보세요"
        ),
        "CTR(%)": (
            "💡 클릭률 개선 방안:\n"
            "   - 광고 첫 3초 안에 시선을 사로잡는 소재로 변경해보세요\n"
            "   - 혜택(할인/무료배송 등)을 광고 상단에 배치해보세요\n"
            "   - A/B 테스트로 어떤 소재가 더 클릭이 높은지 비교해보세요"
        ),
        "CPA": (
            "💡 전환당 비용 개선 방안:\n"
            "   - 랜딩페이지(도착 페이지)의 구매 동선을 점검해보세요\n"
            "   - 리타겟팅(재방문 고객) 광고 비중을 늘려보세요\n"
            "   - 전환이 잘 나오는 시간대에 예산을 집중 배분해보세요"
        ),
        "CPM": (
            "💡 노출 비용 개선 방안:\n"
            "   - 경쟁이 덜한 시간대나 타겟으로 변경을 검토해보세요\n"
            "   - 광고 품질 점수를 높이기 위해 소재 관련성을 개선해보세요\n"
            "   - 자동 입찰 전략을 검토해보세요"
        ),
        "ROAS(%)": (
            "💡 광고 수익률 개선 방안:\n"
            "   - 객단가가 높은 상품 위주로 광고를 집중해보세요\n"
            "   - 구매 전환이 높은 오디언스 세그먼트에 예산을 재배분해보세요\n"
            "   - 교차판매/업셀링 전략을 랜딩페이지에 추가해보세요"
        ),
        "전환수": (
            "💡 전환수 개선 방안:\n"
            "   - 전환 캠페인의 픽셀/이벤트 설정이 정상인지 점검해보세요\n"
            "   - 프로모션이나 한정 혜택을 활용해서 구매를 유도해보세요\n"
            "   - 유사 타겟(Lookalike) 오디언스를 활용해보세요"
        ),
        "클릭수": (
            "💡 클릭수 개선 방안:\n"
            "   - 노출 대비 클릭이 낮다면 소재 매력도를 점검해보세요\n"
            "   - 새로운 광고 포맷(릴스, 캐러셀 등)을 시도해보세요"
        ),
        "노출수": (
            "💡 노출수 개선 방안:\n"
            "   - 예산이 일찍 소진되고 있지 않은지 확인해보세요\n"
            "   - 타겟 범위가 너무 좁지 않은지 점검해보세요"
        ),
        "광고비(원)": (
            "💡 예산 관리 방안:\n"
            "   - 성과가 좋은 캠페인에 예산을 집중해보세요\n"
            "   - 비효율 캠페인은 과감하게 중단하거나 축소해보세요"
        ),
    }

    return suggestions.get(metric_key, "💡 해당 지표를 모니터링하며 원인을 분석해보세요.")


# ============================================================
# 5. 리포트 텍스트 생성
# ============================================================
def generate_report_text(analysis):
    """고객사에 전달할 주간 리포트 텍스트 생성"""

    current = analysis["current"]
    changes = analysis["changes"]
    insights = analysis["insights"]
    improvements = analysis["improvements"]

    week = current.get("주차", "이번 주")
    date = current.get("날짜", datetime.now().strftime("%Y-%m-%d"))

    # ---- 리포트 본문 ----
    report = []
    report.append(f"{'='*50}")
    report.append(f"📊 메타 광고 주간 성과 리포트")
    report.append(f"📅 {date} ({week})")
    report.append(f"{'='*50}")
    report.append("")

    # 핵심 요약
    report.append("■ 이번 주 핵심 요약")
    report.append("-" * 40)

    ad_spend = _to_number(current.get("광고비(원)", 0))
    revenue = _to_number(current.get("매출(원)", 0))
    conversions = _to_number(current.get("전환수", 0))
    roas = _to_number(current.get("ROAS(%)", 0))

    report.append(f"  💰 광고비: {ad_spend:,.0f}원")
    report.append(f"  📈 매출: {revenue:,.0f}원")
    report.append(f"  🛒 전환(구매): {conversions:.0f}건")
    report.append(f"  📊 광고 수익률(ROAS): {roas:.0f}%")
    report.append("")

    # 쉬운 해석
    if roas >= 300:
        report.append(f"  → 광고비 대비 {roas/100:.1f}배의 매출을 만들어냈습니다. 효율 좋습니다! 👍")
    elif roas >= 200:
        report.append(f"  → 광고비 대비 {roas/100:.1f}배의 매출입니다. 보통 수준이며, 개선 여지가 있습니다.")
    else:
        report.append(f"  → 광고비 대비 {roas/100:.1f}배 매출로, 효율 개선이 필요합니다. 🔧")
    report.append("")

    # 주요 지표 변화
    report.append("■ 전주 대비 주요 변화")
    report.append("-" * 40)

    key_metrics = ["CPC", "CTR(%)", "CPA", "CPM", "ROAS(%)"]
    for key in key_metrics:
        if key in changes:
            c = changes[key]
            arrow = "📈" if c["change_pct"] > 0 else "📉" if c["change_pct"] < 0 else "➡️"
            report.append(
                f"  {arrow} {c['label']}: {c['previous']:,.0f} → {c['current']:,.0f} "
                f"({'+' if c['change_pct'] > 0 else ''}{c['change_pct']}%)"
            )
    report.append("")

    # 인사이트
    report.append("■ 이번 주 인사이트")
    report.append("-" * 40)
    for insight in insights:
        report.append(f"  {insight}")
    report.append("")

    # 개선 방향
    if improvements:
        report.append("■ 다음 주 개선 방향")
        report.append("-" * 40)
        for imp in improvements:
            report.append(f"  {imp}")
        report.append("")

    # 마무리
    report.append("■ 담당자 코멘트")
    report.append("-" * 40)
    if improvements:
        report.append("  위 분석 결과를 바탕으로, 다음 주에는 부족한 지표를")
        report.append("  집중 개선하겠습니다. 특히 소재 최적화와 타겟 세분화에")
        report.append("  중점을 두고 운영할 예정입니다.")
    else:
        report.append("  전반적으로 안정적인 성과를 유지하고 있습니다.")
        report.append("  현재 전략을 유지하되, 더 높은 성과를 위해")
        report.append("  새로운 소재 테스트를 병행하겠습니다.")
    report.append("")
    report.append(f"{'='*50}")
    report.append("CrowedSlave 자동 리포트 시스템")
    report.append(f"{'='*50}")

    return "\n".join(report)


# ============================================================
# 6. 리포트를 스프레드시트에 저장
# ============================================================
def save_report_to_sheet(spreadsheet, analysis, report_text):
    """생성된 리포트를 '주간리포트' 시트에 저장"""

    try:
        # 시트가 없으면 새로 생성
        try:
            report_sheet = spreadsheet.worksheet(REPORT_SHEET_NAME)
        except gspread.exceptions.WorksheetNotFound:
            report_sheet = spreadsheet.add_worksheet(
                title=REPORT_SHEET_NAME, rows=100, cols=5
            )
            # 헤더 추가
            report_sheet.update("A1:E1", [["주차", "생성일", "리포트내용", "핵심인사이트", "개선방향"]])
            print(f"📝 '{REPORT_SHEET_NAME}' 시트를 새로 만들었습니다.")

        current = analysis["current"]
        week = current.get("주차", "")
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        insights_text = "\n".join(analysis["insights"])
        improvements_text = "\n".join(analysis["improvements"]) if analysis["improvements"] else "현재 전략 유지"

        # 다음 빈 행에 추가
        next_row = len(report_sheet.get_all_values()) + 1
        report_sheet.update(
            f"A{next_row}:E{next_row}",
            [[week, today, report_text, insights_text, improvements_text]]
        )

        print(f"✅ 리포트가 '{REPORT_SHEET_NAME}' 시트에 저장되었습니다! (행 {next_row})")
        return True

    except Exception as e:
        print(f"❌ 리포트 저장 실패: {e}")
        return False


# ============================================================
# 7. 메인 실행
# ============================================================
def main():
    print("\n🚀 메타 광고 주간 리포트 봇을 시작합니다...\n")

    # .env 파일 확인
    if not SPREADSHEET_ID or SPREADSHEET_ID == "여기에_스프레드시트_ID를_붙여넣으세요":
        print("❌ .env 파일에 SPREADSHEET_ID를 설정해주세요!")
        print("   → .env.example 파일을 .env로 복사한 후 값을 채워주세요.")
        print("   → cp .env.example .env")
        return

    # Step 1: Google Sheets 연결
    spreadsheet = connect_google_sheets()
    if not spreadsheet:
        return

    # Step 2: 데이터 읽기
    data = read_weekly_data(spreadsheet)
    if not data:
        return

    # Step 3: 분석
    print("\n🔍 주간 성과를 분석중입니다...\n")
    analysis = analyze_weekly_performance(data)

    # Step 4: 리포트 생성
    report_text = generate_report_text(analysis)
    print(report_text)

    # Step 5: 리포트를 스프레드시트에 저장
    print("\n💾 리포트를 스프레드시트에 저장합니다...\n")
    save_report_to_sheet(spreadsheet, analysis, report_text)

    print("\n🎉 완료! 스프레드시트에서 리포트를 확인해보세요.")


if __name__ == "__main__":
    main()
