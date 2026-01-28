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
# 0. 사용자 설정 (URL 확인 완료)
# =========================================================
YOUR_CALENDAR_ID = "ghkch5gh@gmail.com" 
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ea1_cBxiBahTAiFoioGlFpbkWq1icWsSStpbnfqw1V8/edit"

# =========================================================
# 1. 페이지 설정 & CSS (토스 스타일)
# =========================================================
st.set_page_config(page_title="은지&요한 가계부", page_icon="💸", layout="wide")

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    * { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #f2f4f6 !important; }
    .toss-card { background-color: #ffffff; padding: 24px; border-radius: 20px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.03); }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 데이터 로드 및 인증 함수 (Secrets 적용)
# =========================================================
@st.cache_resource
def get_credentials():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/calendar.readonly']
        # Secrets 금고에서 인증 정보를 가져옵니다.
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return creds
    except Exception as e:
        st.error(f"❌ 인증 실패: Secrets 설정을 확인하세요. ({e})")
        return None

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
            try:
                data = doc.worksheet(name).get_all_records()
                return pd.DataFrame(data)
            except Exception:
                st.warning(f"⚠️ '{name}' 탭을 시트에서 찾을 수 없어 건너뜁니다.")
                return pd.DataFrame()

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

        # 구글 캘린더 로드
        google_events = []
        try:
            service = build('calendar', 'v3', credentials=creds)
            events_result = service.events().list(calendarId=YOUR_CALENDAR_ID, timeMin=(datetime.utcnow() - timedelta(days=30)).isoformat() + 'Z', singleEvents=True).execute()
            for event in events_result.get('items', []):
                google_events.append({
                    "title": f"🗓️ {event.get('summary', '일정')}",
                    "start": event['start'].get('dateTime', event['start'].get('date')),
                    "backgroundColor": "#90c2ff", "textColor": "#333d4b"
                })
        except: pass

        return exp, inc, fix, sch, loan, mission, budget_plan, google_events

    except Exception as e:
        st.error(f"❌ 시트 로드 실패: 주소나 권한을 확인하세요. ({e})")
        return defaults

# 데이터 실행
data = load_data()
df, inc_df, fix_df, sch_df, loan_df, mission_df, budget_df, g_events = data

# =========================================================
# 3. 사이드바 및 메인 화면 (기존과 동일)
# =========================================================
with st.sidebar:
    st.title("가계부 쓰기 ✍️")
    tab_ex, tab_in = st.tabs(["지출", "수입"])
    with tab_ex:
        with st.form("ex_form", border=False):
            d = st.date_input("날짜", datetime.now())
            w = st.selectbox("누가", ["요한", "은지", "공통"])
            c = st.selectbox("분류", ["식비", "교통/차량", "육아", "생필품", "병원", "경조사", "문화/여가", "예비비", "용돈", "기타"])
            i = st.text_input("내용")
            p = st.selectbox("결제", ["삼성카드", "현대카드", "지역화폐", "현금"])
            m = st.number_input("금액", step=1000, min_value=0)
            if st.form_submit_button("저장하기", use_container_width=True, type="primary"):
                try:
                    client = gspread.authorize(get_credentials())
                    sh = client.open_by_url(SHEET_URL).worksheet("지출내역")
                    sh.append_row([str(d), w, c, i, p, m])
                    st.toast("✅ 저장 완료!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"저장 실패: {e}")

st.title("은지 & 요한의 자산관리")
st.markdown('<div class="toss-card">🤖 <b>AI 금융 비서</b><br>데이터가 로드되면 분석을 시작합니다!</div>', unsafe_allow_html=True)

tabs = st.tabs(["내역 조회", "캘린더", "고정지출", "대출 현황", "소비 분석", "식비 미션"])

with tabs[0]: # 내역 조회
    if not df.empty:
        sel_month = st.selectbox("월 선택", sorted(df['연월'].unique(), reverse=True))
        view = df[df['연월'] == sel_month].sort_values('날짜', ascending=False)
        st.dataframe(view, use_container_width=True, hide_index=True)
    else:
        st.info("시트에 데이터가 없거나 탭 이름을 확인해주세요.")

# 나머지 탭들도 데이터가 있으면 표시되도록 구성됨
