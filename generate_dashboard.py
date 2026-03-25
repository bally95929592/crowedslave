# -*- coding: utf-8 -*-
"""
대시보드 HTML 생성기
====================
구글 스프레드시트에서 브랜드별 일별 광고 데이터를 읽어와
인터랙티브 다크 테마 대시보드(index.html)를 생성합니다.

사용법:
    python generate_dashboard.py

필요 파일:
    - credentials.json (Google Service Account 키)

출력:
    - index.html (자체 완결형 대시보드, GitHub Pages 호환)
"""

import gspread
import json
import sys
import os
from google.oauth2.service_account import Credentials
from datetime import datetime

# ============================================================
# 설정
# ============================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

SPREADSHEET_ID = "1MgqPG7eKlBHLq4uyyE_aXsggW0Z91m-ZVHM6rn1WBzA"
SKIP_SHEETS = {"시트 1", "시트1", "Sheet1", "Sheet 1"}

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "credentials.json")
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# 컬럼 매핑 (헤더 텍스트 -> 내부 키)
COLUMN_MAP = {
    "년": "year",
    "월": "month",
    "일": "day",
    "매체": "media",
    "전환수(등록)": "conversions",
    "진성DB": "db",
    "비용(일)": "cost",
    "노출(일)": "impressions",
    "클릭(일)": "clicks",
    "CPM": "cpm",
    "CPC": "cpc",
    "CTR": "ctr",
    "CVR": "cvr",
    "CPA": "cpa",
    "특이사항": "notes",
}


# ============================================================
# 유틸리티
# ============================================================
def to_num(val):
    """쉼표, %, 공백, 원화 기호 등을 처리하여 숫자 변환."""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("%", "").replace("₩", "").replace("원", "").strip()
    if not s or s == "-" or s == "N/A" or s == "#DIV/0!":
        return 0
    try:
        return float(s)
    except ValueError:
        return 0


def safe_div(a, b):
    """0 나누기 방지."""
    if b == 0:
        return 0
    return a / b


# ============================================================
# Google Sheets 연결 및 데이터 읽기
# ============================================================
def connect():
    """Google Sheets에 연결하고 스프레드시트 객체를 반환."""
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[오류] credentials.json 파일을 찾을 수 없습니다: {CREDENTIALS_FILE}")
        print("Google Cloud Console에서 서비스 계정 키를 다운로드하세요.")
        sys.exit(1)

    print("[1/4] Google Sheets에 연결 중...")
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    print(f"  -> 스프레드시트 '{spreadsheet.title}' 연결 완료")
    return spreadsheet


def read_all_brands(spreadsheet):
    """모든 브랜드 시트를 읽어 브랜드별 일별 데이터 딕셔너리를 반환."""
    all_data = {}
    worksheets = spreadsheet.worksheets()
    brand_sheets = [ws for ws in worksheets if ws.title.strip() not in SKIP_SHEETS]

    if not brand_sheets:
        print("[오류] 읽을 수 있는 브랜드 시트가 없습니다.")
        sys.exit(1)

    print(f"\n[2/4] 브랜드 시트 읽기 ({len(brand_sheets)}개 발견)...")

    for ws in brand_sheets:
        brand_name = ws.title.strip()
        print(f"  -> '{brand_name}' 시트 읽는 중...", end=" ")

        try:
            records = ws.get_all_values()
        except Exception as e:
            print(f"실패 ({e})")
            continue

        if len(records) < 2:
            print("데이터 없음 (건너뜀)")
            continue

        # 헤더 파싱
        raw_headers = records[0]
        header_indices = {}
        for i, h in enumerate(raw_headers):
            h_clean = h.strip()
            if h_clean in COLUMN_MAP:
                header_indices[COLUMN_MAP[h_clean]] = i

        # 필수 컬럼 확인
        required = {"year", "month", "day", "cost"}
        missing = required - set(header_indices.keys())
        if missing:
            print(f"필수 컬럼 누락: {missing} (건너뜀)")
            continue

        # 데이터 행 파싱
        rows = []
        for row_idx, row in enumerate(records[1:], start=2):
            year = to_num(row[header_indices["year"]]) if "year" in header_indices else 0
            month = to_num(row[header_indices["month"]]) if "month" in header_indices else 0
            day = to_num(row[header_indices["day"]]) if "day" in header_indices else 0

            if year == 0 or month == 0 or day == 0:
                continue

            try:
                date_str = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                continue

            def get_val(key):
                if key in header_indices and header_indices[key] < len(row):
                    return to_num(row[header_indices[key]])
                return 0

            cost = get_val("cost")
            impressions = get_val("impressions")
            clicks = get_val("clicks")
            conversions = get_val("conversions")
            db = get_val("db")
            notes_idx = header_indices.get("notes")
            notes = ""
            if notes_idx is not None and notes_idx < len(row):
                notes = str(row[notes_idx]).strip()

            # 원시 데이터에서 지표 재계산 (시트 값보다 정확)
            calc_cpc = safe_div(cost, clicks)
            calc_cpm = safe_div(cost, impressions) * 1000
            calc_ctr = safe_div(clicks, impressions) * 100
            calc_cvr = safe_div(db, clicks) * 100
            calc_cpa = safe_div(cost, db)

            media = ""
            if "media" in header_indices and header_indices["media"] < len(row):
                media = str(row[header_indices["media"]]).strip()

            rows.append({
                "date": date_str,
                "media": media,
                "cost": round(cost, 0),
                "impressions": round(impressions, 0),
                "clicks": round(clicks, 0),
                "conversions": round(conversions, 0),
                "db": round(db, 0),
                "cpc": round(calc_cpc, 0),
                "cpm": round(calc_cpm, 0),
                "ctr": round(calc_ctr, 2),
                "cvr": round(calc_cvr, 2),
                "cpa": round(calc_cpa, 0),
                "notes": notes,
            })

        # 날짜순 정렬
        rows.sort(key=lambda r: r["date"])

        if rows:
            all_data[brand_name] = rows
            print(f"{len(rows)}행 로드 완료")
        else:
            print("유효 데이터 없음 (건너뜀)")

    return all_data


