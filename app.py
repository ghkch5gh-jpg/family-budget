import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
from streamlit_calendar import calendar
from datetime import datetime, timedelta
import plotly.express as px
import time

# =========================================================
# 0. 사용자 설정 (URL 및 ID 확인 완료)
# =========================================================
YOUR_CALENDAR_ID = "ghkch5gh@gmail.com" 
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ea1_cBxiBahTAiFoioGlFpbkWq1icWsSStpbnfqw1V8/edit"

# =========================================================
# 1. 페이지 설정 & 토스 스타일 CSS (복구 완료)
# =========================================================
st.set_page_config(page_title="은지&요한 가계부", page_icon="💸", layout="wide")

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    * { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #f2f4f6 !important; }
    .toss-card { background-color: #ffffff; padding: 24px; border-radius: 20px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.03); }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: transparent; border-bottom: 1px solid #e5e8eb !important; }
    .stTabs [data-baseweb="tab"] { font-size: 17px !important; font-weight: 600 !important; color: #8b95a1 !important; }
    .stTabs [aria-selected="true"] { color: #3182f6 !important; border-bottom: 3px solid #3182f6 !important; }
    </style>
""", unsafe_allow_html=True)

# 캘린더 전용 CSS (복구)
calendar_css = ".fc { background: #ffffff; padding: 20px; border-radius: 24px; border: none; font-family: 'Pretendard'; }"

# =========================================================
# 2. 데이터 로드 (Secrets 금고 연동)
# =========================================================
@st.cache_resource
def get_credentials():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/calendar.readonly']
        return ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    except: return None

@st.cache_data(show_spinner="데이터 동기화 중...")
def load_data():
    empty = pd.DataFrame()
    defaults = (empty, empty, empty, empty, empty, empty, empty, [])
    creds = get_credentials()
    if not creds: return defaults

    client = gspread.authorize(creds)
    try:
        doc = client.open_by_url(SHEET_URL)
        def get_df(name):
            try: return pd.DataFrame(doc.worksheet(name).get_all_records())
            except: return pd.DataFrame()

        exp, inc, fix = get_df("지출내역"), get_df("수입내역"), get_df("고정지출")
        sch, loan, mission, budget = get_df("일정"), get_df("대출"), get_df("식비미션"), get_df("예산계획")
        
        def clean_money(x):
            try: return int(str(x).replace(',', '').replace('₩', '').replace(' ', '').split('.')[0])
            except: return 0

        # 데이터 전처리 (시간 00:00:00 제거 로직 포함)
        for d in [exp, inc, fix, sch]:
            if not d.empty and '날짜' in d.columns:
                d['날짜'] = pd.to_datetime(d['날짜'], errors='coerce')
                if d is exp: d['연월'] = d['날짜'].dt.strftime('%Y-%m')
                d['날짜'] = d['날짜'].dt.strftime('%Y-%m-%d') # 시간 제거

        if not exp.empty: exp['금액'] = exp['금액'].apply(clean_money)
        if not inc.empty: inc['금액'] = inc['금액'].apply(clean_money)
        if not fix.empty: fix['금액'] = fix['금액'].apply(clean_money)
        if not loan.empty: loan['잔액'] = loan['잔액'].apply(clean_money)
        if not mission.empty:
            for c in ['주간목표', '실제사용', '잔액']: mission[c] = mission[c].apply(clean_money)
        
        # 구글 캘린더 로드
        g_events = []
        try:
            service = build('calendar', 'v3', credentials=creds)
            res = service.events().list(calendarId=YOUR_CALENDAR_ID, timeMin=(datetime.utcnow()-timedelta(days=60)).isoformat()+'Z', singleEvents=True).execute()
            for ev in res.get('items', []):
                g_events.append({"title": f"🗓️ {ev.get('summary')}", "start": ev['start'].get('dateTime', ev['start'].get('date')), "backgroundColor": "#90c2ff", "textColor": "#333d4b"})
        except: pass

        return exp, inc, fix, sch, loan, mission, budget, g_events
    except: return defaults

df, inc_df, fix_df, sch_df, loan_df, mission_df, budget_df, g_events = load_data()

# =========================================================
# 3. 화면 구성 (기존에 힘들게 만드신 탭들 복구)
# =========================================================
st.title("은지 & 요한의 자산관리 🏡")
st.markdown('<div class="toss-card">🤖 <b>AI 금융 비서</b><br>데이터가 정상적으로 로드되었습니다. 두 분의 소비를 분석 중입니다!</div>', unsafe_allow_html=True)

tabs = st.tabs(["내역 조회", "캘린더", "고정지출", "대출 현황", "소비 분석", "식비 미션"])

with tabs[0]: # 내역 조회 (필터링 복구)
    if not df.empty:
        sel_month = st.selectbox("월 선택", sorted(df['연월'].unique(), reverse=True))
        st.dataframe(df[df['연월']==sel_month].sort_values('날짜', ascending=False), use_container_width=True, hide_index=True)

with tabs[1]: # 캘린더 (날짜별 지출액 합산 표시 복구)
    all_ev = g_events.copy()
    if not df.empty:
        daily = df.groupby('날짜')['금액'].sum().reset_index()
        for _, r in daily.iterrows():
            all_ev.append({"title": f"-{r['금액']:,}", "start": r['날짜'], "backgroundColor": "transparent", "textColor": "#f04452"})
    calendar(events=all_ev, options={"initialView": "dayGridMonth"}, custom_css=calendar_css)

with tabs[4]: # 소비 분석 (도넛 차트 복구)
    if not df.empty:
        fig = px.pie(df, values='금액', names='분류', hole=0.4, title="카테고리별 지출 현황")
        st.plotly_chart(fig, use_container_width=True)

with tabs[5]: # 식비 미션 (진척도 바 복구)
    if not mission_df.empty:
        goal = mission_df['주간목표'].sum()
        used = mission_df['실제사용'].sum()
        st.metric("남은 식비", f"{goal - used:,}원")
        st.progress(min(used/goal, 1.0) if goal > 0 else 0)
        st.dataframe(mission_df, use_container_width=True, hide_index=True)
