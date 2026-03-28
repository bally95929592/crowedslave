"""
Meta Marketing API 광고 데이터 수집기

비즈니스 포트폴리오의 모든 광고 계정에서 캠페인, 광고세트, 광고(크리에이티브) 데이터를 수집하여
Google Sheets와 JSON 파일로 저장합니다.
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta
from typing import Optional

import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경변수 설정
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
META_BUSINESS_ID = os.getenv("META_BUSINESS_ID")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

# API 기본 설정
API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("meta_api_collector.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# 수집할 인사이트 필드
INSIGHT_FIELDS = [
    "campaign_id",
    "campaign_name",
    "adset_id",
    "adset_name",
    "ad_id",
    "ad_name",
    "impressions",
    "reach",
    "clicks",
    "spend",
    "actions",
    "cpc",
    "cpm",
    "ctr",
    "frequency",
    "cost_per_action_type",
    "video_avg_time_watched_actions",
    "video_p25_watched_actions",
    "video_p50_watched_actions",
    "video_p75_watched_actions",
    "video_p100_watched_actions",
    "video_play_actions",
]

# 크리에이티브 필드
CREATIVE_FIELDS = [
    "thumbnail_url",
    "body",
    "title",
    "object_story_spec",
    "asset_feed_spec",
]


def calculate_date_range(days: int) -> dict:
    """날짜 범위를 계산합니다."""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    logger.info(f"📅 날짜 범위: {start_date} ~ {end_date} ({days}일간)")
    return {"since": start_date, "until": end_date}


def api_request(url: str, params: dict, max_retries: int = 5) -> Optional[dict]:
    """
    Meta API 요청을 수행합니다.
    레이트 리밋 및 오류 처리를 포함합니다.
    """
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.json()

            # 레이트 리밋 처리 (HTTP 429 또는 에러 코드 17/32/80004)
            if response.status_code == 429 or response.status_code == 400:
                error_data = response.json().get("error", {})
                error_code = error_data.get("code", 0)

                if error_code in (17, 32, 80004):
                    wait_time = min(60 * attempt, 300)
                    logger.warning(
                        f"⚠️ API 레이트 리밋 도달 (코드: {error_code}). "
                        f"{wait_time}초 대기 후 재시도... (시도 {attempt}/{max_retries})"
                    )
                    time.sleep(wait_time)
                    continue

            # 기타 오류
            error_msg = response.json().get("error", {}).get("message", "알 수 없는 오류")
            logger.error(f"❌ API 오류 (HTTP {response.status_code}): {error_msg}")

            if attempt < max_retries:
                wait_time = 5 * attempt
                logger.info(f"🔄 {wait_time}초 후 재시도... (시도 {attempt}/{max_retries})")
                time.sleep(wait_time)
            else:
                logger.error(f"❌ 최대 재시도 횟수 초과. URL: {url}")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ 요청 타임아웃. 재시도 {attempt}/{max_retries}")
            time.sleep(5 * attempt)
        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ 연결 오류. 재시도 {attempt}/{max_retries}")
            time.sleep(5 * attempt)
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 요청 예외 발생: {e}")
            if attempt == max_retries:
                return None
            time.sleep(5 * attempt)

    return None


def fetch_all_pages(url: str, params: dict) -> list:
    """
    페이지네이션을 처리하여 모든 결과를 수집합니다.
    """
    all_data = []

    while True:
        result = api_request(url, params)
        if not result:
            break

        data = result.get("data", [])
        all_data.extend(data)
        logger.info(f"  → 현재 페이지에서 {len(data)}건 수집 (누적: {len(all_data)}건)")

        # 다음 페이지 확인
        paging = result.get("paging", {})
        next_url = paging.get("next")
        if next_url:
            url = next_url
            params = {}  # next URL에 파라미터가 포함되어 있음
            time.sleep(1)  # 레이트 리밋 방지를 위한 딜레이
        else:
            break

    return all_data


def get_all_ad_accounts(business_id: str, token: str) -> list:
    """
    비즈니스 포트폴리오의 모든 광고 계정을 조회합니다.
    """
    logger.info(f"🏢 비즈니스 ID {business_id}의 광고 계정 목록 조회 중...")

    url = f"{BASE_URL}/{business_id}/owned_ad_accounts"
    params = {
        "access_token": token,
        "fields": "id,name,account_id,account_status,currency,timezone_name",
        "limit": 100,
    }

    accounts = fetch_all_pages(url, params)

    # 활성 계정만 필터링 (account_status: 1 = 활성)
    active_accounts = [acc for acc in accounts if acc.get("account_status") == 1]

    logger.info(
        f"✅ 총 {len(accounts)}개 광고 계정 중 활성 계정 {len(active_accounts)}개 발견"
    )

    for acc in active_accounts:
        logger.info(f"  - {acc.get('name')} ({acc.get('id')}) [{acc.get('currency')}]")

    return active_accounts


def get_campaigns(account_id: str, token: str, date_range: dict) -> list:
    """
    광고 계정의 캠페인 데이터와 인사이트를 수집합니다.
    """
    logger.info(f"📊 캠페인 데이터 수집 중... (계정: {account_id})")

    url = f"{BASE_URL}/{account_id}/campaigns"
    params = {
        "access_token": token,
        "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time",
        "limit": 100,
    }

    campaigns = fetch_all_pages(url, params)
    logger.info(f"  → {len(campaigns)}개 캠페인 발견")

    # 각 캠페인의 인사이트 수집
    for campaign in campaigns:
        campaign_id = campaign.get("id")
        insights = _get_insights(
            entity_id=campaign_id,
            token=token,
            date_range=date_range,
            level="campaign",
        )
        campaign["insights"] = insights

    return campaigns


def get_adsets(account_id: str, token: str, date_range: dict) -> list:
    """
    광고 계정의 광고세트 데이터와 인사이트를 수집합니다.
    """
    logger.info(f"📋 광고세트 데이터 수집 중... (계정: {account_id})")

    url = f"{BASE_URL}/{account_id}/adsets"
    params = {
        "access_token": token,
        "fields": (
            "id,name,status,campaign_id,daily_budget,lifetime_budget,"
            "targeting,optimization_goal,billing_event,bid_strategy,start_time,end_time"
        ),
        "limit": 100,
    }

    adsets = fetch_all_pages(url, params)
    logger.info(f"  → {len(adsets)}개 광고세트 발견")

    # 각 광고세트의 인사이트 수집
    for adset in adsets:
        adset_id = adset.get("id")
        insights = _get_insights(
            entity_id=adset_id,
            token=token,
            date_range=date_range,
            level="adset",
        )
        adset["insights"] = insights

    return adsets


def get_ads_with_creatives(account_id: str, token: str, date_range: dict) -> list:
    """
    광고 데이터와 크리에이티브 정보(썸네일, 텍스트, 제목, URL, CTA)를 수집합니다.
    """
    logger.info(f"🎨 광고 및 크리에이티브 데이터 수집 중... (계정: {account_id})")

    url = f"{BASE_URL}/{account_id}/ads"
    params = {
        "access_token": token,
        "fields": (
            "id,name,status,campaign_id,adset_id,"
            "creative{id,thumbnail_url,body,title,object_story_spec,asset_feed_spec}"
        ),
        "limit": 100,
    }

    ads = fetch_all_pages(url, params)
    logger.info(f"  → {len(ads)}개 광고 발견")

    # 각 광고의 인사이트 수집 및 크리에이티브 정보 추출
    for ad in ads:
        ad_id = ad.get("id")

        # 인사이트 수집
        insights = _get_insights(
            entity_id=ad_id,
            token=token,
            date_range=date_range,
            level="ad",
        )
        ad["insights"] = insights

        # 크리에이티브 정보 추출
        creative = ad.get("creative", {})
        ad["creative_info"] = _extract_creative_info(creative)

    return ads


def _get_insights(entity_id: str, token: str, date_range: dict, level: str) -> list:
    """
    특정 엔티티(캠페인/광고세트/광고)의 인사이트를 수집합니다.
    """
    url = f"{BASE_URL}/{entity_id}/insights"
    params = {
        "access_token": token,
        "fields": ",".join(INSIGHT_FIELDS),
        "time_range": json.dumps(date_range),
        "time_increment": 1,  # 일별 데이터
        "limit": 100,
    }

    insights = fetch_all_pages(url, params)
    return insights


def _extract_creative_info(creative: dict) -> dict:
    """
    크리에이티브 데이터에서 주요 정보를 추출합니다.
    """
    info = {
        "creative_id": creative.get("id", ""),
        "thumbnail_url": creative.get("thumbnail_url", ""),
        "body": creative.get("body", ""),
        "title": creative.get("title", ""),
        "link_url": "",
        "call_to_action_type": "",
    }

    # object_story_spec에서 링크 URL 및 CTA 추출
    story_spec = creative.get("object_story_spec", {})

    # 링크 광고
    link_data = story_spec.get("link_data", {})
    if link_data:
        info["link_url"] = link_data.get("link", "")
        cta = link_data.get("call_to_action", {})
        info["call_to_action_type"] = cta.get("type", "")
        if not info["body"]:
            info["body"] = link_data.get("message", "")
        if not info["title"]:
            info["title"] = link_data.get("name", "")

    # 동영상 광고
    video_data = story_spec.get("video_data", {})
    if video_data:
        info["link_url"] = video_data.get("link", info["link_url"])
        cta = video_data.get("call_to_action", {})
        if cta:
            info["call_to_action_type"] = cta.get("type", info["call_to_action_type"])
            cta_value = cta.get("value", {})
            if cta_value and not info["link_url"]:
                info["link_url"] = cta_value.get("link", "")

    # asset_feed_spec에서 추가 정보 추출 (다이나믹 크리에이티브)
    asset_feed = creative.get("asset_feed_spec", {})
    if asset_feed:
        bodies = asset_feed.get("bodies", [])
        if bodies and not info["body"]:
            info["body"] = bodies[0].get("text", "")

        titles = asset_feed.get("titles", [])
        if titles and not info["title"]:
            info["title"] = titles[0].get("text", "")

        link_urls = asset_feed.get("link_urls", [])
        if link_urls and not info["link_url"]:
            info["link_url"] = link_urls[0].get("website_url", "")

        call_to_action_types = asset_feed.get("call_to_action_types", [])
        if call_to_action_types and not info["call_to_action_type"]:
            info["call_to_action_type"] = call_to_action_types[0]

    return info


def _flatten_ad_data(account: dict, ad: dict, insight: dict) -> dict:
    """
    광고 데이터를 시트 저장용으로 평탄화합니다.
    """
    creative_info = ad.get("creative_info", {})

    # actions에서 주요 전환 추출
    actions = insight.get("actions", [])
    action_map = {a.get("action_type"): a.get("value") for a in actions}

    # cost_per_action_type 추출
    cost_per_actions = insight.get("cost_per_action_type", [])
    cost_action_map = {a.get("action_type"): a.get("value") for a in cost_per_actions}

    # 동영상 조회 지표 추출
    video_views = {}
    for field_name in [
        "video_play_actions",
        "video_p25_watched_actions",
        "video_p50_watched_actions",
        "video_p75_watched_actions",
        "video_p100_watched_actions",
        "video_avg_time_watched_actions",
    ]:
        field_data = insight.get(field_name, [])
        if field_data:
            video_views[field_name] = field_data[0].get("value", "0")
        else:
            video_views[field_name] = "0"

    return {
        "날짜": insight.get("date_start", ""),
        "계정_ID": account.get("id", ""),
        "계정_이름": account.get("name", ""),
        "캠페인_ID": insight.get("campaign_id", ad.get("campaign_id", "")),
        "캠페인_이름": insight.get("campaign_name", ""),
        "광고세트_ID": insight.get("adset_id", ad.get("adset_id", "")),
        "광고세트_이름": insight.get("adset_name", ""),
        "광고_ID": insight.get("ad_id", ad.get("id", "")),
        "광고_이름": insight.get("ad_name", ad.get("name", "")),
        "상태": ad.get("status", ""),
        "노출수": insight.get("impressions", "0"),
        "도달수": insight.get("reach", "0"),
        "클릭수": insight.get("clicks", "0"),
        "지출액": insight.get("spend", "0"),
        "CPC": insight.get("cpc", "0"),
        "CPM": insight.get("cpm", "0"),
        "CTR": insight.get("ctr", "0"),
        "빈도": insight.get("frequency", "0"),
        "링크클릭": action_map.get("link_click", "0"),
        "랜딩페이지뷰": action_map.get("landing_page_view", "0"),
        "구매": action_map.get("purchase", action_map.get("offsite_conversion.fb_pixel_purchase", "0")),
        "장바구니": action_map.get("add_to_cart", action_map.get("offsite_conversion.fb_pixel_add_to_cart", "0")),
        "리드": action_map.get("lead", action_map.get("offsite_conversion.fb_pixel_lead", "0")),
        "등록완료": action_map.get("complete_registration", "0"),
        "구매당비용": cost_action_map.get("purchase", cost_action_map.get("offsite_conversion.fb_pixel_purchase", "0")),
        "리드당비용": cost_action_map.get("lead", cost_action_map.get("offsite_conversion.fb_pixel_lead", "0")),
        "동영상재생": video_views.get("video_play_actions", "0"),
        "동영상_25%": video_views.get("video_p25_watched_actions", "0"),
        "동영상_50%": video_views.get("video_p50_watched_actions", "0"),
        "동영상_75%": video_views.get("video_p75_watched_actions", "0"),
        "동영상_100%": video_views.get("video_p100_watched_actions", "0"),
        "평균시청시간": video_views.get("video_avg_time_watched_actions", "0"),
        "썸네일_URL": creative_info.get("thumbnail_url", ""),
        "광고_텍스트": creative_info.get("body", ""),
        "헤드라인": creative_info.get("title", ""),
        "링크_URL": creative_info.get("link_url", ""),
        "CTA_타입": creative_info.get("call_to_action_type", ""),
    }


def save_to_sheets(data: list) -> None:
    """
    수집된 데이터를 Google Sheets에 저장합니다.
    """
    if not SPREADSHEET_ID:
        logger.warning("⚠️ SPREADSHEET_ID가 설정되지 않아 시트 저장을 건너뜁니다.")
        return

    if not data:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return

    logger.info(f"📝 Google Sheets에 {len(data)}건의 데이터 저장 중...")

    try:
        # 구글 인증
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "credentials.json", scope
        )
        client = gspread.authorize(creds)

        # 스프레드시트 열기
        spreadsheet = client.open_by_key(SPREADSHEET_ID)

        # "Meta_광고데이터" 시트 찾기 또는 생성
        sheet_name = "Meta_광고데이터"
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            logger.info(f"  → 기존 '{sheet_name}' 시트 발견. 데이터를 업데이트합니다.")
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name, rows=str(len(data) + 1), cols=str(len(data[0]))
            )
            logger.info(f"  → '{sheet_name}' 시트를 새로 생성했습니다.")

        # 헤더 작성
        headers = list(data[0].keys())

        # 데이터 행 준비
        rows = [headers]
        for item in data:
            row = [str(item.get(h, "")) for h in headers]
            rows.append(row)

        # 시트 크기 조정
        if worksheet.row_count < len(rows) or worksheet.col_count < len(headers):
            worksheet.resize(rows=max(len(rows), worksheet.row_count), cols=len(headers))

        # 기존 데이터 삭제 후 새 데이터 입력
        worksheet.clear()

        # 배치로 업데이트 (API 호출 최소화)
        batch_size = 500
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            start_row = i + 1
            end_row = start_row + len(batch) - 1
            end_col = chr(ord("A") + len(headers) - 1) if len(headers) <= 26 else "AZ"

            # 열 이름 계산 (26개 이상 열 지원)
            def col_letter(n):
                result = ""
                while n > 0:
                    n, remainder = divmod(n - 1, 26)
                    result = chr(65 + remainder) + result
                return result

            end_col_letter = col_letter(len(headers))
            cell_range = f"A{start_row}:{end_col_letter}{end_row}"
            worksheet.update(range_name=cell_range, values=batch)

            logger.info(f"  → {i + 1}~{min(i + batch_size, len(rows))}행 저장 완료")
            time.sleep(1)  # API 레이트 리밋 방지

        # 헤더 서식 설정 (볼드체)
        worksheet.format("1:1", {"textFormat": {"bold": True}})

        logger.info(f"✅ Google Sheets 저장 완료! (총 {len(data)}건)")

    except FileNotFoundError:
        logger.error("❌ credentials.json 파일을 찾을 수 없습니다. 구글 서비스 계정 키 파일을 확인하세요.")
    except gspread.exceptions.SpreadsheetNotFound:
        logger.error(f"❌ 스프레드시트를 찾을 수 없습니다. SPREADSHEET_ID를 확인하세요: {SPREADSHEET_ID}")
    except gspread.exceptions.APIError as e:
        logger.error(f"❌ Google Sheets API 오류: {e}")
    except Exception as e:
        logger.error(f"❌ Google Sheets 저장 중 예외 발생: {e}")


def save_to_json(data: list, filename: str = "meta_ads_data.json") -> None:
    """
    수집된 데이터를 JSON 파일로 저장합니다 (대시보드 연동용).
    """
    if not data:
        logger.warning("⚠️ 저장할 데이터가 없습니다.")
        return

    logger.info(f"💾 JSON 파일로 {len(data)}건의 데이터 저장 중...")

    try:
        output = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_records": len(data),
            "data": data,
        }

        # 계정별 요약 통계 추가
        account_summary = {}
        for item in data:
            acc_name = item.get("계정_이름", "알 수 없음")
            if acc_name not in account_summary:
                account_summary[acc_name] = {
                    "계정_ID": item.get("계정_ID", ""),
                    "총_지출액": 0,
                    "총_노출수": 0,
                    "총_클릭수": 0,
                    "총_도달수": 0,
                    "광고_수": 0,
                }
            summary = account_summary[acc_name]
            summary["총_지출액"] += float(item.get("지출액", 0))
            summary["총_노출수"] += int(item.get("노출수", 0))
            summary["총_클릭수"] += int(item.get("클릭수", 0))
            summary["총_도달수"] += int(item.get("도달수", 0))
            summary["광고_수"] += 1

        # 소수점 정리
        for acc_name, summary in account_summary.items():
            summary["총_지출액"] = round(summary["총_지출액"], 2)

        output["account_summary"] = account_summary

        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ JSON 파일 저장 완료: {filepath}")

    except Exception as e:
        logger.error(f"❌ JSON 저장 중 오류 발생: {e}")


def main():
    """
    메인 실행 함수: 전체 데이터 수집 프로세스를 조율합니다.
    """
    parser = argparse.ArgumentParser(description="Meta Marketing API 광고 데이터 수집기")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        choices=[3, 5, 7, 15, 30],
        help="수집할 기간 (일수). 기본값: 7",
    )
    parser.add_argument(
        "--json-output",
        type=str,
        default="meta_ads_data.json",
        help="JSON 출력 파일명. 기본값: meta_ads_data.json",
    )
    parser.add_argument(
        "--skip-sheets",
        action="store_true",
        help="Google Sheets 저장을 건너뜁니다.",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🚀 Meta Marketing API 광고 데이터 수집 시작")
    logger.info("=" * 60)

    # 환경변수 확인
    if not META_ACCESS_TOKEN:
        logger.error("❌ META_ACCESS_TOKEN이 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)
    if not META_BUSINESS_ID:
        logger.error("❌ META_BUSINESS_ID가 설정되지 않았습니다. .env 파일을 확인하세요.")
        sys.exit(1)

    logger.info(f"📌 비즈니스 ID: {META_BUSINESS_ID}")
    logger.info(f"📌 수집 기간: 최근 {args.days}일")

    # 날짜 범위 계산
    date_range = calculate_date_range(args.days)

    # 1. 모든 광고 계정 조회
    accounts = get_all_ad_accounts(META_BUSINESS_ID, META_ACCESS_TOKEN)
    if not accounts:
        logger.error("❌ 활성 광고 계정이 없습니다. 비즈니스 ID와 토큰을 확인하세요.")
        sys.exit(1)

    # 2. 각 계정별 데이터 수집
    all_flattened_data = []
    collection_start = time.time()

    for idx, account in enumerate(accounts, 1):
        account_id = account.get("id")
        account_name = account.get("name", "알 수 없음")

        logger.info("")
        logger.info(f"{'─' * 50}")
        logger.info(f"🔄 [{idx}/{len(accounts)}] 계정 처리 중: {account_name} ({account_id})")
        logger.info(f"{'─' * 50}")

        try:
            # 캠페인 데이터 수집
            campaigns = get_campaigns(account_id, META_ACCESS_TOKEN, date_range)
            logger.info(f"  ✅ 캠페인 {len(campaigns)}개 수집 완료")

            # 광고세트 데이터 수집
            adsets = get_adsets(account_id, META_ACCESS_TOKEN, date_range)
            logger.info(f"  ✅ 광고세트 {len(adsets)}개 수집 완료")

            # 광고 + 크리에이티브 데이터 수집
            ads = get_ads_with_creatives(account_id, META_ACCESS_TOKEN, date_range)
            logger.info(f"  ✅ 광고 {len(ads)}개 수집 완료")

            # 광고 데이터 평탄화 (시트/JSON 저장용)
            for ad in ads:
                insights = ad.get("insights", [])
                if insights:
                    for insight in insights:
                        flat = _flatten_ad_data(account, ad, insight)
                        all_flattened_data.append(flat)
                else:
                    # 인사이트가 없는 광고도 기본 정보 포함
                    flat = _flatten_ad_data(account, ad, {})
                    all_flattened_data.append(flat)

        except Exception as e:
            logger.error(f"❌ 계정 {account_name} 처리 중 오류 발생: {e}")
            continue

        # 계정 간 딜레이 (레이트 리밋 방지)
        if idx < len(accounts):
            logger.info("  ⏳ 다음 계정 처리 전 3초 대기...")
            time.sleep(3)

    collection_duration = time.time() - collection_start

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"📊 데이터 수집 완료! 총 {len(all_flattened_data)}건 (소요시간: {collection_duration:.1f}초)")
    logger.info("=" * 60)

    # 3. Google Sheets에 저장
    if not args.skip_sheets:
        save_to_sheets(all_flattened_data)
    else:
        logger.info("⏭️ Google Sheets 저장 건너뜀 (--skip-sheets 옵션)")

    # 4. JSON 파일로 저장
    save_to_json(all_flattened_data, filename=args.json_output)

    logger.info("")
    logger.info("=" * 60)
    logger.info("🎉 모든 작업이 완료되었습니다!")
    logger.info(f"  - 수집 계정 수: {len(accounts)}개")
    logger.info(f"  - 총 데이터 건수: {len(all_flattened_data)}건")
    logger.info(f"  - JSON 파일: {args.json_output}")
    if not args.skip_sheets and SPREADSHEET_ID:
        logger.info(f"  - Google Sheets: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