# ============================================================
# HTML 대시보드 생성
# ============================================================
def generate_html(all_data):
    """브랜드 데이터를 포함한 자체 완결형 index.html을 생성."""
    print(f"\n[3/4] 대시보드 HTML 생성 중...")

    brand_names = sorted(all_data.keys())
    data_json = json.dumps(all_data, ensure_ascii=False, separators=(",", ":"))
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>광고 성과 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
:root{{
  --bg:#1a1a2e;--card:#16213e;--accent:#0f3460;--highlight:#e94560;
  --text:#e8e8e8;--text-dim:#8892a4;--green:#00c853;--red:#ff5252;--yellow:#ffc107;
  --blue:#448aff;--border:#253555;
}}
body{{font-family:'Segoe UI','Apple SD Gothic Neo','Malgun Gothic',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;}}
.container{{max-width:1400px;margin:0 auto;padding:20px;}}

/* 헤더 */
.header{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;margin-bottom:24px;padding:20px 24px;background:var(--card);border-radius:12px;border:1px solid var(--border);}}
.header h1{{font-size:22px;font-weight:700;color:var(--text);}}
.header h1 span{{color:var(--highlight);}}
.header-right{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}}
.meta-info{{font-size:12px;color:var(--text-dim);}}

/* 셀렉트 */
select{{background:var(--accent);color:var(--text);border:1px solid var(--border);padding:10px 16px;border-radius:8px;font-size:14px;cursor:pointer;outline:none;min-width:180px;}}
select:hover{{border-color:var(--highlight);}}

/* 기간 버튼 */
.period-bar{{display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap;}}
.period-btn{{background:var(--card);color:var(--text-dim);border:1px solid var(--border);padding:10px 20px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s;}}
.period-btn:hover{{border-color:var(--highlight);color:var(--text);}}
.period-btn.active{{background:var(--highlight);color:#fff;border-color:var(--highlight);}}

/* KPI 카드 */
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px;}}
.kpi-card{{background:var(--card);border-radius:12px;padding:20px;border:1px solid var(--border);transition:transform .2s;}}
.kpi-card:hover{{transform:translateY(-2px);}}
.kpi-label{{font-size:13px;color:var(--text-dim);margin-bottom:8px;}}
.kpi-value{{font-size:28px;font-weight:700;margin-bottom:6px;}}
.kpi-change{{font-size:13px;display:flex;align-items:center;gap:4px;}}
.kpi-change.up{{color:var(--green);}}
.kpi-change.down{{color:var(--red);}}
.kpi-change.neutral{{color:var(--text-dim);}}

/* 차트 */
.chart-section{{background:var(--card);border-radius:12px;padding:24px;border:1px solid var(--border);margin-bottom:24px;}}
.chart-section h3{{font-size:16px;margin-bottom:16px;color:var(--text);}}
.chart-wrap{{position:relative;height:350px;}}

