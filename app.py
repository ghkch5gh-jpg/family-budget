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
# 1. 페이지 설정 & CSS
# =========================================================
st.set_page_config(page_title="은지&요한 가계부", page_icon="💸", layout="wide")

st.markdown("""
    <style>
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    * { font-family: 'Pretendard', sans-serif !important; }
    .stApp { background-color: #f2f4f6 !important; }
    .toss-card { background-color: #ffffff; padding: 24px; border-radius: 20px; margin-bottom: 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.03); }
    .metric-card { background-color: #f9fafb; padding: 16px; border-radius: 12px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 2. 데이터 로드 함수 (업그레이드 버전)
# =========================================================
@st.cache_resource
def get_credentials():
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
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
        
        # 데이터를 안전하게 가져오는 함수
        def get_df(name):
            try:
                wb = doc.worksheet(name)
                data = wb.get_all_records()
                return pd.DataFrame(data)
            except:
                return pd.DataFrame() # 탭이 없거나 비어있으면 빈 껍데기 반환

        # 각 시트 데이터 가져오기
        exp = get_df("지출내역")
        inc = get_df("수입내역")
        fix = get_df("고정지출")
        sch = get_df("일정")
        loan = get_df("대출")
        mission = get_df("식비미션")
        budget_plan = get_df("예산계획")

        # 금액 정리 함수 (쉼표, 원 제거)
        def clean_money(x):
            try: return int(str(x).replace(',', '').replace('₩', '').replace(' ', '').split('.')[0])
            except: return 0
            
        # 날짜 정리 함수 (시간 00:00:00 제거)
        def clean_date(df, col_name='날짜'):
            if col_name in df.columns:
                df[col_name] = pd.to_datetime(df[col_name], errors='coerce').dt.strftime('%Y-%m-%d')
            return df

        # 전처리 적용
        if not exp.empty:
            exp = clean_date(exp)
            if '금액' in exp.columns: exp['금액'] = exp['금액'].apply(clean_money)
            if '날짜' in exp.columns: exp['연월'] = pd.to_datetime(exp['날짜']).dt.strftime('%Y-%m')

        if not inc.empty:
            inc = clean_date(inc)
            if '금액' in inc.columns: inc['금액'] = inc['금액'].apply(clean_money)

        if not fix.empty:
            fix = clean_date(fix)
            if '금액' in fix.columns: fix['금액'] = fix['금액'].apply(clean_money)
            
        if not loan.empty:
            if '잔액' in loan.columns: loan['잔액'] = loan['잔액'].apply(clean_money)

        if not budget_plan.empty:
             for col in ['예산', '금액']:
                if col in budget_plan.columns: budget_plan[col] = budget_plan[col].apply(clean_money)

        # 구글 캘린더 (선택사항)
        google_events = []
        try:
            service = build('calendar', 'v3', credentials=creds)
            events_result = service.events().list(calendarId=YOUR_CALENDAR_ID, maxResults=10, singleEvents=True, orderBy='startTime').execute()
            for event in events_result.get('items', []):
                start = event['start'].get('dateTime', event['start'].get('date'))
                google_events.append({"title": f"📅 {event.get('summary')}", "start": start, "backgroundColor": "#E8F3FF", "textColor": "#3182F6"})
        except: pass

        return exp, inc, fix, sch, loan, mission, budget_plan, google_events

    except Exception:
        return defaults

# 데이터 로드 실행
data = load_data()
df, inc_df, fix_df, sch_df, loan_df, mission_df, budget_df, g_events = data

# =========================================================
# 3. 화면 구성 (사이드바 + 메인)
# =========================================================
with st.sidebar:
    st.title("가계부 쓰기 ✍️")
    tab1, tab2 = st.tabs(["지출 등록", "수입 등록"])
    
    with tab1: # 지출
        with st.form("ex_form", border=False):
            d = st.date_input("날짜", datetime.now())
            w = st.selectbox("누가", ["요한", "은지", "공통", "라온"])
            c = st.selectbox("분류", ["식비", "교통/차량", "육아", "생필품", "병원", "경조사", "문화/여가", "주거/통신", "기타"])
            i = st.text_input("내용", placeholder="예: 점심값")
            p = st.selectbox("결제", ["삼성카드", "현대카드", "지역화폐", "현금", "계좌이체"])
            m = st.number_input("금액", step=1000, min_value=0)
            if st.form_submit_button("지출 저장", type="primary", use_container_width=True):
                try:
                    client = gspread.authorize(get_credentials())
                    client.open_by_url(SHEET_URL).worksheet("지출내역").append_row([str(d), w, c, i, p, m])
                    st.toast("✅ 지출이 저장되었습니다!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                except: st.error("저장 실패")

    with tab2: # 수입
        with st.form("in_form", border=False):
            d = st.date_input("날짜", datetime.now())
            c = st.selectbox("분류", ["월급", "보너스", "이자", "기타"])
            i = st.text_input("내용")
            m = st.number_input("금액", step=10000)
            if st.form_submit_button("수입 저장", use_container_width=True):
                try:
                    client = gspread.authorize(get_credentials())
                    client.open_by_url(SHEET_URL).worksheet("수입내역").append_row([str(d), c, i, m])
                    st.toast("💰 수입이 저장되었습니다!")
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
                except: st.error("저장 실패")

# 메인 대시보드
st.title("은지 & 요한의 자산관리 🏡")

# 상단 요약 카드
if not df.empty and '금액' in df.columns:
    this_month = datetime.now().strftime('%Y-%m')
    this_month_sum = df[df['연월'] == this_month]['금액'].sum()
    st.markdown(f"""
        <div class="toss-card">
            <span style="color:#6b7684">이번 달 총 지출</span><br>
            <span style="font-size:28px; font-weight:bold">{this_month_sum:,.0f}원</span>
        </div>
    """, unsafe_allow_html=True)

tabs = st.tabs(["내역 조회", "고정지출", "대출 현황", "식비 미션", "캘린더"])

with tabs[0]: # 내역 조회
    if not df.empty:
        month_list = sorted(df['연월'].unique(), reverse=True) if '연월' in df.columns else []
        sel_month = st.selectbox("월 선택", month_list)
        if sel_month:
            view = df[df['연월'] == sel_month].sort_values('날짜', ascending=False)
            st.dataframe(view, use_container_width=True, hide_index=True)
    else:
        st.info("💡 아직 지출 내역이 없어요. 왼쪽에서 첫 지출을 기록해보세요!")

with tabs[1]: # 고정지출
    if not fix_df.empty:
        st.dataframe(fix_df, use_container_width=True, hide_index=True)
        if '금액' in fix_df.columns:
            st.caption(f"매달 나가는 돈: 약 {fix_df['금액'].sum():,.0f}원")
    else:
        st.info("💡 '고정지출' 시트에 데이터가 없거나 제목줄(1행)이 안 맞아요.")

with tabs[2]: # 대출
    if not loan_df.empty:
        st.dataframe(loan_df, use_container_width=True, hide_index=True)
        if '잔액' in loan_df.columns:
            st.caption(f"남은 대출금 합계: {loan_df['잔액'].sum():,.0f}원")
    else:
        st.info("💡 '대출' 시트가 비어있어요.")

with tabs[3]: # 식비 미션
    if not mission_df.empty:
        st.dataframe(mission_df, use_container_width=True, hide_index=True)
    else:
        st.info("💡 '식비미션' 시트를 작성하면 목표 달성 현황을 볼 수 있어요.")

with tabs[4]: # 캘린더
    # 구글 캘린더 일정 + 가계부 일정 합치기
    events = g_events.copy()
    if not sch_df.empty:
        for _, row in sch_df.iterrows():
            events.append({
                "title": f"💰 {row['내용']}",
                "start": str(row['날짜']),
                "backgroundColor": "#ffec99",
                "textColor": "#000000"
            })
    
    calendar_options = {
        "headerToolbar
