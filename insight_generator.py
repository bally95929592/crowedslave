"""
마케팅 인사이트 자동 생성 모듈

광고 성과 데이터를 분석하여 한국어 마케팅 인사이트를 자동으로 생성합니다.
대시보드 및 주간 리포트에서 활용할 수 있도록 JSON 형식으로 출력합니다.
"""

from datetime import datetime, timedelta
from typing import Any


# ──────────────────────────────────────────────
# 유틸리티 함수
# ──────────────────────────────────────────────

def _원(value: float) -> str:
    """금액을 원화 형식으로 변환합니다."""
    if value >= 1_000_000:
        return f"{value / 10_000:,.0f}만원"
    return f"{value:,.0f}원"


def _퍼센트(value: float) -> str:
    """비율을 퍼센트 문자열로 변환합니다."""
    return f"{value:.2f}%"


def _변화율(current: float, previous: float) -> tuple[float, str]:
    """이전 대비 변화율을 계산하고 방향 표시를 반환합니다."""
    if previous == 0:
        return 0.0, "→"
    rate = ((current - previous) / previous) * 100
    if rate > 0:
        direction = "▲"
    elif rate < 0:
        direction = "▼"
    else:
        direction = "→"
    return rate, direction


def _안전_나누기(numerator: float, denominator: float, default: float = 0.0) -> float:
    """0으로 나누기를 방지하는 안전한 나눗셈입니다."""
    if denominator == 0:
        return default
    return numerator / denominator


def _집계(ads_data: list[dict], key: str) -> float:
    """광고 데이터 리스트에서 특정 키의 합계를 구합니다."""
    return sum(ad.get(key, 0) for ad in ads_data)


def _평균(ads_data: list[dict], key: str) -> float:
    """광고 데이터 리스트에서 특정 키의 평균을 구합니다."""
    values = [ad.get(key, 0) for ad in ads_data if ad.get(key) is not None]
    return _안전_나누기(sum(values), len(values))


# ──────────────────────────────────────────────
# Type A: 성과 요약 인사이트
# ──────────────────────────────────────────────

def generate_summary_insight(current_data: list[dict], previous_data: list[dict]) -> str:
    """
    성과 요약 인사이트를 생성합니다.

    현재 기간과 이전 기간의 광고 데이터를 비교하여
    총 지출, 평균 CPA, CPC, CTR, 전환수 등 핵심 지표를 요약합니다.

    매개변수:
        current_data: 현재 기간 광고 데이터 (리스트 of dict)
            각 dict에는 spend, impressions, clicks, conversions, ad_name 키가 포함됩니다.
        previous_data: 이전 기간 광고 데이터 (같은 형식)

    반환값:
        한국어로 작성된 성과 요약 문자열
    """
    # 현재 기간 지표 계산
    총지출 = _집계(current_data, "spend")
    총노출 = _집계(current_data, "impressions")
    총클릭 = _집계(current_data, "clicks")
    총전환 = _집계(current_data, "conversions")

    평균CPA = _안전_나누기(총지출, 총전환)
    평균CPC = _안전_나누기(총지출, 총클릭)
    CTR = _안전_나누기(총클릭, 총노출) * 100

    # 이전 기간 지표 계산
    이전_총지출 = _집계(previous_data, "spend")
    이전_총전환 = _집계(previous_data, "conversions")
    이전_총클릭 = _집계(previous_data, "clicks")
    이전_총노출 = _집계(previous_data, "impressions")

    이전_CPA = _안전_나누기(이전_총지출, 이전_총전환)
    이전_CPC = _안전_나누기(이전_총지출, 이전_총클릭)
    이전_CTR = _안전_나누기(이전_총클릭, 이전_총노출) * 100

    # 변화율 계산
    지출_변화, 지출_방향 = _변화율(총지출, 이전_총지출)
    CPA_변화, CPA_방향 = _변화율(평균CPA, 이전_CPA)
    CPC_변화, CPC_방향 = _변화율(평균CPC, 이전_CPC)
    CTR_변화, CTR_방향 = _변화율(CTR, 이전_CTR)
    전환_변화, 전환_방향 = _변화율(총전환, 이전_총전환)

    # 최고/최저 소재 찾기
    최고소재 = min(current_data, key=lambda x: _안전_나누기(x.get("spend", 0), x.get("conversions", 1), float("inf"))) if current_data else None
    최저소재 = max(current_data, key=lambda x: _안전_나누기(x.get("spend", 0), max(x.get("conversions", 1), 1))) if current_data else None

    lines = []
    lines.append("📊 성과 요약")
    lines.append("")
    lines.append(f"  총 광고비: {_원(총지출)} ({지출_방향} 전기 대비 {abs(지출_변화):.1f}%)")
    lines.append(f"  전환 건수: {총전환:,.0f}건 ({전환_방향} 전기 대비 {abs(전환_변화):.1f}%)")
    lines.append(f"  평균 CPA: {_원(평균CPA)} ({CPA_방향} 전기 대비 {abs(CPA_변화):.1f}%)")
    lines.append(f"  평균 CPC: {_원(평균CPC)} ({CPC_방향} 전기 대비 {abs(CPC_변화):.1f}%)")
    lines.append(f"  CTR: {_퍼센트(CTR)} ({CTR_방향} 전기 대비 {abs(CTR_변화):.1f}%)")
    lines.append("")

    if 최고소재:
        최고CPA = _안전_나누기(최고소재.get("spend", 0), 최고소재.get("conversions", 1))
        lines.append(f"  🏆 최고 성과 소재: {최고소재.get('ad_name', '알 수 없음')} (CPA {_원(최고CPA)})")

    if 최저소재 and 최저소재 != 최고소재:
        최저CPA = _안전_나누기(최저소재.get("spend", 0), max(최저소재.get("conversions", 1), 1))
        lines.append(f"  ⚠️ 개선 필요 소재: {최저소재.get('ad_name', '알 수 없음')} (CPA {_원(최저CPA)})")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Type B: 소재 분석 인사이트