/* 비교 테이블 */
.comparison-section{{background:var(--card);border-radius:12px;padding:24px;border:1px solid var(--border);margin-bottom:24px;}}
.comparison-section h3{{font-size:16px;margin-bottom:16px;}}
table{{width:100%;border-collapse:collapse;}}
th,td{{padding:12px 16px;text-align:right;font-size:14px;border-bottom:1px solid var(--border);}}
th{{color:var(--text-dim);font-weight:600;text-align:right;}}
th:first-child,td:first-child{{text-align:left;}}
td.up{{color:var(--green);}}
td.down{{color:var(--red);}}

/* 인사이트 */
.insights-section{{background:var(--card);border-radius:12px;padding:24px;border:1px solid var(--border);margin-bottom:24px;}}
.insights-section h3{{font-size:16px;margin-bottom:16px;}}
.insight-item{{padding:12px 16px;margin-bottom:8px;border-radius:8px;font-size:14px;line-height:1.6;display:flex;align-items:flex-start;gap:10px;}}
.insight-item .icon{{font-size:18px;flex-shrink:0;margin-top:1px;}}
.insight-positive{{background:rgba(0,200,83,.08);border-left:3px solid var(--green);}}
.insight-negative{{background:rgba(255,82,82,.08);border-left:3px solid var(--red);}}
.insight-tip{{background:rgba(68,138,255,.08);border-left:3px solid var(--blue);}}
.no-data{{text-align:center;padding:60px 20px;color:var(--text-dim);font-size:16px;}}

/* 메타 API 섹션 */
.meta-section{{background:var(--card);border-radius:12px;padding:24px;border:1px solid var(--border);margin-bottom:24px;}}
.meta-section h3{{font-size:16px;margin-bottom:16px;display:flex;align-items:center;gap:8px;}}
.meta-badge{{background:var(--accent);color:var(--blue);font-size:11px;padding:3px 8px;border-radius:4px;}}
.setup-guide{{background:var(--bg);border-radius:8px;padding:20px;font-size:13px;line-height:1.8;}}
.setup-guide h4{{color:var(--highlight);margin-bottom:12px;font-size:14px;}}
.setup-guide ol{{padding-left:20px;}}
.setup-guide li{{margin-bottom:8px;color:var(--text-dim);}}
.setup-guide code{{background:var(--accent);padding:2px 6px;border-radius:4px;font-size:12px;color:var(--yellow);}}
.meta-placeholder{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;margin-top:16px;}}
.meta-ad-card{{background:var(--bg);border-radius:8px;padding:16px;border:1px dashed var(--border);text-align:center;}}
.meta-ad-card .thumb{{width:100%;height:120px;background:var(--accent);border-radius:6px;display:flex;align-items:center;justify-content:center;color:var(--text-dim);font-size:13px;margin-bottom:12px;}}
.meta-ad-card .metrics{{font-size:12px;color:var(--text-dim);}}

/* 푸터 */
.footer{{text-align:center;padding:20px;color:var(--text-dim);font-size:12px;}}

