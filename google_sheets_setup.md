# 🔗 Google Sheets API 연동 가이드

## 📋 목차
1. [Google Cloud Console 설정](#1-google-cloud-console-설정)
2. [서비스 계정 생성](#2-서비스-계정-생성)
3. [스프레드시트 공유 설정](#3-스프레드시트-공유-설정)
4. [Python 환경 설치](#4-python-환경-설치)
5. [연동 코드 실행](#5-연동-코드-실행)

---

## 1. Google Cloud Console 설정

### Step 1: 프로젝트 생성
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 상단 프로젝트 선택 → **"새 프로젝트"** 클릭
3. 프로젝트 이름: `crowedslave-meta-ads` (원하는 이름)
4. **만들기** 클릭

### Step 2: Google Sheets API 활성화
1. 좌측 메뉴 → **API 및 서비스** → **라이브러리**
2. 검색창에 `Google Sheets API` 검색
3. **사용 설정** 클릭
4. 동일하게 `Google Drive API`도 검색 후 **사용 설정**

> ⚠️ **반드시 2개 모두 활성화해야 합니다!**
> - Google Sheets API: 스프레드시트 읽기/쓰기
> - Google Drive API: 스프레드시트 파일 접근 권한

---

## 2. 서비스 계정 생성

### Step 1: 사용자 인증 정보 생성
1. **API 및 서비스** → **사용자 인증 정보**
2. **+ 사용자 인증 정보 만들기** → **서비스 계정**
3. 서비스 계정 이름: `meta-ads-bot`
4. **만들고 계속하기** 클릭
5. 역할: **편집자** 선택 → **완료**

### Step 2: JSON 키 다운로드
1. 생성된 서비스 계정 클릭
2. **키** 탭 → **키 추가** → **새 키 만들기**
3. **JSON** 선택 → **만들기**
4. 다운로드된 JSON 파일을 프로젝트 폴더에 저장

```
📁 클로드 실습/
├── credentials.json          ← 여기에 저장!
├── meta_ads_weekly_report_bot.md
├── google_sheets_setup.md
├── meta_ads_report.py
└── .env
```

> 🔒 **보안 주의**: `credentials.json`은 절대 GitHub에 올리면 안 됩니다!

---

## 3. 스프레드시트 공유 설정

### 가장 중요한 단계!

1. 다운로드한 `credentials.json` 파일을 열어보면 `client_email` 항목이 있습니다
   ```
   "client_email": "meta-ads-bot@프로젝트명.iam.gserviceaccount.com"
   ```

2. Google 스프레드시트 열기

3. 우측 상단 **공유** 버튼 클릭

4. 위의 `client_email` 주소를 입력하고 **편집자** 권한으로 공유

5. 스프레드시트 URL에서 **SPREADSHEET_ID** 복사
   ```
   https://docs.google.com/spreadsheets/d/여기가_SPREADSHEET_ID/edit
   ```

---

## 4. Python 환경 설치

```bash
# 필수 패키지 설치
pip install gspread google-auth google-auth-oauthlib python-dotenv
```

---

## 5. 스프레드시트 구조 (권장)

### 시트 이름: `메타광고_주간데이터`

| 날짜 | 주차 | 광고비(원) | 노출수 | 도달수 | 클릭수 | 전환수 | 매출(원) | CPC | CTR(%) | CPM | CPA | ROAS(%) |
|------|------|-----------|--------|--------|--------|--------|---------|-----|--------|-----|-----|---------|
| 2026-03-01 | W1 | 750,000 | 125,000 | 85,000 | 3,200 | 45 | 2,250,000 | 234 | 2.56 | 6,000 | 16,667 | 300 |
| 2026-03-08 | W2 | 820,000 | 140,000 | 92,000 | 3,800 | 52 | 2,870,000 | 216 | 2.71 | 5,857 | 15,769 | 350 |

### 시트 이름: `주간리포트`

| 주차 | 생성일 | 리포트내용 | 핵심인사이트 | 개선방향 |
|------|--------|-----------|-------------|---------|
| W2 | 2026-03-08 | (자동생성) | (자동생성) | (자동생성) |

---

## 6. 문제 해결 (FAQ)

### ❌ "403 Forbidden" 에러
→ 스프레드시트를 서비스 계정 이메일에 **공유**했는지 확인

### ❌ "API has not been enabled" 에러
→ Google Cloud Console에서 **Sheets API, Drive API** 둘 다 활성화했는지 확인

### ❌ "File not found" 에러
→ SPREADSHEET_ID가 정확한지 URL에서 다시 복사

### ❌ "credentials.json not found" 에러
→ JSON 키 파일이 프로젝트 폴더에 있는지 확인, .env 파일의 경로 확인
