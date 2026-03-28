"""
메타 광고 크리에이티브 소구점 자동 분류기

광고 텍스트(본문 + 제목)를 분석하여 소구점(appeal point)을 자동으로 분류합니다.
8개 소구점 카테고리를 기반으로 키워드 매칭 및 신뢰도 점수를 산출합니다.
"""

import re
from collections import Counter, defaultdict
from itertools import combinations

# ──────────────────────────────────────────────
# 소구점 카테고리 정의
# ──────────────────────────────────────────────

APPEAL_CATEGORIES = {
    "💰 가격/할인": {
        "keywords": [
            "할인", "세일", "%", "무료배송", "최저가", "특가", "파격",
            "반값", "초특가", "프로모션가", "원", "무료", "배송비"
        ],
        "patterns": [
            r"\d+%\s*(할인|OFF|off)",
            r"\d+[,.]?\d*원",
            r"무료\s*배송",
            r"최대\s*\d+%",
        ],
    },
    "⭐ 후기/신뢰": {
        "keywords": [
            "후기", "리뷰", "만족", "재구매", "평점", "실사용", "인증",
            "검증", "추천", "베스트셀러", "판매1위", "누적"
        ],
        "patterns": [
            r"\d+만\s*(명|개|건)",
            r"★+",
            r"\d+(\.\d+)?\s*점",
            r"누적\s*(판매|후기|리뷰)",
        ],
    },
    "🎁 혜택/프로모션": {
        "keywords": [
            "증정", "사은품", "1+1", "쿠폰", "적립", "포인트",
            "추가증정", "덤", "선물", "이벤트"
        ],
        "patterns": [
            r"\d+\+\d+",
            r"(추가|무료)\s*증정",
            r"\d+%\s*적립",
        ],
    },
    "💖 감성/브랜딩": {
        "keywords": [
            "특별한", "프리미엄", "당신만의", "감각적", "럭셔리", "품격",
            "고급", "세련", "트렌디", "힙한"
        ],
        "patterns": [
            r"나만의",
            r"당신[을의에]게?",
        ],
    },
    "⚡ 긴급/한정": {
        "keywords": [
            "오늘만", "한정", "마감임박", "선착순", "품절임박", "단독",
            "한시적", "지금바로", "놓치지마"
        ],
        "patterns": [
            r"오늘\s*(까지|만|내)",
            r"\d+일\s*(남음|한정)",
            r"선착순\s*\d+",
            r"지금\s*바로",
            r"놓치지\s*마",
        ],
    },
    "🔬 기능/성분": {
        "keywords": [
            "성분", "특허", "기술", "효과", "기능성", "임상", "인체적용",
            "식약처", "검증된", "원료"
        ],
        "patterns": [
            r"특허\s*(등록|출원|제\d+호)",
            r"임상\s*(시험|테스트|완료)",
            r"식약처\s*(인증|인정|허가)",
        ],
    },
    "🎯 타겟특화": {
        "keywords": [
            "하는 분", "고민이라면", "족", "직장인", "주부", "학생",
            "MZ", "2030", "4050"
        ],
        "patterns": [
            r"~?(하시는|하는)\s*분",
            r"고민이(라면|신|시라면)",
            r"(직장인|주부|학생|엄마|아빠|대학생)(들|을|의|이)?",
            r"(20|30|40|50)대",
        ],
    },
    "📸 비주얼유형": {
        "keywords": [],
        "patterns": [],
    },
}

# 비주얼 유형 분류 규칙
VISUAL_TYPE_RULES = {
    "제품컷": ["product", "item", "packshot", "still", "studio"],
    "모델컷": ["model", "person", "lifestyle", "wearing", "look"],
    "후기컷": ["review", "testimonial", "ugc", "user", "real"],
    "일러스트": ["illust", "graphic", "cartoon", "design", "vector"],
    "영상": ["video", "mov", "mp4", "reel", "motion"],
}


# ──────────────────────────────────────────────
# 핵심 분류 함수
# ──────────────────────────────────────────────