/* 반응형 */
@media(max-width:768px){{
  .container{{padding:12px;}}
  .header{{flex-direction:column;align-items:flex-start;padding:16px;}}
  .kpi-value{{font-size:22px;}}
  .chart-wrap{{height:250px;}}
  .period-btn{{padding:8px 14px;font-size:13px;}}
}}
</style>
</head>
<body>
<div class="container">

  <!-- 헤더 -->
  <div class="header">
    <h1>광고 성과 <span>대시보드</span></h1>
    <div class="header-right">
      <select id="brandSelect" onchange="onBrandChange()">
        <option value="">브랜드 선택</option>
      </select>
      <span class="meta-info">마지막 업데이트: {generated_at}</span>
    </div>
  </div>

  <!-- 기간 선택 -->
  <div class="period-bar" id="periodBar">
    <button class="period-btn" data-days="3" onclick="setPeriod(3)">3일</button>
    <button class="period-btn" data-days="5" onclick="setPeriod(5)">5일</button>
    <button class="period-btn active" data-days="7" onclick="setPeriod(7)">7일</button>
    <button class="period-btn" data-days="15" onclick="setPeriod(15)">15일</button>
    <button class="period-btn" data-days="30" onclick="setPeriod(30)">30일</button>
  </div>

  <!-- KPI 카드 -->
  <div class="kpi-grid" id="kpiGrid"></div>

  <!-- 일별 차트 -->
  <div class="chart-section" id="chartSection" style="display:none;">
    <h3>일별 추이</h3>
    <div class="chart-wrap"><canvas id="dailyChart"></canvas></div>
  </div>

  <!-- 기간 비교 -->
  <div class="comparison-section" id="compSection" style="display:none;">
    <h3 id="compTitle">기간 비교</h3>
    <table id="compTable"><thead></thead><tbody></tbody></table>
  </div>

  <!-- 자동 인사이트 -->
  <div class="insights-section" id="insightSection" style="display:none;">
    <h3>자동 분석 인사이트</h3>
    <div id="insightList"></div>
  </div>

  <!-- 메타 소재 분석 (플레이스홀더) -->
  <div class="meta-section">
    <h3>메타 소재 분석 <span class="meta-badge">API 연동 필요</span></h3>
    <div class="meta-placeholder">
      <div class="meta-ad-card"><div class="thumb">소재 미리보기</div><div class="metrics">CPC: - | CTR: - | CPA: -</div></div>
      <div class="meta-ad-card"><div class="thumb">소재 미리보기</div><div class="metrics">CPC: - | CTR: - | CPA: -</div></div>
      <div class="meta-ad-card"><div class="thumb">소재 미리보기</div><div class="metrics">CPC: - | CTR: - | CPA: -</div></div>
    </div>
    <div class="setup-guide" style="margin-top:20px;">
      <h4>Meta Marketing API 연동 가이드</h4>
      <ol>
        <li><a href="https://developers.facebook.com" style="color:var(--blue);" target="_blank">developers.facebook.com</a> 에서 앱을 생성합니다.</li>
        <li>앱에 <strong>Marketing API</strong> 제품을 추가합니다.</li>
        <li><code>ads_read</code> 권한이 포함된 사용자 액세스 토큰을 발급받습니다.</li>
        <li>장기 토큰(60일)으로 교환합니다:
          <br><code>GET /oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN</code>
        </li>
        <li>광고 계정 ID(<code>act_XXXXXXXXX</code>)를 확인합니다.</li>
        <li>발급받은 토큰과 계정 ID를 <code>config.json</code>에 저장하면 대시보드에 소재별 성과가 자동 연동됩니다.</li>
      </ol>
    </div>
  </div>

  <div class="footer">광고 성과 대시보드 &middot; 데이터 기준: {generated_at}</div>
</div>

<script>
// ============================================================
// 데이터 (Python에서 임베딩)
// ============================================================
const BRAND_DATA = {data_json};
const BRANDS = {json.dumps(brand_names, ensure_ascii=False)};

// ============================================================
// 상태
// ============================================================
let currentBrand = BRANDS[0] || "";
let currentPeriod = 7;
let chartInstance = null;

// ============================================================
// 초기화
// ============================================================
(function init() {{
  const sel = document.getElementById("brandSelect");
  BRANDS.forEach(b => {{
    const opt = document.createElement("option");
    opt.value = b; opt.textContent = b;
    sel.appendChild(opt);
  }});
  if (BRANDS.length > 0) {{
    sel.value = BRANDS[0];
    render();
  }}
}})();

function onBrandChange() {{
  currentBrand = document.getElementById("brandSelect").value;
  render();
}}

function setPeriod(days) {{
  currentPeriod = days;
  document.querySelectorAll(".period-btn").forEach(b => {{
    b.classList.toggle("active", parseInt(b.dataset.days) === days);
  }});
  render();
}}

// ============================================================
// 포맷 유틸
// ============================================================
function fmt(n, type) {{
  if (n === null || n === undefined || isNaN(n)) return "-";
  if (type === "money") return "\\u20A9" + Math.round(n).toLocaleString("ko-KR");
  if (type === "pct") return n.toFixed(2) + "%";
  if (type === "int") return Math.round(n).toLocaleString("ko-KR");
  return n.toLocaleString("ko-KR");
}}

function pctChange(curr, prev) {{
  if (!prev || prev === 0) return null;
  return ((curr - prev) / Math.abs(prev)) * 100;
}}

// ============================================================
// 집계
// ============================================================
function aggregate(rows) {{
  const s = {{cost:0, impressions:0, clicks:0, db:0, conversions:0, count:0}};
  rows.forEach(r => {{
    s.cost += r.cost || 0;
    s.impressions += r.impressions || 0;
    s.clicks += r.clicks || 0;
    s.db += r.db || 0;
    s.conversions += r.conversions || 0;
    s.count++;
  }});
  s.cpc = s.clicks ? s.cost / s.clicks : 0;
  s.cpm = s.impressions ? (s.cost / s.impressions) * 1000 : 0;
  s.ctr = s.impressions ? (s.clicks / s.impressions) * 100 : 0;
  s.cpa = s.db ? s.cost / s.db : 0;
  return s;
}}

