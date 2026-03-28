# -*- coding: utf-8 -*-
"""
메타 광고 데이터 수집 + 대시보드 JSON 생성 통합 스크립트
"""
import requests
import json
import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('META_ACCESS_TOKEN')
BASE_URL = 'https://graph.facebook.com/v21.0'

# ===== 소구점 분류 엔진 =====
APPEAL_CATEGORIES = {
    '💰 가격/할인': ['할인', '세일', '%', '무료배송', '최저가', '특가', '파격', '반값', '초특가', '무료', '가격', '저렴', '원가', '프로모션'],
    '⭐ 후기/신뢰': ['후기', '리뷰', '만족', '재구매', '평점', '실사용', '인증', '검증', '추천', '베스트셀러', '판매1위', '누적', '매출'],
    '🎁 혜택/프로모션': ['증정', '사은품', '1+1', '쿠폰', '적립', '포인트', '추가증정', '덤', '선물', '이벤트', '혜택'],
    '💖 감성/브랜딩': ['특별한', '프리미엄', '당신만의', '감각적', '럭셔리', '품격', '고급', '세련', '트렌디', '힙한', '감성'],
    '⚡ 긴급/한정': ['오늘만', '한정', '마감임박', '선착순', '품절임박', '단독', '한시적', '지금바로', '놓치지마', '마감'],
    '🔬 기능/성분': ['성분', '특허', '기술', '효과', '기능성', '임상', '식약처', '검증된', '원료', '효능', '순수익률'],
    '🎯 타겟특화': ['하는 분', '고민이라면', '사장님', '직장인', '주부', '학생', 'MZ', '2030', '4050', '창업', '예비'],
}

def classify_appeal(text):
    if not text:
        return []
    results = []
    for category, keywords in APPEAL_CATEGORIES.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            results.append({
                'category': category,
                'matched': matched,
                'confidence': min(len(matched) / 3, 1.0)
            })
    results.sort(key=lambda x: x['confidence'], reverse=True)
    return results

# ===== 데이터 수집 =====
def get_all_ad_accounts():
    """모든 광고 계정 가져오기"""
    accounts = []
    url = f'{BASE_URL}/me/adaccounts'
    params = {
        'fields': 'name,account_id,account_status,currency',
        'access_token': TOKEN,
        'limit': 100
    }
    while url:
        resp = requests.get(url, params=params)
        data = resp.json()
        if 'data' in data:
            accounts.extend(data['data'])
        url = data.get('paging', {}).get('next')
        params = {}  # next URL에 이미 params 포함
    print(f'📊 총 {len(accounts)}개 광고 계정 발견')
    return accounts

def get_ads_with_insights(account_id, account_name, days=7):
    """광고별 소재 + 성과 데이터"""
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    ads = []

    # 1. 광고 목록 + 소재 정보
    resp = requests.get(
        f'{BASE_URL}/{account_id}/ads',
        params={
            'fields': 'name,status,creative.fields(title,body,thumbnail_url,image_url,object_story_spec,call_to_action_type)',
            'filtering': json.dumps([{'field': 'effective_status', 'operator': 'IN', 'value': ['ACTIVE', 'PAUSED']}]),
            'access_token': TOKEN,
            'limit': 50
        }
    )
    ads_data = resp.json().get('data', [])

    # 2. 광고별 인사이트
    resp2 = requests.get(
        f'{BASE_URL}/{account_id}/insights',
        params={
            'fields': 'ad_id,ad_name,impressions,reach,clicks,spend,cpc,cpm,ctr,frequency,actions,cost_per_action_type',
            'level': 'ad',
            'time_range': json.dumps({'since': start_date, 'until': end_date}),
            'access_token': TOKEN,
            'limit': 100
        }
    )
    insights_data = resp2.json().get('data', [])
    insights_map = {i['ad_id']: i for i in insights_data}

    # 3. 일별 데이터
    resp3 = requests.get(
        f'{BASE_URL}/{account_id}/insights',
        params={
            'fields': 'impressions,clicks,spend,cpc,cpm,ctr,actions,cost_per_action_type',
            'time_range': json.dumps({'since': start_date, 'until': end_date}),
            'time_increment': 1,
            'access_token': TOKEN,
            'limit': 100
        }
    )
    daily_data = resp3.json().get('data', [])

    # 4. 합치기
    for ad in ads_data:
        ad_id = ad.get('id', '').replace('act_', '')
        insight = insights_map.get(ad_id, {})
        creative = ad.get('creative', {})

        # 소재 텍스트 추출
        body = creative.get('body', '')
        title = creative.get('title', '')
        full_text = f'{title} {body}'

        # 썸네일/이미지 URL
        thumbnail = creative.get('thumbnail_url', '')
        image_url = creative.get('image_url', '')

        # object_story_spec에서 영상 정보
        oss = creative.get('object_story_spec', {})
        video_data = oss.get('video_data', {})
        link_data = oss.get('link_data', {})

        video_id = video_data.get('video_id', '')
        video_thumbnail = video_data.get('image_url', '')

        if not thumbnail and video_thumbnail:
            thumbnail = video_thumbnail
        if not thumbnail and link_data.get('image_hash'):
            thumbnail = image_url

        # 전환 데이터 추출
        actions = insight.get('actions', [])
        conversions = {}
        for a in actions:
            conversions[a['action_type']] = int(a['value'])

        cost_per_action = insight.get('cost_per_action_type', [])
        cpa_map = {}
        for c in cost_per_action:
            cpa_map[c['action_type']] = float(c['value'])

        # 소구점 분류
        appeals = classify_appeal(full_text)

        # 소재 유형 판별
        creative_type = '영상' if video_id else '이미지'

        spend = float(insight.get('spend', 0))
        clicks = int(insight.get('clicks', 0))
        impressions = int(insight.get('impressions', 0))

        ad_result = {
            'ad_id': ad_id,
            'ad_name': ad.get('name', ''),
            'status': ad.get('status', ''),
            'account_name': account_name,
            'account_id': account_id,
            # 소재 정보
            'title': title,
            'body': body,
            'thumbnail_url': thumbnail,
            'image_url': image_url,
            'video_id': video_id,
            'creative_type': creative_type,
            'cta': creative.get('call_to_action_type', ''),
            # 성과 지표
            'impressions': impressions,
            'reach': int(insight.get('reach', 0)),
            'clicks': clicks,
            'spend': spend,
            'cpc': float(insight.get('cpc', 0)),
            'cpm': float(insight.get('cpm', 0)),
            'ctr': float(insight.get('ctr', 0)),
            'frequency': float(insight.get('frequency', 0)),
            # 전환
            'conversions': conversions,
            'cpa_map': cpa_map,
            'link_clicks': conversions.get('link_click', 0),
            'landing_page_views': conversions.get('landing_page_view', 0),
            # 소구점
            'appeal_points': [a['category'] for a in appeals],
            'appeal_details': appeals,
            # 등급
            'grade': '',
        }

        ads.append(ad_result)

    return ads, daily_data