def classify_appeal_points(text: str) -> list[dict]:
    """
    광고 텍스트를 분석하여 소구점을 분류합니다.

    Args:
        text: 광고 본문 + 제목 텍스트

    Returns:
        소구점 분류 결과 리스트. 각 항목은
        {category, confidence, matched_keywords} 딕셔너리입니다.
        confidence 기준 내림차순 정렬됩니다.
    """
    if not text or not text.strip():
        return []

    text_lower = text.lower()
    results = []

    for category, rules in APPEAL_CATEGORIES.items():
        # 📸 비주얼유형은 텍스트 분류 대상이 아님
        if category == "📸 비주얼유형":
            continue

        matched_keywords = []

        # 키워드 매칭
        for kw in rules["keywords"]:
            if kw.lower() in text_lower:
                matched_keywords.append(kw)

        # 정규식 패턴 매칭
        pattern_match_count = 0
        for pattern in rules.get("patterns", []):
            if re.search(pattern, text, re.IGNORECASE):
                pattern_match_count += 1

        # 신뢰도 계산: 키워드 매칭 수 + 패턴 매칭 보너스
        total_possible = max(len(rules["keywords"]), 1)
        keyword_score = len(matched_keywords) / total_possible
        pattern_bonus = min(pattern_match_count * 0.15, 0.3)
        confidence = min(round(keyword_score + pattern_bonus, 2), 1.0)

        if matched_keywords or pattern_match_count > 0:
            results.append({
                "category": category,
                "confidence": confidence,
                "matched_keywords": matched_keywords,
            })

    # 신뢰도 내림차순 정렬
    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results


def classify_visual_type(thumbnail_url: str, ad_name: str = "") -> str:
    """
    썸네일 URL과 광고명을 기반으로 비주얼 유형을 분류합니다.

    Args:
        thumbnail_url: 광고 이미지/영상 URL
        ad_name: 광고 이름 (선택)

    Returns:
        비주얼 유형 문자열 (제품컷/모델컷/후기컷/일러스트/영상)
    """
    if not thumbnail_url:
        return "분류불가"

    combined = (thumbnail_url + " " + ad_name).lower()

    # 영상 우선 체크 (확장자 기반)
    video_extensions = [".mp4", ".mov", ".avi", ".webm"]
    if any(ext in combined for ext in video_extensions):
        return "영상"

    # URL·광고명 패턴 매칭
    scores = {}
    for visual_type, keywords in VISUAL_TYPE_RULES.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[visual_type] = score

    if scores:
        return max(scores, key=scores.get)

    return "분류불가"


# ──────────────────────────────────────────────
# 광고 크리에이티브 분석
# ──────────────────────────────────────────────

def analyze_ad_creative(ad_data: dict) -> dict:
    """
    단일 광고 크리에이티브를 종합 분석합니다.

    Args:
        ad_data: 광고 데이터 딕셔너리. 다음 키를 포함할 수 있습니다:
            - body (str): 광고 본문
            - title (str): 광고 제목
            - ad_name (str): 광고 이름
            - thumbnail_url (str): 썸네일 URL
            - spend (float): 지출 금액
            - impressions (int): 노출수
            - clicks (int): 클릭수
            - conversions (int): 전환수

    Returns:
        분석 결과 딕셔너리
    """
    body = ad_data.get("body", "")
    title = ad_data.get("title", "")
    ad_name = ad_data.get("ad_name", "")
    thumbnail_url = ad_data.get("thumbnail_url", "")

    # 본문 + 제목 결합하여 분석
    full_text = f"{body} {title}".strip()

    # 소구점 분류
    appeal_points = classify_appeal_points(full_text)

    # 비주얼 유형 분류
    visual_type = classify_visual_type(thumbnail_url, ad_name)

    # 성과 지표 계산
    impressions = ad_data.get("impressions", 0)
    clicks = ad_data.get("clicks", 0)
    spend = ad_data.get("spend", 0)
    conversions = ad_data.get("conversions", 0)

    ctr = round((clicks / impressions * 100), 2) if impressions > 0 else 0
    cpc = round(spend / clicks, 0) if clicks > 0 else 0
    cpa = round(spend / conversions, 0) if conversions > 0 else 0
    cvr = round((conversions / clicks * 100), 2) if clicks > 0 else 0

    # 주요 소구점 (신뢰도 0.1 이상만)
    primary_appeals = [ap for ap in appeal_points if ap["confidence"] >= 0.1]

    return {
        "ad_name": ad_name,
        "body": body,
        "title": title,
        "full_text": full_text,
        "appeal_points": appeal_points,
        "primary_appeals": [ap["category"] for ap in primary_appeals],
        "visual_type": visual_type,
        "metrics": {
            "impressions": impressions,
            "clicks": clicks,
            "spend": spend,
            "conversions": conversions,
            "ctr": ctr,
            "cpc": cpc,
            "cpa": cpa,
            "cvr": cvr,
        },
    }