// ============================================================
// 메인 렌더
// ============================================================
function render() {{
  const data = BRAND_DATA[currentBrand];
  if (!data || data.length === 0) {{
    document.getElementById("kpiGrid").innerHTML = '<div class="no-data">선택한 브랜드의 데이터가 없습니다.</div>';
    document.getElementById("chartSection").style.display = "none";
    document.getElementById("compSection").style.display = "none";
    document.getElementById("insightSection").style.display = "none";
    return;
  }}

  const sorted = [...data].sort((a, b) => a.date.localeCompare(b.date));
  const latest = sorted.slice(-currentPeriod);
  const previous = sorted.slice(-currentPeriod * 2, -currentPeriod);

  const cur = aggregate(latest);
  const prev = aggregate(previous);

  renderKPI(cur, prev);
  renderChart(latest);
  renderComparison(cur, prev);
  renderInsights(cur, prev);
}}

// ============================================================
// KPI 카드
// ============================================================
function renderKPI(cur, prev) {{
  const metrics = [
    {{ label: "\\uCD1D \\uBE44\\uC6A9", key: "cost", type: "money", inverse: true }},
    {{ label: "\\uCD1D DB", key: "db", type: "int", inverse: false }},
    {{ label: "CPC", key: "cpc", type: "money", inverse: true }},
    {{ label: "CTR", key: "ctr", type: "pct", inverse: false }},
    {{ label: "CPM", key: "cpm", type: "money", inverse: true }},
    {{ label: "CPA", key: "cpa", type: "money", inverse: true }},
  ];

  let html = "";
  metrics.forEach(m => {{
    const val = cur[m.key];
    const change = pctChange(cur[m.key], prev[m.key]);
    let changeHtml = '<span class="kpi-change neutral">\\u2014 \\uBE44\\uAD50 \\uB370\\uC774\\uD130 \\uC5C6\\uC74C</span>';

    if (change !== null) {{
      // inverse: 비용/CPC/CPM/CPA는 감소가 긍정적
      const isGood = m.inverse ? change < 0 : change > 0;
      const cls = Math.abs(change) < 1 ? "neutral" : (isGood ? "up" : "down");
      const arrow = change > 0 ? "\\u25B2" : (change < 0 ? "\\u25BC" : "\\u25CF");
      changeHtml = '<span class="kpi-change ' + cls + '">' + arrow + " " + Math.abs(change).toFixed(1) + "% \\uC804 \\uAE30\\uAC04 \\uB300\\uBE44</span>";
    }}

    html += '<div class="kpi-card"><div class="kpi-label">' + m.label + '</div><div class="kpi-value">' + fmt(val, m.type) + "</div>" + changeHtml + "</div>";
  }});
  document.getElementById("kpiGrid").innerHTML = html;
}}

// ============================================================
// 일별 차트
// ============================================================
function renderChart(rows) {{
  const section = document.getElementById("chartSection");
  section.style.display = "block";
  const ctx = document.getElementById("dailyChart").getContext("2d");
  if (chartInstance) chartInstance.destroy();

  const labels = rows.map(r => r.date.slice(5));
  const costData = rows.map(r => r.cost);
  const clickData = rows.map(r => r.clicks);
  const dbData = rows.map(r => r.db);

  chartInstance = new Chart(ctx, {{
    type: "line",
    data: {{
      labels,
      datasets: [
        {{
          label: "\\uBE44\\uC6A9",
          data: costData,
          borderColor: "#e94560",
          backgroundColor: "rgba(233,69,96,.1)",
          yAxisID: "y",
          tension: 0.3,
          fill: true,
        }},
        {{
          label: "\\uD074\\uB9AD",
          data: clickData,
          borderColor: "#448aff",
          backgroundColor: "rgba(68,138,255,.1)",
          yAxisID: "y1",
          tension: 0.3,
        }},
        {{
          label: "DB",
          data: dbData,
          borderColor: "#00c853",
          backgroundColor: "rgba(0,200,83,.1)",
          yAxisID: "y1",
          tension: 0.3,
        }},
      ],
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: "index", intersect: false }},
      plugins: {{
        legend: {{ labels: {{ color: "#8892a4" }} }},
        tooltip: {{
          backgroundColor: "#16213e",
          titleColor: "#e8e8e8",
          bodyColor: "#e8e8e8",
          borderColor: "#253555",
          borderWidth: 1,
          callbacks: {{
            label: function(ctx) {{
              let v = ctx.raw;
              if (ctx.dataset.label === "\\uBE44\\uC6A9") return ctx.dataset.label + ": \\u20A9" + Math.round(v).toLocaleString();
              return ctx.dataset.label + ": " + Math.round(v).toLocaleString();
            }}
          }}
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: "#8892a4" }}, grid: {{ color: "rgba(37,53,85,.5)" }} }},
        y: {{
          type: "linear", position: "left",
          ticks: {{
            color: "#e94560",
            callback: v => "\\u20A9" + (v >= 1000000 ? (v/1000000).toFixed(1)+"M" : (v >= 1000 ? (v/1000).toFixed(0)+"K" : v))
          }},
          grid: {{ color: "rgba(37,53,85,.5)" }},
        }},
        y1: {{
          type: "linear", position: "right",
          ticks: {{ color: "#448aff" }},
          grid: {{ drawOnChartArea: false }},
        }},
      }},
    }},
  }});
}}

