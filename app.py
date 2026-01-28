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
# 0. 사용자 설정
# =========================================================
YOUR_CALENDAR_ID = "ghkch5gh@gmail.com" 
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ea1_cBxiBahTAiFoioGlFpbkWq1icWsSStpbnfqw1V8/edit"

# =========================================================
# 1. 페이지 설정 & 기본 CSS (이전 완성본 디자인 복구)
# =========================================================
st.set_page_config(
    page_title="은지&요한 가계부",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    * { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #f2f4f6 !important; }
    .toss-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.03);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
        border-bottom: 1px solid #e5e8eb !important;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        font-size: 17px !important;
        font-weight: 600 !important;
        color: #8b95a1 !important;
        padding: 0 0 12px 0 !important;
    }
    .stTabs [aria-selected="true"] {
        color: #3182f6 !important;
        border-bottom: 3px solid #3182f6 !important;
    }
    </style>
""", unsafe_allow_html=True)

# 캘린더 커스텀 CSS
calendar_css = """
    .fc { background: #ffffff; padding: 20px; border-radius: 24px; border: none; font-family: 'Pretendard', sans-serif; }
    .fc-toolbar-title { font-size: 24px !important; font-weight: 800 !important; color: #191f28; }
    .fc-button { background-color: #f2f4f6 !important; border: none !important; color: #4e5968 !important; border-radius: 8px !important; font-weight: 600 !important; }
    .fc-button-active { background-color: #3182f6 !important; color: white !important; }
    .fc-day-today { background: transparent !important; }
    .fc-day-today .fc-daygrid-day-number { background: #3182f6; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; justify-content: center; align-items: center; }
"""

# =========================================================
# 2. 데이터 로드 및 헬퍼 함수 (Secrets 연동)
# =========================================================
@st.cache_resource
def get_credentials():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/calendar.readonly']
        # Secrets 금고에서 인증 정보를 가져옵니다.
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return creds
    except Exception: return None

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

        exp = get_df("지출내역")
        inc = get_df("수입내역")
        fix = get_df("고정지출")
        sch = get_df("일정")
        loan = get_df("대출")
        mission = get_df("식비미션")
        budget_plan = get_df("예산계획")
        
        def clean_money(x):
            try: return int(str(x).replace(',', '').replace('₩', '').replace(' ', '').split('.')[0])
            except: return 0

        # 전처리
        if not exp.empty:
            exp['날짜'] = pd.to_datetime(exp['날짜'], errors='coerce')
            exp['금액'] = exp['금액'].apply(clean_money)
            exp['연월'] = exp['날짜'].dt.strftime('%Y-%m')
        if not inc.empty: inc['금액'] = inc['금액'].apply(clean_money)
        if not fix.empty:
            fix['날짜'] = pd.to_datetime(fix['날짜'], errors='coerce')
            fix['금액'] = fix['금액'].apply(clean_money)
            fix['연월'] = fix['날짜'].dt.strftime('%Y-%m')
        if not loan.empty: loan['잔액'] = loan['잔액'].apply(clean_money)
        if not mission.empty:
            for col in ['주간목표', '실제사용', '잔액']:
                if col in mission.columns: mission[col] = mission[col].apply(clean_money)
        if not budget_plan.empty:
            for col in ['예산', '계획', '금액']:
                if col in budget_plan.columns: budget_plan[col] = budget_plan[col].apply(clean_money)

        # 구글 캘린더
        google_events = []
        try:
            service = build('calendar', 'v3', credentials=creds)
            events_result = service.events().list(calendarId=YOUR_CALENDAR_ID, timeMin=(datetime.utcnow() - timedelta(days=90)).isoformat() + 'Z', singleEvents=True).execute()
            for event in events_result.get('items', []):
                google_events.append({
                    "title": f"🗓️ {event.get('summary')}", "start": event['start'].get('dateTime', event['start'].get('date')),
                    "backgroundColor": "#90c2ff", "textColor": "#333d4b"
                })
        except: pass

        return exp, inc, fix, sch, loan, mission, budget_plan, google_events
    except: return defaults

data = load_data()
df, inc_df, fix_df, sch_df, loan_df, mission_df, budget_df, g_events = data

def calc_height(dataframe):
    if dataframe.empty: return 100
    return (len(dataframe) * 36) + 40

# =========================================================
# 3. 사이드바 & 메인 대시보드
# =========================================================
with st.sidebar:
    st.title("가계부 쓰기 ✍️")
    t1, t2 = st.tabs(["지출", "수입"])
    with t1:
        with st.form("exp_form", border=False):
            d = st.date_input("날짜", datetime.now())
            w = st.selectbox("누가", ["요한", "은지", "공통"])
            c = st.selectbox("분류", ["식비", "교통/차량", "육아", "생필품", "병원", "경조사", "문화/여가", "예비비", "용돈", "기타"])
            i = st.text_input("내용")
            p = st.selectbox("결제", ["삼성카드", "현대카드", "지역화폐", "현금"])
            m = st.number_input("금액", step=1000, min_value=0)
            if st.form_submit_button("지출 저장하기", use_container_width=True, type="primary"):
                try:
                    client = gspread.authorize(get_credentials())
                    sh = client.open_by_url(SHEET_URL).worksheet("지출내역")
                    sh.append_row([str(d), w, c, i, p, m])
                    st.toast("✅ 저장 완료!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                except: st.error("저장 실패")

st.title("은지 & 요한의 자산관리")
st.markdown('<div class="toss-card">🤖 <b>AI 금융 비서</b><br>데이터가 쌓이면 스마트한 소비 분석을 도와드려요!</div>', unsafe_allow_html=True)

tabs = st.tabs(["내역 조회", "캘린더", "고정지출", "대출 현황", "소비 분석", "식비 미션"])

with tabs[0]: # 내역 조회 (필터 및 강조 복구)
    if not df.empty:
        sel_month = st.selectbox("조회할 월", sorted(df['연월'].unique(), reverse=True))
        view_df = df[df['연월'] == sel_month].copy()
        view_df['날짜'] = view_df['날짜'].dt.strftime('%m.%d')
        st.dataframe(view_df[['날짜', '분류', '내용', '금액', '누가']].sort_values('날짜', ascending=False), use_container_width=True, hide_index=True)
    else: st.info("데이터가 없습니다.")

with tabs[1]: # 캘린더 (지출 합계 표시 복구)
    all_events = g_events.copy()
    if not df.empty:
        df['date_str'] = df['날짜'].dt.strftime('%Y-%m-%d')
        daily_sum = df.groupby('date_str')['금액'].sum().reset_index()
        for _, row in daily_sum.iterrows():
            all_events.append({"title": f"-{row['금액']:,}", "start": row['date_str'], "backgroundColor": "transparent", "textColor": "#f04452"})
    calendar(events=all_events, options={"initialView": "dayGridMonth"}, custom_css=calendar_css)

with tabs[4]: # 소비 분석 (차트 복구)
    if not df.empty:
        fig = px.pie(df, values='금액', names='분류', hole=0.4, title="카테고리별 지출 비율")
        st.plotly_chart(fig, use_container_width=True)