def analyze_all_creatives(ads_data: list) -> dict:
    """
    여러 광고 크리에이티브를 일괄 분석하고 요약 통계를 생성합니다.

    Args:
        ads_data: 광고 데이터 딕셔너리 리스트

    Returns:
        전체 분석 결과 및 요약 통계 딕셔너리
    """
    if not ads_data:
        return {"results": [], "summary": {}}

    results = [analyze_ad_creative(ad) for ad in ads_data]

    # 소구점별 빈도 집계
    appeal_counter = Counter()
    visual_counter = Counter()

    for r in results:
        for ap in r["primary_appeals"]:
            appeal_counter[ap] += 1
        visual_counter[r["visual_type"]] += 1

    total = len(results)

    # 소구점별 사용 비율
    appeal_distribution = {
        cat: {
            "count": count,
            "ratio": round(count / total * 100, 1),
        }
        for cat, count in appeal_counter.most_common()
    }

    # 비주얼 유형 분포
    visual_distribution = {
        vtype: {
            "count": count,
            "ratio": round(count / total * 100, 1),
        }
        for vtype, count in visual_counter.most_common()
    }

    summary = {
        "total_creatives": total,
        "appeal_distribution": appeal_distribution,
        "visual_distribution": visual_distribution,
        "avg_appeals_per_creative": round(
            sum(len(r["primary_appeals"]) for r in results) / total, 1
        ),
    }

    return {"results": results, "summary": summary}


# ──────────────────────────────────────────────
# 성과 분석
# ──────────────────────────────────────────────

def get_appeal_performance(ads_with_appeals: list) -> dict:
    """
    소구점별 성과를 비교 분석합니다.

    Args:
        ads_with_appeals: analyze_ad_creative() 결과 리스트

    Returns:
        소구점별 평균 성과 지표 딕셔너리
    """
    appeal_metrics = defaultdict(lambda: {
        "count": 0,
        "total_impressions": 0,
        "total_clicks": 0,
        "total_spend": 0,
        "total_conversions": 0,
    })

    for ad in ads_with_appeals:
        metrics = ad.get("metrics", {})
        for appeal in ad.get("primary_appeals", []):
            bucket = appeal_metrics[appeal]
            bucket["count"] += 1
            bucket["total_impressions"] += metrics.get("impressions", 0)
            bucket["total_clicks"] += metrics.get("clicks", 0)
            bucket["total_spend"] += metrics.get("spend", 0)
            bucket["total_conversions"] += metrics.get("conversions", 0)

    performance = {}
    for appeal, data in appeal_metrics.items():
        imp = data["total_impressions"]
        clk = data["total_clicks"]
        spd = data["total_spend"]
        conv = data["total_conversions"]

        performance[appeal] = {
            "creative_count": data["count"],
            "avg_ctr": round((clk / imp * 100), 2) if imp > 0 else 0,
            "avg_cpc": round(spd / clk, 0) if clk > 0 else 0,
            "avg_cpa": round(spd / conv, 0) if conv > 0 else 0,
            "avg_cvr": round((conv / clk * 100), 2) if clk > 0 else 0,
            "total_spend": round(spd, 0),
            "total_conversions": conv,
        }

    # CTR 기준 내림차순 정렬
    performance = dict(
        sorted(performance.items(), key=lambda x: x[1]["avg_ctr"], reverse=True)
    )
    return performance


def get_best_combinations(ads_with_appeals: list, top_n: int = 5) -> list:
    """
    성과가 가장 좋은 소구점 조합을 찾습니다.

    Args:
        ads_with_appeals: analyze_ad_creative() 결과 리스트
        top_n: 반환할 상위 조합 수

    Returns:
        최고 성과 소구점 조합 리스트
    """
    combo_metrics = defaultdict(lambda: {
        "count": 0,
        "total_clicks": 0,
        "total_impressions": 0,
        "total_conversions": 0,
        "total_spend": 0,
    })

    for ad in ads_with_appeals:
        appeals = sorted(ad.get("primary_appeals", []))
        metrics = ad.get("metrics", {})

        if len(appeals) < 2:
            continue

        # 2개 조합 생성
        for combo in combinations(appeals, 2):
            key = " + ".join(combo)
            bucket = combo_metrics[key]
            bucket["count"] += 1
            bucket["total_impressions"] += metrics.get("impressions", 0)
            bucket["total_clicks"] += metrics.get("clicks", 0)
            bucket["total_spend"] += metrics.get("spend", 0)
            bucket["total_conversions"] += metrics.get("conversions", 0)

    results = []
    for combo_name, data in combo_metrics.items():
        imp = data["total_impressions"]
        clk = data["total_clicks"]
        spd = data["total_spend"]
        conv = data["total_conversions"]

        results.append({
            "combination": combo_name,
            "creative_count": data["count"],
            "avg_ctr": round((clk / imp * 100), 2) if imp > 0 else 0,
            "avg_cvr": round((conv / clk * 100), 2) if clk > 0 else 0,
            "avg_cpa": round(spd / conv, 0) if conv > 0 else 0,
            "total_conversions": conv,
        })

    # 전환율 기준 내림차순 정렬 (최소 2개 크리에이티브)
    results = [r for r in results if r["creative_count"] >= 2]
    results.sort(key=lambda x: x["avg_cvr"], reverse=True)

    return results[:top_n]