// ============================================================
// 기간 비교 테이블
// ============================================================
function renderComparison(cur, prev) {{
  const section = document.getElementById("compSection");
  if (prev.count === 0) {{
    section.style.display = "none";
    return;
  }}
  section.style.display = "block";
  document.getElementById("compTitle").textContent = "\\uAE30\\uAC04 \\uBE44\\uAD50 (\\uCD5C\\uADFC " + currentPeriod + "\\uC77C vs \\uC774\\uC804 " + currentPeriod + "\\uC77C)";

  const rows = [
    ["\\uBE44\\uC6A9", cur.cost, prev.cost, "money", true],
    ["\\uD074\\uB9AD", cur.clicks, prev.clicks, "int", false],
    ["DB", cur.db, prev.db, "int", false],
    ["CPC", cur.cpc, prev.cpc, "money", true],
    ["CTR", cur.ctr, prev.ctr, "pct", false],
    ["CPM", cur.cpm, prev.cpm, "money", true],
    ["CPA", cur.cpa, prev.cpa, "money", true],
  ];

  let thead = "<tr><th>\\uC9C0\\uD45C</th><th>\\uCD5C\\uADFC " + currentPeriod + "\\uC77C</th><th>\\uC774\\uC804 " + currentPeriod + "\\uC77C</th><th>\\uBCC0\\uD654\\uC728</th></tr>";
  let tbody = "";
  rows.forEach(([label, c, p, type, inverse]) => {{
    const ch = pctChange(c, p);
    let chText = "-";
    let cls = "";
    if (ch !== null) {{
      const isGood = inverse ? ch < 0 : ch > 0;
      cls = Math.abs(ch) < 1 ? "" : (isGood ? "up" : "down");
      const arrow = ch > 0 ? "\\u25B2" : (ch < 0 ? "\\u25BC" : "");
      chText = arrow + " " + Math.abs(ch).toFixed(1) + "%";
    }}
    tbody += "<tr><td>" + label + "</td><td>" + fmt(c, type) + "</td><td>" + fmt(p, type) + "</td><td class=\\"" + cls + "\\">" + chText + "</td></tr>";
  }});

  document.querySelector("#compTable thead").innerHTML = thead;
  document.querySelector("#compTable tbody").innerHTML = tbody;
}}