def grade_ads(ads):
    """소재 등급 분류"""
    if not ads:
        return ads

    # CPA 또는 CPC 기준으로 등급 분류
    active_ads = [a for a in ads if a['spend'] > 0]
    if not active_ads:
        return ads

    avg_cpc = sum(a['cpc'] for a in active_ads) / len(active_ads) if active_ads else 0
    avg_ctr = sum(a['ctr'] for a in active_ads) / len(active_ads) if active_ads else 0

    for ad in ads:
        if ad['spend'] < 50000:
            ad['grade'] = '⚫ 학습중'
        elif ad['ctr'] >= avg_ctr * 1.2 and ad['cpc'] <= avg_cpc * 0.8:
            ad['grade'] = '🟢 우수'
        elif ad['ctr'] <= avg_ctr * 0.7 or ad['cpc'] >= avg_cpc * 1.3:
            ad['grade'] = '🔴 부진'
        else:
            ad['grade'] = '🟡 보통'

    return ads

def generate_insights(ads, daily_data, account_name):
    """자동 인사이트 생성"""
    if not ads:
        return {'summary': f'{account_name}: 데이터 없음', 'details': []}

    active_ads = [a for a in ads if a['spend'] > 0]
    if not active_ads:
        return {'summary': f'{account_name}: 활성 소재 없음', 'details': []}

    total_spend = sum(a['spend'] for a in active_ads)
    total_clicks = sum(a['clicks'] for a in active_ads)
    total_impressions = sum(a['impressions'] for a in active_ads)
    avg_cpc = total_spend / total_clicks if total_clicks > 0 else 0
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    total_link_clicks = sum(a['link_clicks'] for a in active_ads)

    # TOP/WORST 소재
    sorted_by_ctr = sorted(active_ads, key=lambda x: x['ctr'], reverse=True)
    top_ad = sorted_by_ctr[0] if sorted_by_ctr else None
    worst_ad = sorted_by_ctr[-1] if len(sorted_by_ctr) > 1 else None

    # 소구점별 성과
    appeal_perf = {}
    for ad in active_ads:
        for ap in ad['appeal_points']:
            if ap not in appeal_perf:
                appeal_perf[ap] = {'spend': 0, 'clicks': 0, 'impressions': 0, 'count': 0}
            appeal_perf[ap]['spend'] += ad['spend']
            appeal_perf[ap]['clicks'] += ad['clicks']
            appeal_perf[ap]['impressions'] += ad['impressions']
            appeal_perf[ap]['count'] += 1

    for ap in appeal_perf:
        p = appeal_perf[ap]
        p['avg_cpc'] = p['spend'] / p['clicks'] if p['clicks'] > 0 else 0
        p['avg_ctr'] = (p['clicks'] / p['impressions'] * 100) if p['impressions'] > 0 else 0

    # 피로도 감지
    fatigue_alerts = []
    if daily_data and len(daily_data) >= 3:
        ctrs = [float(d.get('ctr', 0)) for d in daily_data[-3:]]
        if len(ctrs) == 3 and ctrs[0] > ctrs[1] > ctrs[2]:
            fatigue_alerts.append('🔄 CTR 3일 연속 하락 → 소재 교체 검토 필요')

    for ad in active_ads:
        if ad['frequency'] > 3.0:
            fatigue_alerts.append(f'⚠️ {ad["ad_name"]}: 빈도 {ad["frequency"]:.1f}회 → 타겟 확장 필요')

    # 개선방안
    improvements = []
    poor_ads = [a for a in active_ads if a['grade'] == '🔴 부진']
    good_ads = [a for a in active_ads if a['grade'] == '🟢 우수']

    if poor_ads:
        names = ', '.join([a['ad_name'][:15] for a in poor_ads[:3]])
        improvements.append(f'🔴 부진 소재 {len(poor_ads)}개 OFF 권장: {names}')
    if good_ads:
        names = ', '.join([a['ad_name'][:15] for a in good_ads[:3]])
        improvements.append(f'🟢 우수 소재 예산 증액 권장: {names}')
    if good_ads:
        top_appeals = good_ads[0]['appeal_points']
        if top_appeals:
            improvements.append(f'💡 TOP 소재 소구점: {", ".join(top_appeals[:3])} → 이 조합으로 신규 소재 제작 추천')

    insight = {
        'summary': {
            'total_spend': total_spend,
            'total_clicks': total_clicks,
            'total_impressions': total_impressions,
            'total_link_clicks': total_link_clicks,
            'avg_cpc': round(avg_cpc, 0),
            'avg_ctr': round(avg_ctr, 2),
            'active_ads': len(active_ads),
            'total_ads': len(ads),
        },
        'top_ad': {
            'name': top_ad['ad_name'] if top_ad else '',
            'ctr': top_ad['ctr'] if top_ad else 0,
            'cpc': top_ad['cpc'] if top_ad else 0,
            'appeals': top_ad['appeal_points'] if top_ad else [],
        } if top_ad else None,
        'worst_ad': {
            'name': worst_ad['ad_name'] if worst_ad else '',
            'ctr': worst_ad['ctr'] if worst_ad else 0,
            'cpc': worst_ad['cpc'] if worst_ad else 0,
        } if worst_ad else None,
        'appeal_performance': appeal_perf,
        'fatigue_alerts': fatigue_alerts,
        'improvements': improvements,
        'grade_distribution': {
            '🟢 우수': len([a for a in ads if a['grade'] == '🟢 우수']),
            '🟡 보통': len([a for a in ads if a['grade'] == '🟡 보통']),
            '🔴 부진': len([a for a in ads if a['grade'] == '🔴 부진']),
            '⚫ 학습중': len([a for a in ads if a['grade'] == '⚫ 학습중']),
        }
    }

    return insight