# ──────────────────────────────────────────────
# 인사이트 생성
# ──────────────────────────────────────────────

def generate_creative_insight(analysis: dict) -> str:
    """
    크리에이티브 분석 결과를 바탕으로 한국어 인사이트 텍스트를 생성합니다.

    Args:
        analysis: analyze_all_creatives() 반환값

    Returns:
        한국어 인사이트 문자열
    """
    summary = analysis.get("summary", {})
    results = analysis.get("results", [])

    if not summary or not results:
        return "분석할 크리에이티브 데이터가 없습니다."

    total = summary.get("total_creatives", 0)
    appeal_dist = summary.get("appeal_distribution", {})
    visual_dist = summary.get("visual_distribution", {})
    avg_appeals = summary.get("avg_appeals_per_creative", 0)

    lines = []
    lines.append("=" * 50)
    lines.append("📊 크리에이티브 소구점 분석 리포트")
    lines.append("=" * 50)
    lines.append("")

    # 기본 현황
    lines.append(f"▶ 분석 크리에이티브 수: {total}개")
    lines.append(f"▶ 크리에이티브당 평균 소구점 수: {avg_appeals}개")
    lines.append("")

    # 소구점 분포
    lines.append("── 소구점 사용 빈도 ──")
    for cat, info in appeal_dist.items():
        bar = "█" * int(info["ratio"] / 5)
        lines.append(f"  {cat}: {info['count']}개 ({info['ratio']}%) {bar}")
    lines.append("")

    # 비주얼 유형 분포
    lines.append("── 비주얼 유형 분포 ──")
    for vtype, info in visual_dist.items():
        lines.append(f"  {vtype}: {info['count']}개 ({info['ratio']}%)")
    lines.append("")

    # 성과 기반 인사이트 생성
    performance = get_appeal_performance(results)
    if performance:
        lines.append("── 소구점별 성과 비교 ──")
        for appeal, perf in performance.items():
            lines.append(
                f"  {appeal}: CTR {perf['avg_ctr']}% | "
                f"CPC {perf['avg_cpc']:,.0f}원 | "
                f"CVR {perf['avg_cvr']}%"
            )
        lines.append("")

        # 최고 성과 소구점
        best_appeal = next(iter(performance))
        best_ctr = performance[best_appeal]["avg_ctr"]
        lines.append(f"💡 최고 CTR 소구점: {best_appeal} ({best_ctr}%)")

    # 최고 조합 분석
    best_combos = get_best_combinations(results)
    if best_combos:
        lines.append("")
        lines.append("── 최고 성과 소구점 조합 (TOP 3) ──")
        for i, combo in enumerate(best_combos[:3], 1):
            lines.append(
                f"  {i}위. {combo['combination']} "
                f"(CVR {combo['avg_cvr']}%, "
                f"크리에이티브 {combo['creative_count']}개)"
            )

    # 전략 제안
    lines.append("")
    lines.append("── 전략 제안 ──")

    # 가장 많이 쓰이는 소구점 vs 가장 성과 좋은 소구점 비교
    if appeal_dist and performance:
        most_used = next(iter(appeal_dist))
        best_perf = next(iter(performance))

        if most_used != best_perf:
            lines.append(
                f"  ⚠ 가장 많이 사용된 소구점({most_used})과 "
                f"최고 성과 소구점({best_perf})이 다릅니다."
            )
            lines.append(
                f"    → {best_perf} 소구점의 크리에이티브를 확대해 보세요."
            )
        else:
            lines.append(
                f"  ✅ 가장 많이 사용된 소구점({most_used})이 "
                f"성과도 가장 좋습니다. 현재 전략을 유지하세요."
            )

    # 소구점 다양성 체크
    if avg_appeals < 1.5:
        lines.append("  💬 크리에이티브당 소구점이 적습니다. 복합 소구점 활용을 검토하세요.")
    elif avg_appeals > 3:
        lines.append("  💬 크리에이티브당 소구점이 많습니다. 핵심 메시지에 집중해 보세요.")

    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