// ============================================================
// 자동 인사이트
// ============================================================
function renderInsights(cur, prev) {{
  const section = document.getElementById("insightSection");
  const list = document.getElementById("insightList");

  if (prev.count === 0) {{
    section.style.display = "none";
    return;
  }}
  section.style.display = "block";

  const insights = [];

  // CPC 분석
  const cpcCh = pctChange(cur.cpc, prev.cpc);
  if (cpcCh !== null) {{
    if (cpcCh < -10) insights.push({{ type: "positive", text: "CPC\\uAC00 \\uC804 \\uAE30\\uAC04 \\uB300\\uBE44 " + Math.abs(cpcCh).toFixed(1) + "% \\uAC10\\uC18C\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uC18C\\uC7AC \\uD6A8\\uC728\\uC774 \\uC88B\\uC544\\uC9C0\\uACE0 \\uC788\\uC2B5\\uB2C8\\uB2E4." }});
    else if (cpcCh > 10) insights.push({{ type: "negative", text: "CPC\\uAC00 " + cpcCh.toFixed(1) + "% \\uC0C1\\uC2B9\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uACBD\\uC7C1 \\uC2EC\\uD654 \\uB610\\uB294 \\uD0C0\\uAC9F\\uD305 \\uD6A8\\uC728 \\uC800\\uD558\\uAC00 \\uC6D0\\uC778\\uC77C \\uC218 \\uC788\\uC2B5\\uB2C8\\uB2E4." }});
  }}

  // CTR 분석
  const ctrCh = pctChange(cur.ctr, prev.ctr);
  if (ctrCh !== null) {{
    if (ctrCh > 10) insights.push({{ type: "positive", text: "CTR\\uC774 " + ctrCh.toFixed(1) + "% \\uC0C1\\uC2B9\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uD0C0\\uAC9F \\uC624\\uB514\\uC5B8\\uC2A4\\uC758 \\uBC18\\uC751\\uC774 \\uC88B\\uC544\\uC9C0\\uACE0 \\uC788\\uC2B5\\uB2C8\\uB2E4." }});
    else if (ctrCh < -10) insights.push({{ type: "negative", text: "CTR\\uC774 " + Math.abs(ctrCh).toFixed(1) + "% \\uD558\\uB77D\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uC18C\\uC7AC \\uD53C\\uB85C\\uB3C4\\uAC00 \\uC0DD\\uACBC\\uC744 \\uC218 \\uC788\\uC5B4 \\uC0C8\\uB85C\\uC6B4 \\uD06C\\uB9AC\\uC5D0\\uC774\\uD2F0\\uBE0C\\uB97C \\uD14C\\uC2A4\\uD2B8\\uD574\\uBCF4\\uC138\\uC694." }});
  }}

  // CPA 분석
  const cpaCh = pctChange(cur.cpa, prev.cpa);
  if (cpaCh !== null) {{
    if (cpaCh < -10) insights.push({{ type: "positive", text: "DB \\uD655\\uBCF4 \\uB2E8\\uAC00(CPA)\\uAC00 " + Math.abs(cpaCh).toFixed(1) + "% \\uAC1C\\uC120\\uB418\\uC5C8\\uC2B5\\uB2C8\\uB2E4. \\uC804\\uD658 \\uD6A8\\uC728\\uC774 \\uC88B\\uC544\\uC9C0\\uACE0 \\uC788\\uC2B5\\uB2C8\\uB2E4." }});
    else if (cpaCh > 10) insights.push({{ type: "negative", text: "DB \\uD655\\uBCF4 \\uB2E8\\uAC00(CPA)\\uAC00 " + cpaCh.toFixed(1) + "% \\uC0C1\\uC2B9\\uD558\\uACE0 \\uC788\\uC2B5\\uB2C8\\uB2E4. \\uB79C\\uB529\\uD398\\uC774\\uC9C0 \\uC804\\uD658 \\uB3D9\\uC120\\uC744 \\uC810\\uAC80\\uD574\\uBCF4\\uC138\\uC694." }});
  }}

  // DB 수량 분석
  const dbCh = pctChange(cur.db, prev.db);
  if (dbCh !== null) {{
    if (dbCh > 15) insights.push({{ type: "positive", text: "DB \\uD655\\uBCF4\\uB7C9\\uC774 " + dbCh.toFixed(1) + "% \\uC99D\\uAC00\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uD604\\uC7AC \\uCE94\\uD398\\uC778 \\uC804\\uB7B5\\uC774 \\uD6A8\\uACFC\\uC801\\uC785\\uB2C8\\uB2E4." }});
    else if (dbCh < -15) insights.push({{ type: "negative", text: "DB \\uD655\\uBCF4\\uB7C9\\uC774 " + Math.abs(dbCh).toFixed(1) + "% \\uAC10\\uC18C\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uC608\\uC0B0 \\uBC30\\uBD84 \\uB610\\uB294 \\uD0C0\\uAC9F\\uD305 \\uC870\\uC815\\uC744 \\uAC80\\uD1A0\\uD574\\uBCF4\\uC138\\uC694." }});
  }}

  // 비용 분석
  const costCh = pctChange(cur.cost, prev.cost);
  if (costCh !== null) {{
    if (costCh > 20 && (dbCh === null || dbCh < costCh * 0.5)) {{
      insights.push({{ type: "negative", text: "\\uBE44\\uC6A9\\uC774 " + costCh.toFixed(1) + "% \\uC99D\\uAC00\\uD588\\uC9C0\\uB9CC DB \\uC99D\\uAC00\\uC728\\uC740 \\uC774\\uC5D0 \\uBBF8\\uCE58\\uC9C0 \\uBABB\\uD569\\uB2C8\\uB2E4. \\uBE44\\uD6A8\\uC728 \\uCE94\\uD398\\uC778\\uC744 \\uC810\\uAC80\\uD558\\uC138\\uC694." }});
    }}
  }}

  // CPM 분석
  const cpmCh = pctChange(cur.cpm, prev.cpm);
  if (cpmCh !== null) {{
    if (cpmCh > 15) insights.push({{ type: "tip", text: "CPM\\uC774 " + cpmCh.toFixed(1) + "% \\uC0C1\\uC2B9\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uACBD\\uC7C1 \\uC2EC\\uD654 \\uAD6C\\uAC04\\uC77C \\uC218 \\uC788\\uC73C\\uB2C8 \\uD0C0\\uAC9F \\uC624\\uB514\\uC5B8\\uC2A4 \\uD655\\uC7A5 \\uB610\\uB294 \\uAC8C\\uC7AC \\uC704\\uCE58 \\uBCC0\\uACBD\\uC744 \\uAC80\\uD1A0\\uD574\\uBCF4\\uC138\\uC694." }});
  }}

  // 종합 개선 팁
  if (ctrCh !== null && ctrCh < -5 && cpcCh !== null && cpcCh > 5) {{
    insights.push({{ type: "tip", text: "CTR \\uD558\\uB77D\\uACFC CPC \\uC0C1\\uC2B9\\uC774 \\uB3D9\\uC2DC\\uC5D0 \\uBC1C\\uC0DD\\uD588\\uC2B5\\uB2C8\\uB2E4. \\uC18C\\uC7AC \\uAD50\\uCCB4\\uC640 \\uD568\\uAED8 \\uD0C0\\uAC9F\\uD305 \\uC138\\uBD84\\uD654\\uB97C \\uAD8C\\uC7A5\\uD569\\uB2C8\\uB2E4." }});
  }}
  if (cpaCh !== null && cpaCh > 10 && ctrCh !== null && ctrCh > 0) {{
    insights.push({{ type: "tip", text: "\\uD074\\uB9AD\\uC740 \\uBC1C\\uC0DD\\uD558\\uC9C0\\uB9CC \\uC804\\uD658\\uC774 \\uC548 \\uB418\\uACE0 \\uC788\\uC2B5\\uB2C8\\uB2E4. \\uB79C\\uB529\\uD398\\uC774\\uC9C0 \\uB0B4 CTA \\uBC84\\uD2BC, \\uD3FC \\uAD6C\\uC870, \\uD398\\uC774\\uC9C0 \\uC18D\\uB3C4\\uB97C \\uC810\\uAC80\\uD574\\uBCF4\\uC138\\uC694." }});
  }}

  if (insights.length === 0) {{
    insights.push({{ type: "positive", text: "\\uC804\\uBC18\\uC801\\uC73C\\uB85C \\uC548\\uC815\\uC801\\uC778 \\uC131\\uACFC\\uB97C \\uC720\\uC9C0\\uD558\\uACE0 \\uC788\\uC2B5\\uB2C8\\uB2E4. \\uD604\\uC7AC \\uCE94\\uD398\\uC778 \\uC804\\uB7B5\\uC744 \\uC720\\uC9C0\\uD558\\uBA74\\uC11C \\uC18C\\uC7AC \\uD14C\\uC2A4\\uD2B8\\uB97C \\uBCD1\\uD589\\uD574\\uBCF4\\uC138\\uC694." }});
  }}

  const iconMap = {{ positive: "\\u2705", negative: "\\u26A0\\uFE0F", tip: "\\uD83D\\uDCA1" }};
  const classMap = {{ positive: "insight-positive", negative: "insight-negative", tip: "insight-tip" }};

  list.innerHTML = insights.map(i =>
    '<div class="insight-item ' + classMap[i.type] + '"><span class="icon">' + iconMap[i.type] + "</span><span>" + i.text + "</span></div>"
  ).join("");
}}
</script>
</body>
</html>"""

    return html


# ============================================================
# 메인
# ============================================================
def main():
    print("=" * 60)
    print("  광고 성과 대시보드 생성기")
    print("=" * 60)

    spreadsheet = connect()
    all_data = read_all_brands(spreadsheet)

    if not all_data:
        print("\n[오류] 읽을 수 있는 데이터가 없습니다.")
        sys.exit(1)

    html = generate_html(all_data)

    print(f"\n[4/4] 파일 저장 중...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    total_rows = sum(len(v) for v in all_data.values())
    print(f"  -> {OUTPUT_FILE}")
    print(f"\n완료!")
    print(f"  - 브랜드: {len(all_data)}개 ({', '.join(sorted(all_data.keys()))})")
    print(f"  - 총 데이터: {total_rows}행")
    print(f"  - 출력 파일: index.html")
    print(f"\n브라우저에서 index.html을 열거나 GitHub Pages에 배포하세요.")


if __name__ == "__main__":
    main()