# ──────────────────────────────────────────────

def generate_creative_insight(ads_data: list[dict], appeal_analysis: dict | None = None) -> str:
    """
    소재 분석 인사이트를 생성합니다.

    성과 상위/하위 소재의 공통 요소를 분석하고
    새로운 소재 제작 방향을 추천합니다.

    매개변수:
        ads_data: 광고 소재별 성과 데이터
            각 dict에는 ad_name, spend, conversions, clicks, impressions,
            그리고 선택적으로 appeal, format, target_audience 키가 포함됩니다.
        appeal_analysis: 소구점 분석 데이터 (선택)
            키: 소구점 이름, 값: dict with avg_cpa, count 등

    반환값:
        한국어로 작성된 소재 분석 문자열
    """
    if not ads_data:
        return "📎 소재 분석\n\n  분석할 소재 데이터가 없습니다."

    # CPA 기준으로 소재 정렬
    소재_성과 = []
    for ad in ads_data:
        cpa = _안전_나누기(ad.get("spend", 0), max(ad.get("conversions", 0), 1), float("inf"))
        ctr = _안전_나누기(ad.get("clicks", 0), max(ad.get("impressions", 1), 1)) * 100
        소재_성과.append({**ad, "_cpa": cpa, "_ctr": ctr})

    소재_성과.sort(key=lambda x: x["_cpa"])

    # 상위/하위 분리 (상위 30%, 하위 30%)
    구분점 = max(1, len(소재_성과) // 3)
    TOP소재 = 소재_성과[:구분점]
    LOW소재 = 소재_성과[-구분점:]

    lines = []
    lines.append("📎 소재 분석")
    lines.append("")

    # TOP 소재 공통 요소
    lines.append("  ✅ 성과 좋은 소재 (TOP)")
    for ad in TOP소재[:5]:
        lines.append(f"    - {ad.get('ad_name', '?')}: CPA {_원(ad['_cpa'])}, CTR {_퍼센트(ad['_ctr'])}")

    top_appeals = _공통요소_추출(TOP소재, "appeal")
    top_formats = _공통요소_추출(TOP소재, "format")
    if top_appeals:
        lines.append(f"    → 공통 소구점: {', '.join(top_appeals)}")
    if top_formats:
        lines.append(f"    → 공통 형식: {', '.join(top_formats)}")

    lines.append("")

    # LOW 소재 공통 요소
    lines.append("  ❌ 성과 부진 소재 (LOW)")
    for ad in LOW소재[:5]:
        lines.append(f"    - {ad.get('ad_name', '?')}: CPA {_원(ad['_cpa'])}, CTR {_퍼센트(ad['_ctr'])}")

    low_appeals = _공통요소_추출(LOW소재, "appeal")
    low_formats = _공통요소_추출(LOW소재, "format")
    if low_appeals:
        lines.append(f"    → 공통 소구점: {', '.join(low_appeals)}")
    if low_formats:
        lines.append(f"    → 공통 형식: {', '.join(low_formats)}")

    lines.append("")

    # 소구점 분석이 있을 경우 추가
    if appeal_analysis:
        lines.append("  📊 소구점별 성과")
        정렬된_소구 = sorted(appeal_analysis.items(), key=lambda x: x[1].get("avg_cpa", float("inf")))
        for 소구점, 데이터 in 정렬된_소구[:5]:
            avg_cpa = 데이터.get("avg_cpa", 0)
            count = 데이터.get("count", 0)
            lines.append(f"    - {소구점}: 평균 CPA {_원(avg_cpa)} ({count}개 소재)")
        lines.append("")

    # 새 소재 추천
    lines.append("  💡 새 소재 제작 추천")
    if top_appeals:
        lines.append(f"    - '{top_appeals[0]}' 소구점을 활용한 새 소재 제작을 추천드립니다.")
    if top_formats:
        lines.append(f"    - '{top_formats[0]}' 형식이 좋은 성과를 보이고 있습니다.")
    if low_appeals:
        lines.append(f"    - '{low_appeals[0]}' 소구점은 성과가 낮으니 다른 방향을 시도해보세요.")

    return "\n".join(lines)


def _공통요소_추출(ads: list[dict], key: str) -> list[str]:
    """소재 리스트에서 특정 키의 공통 요소를 빈도순으로 추출합니다."""
    요소_카운트: dict[str, int] = {}
    for ad in ads:
        value = ad.get(key)
        if value:
            if isinstance(value, list):
                for v in value:
                    요소_카운트[str(v)] = 요소_카운트.get(str(v), 0) + 1
            else:
                요소_카운트[str(value)] = 요소_카운트.get(str(value), 0) + 1

    정렬 = sorted(요소_카운트.items(), key=lambda x: x[1], reverse=True)
    return [item[0] for item in 정렬]


# ──────────────────────────────────────────────
# Type C: 개선방안 인사이트
# ──────────────────────────────────────────────

def generate_improvement_insight(ads_data: list[dict]) -> str:
    """
    개선방안 인사이트를 생성합니다.

    CPA가 평균보다 높은 소재의 OFF 추천, 예산 재배분,
    신규 소재 방향, 타겟 최적화 방안을 제시합니다.

    매개변수:
        ads_data: 광고 소재별 성과 데이터
            각 dict에는 ad_name, spend, conversions, clicks, impressions,
            선택적으로 target_audience, appeal 키가 포함됩니다.

    반환값:
        한국어로 작성된 개선방안 문자열
    """
    if not ads_data:
        return "🔧 개선방안\n\n  분석할 데이터가 없습니다."

    # 전체 평균 CPA 계산
    총지출 = _집계(ads_data, "spend")
    총전환 = _집계(ads_data, "conversions")
    평균CPA = _안전_나누기(총지출, 총전환)

    # 소재별 CPA 계산
    소재_성과 = []
    for ad in ads_data:
        cpa = _안전_나누기(ad.get("spend", 0), max(ad.get("conversions", 0), 1), float("inf"))
        소재_성과.append({**ad, "_cpa": cpa})

    CPA_기준 = 평균CPA * 1.3

    # OFF 추천 소재 (CPA가 평균의 1.3배 초과)
    OFF_소재 = [ad for ad in 소재_성과 if ad["_cpa"] > CPA_기준]
    ON_소재 = [ad for ad in 소재_성과 if ad["_cpa"] <= CPA_기준]

    ON_소재.sort(key=lambda x: x["_cpa"])
    OFF_소재.sort(key=lambda x: x["_cpa"], reverse=True)

    lines = []
    lines.append("🔧 개선방안")
    lines.append("")

    # 1. OFF 추천
    lines.append(f"  🚫 OFF 추천 소재 (CPA > {_원(CPA_기준)}, 평균의 1.3배 초과)")
    if OFF_소재:
        OFF_총예산 = sum(ad.get("spend", 0) for ad in OFF_소재)
        for ad in OFF_소재:
            lines.append(f"    - {ad.get('ad_name', '?')}: CPA {_원(ad['_cpa'])} / 지출 {_원(ad.get('spend', 0))}")
        lines.append(f"    → 절감 가능 예산: {_원(OFF_총예산)}")
    else:
        lines.append("    - CPA가 기준을 초과하는 소재가 없습니다. 전반적으로 양호합니다.")
    lines.append("")

    # 2. 예산 재배분 추천
    lines.append("  💰 예산 재배분 추천")
    if ON_소재 and OFF_소재:
        OFF_총예산 = sum(ad.get("spend", 0) for ad in OFF_소재)
        재배분_소재수 = min(3, len(ON_소재))
        소재당_추가 = _안전_나누기(OFF_총예산, 재배분_소재수)
        for ad in ON_소재[:재배분_소재수]:
            현재예산 = ad.get("spend", 0)
            lines.append(
                f"    - {ad.get('ad_name', '?')}: "
                f"현재 {_원(현재예산)} → 추천 {_원(현재예산 + 소재당_추가)} "
                f"(+{_원(소재당_추가)})"
            )
        lines.append(f"    → OFF 소재 예산 {_원(OFF_총예산)}을 상위 소재에 재배분하면 전환 효율이 올라갑니다.")
    elif ON_소재:
        lines.append("    - 현재 예산 배분이 적절합니다. 큰 변경은 필요하지 않습니다.")
    lines.append("")

    # 3. 신규 소재 제안
    lines.append("  🎨 신규 소재 방향 제안")
    if ON_소재:
        best = ON_소재[0]
        best_appeal = best.get("appeal", "")
        best_format = best.get("format", "")
        lines.append(f"    - 최고 성과 소재 '{best.get('ad_name', '?')}'를 참고하세요.")
        if best_appeal:
            lines.append(f"    - 소구점 '{best_appeal}'을 변형한 새로운 소재를 테스트해보세요.")
        if best_format:
            lines.append(f"    - '{best_format}' 형식을 유지하면서 다른 메시지를 시도해보세요.")
        lines.append("    - 기존 성과 좋은 소재의 핵심 요소를 유지하되, 이미지나 카피를 변경해보세요.")
    lines.append("")

    # 4. 타겟 최적화
    lines.append("  🎯 타겟 최적화 제안")
    타겟별_전환 = _타겟별_성과(ads_data)
    if 타겟별_전환:
        정렬된_타겟 = sorted(타겟별_전환.items(), key=lambda x: x[1]["cpa"])
        best_target = 정렬된_타겟[0]
        lines.append(f"    - '{best_target[0]}' 타겟의 전환 효율이 가장 좋습니다 (CPA {_원(best_target[1]['cpa'])})")
        if len(정렬된_타겟) > 1:
            worst_target = 정렬된_타겟[-1]
            lines.append(f"    - '{worst_target[0]}' 타겟은 효율이 낮습니다 (CPA {_원(worst_target[1]['cpa'])})")
            lines.append(f"    → '{worst_target[0]}' 예산을 '{best_target[0]}'로 이동하는 것을 추천드립니다.")
    else:
        lines.append("    - 타겟 정보가 없어 별도 분석이 어렵습니다.")

    return "\n".join(lines)


def _타겟별_성과(ads_data: list[dict]) -> dict[str, dict]:
    """타겟 오디언스별 성과를 집계합니다."""
    타겟_데이터: dict[str, dict] = {}
    for ad in ads_data:
        target = ad.get("target_audience")
        if not target:
            continue
        if target not in 타겟_데이터:
            타겟_데이터[target] = {"spend": 0, "conversions": 0}
        타겟_데이터[target]["spend"] += ad.get("spend", 0)
        타겟_데이터[target]["conversions"] += ad.get("conversions", 0)

    결과 = {}
    for target, data in 타겟_데이터.items():
        결과[target] = {
            "spend": data["spend"],
            "conversions": data["conversions"],
            "cpa": _안전_나누기(data["spend"], max(data["conversions"], 1)),
        }
    return 결과


# ──────────────────────────────────────────────
# Type D: 기간 비교 인사이트
# ──────────────────────────────────────────────

def generate_comparison_insight(current_data: list[dict], previous_data: list[dict]) -> str:
    """
    기간 비교 인사이트를 생성합니다.

    현재 기간과 이전 기간을 비교하여 트렌드를 파악하고
    원인 분석을 제시합니다.

    매개변수:
        current_data: 현재 기간 광고 데이터
        previous_data: 이전 기간 광고 데이터

    반환값:
        한국어로 작성된 기간 비교 분석 문자열
    """
    # 지표 계산
    현재 = _기간_지표_계산(current_data)
    이전 = _기간_지표_계산(previous_data)

    lines = []
    lines.append("📅 기간 비교 분석")
    lines.append("")

    # 주요 지표 비교 테이블
    지표목록 = [
        ("광고비", "spend", _원, False),
        ("전환수", "conversions", lambda x: f"{x:,.0f}건", True),
        ("CPA", "cpa", _원, False),
        ("CPC", "cpc", _원, False),
        ("CTR", "ctr", _퍼센트, True),
        ("노출수", "impressions", lambda x: f"{x:,.0f}회", True),
        ("클릭수", "clicks", lambda x: f"{x:,.0f}회", True),
    ]

    lines.append("  지표          이전 기간      현재 기간      변화")
    lines.append("  " + "─" * 55)

    트렌드_개선 = []
    트렌드_악화 = []

    for 이름, key, formatter, 높을수록_좋음 in 지표목록:
        현재값 = 현재.get(key, 0)
        이전값 = 이전.get(key, 0)
        변화율, 방향 = _변화율(현재값, 이전값)

        # 개선/악화 판단
        if 높을수록_좋음:
            개선 = 변화율 > 0
        else:
            개선 = 변화율 < 0  # CPA, CPC 등은 낮을수록 좋음

        if abs(변화율) > 5:  # 5% 이상 변화만 트렌드로 인식
            if 개선:
                트렌드_개선.append((이름, 변화율))
            else:
                트렌드_악화.append((이름, 변화율))

        lines.append(
            f"  {이름:<10} {formatter(이전값):>12}  {formatter(현재값):>12}  "
            f"{방향} {abs(변화율):.1f}%"
        )

    lines.append("")

    # 트렌드 분석
    lines.append("  📈 트렌드 분석")
    if 트렌드_개선:
        개선_목록 = ", ".join(f"{이름}({abs(율):.1f}%↑ 개선)" for 이름, 율 in 트렌드_개선)
        lines.append(f"    ✅ 개선 중: {개선_목록}")
    if 트렌드_악화:
        악화_목록 = ", ".join(f"{이름}({abs(율):.1f}%↓ 악화)" for 이름, 율 in 트렌드_악화)
        lines.append(f"    ⚠️ 악화 중: {악화_목록}")
    if not 트렌드_개선 and not 트렌드_악화:
        lines.append("    → 큰 변화 없이 안정적인 상태입니다.")
    lines.append("")

    # 원인 분석
    lines.append("  🔍 원인 분석")
    원인들 = _원인_분석(현재, 이전, current_data, previous_data)
    for 원인 in 원인들:
        lines.append(f"    - {원인}")
    if not 원인들:
        lines.append("    - 뚜렷한 원인을 파악하기 어렵습니다. 소재 변경이나 시장 상황을 확인해보세요.")

    return "\n".join(lines)


def _기간_지표_계산(data: list[dict]) -> dict[str, float]:
    """기간 데이터의 주요 지표를 계산합니다."""
    spend = _집계(data, "spend")
    impressions = _집계(data, "impressions")
    clicks = _집계(data, "clicks")
    conversions = _집계(data, "conversions")

    return {
        "spend": spend,
        "impressions": impressions,
        "clicks": clicks,
        "conversions": conversions,
        "cpa": _안전_나누기(spend, conversions),
        "cpc": _안전_나누기(spend, clicks),
        "ctr": _안전_나누기(clicks, impressions) * 100,
    }


def _원인_분석(
    현재: dict[str, float],
    이전: dict[str, float],
    current_data: list[dict],
    previous_data: list[dict],
) -> list[str]:
    """성과 변화의 원인을 추정합니다."""
    원인들 = []

    # CPA 변화 원인
    cpa_변화, _ = _변화율(현재["cpa"], 이전["cpa"])
    ctr_변화, _ = _변화율(현재["ctr"], 이전["ctr"])
    cpc_변화, _ = _변화율(현재["cpc"], 이전["cpc"])

    if abs(cpa_변화) > 10:
        if cpa_변화 > 0:
            if ctr_변화 < -5:
                원인들.append("CTR 하락으로 인해 CPA가 상승했습니다. 소재 매력도를 점검해보세요.")
            if cpc_변화 > 10:
                원인들.append("CPC 상승이 CPA 상승의 원인입니다. 경쟁 입찰 상황을 확인해보세요.")
        else:
            if ctr_변화 > 5:
                원인들.append("CTR 개선이 CPA 하락에 기여했습니다. 현재 소재가 잘 작동하고 있습니다.")
            if cpc_변화 < -10:
                원인들.append("CPC가 낮아져 비용 효율이 개선되었습니다.")

    # 소재 수 변화
    현재_소재수 = len(current_data)
    이전_소재수 = len(previous_data)
    if 현재_소재수 != 이전_소재수:
        차이 = 현재_소재수 - 이전_소재수
        if 차이 > 0:
            원인들.append(f"소재가 {차이}개 추가되었습니다. 새 소재의 성과를 모니터링하세요.")
        else:
            원인들.append(f"소재가 {abs(차이)}개 줄었습니다. 소재 다양성이 감소했을 수 있습니다.")

    # 예산 변화
    spend_변화, _ = _변화율(현재["spend"], 이전["spend"])
    conversion_변화, _ = _변화율(현재["conversions"], 이전["conversions"])

    if spend_변화 > 20 and conversion_변화 < spend_변화 * 0.5:
        원인들.append("예산이 크게 늘었지만 전환은 비례하여 증가하지 않았습니다. 예산 최적화가 필요합니다.")

    return 원인들


# ──────────────────────────────────────────────
# Type E: 소재 피로도 감지
# ──────────────────────────────────────────────

def detect_fatigue(daily_data: list[dict]) -> list[dict]:
    """
    소재 피로도를 감지합니다.

    CTR이 3일 연속 하락하거나 Frequency가 3.0을 초과하는 소재를
    찾아 경고와 함께 추천 조치를 반환합니다.

    매개변수:
        daily_data: 일별 소재 성과 데이터
            각 dict에는 ad_name, date, ctr (또는 clicks/impressions),
            frequency (선택) 키가 포함됩니다.

    반환값:
        피로도가 감지된 소재 목록 (list of dict)
        각 dict에는 ad_name, issue, severity, recommendation 키가 포함됩니다.
    """
    if not daily_data:
        return []

    # 소재별로 일별 데이터 그룹화
    소재별_일별: dict[str, list[dict]] = {}
    for row in daily_data:
        name = row.get("ad_name", "알 수 없음")
        if name not in 소재별_일별:
            소재별_일별[name] = []
        소재별_일별[name].append(row)

    피로_목록 = []

    for 소재명, 일별 in 소재별_일별.items():
        # 날짜순 정렬
        일별.sort(key=lambda x: x.get("date", ""))

        # CTR 계산 (ctr 키가 없으면 clicks/impressions로 계산)
        ctr_목록 = []
        for row in 일별:
            ctr = row.get("ctr")
            if ctr is None:
                ctr = _안전_나누기(row.get("clicks", 0), max(row.get("impressions", 1), 1)) * 100
            ctr_목록.append(ctr)

        # CTR 3일 연속 하락 감지
        if len(ctr_목록) >= 3:
            연속하락 = 0
            최대_연속하락 = 0
            for i in range(1, len(ctr_목록)):
                if ctr_목록[i] < ctr_목록[i - 1]:
                    연속하락 += 1
                    최대_연속하락 = max(최대_연속하락, 연속하락)
                else:
                    연속하락 = 0

            if 최대_연속하락 >= 3:
                첫CTR = ctr_목록[0]
                마지막CTR = ctr_목록[-1]
                하락폭 = 첫CTR - 마지막CTR

                심각도 = "높음" if 최대_연속하락 >= 5 else ("보통" if 최대_연속하락 >= 3 else "낮음")

                피로_목록.append({
                    "ad_name": 소재명,
                    "issue": f"CTR이 {최대_연속하락}일 연속 하락 중 ({_퍼센트(첫CTR)} → {_퍼센트(마지막CTR)})",
                    "issue_type": "ctr_decline",
                    "severity": 심각도,
                    "recommendation": "소재 교체를 추천드립니다. 새로운 이미지나 카피로 변경해보세요.",
                    "decline_days": 최대_연속하락,
                    "ctr_drop": round(하락폭, 2),
                })

        # Frequency 경고
        최근_frequency = [row.get("frequency", 0) for row in 일별[-3:] if row.get("frequency")]
        if 최근_frequency:
            평균_frequency = sum(최근_frequency) / len(최근_frequency)
            if 평균_frequency > 3.0:
                심각도 = "높음" if 평균_frequency > 5.0 else ("보통" if 평균_frequency > 3.5 else "낮음")

                피로_목록.append({
                    "ad_name": 소재명,
                    "issue": f"노출 빈도가 너무 높습니다 (Frequency: {평균_frequency:.1f})",
                    "issue_type": "high_frequency",
                    "severity": 심각도,
                    "recommendation": "같은 사람에게 광고가 너무 자주 노출되고 있습니다. 타겟을 확장하거나 소재를 교체해주세요.",
                    "avg_frequency": round(평균_frequency, 1),
                })

    return 피로_목록


# ──────────────────────────────────────────────
# 통합 리포트 생성
# ──────────────────────────────────────────────

def generate_full_report(all_data: dict, period_days: int = 7) -> dict:
    """
    모든 인사이트를 통합한 전체 리포트를 생성합니다.

    매개변수:
        all_data: 전체 데이터 딕셔너리
            - current_ads: 현재 기간 소재별 데이터 (list[dict])
            - previous_ads: 이전 기간 소재별 데이터 (list[dict])
            - daily_data: 일별 소재 데이터 (list[dict], 피로도 감지용)
            - appeal_analysis: 소구점 분석 (dict, 선택)
        period_days: 분석 기간 일수 (기본 7일)

    반환값:
        모든 인사이트가 포함된 딕셔너리
    """
    current_ads = all_data.get("current_ads", [])
    previous_ads = all_data.get("previous_ads", [])
    daily_data = all_data.get("daily_data", [])
    appeal_analysis = all_data.get("appeal_analysis")

    생성일시 = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 각 인사이트 생성
    요약 = generate_summary_insight(current_ads, previous_ads)
    소재분석 = generate_creative_insight(current_ads, appeal_analysis)
    개선방안 = generate_improvement_insight(current_ads)
    기간비교 = generate_comparison_insight(current_ads, previous_ads)
    피로도 = detect_fatigue(daily_data)

    # 피로도 텍스트 생성
    피로도_텍스트_lines = ["😴 소재 피로도 감지", ""]
    if 피로도:
        for item in 피로도:
            심각도_마크 = {"높음": "🔴", "보통": "🟡", "낮음": "🟢"}.get(item["severity"], "⚪")
            피로도_텍스트_lines.append(f"  {심각도_마크} [{item['severity']}] {item['ad_name']}")
            피로도_텍스트_lines.append(f"    문제: {item['issue']}")
            피로도_텍스트_lines.append(f"    추천: {item['recommendation']}")
            피로도_텍스트_lines.append("")
    else:
        피로도_텍스트_lines.append("  ✅ 피로도가 감지된 소재가 없습니다.")

    피로도_텍스트 = "\n".join(피로도_텍스트_lines)

    return {
        "generated_at": 생성일시,
        "period_days": period_days,
        "insights": {
            "summary": 요약,
            "creative_analysis": 소재분석,
            "improvement": 개선방안,
            "period_comparison": 기간비교,
            "fatigue_detection": 피로도_텍스트,
        },
        "fatigue_alerts": 피로도,
        "metadata": {
            "current_ad_count": len(current_ads),
            "previous_ad_count": len(previous_ads),
            "daily_data_rows": len(daily_data),
            "total_spend": _집계(current_ads, "spend"),
            "total_conversions": _집계(current_ads, "conversions"),
        },
    }


# ──────────────────────────────────────────────
# 대시보드용 포맷터
# ──────────────────────────────────────────────

def format_insight_for_dashboard(insights: dict) -> dict:
    """
    인사이트를 대시보드에서 사용할 수 있는 JSON/HTML 형식으로 변환합니다.

    매개변수:
        insights: generate_full_report()의 반환값

    반환값:
        대시보드 렌더링에 적합한 구조화된 딕셔너리
    """
    insight_data = insights.get("insights", {})
    metadata = insights.get("metadata", {})
    fatigue_alerts = insights.get("fatigue_alerts", [])

    # 각 인사이트를 섹션으로 변환
    sections = []

    섹션_매핑 = [
        ("summary", "성과 요약", "chart-bar"),
        ("creative_analysis", "소재 분석", "puzzle-piece"),
        ("improvement", "개선방안", "wrench"),
        ("period_comparison", "기간 비교", "calendar"),
        ("fatigue_detection", "소재 피로도", "exclamation-triangle"),
    ]

    for key, title, icon in 섹션_매핑:
        text = insight_data.get(key, "")
        if text:
            # 텍스트를 줄 단위로 분리하여 HTML 렌더링에 적합하게 변환
            html_lines = []
            for line in text.split("\n"):
                stripped = line.strip()
                if not stripped:
                    html_lines.append("<br>")
                elif stripped.startswith("📊") or stripped.startswith("📎") or \
                     stripped.startswith("🔧") or stripped.startswith("📅") or \
                     stripped.startswith("😴"):
                    html_lines.append(f'<h3 class="insight-title">{stripped}</h3>')
                elif stripped.startswith("✅") or stripped.startswith("❌") or \
                     stripped.startswith("💡") or stripped.startswith("🚫") or \
                     stripped.startswith("💰") or stripped.startswith("🎨") or \
                     stripped.startswith("🎯") or stripped.startswith("📈") or \
                     stripped.startswith("🔍") or stripped.startswith("📊"):
                    html_lines.append(f'<h4 class="insight-subtitle">{stripped}</h4>')
                elif stripped.startswith("→"):
                    html_lines.append(f'<p class="insight-highlight">{stripped}</p>')
                elif stripped.startswith("-"):
                    html_lines.append(f'<li class="insight-item">{stripped[1:].strip()}</li>')
                elif stripped.startswith("지표"):
                    html_lines.append(f'<div class="insight-table-header">{stripped}</div>')
                elif stripped.startswith("─"):
                    html_lines.append('<hr class="insight-divider">')
                else:
                    html_lines.append(f'<p class="insight-text">{stripped}</p>')

            sections.append({
                "id": key,
                "title": title,
                "icon": icon,
                "content_text": text,
                "content_html": "\n".join(html_lines),
            })

    # 피로도 경고를 별도 알림으로
    alerts = []
    for alert in fatigue_alerts:
        alerts.append({
            "ad_name": alert["ad_name"],
            "type": alert.get("issue_type", "unknown"),
            "severity": alert["severity"],
            "message": alert["issue"],
            "action": alert["recommendation"],
        })

    return {
        "generated_at": insights.get("generated_at", ""),
        "period_days": insights.get("period_days", 7),
        "sections": sections,
        "alerts": alerts,
        "summary_metrics": {
            "ad_count": metadata.get("current_ad_count", 0),
            "total_spend": metadata.get("total_spend", 0),
            "total_spend_formatted": _원(metadata.get("total_spend", 0)),
            "total_conversions": metadata.get("total_conversions", 0),
            "avg_cpa": _안전_나누기(
                metadata.get("total_spend", 0),
                max(metadata.get("total_conversions", 1), 1),
            ),
            "avg_cpa_formatted": _원(
                _안전_나누기(
                    metadata.get("total_spend", 0),
                    max(metadata.get("total_conversions", 1), 1),
                )
            ),
            "fatigue_alert_count": len(alerts),
        },
    }


# ──────────────────────────────────────────────
# 테스트 / 예시 실행
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  마케팅 인사이트 생성기 - 테스트 실행")
    print("=" * 60)
    print()

    # 테스트 데이터: 현재 기간
    현재_소재 = [
        {
            "ad_name": "봄맞이_할인_A",
            "spend": 500000,
            "impressions": 100000,
            "clicks": 3500,
            "conversions": 45,
            "appeal": "할인/프로모션",
            "format": "카드뉴스",
            "target_audience": "25-34 여성",
        },
        {
            "ad_name": "신제품_소개_B",
            "spend": 300000,
            "impressions": 80000,
            "clicks": 2000,
            "conversions": 30,
            "appeal": "신제품",
            "format": "동영상",
            "target_audience": "25-34 여성",
        },
        {
            "ad_name": "후기_영상_C",
            "spend": 400000,
            "impressions": 60000,
            "clicks": 1800,
            "conversions": 50,
            "appeal": "사회적 증거",
            "format": "동영상",
            "target_audience": "35-44 여성",
        },
        {
            "ad_name": "브랜드_인지_D",
            "spend": 600000,
            "impressions": 200000,
            "clicks": 4000,
            "conversions": 20,
            "appeal": "브랜드 스토리",
            "format": "이미지",
            "target_audience": "18-24 여성",
        },
        {
            "ad_name": "리타겟팅_E",
            "spend": 200000,
            "impressions": 30000,
            "clicks": 1500,
            "conversions": 35,
            "appeal": "리마인드",
            "format": "카드뉴스",
            "target_audience": "25-34 여성",
        },
    ]

    # 테스트 데이터: 이전 기간
    이전_소재 = [
        {
            "ad_name": "겨울_할인_A",
            "spend": 450000,
            "impressions": 90000,
            "clicks": 2700,
            "conversions": 35,
            "appeal": "할인/프로모션",
            "format": "카드뉴스",
            "target_audience": "25-34 여성",
        },
        {
            "ad_name": "제품_홍보_B",
            "spend": 350000,
            "impressions": 85000,
            "clicks": 2200,
            "conversions": 25,
            "appeal": "제품 특장점",
            "format": "이미지",
            "target_audience": "25-34 여성",
        },
        {
            "ad_name": "이벤트_C",
            "spend": 380000,
            "impressions": 70000,
            "clicks": 2100,
            "conversions": 40,
            "appeal": "이벤트",
            "format": "동영상",
            "target_audience": "35-44 여성",
        },
    ]

    # 테스트 데이터: 일별 (피로도 감지용)
    일별_데이터 = [
        {"ad_name": "봄맞이_할인_A", "date": "2026-03-22", "ctr": 3.8, "frequency": 2.1},
        {"ad_name": "봄맞이_할인_A", "date": "2026-03-23", "ctr": 3.5, "frequency": 2.3},
        {"ad_name": "봄맞이_할인_A", "date": "2026-03-24", "ctr": 3.2, "frequency": 2.5},
        {"ad_name": "봄맞이_할인_A", "date": "2026-03-25", "ctr": 2.8, "frequency": 2.8},
        {"ad_name": "봄맞이_할인_A", "date": "2026-03-26", "ctr": 2.5, "frequency": 3.1},
        {"ad_name": "봄맞이_할인_A", "date": "2026-03-27", "ctr": 2.1, "frequency": 3.4},
        {"ad_name": "브랜드_인지_D", "date": "2026-03-22", "ctr": 2.0, "frequency": 3.2},
        {"ad_name": "브랜드_인지_D", "date": "2026-03-23", "ctr": 1.9, "frequency": 3.5},
        {"ad_name": "브랜드_인지_D", "date": "2026-03-24", "ctr": 1.8, "frequency": 3.8},
        {"ad_name": "브랜드_인지_D", "date": "2026-03-25", "ctr": 1.7, "frequency": 4.1},
        {"ad_name": "브랜드_인지_D", "date": "2026-03-26", "ctr": 1.6, "frequency": 4.4},
        {"ad_name": "브랜드_인지_D", "date": "2026-03-27", "ctr": 1.5, "frequency": 4.8},
    ]

    소구점_분석 = {
        "할인/프로모션": {"avg_cpa": 11000, "count": 3},
        "사회적 증거": {"avg_cpa": 8000, "count": 2},
        "신제품": {"avg_cpa": 10000, "count": 2},
        "브랜드 스토리": {"avg_cpa": 30000, "count": 1},
        "리마인드": {"avg_cpa": 5700, "count": 2},
    }

    # 전체 리포트 생성
    전체_데이터 = {
        "current_ads": 현재_소재,
        "previous_ads": 이전_소재,
        "daily_data": 일별_데이터,
        "appeal_analysis": 소구점_분석,
    }

    리포트 = generate_full_report(전체_데이터, period_days=7)

    # 각 인사이트 출력
    for key, text in 리포트["insights"].items():
        print(text)
        print()
        print("-" * 60)
        print()

    # 대시보드용 포맷 변환
    대시보드_데이터 = format_insight_for_dashboard(리포트)

    print()
    print("=" * 60)
    print("  대시보드용 JSON 구조 미리보기")
    print("=" * 60)
    print()
    print(f"  생성 시각: {대시보드_데이터['generated_at']}")
    print(f"  분석 기간: {대시보드_데이터['period_days']}일")
    print(f"  섹션 수: {len(대시보드_데이터['sections'])}개")
    print(f"  알림 수: {len(대시보드_데이터['alerts'])}개")
    print()
    print("  요약 지표:")
    for key, value in 대시보드_데이터["summary_metrics"].items():
        print(f"    {key}: {value}")
    print()

    if 대시보드_데이터["alerts"]:
        print("  피로도 알림:")
        for alert in 대시보드_데이터["alerts"]:
            print(f"    [{alert['severity']}] {alert['ad_name']}: {alert['message']}")
    print()
    print("테스트 완료!")