# ──────────────────────────────────────────────
# 메인 실행 (데모)
# ──────────────────────────────────────────────

def _run_demo():
    """데모용 샘플 데이터로 분류기를 실행합니다."""

    sample_ads = [
        {
            "ad_name": "봄맞이_할인_제품A_v1",
            "body": "지금 최대 50% 할인! 봄맞이 초특가 세일 🌸 무료배송까지 놓치지 마세요",
            "title": "파격 특가! 오늘만 이 가격",
            "thumbnail_url": "https://cdn.example.com/product_shot_001.jpg",
            "impressions": 50000,
            "clicks": 1500,
            "spend": 300000,
            "conversions": 45,
        },
        {
            "ad_name": "후기_모델컷_v2",
            "body": "누적 판매 10만개 돌파! 재구매율 92% 실사용 후기를 확인하세요 ⭐ 평점 4.9점",
            "title": "베스트셀러 1위, 검증된 품질",
            "thumbnail_url": "https://cdn.example.com/model_lifestyle_002.jpg",
            "impressions": 40000,
            "clicks": 2000,
            "spend": 250000,
            "conversions": 80,
        },
        {
            "ad_name": "프리미엄_기능성_v3",
            "body": "식약처 인증 기능성 원료 사용. 특허받은 기술로 효과를 극대화했습니다",
            "title": "프리미엄 품격, 당신만의 특별한 선택",
            "thumbnail_url": "https://cdn.example.com/product_studio_003.jpg",
            "impressions": 30000,
            "clicks": 900,
            "spend": 200000,
            "conversions": 30,
        },
        {
            "ad_name": "이벤트_1+1_v4",
            "body": "1+1 이벤트 진행중! 사은품 증정 + 3000원 쿠폰까지 🎁 적립 포인트 2배",
            "title": "선물 같은 혜택, 지금 바로 참여하세요",
            "thumbnail_url": "https://cdn.example.com/review_ugc_004.jpg",
            "impressions": 35000,
            "clicks": 1400,
            "spend": 220000,
            "conversions": 55,
        },
        {
            "ad_name": "타겟_직장인_v5",
            "body": "바쁜 직장인을 위한 간편 솔루션. 2030 직장인이라면 꼭 필요한 아이템",
            "title": "고민이라면 지금 확인! 한정 수량 선착순",
            "thumbnail_url": "https://cdn.example.com/illust_graphic_005.jpg",
            "impressions": 25000,
            "clicks": 1100,
            "spend": 180000,
            "conversions": 38,
        },
        {
            "ad_name": "영상_할인후기_v6",
            "body": "실사용 후기 영상 공개! 30% 할인 + 무료배송 이벤트. 재구매 고객 추천",
            "title": "만족도 98%, 오늘만 특가",
            "thumbnail_url": "https://cdn.example.com/video_reel_006.mp4",
            "impressions": 60000,
            "clicks": 3000,
            "spend": 400000,
            "conversions": 120,
        },
    ]

    print("🔍 메타 광고 크리에이티브 소구점 분류기 데모")
    print("=" * 50)
    print()

    # 전체 분석 실행
    analysis = analyze_all_creatives(sample_ads)

    # 개별 결과 출력
    for i, result in enumerate(analysis["results"], 1):
        print(f"── 크리에이티브 {i}: {result['ad_name']} ──")
        print(f"  본문: {result['body'][:50]}...")
        print(f"  제목: {result['title']}")
        print(f"  비주얼 유형: {result['visual_type']}")
        print(f"  소구점:")
        for ap in result["appeal_points"]:
            kws = ", ".join(ap["matched_keywords"]) if ap["matched_keywords"] else "(패턴매칭)"
            print(f"    {ap['category']} (신뢰도: {ap['confidence']}) - [{kws}]")
        m = result["metrics"]
        print(f"  성과: CTR {m['ctr']}% | CPC {m['cpc']:,.0f}원 | CVR {m['cvr']}%")
        print()

    # 종합 인사이트 출력
    insight = generate_creative_insight(analysis)
    print(insight)


if __name__ == "__main__":
    _run_demo()