def main():
    print('🚀 메타 광고 데이터 수집 시작...')
    print()

    # 1. 전체 광고 계정 가져오기
    accounts = get_all_ad_accounts()
    active_accounts = [a for a in accounts if a['account_status'] == 1 and a['currency'] == 'KRW']
    print(f'🇰🇷 KRW 활성 계정: {len(active_accounts)}개')
    print()

    all_data = {}

    for acc in active_accounts:
        acc_id = acc['id']
        acc_name = acc['name']

        print(f'📥 {acc_name} 데이터 수집 중...')

        try:
            ads, daily = get_ads_with_insights(acc_id, acc_name, days=30)

            if not ads or all(a['spend'] == 0 for a in ads):
                print(f'   ⬜ 데이터 없음, 스킵')
                continue

            # 등급 분류
            ads = grade_ads(ads)

            # 인사이트 생성
            insights = generate_insights(ads, daily, acc_name)

            active_count = len([a for a in ads if a['spend'] > 0])
            total_spend = sum(a['spend'] for a in ads)

            all_data[acc_name] = {
                'account_id': acc_id,
                'account_name': acc_name,
                'ads': ads,
                'daily_data': daily,
                'insights': insights,
            }

            print(f'   ✅ 소재 {len(ads)}개 (활성 {active_count}개) | 소진 {total_spend:,.0f}원')

        except Exception as e:
            print(f'   ❌ 에러: {e}')

    # JSON 저장
    output = {
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'period': '30일',
        'brands': all_data,
    }

    with open('dashboard_data.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)

    print()
    print(f'✅ dashboard_data.json 저장 완료!')
    print(f'📊 총 {len(all_data)}개 브랜드 데이터 수집 완료')

    # 요약
    print()
    print('=== 수집 결과 요약 ===')
    for name, data in all_data.items():
        s = data['insights']['summary']
        print(f'{name}: 소진 {s["total_spend"]:,.0f}원 | 클릭 {s["total_clicks"]:,}회 | CTR {s["avg_ctr"]:.2f}%')

if __name__ == '__main__':
    main()
