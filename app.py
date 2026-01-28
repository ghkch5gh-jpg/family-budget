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

# =========================================================
# 1. 페이지 설정 & 기본 CSS
# =========================================================
st.set_page_config(
    page_title="은지&요한 가계부",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 기본 페이지 스타일 (배경, 탭 등)
st.markdown("""
    <style>
    /* 폰트 적용 */
    @import url("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css");
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 배경색 */
    .stApp { background-color: #f2f4f6 !important; }
    
    /* 카드 스타일 */
    .toss-card {
        background-color: #ffffff;
        padding: 24px;
        border-radius: 20px;
        margin-bottom: 16px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.03);
    }
    
    /* 탭 메뉴 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
        border-bottom: 1px solid #e5e8eb !important;
        padding-bottom: 0px;
        margin-bottom: 20px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: transparent !important;
        border: none !important;
        font-size: 17px !important;
        font-weight: 600 !important;
        color: #8b95a1 !important;
        padding: 0 0 12px 0 !important;
        margin-bottom: -1px !important;
    }
    .stTabs [aria-selected="true"] {
        color: #3182f6 !important;
        border-bottom: 3px solid #3182f6 !important;
    }

    /* 표 스타일 */
    [data-testid="stDataFrame"] { background-color: transparent !important; }
    </style>
""", unsafe_allow_html=True)

# 캘린더 전용 커스텀 CSS
calendar_css = """
    .fc {
        background: #ffffff;
        padding: 20px;
        border-radius: 24px;
        border: none;
        font-family: 'Pretendard', sans-serif;
    }
    /* 헤더 툴바 */
    .fc-header-toolbar {
        margin-bottom: 20px !important;
    }
    .fc-toolbar-title {
        font-size: 24px !important;
        font-weight: 800 !important;
        color: #191f28;
    }
    /* 버튼 */
    .fc-button {
        background-color: #f2f4f6 !important;
        border: none !important;
        color: #4e5968 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: none !important;
        padding: 8px 12px !important;
    }
    .fc-button-active {
        background-color: #3182f6 !important;
        color: white !important;
    }
    
    /* 그리드 및 셀 */
    .fc-scrollgrid { border: none !important; }
    .fc-col-header-cell { border: none !important; padding-bottom: 10px; }
    .fc-daygrid-day { border: 1px solid #f2f4f6 !important; }
    
    /* 날짜 숫자 */
    .fc-daygrid-day-number {
        color: #333d4b;
        font-size: 14px;
        padding: 8px;
        text-decoration: none !important;
    }
    
    /* 오늘 날짜 */
    .fc-day-today { background: transparent !important; }
    .fc-day-today .fc-daygrid-day-number {
        background: #3182f6;
        color: white;
        border-radius: 50%;
        width: 28px; height: 28px;
        display: flex; justify-content: center; align-items: center;
    }
    
    /* 이벤트 스타일 (둥글게) */
    .fc-event {
        border-radius: 6px !important;
        border: none !important;
        box-shadow: none !important;
        margin-bottom: 2px !important;
        padding: 2px 4px !important;
    }
    
    /* 지출 금액 텍스트 스타일 */
    .fc-event-title {
        font-weight: 600 !important;
    }
"""

# =========================================================
# 2. 데이터 로드 및 헬퍼 함수
# =========================================================
@st.cache_resource
def get_credentials():
    try:
        scope = [
            'https://spreadsheets.google.com/feeds', 
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/calendar.readonly'
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name('service_account.json', scope)
        return creds
    except Exception:
        return None

SHEET_URL = "https://docs.google.com/spreadsheets/d/1ea1_cBxiBahTAiFoioGlFpbkWq1icWsSStpbnfqw1V8/edit"

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
            if '날짜' in fix.columns:
                fix['날짜'] = pd.to_datetime(fix['날짜'], errors='coerce')
                fix['연월'] = fix['날짜'].dt.strftime('%Y-%m')
            fix['금액'] = fix['금액'].apply(clean_money)
        if not loan.empty: loan['잔액'] = loan['잔액'].apply(clean_money)
        if not mission.empty:
            mission['주간목표'] = mission['주간목표'].apply(clean_money)
            mission['실제사용'] = mission['실제사용'].apply(clean_money)
            mission['잔액'] = mission['잔액'].apply(clean_money)
        if not budget_plan.empty:
            for col in budget_plan.columns:
                if col in ['예산', '계획', '금액']:
                    budget_plan[col] = budget_plan[col].apply(clean_money)
    except Exception:
        return defaults

    # 구글 캘린더 (색상 변경: 파스텔 파랑 적용!)
    google_events = []
    try:
        service = build('calendar', 'v3', credentials=creds)
        events_result = service.events().list(
            calendarId=YOUR_CALENDAR_ID, 
            timeMin=(datetime.utcnow() - timedelta(days=90)).isoformat() + 'Z',
            timeMax=(datetime.utcnow() + timedelta(days=90)).isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        for event in events_result.get('items', []):
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', '제목 없음')
            
            # [수정됨] 파스텔 파랑 (#90c2ff) 및 진한 글씨색 (#333d4b)
            google_events.append({
                "title": f"🗓️ {title}", 
                "start": start,
                "backgroundColor": "#90c2ff", 
                "borderColor": "#90c2ff",
                "textColor": "#333d4b" 
            })
    except: pass

    return exp, inc, fix, sch, loan, mission, budget_plan, google_events

data = load_data()
df, inc_df, fix_df, sch_df, loan_df, mission_df, budget_df, g_events = data
if df is None: df = pd.DataFrame()

def calc_height(dataframe):
    if dataframe.empty: return 100
    return (len(dataframe) * 36) + 40

def get_cat_col(df):
    return '분류' if '분류' in df.columns else ('카테고리' if '카테고리' in df.columns else None)

# =========================================================
# 3. 사이드바
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
                client = gspread.authorize(get_credentials())
                if client:
                    try:
                        sh = client.open_by_url(SHEET_URL).worksheet("지출내역")
                        sh.append_row([str(d), w, c, i, p, m])
                        st.toast("✅ 저장 완료!")
                        load_data.clear()
                        time.sleep(0.5)
                        st.rerun()
                    except: st.error("저장 실패")

    with t2:
        with st.form("inc_form", border=False):
            d = st.date_input("날짜", datetime.now())
            w = st.selectbox("대상", ["요한", "은지"])
            i = st.text_input("내용")
            m = st.number_input("금액", step=10000)
            
            if st.form_submit_button("수입 저장하기", use_container_width=True, type="primary"):
                client = gspread.authorize(get_credentials())
                if client:
                    try:
                        sh = client.open_by_url(SHEET_URL).worksheet("수입내역")
                        sh.append_row([str(d), w, i, m])
                        st.toast("✅ 저장 완료!")
                        load_data.clear()
                        time.sleep(0.5)
                        st.rerun()
                    except: st.error("저장 실패")

# =========================================================
# 4. 메인 대시보드
# =========================================================
st.title("은지 & 요한의 자산관리")

# [1] AI 코칭 영역
st.markdown("""
<div class="toss-card" style="margin-bottom: 20px;">
    <h3 style="margin-bottom: 12px; font-size: 20px; color: #333d4b;">🤖 AI 금융 비서</h3>
    <p style="color: #6b7684; font-size: 16px; line-height: 1.6; margin: 0;">
        안녕하세요! 이곳은 AI가 두 분의 소비 패턴을 분석해주는 공간이에요.<br>
        데이터가 조금 더 쌓이면, <strong>"이번 달 식비가 평소보다 10% 높아요!"</strong> 같은 조언을 드릴 수 있어요.
    </p>
</div>
""", unsafe_allow_html=True)

# [2] 메인 탭
tabs = st.tabs(["내역 조회", "캘린더", "고정지출", "대출 현황", "소비 분석", "식비 미션"])

# ---------------------------------------------------------
# [탭 1] 내역 조회
# ---------------------------------------------------------
with tabs[0]:
    if not df.empty:
        col_cat = get_cat_col(df)
        
        month_list = sorted(df['연월'].unique(), reverse=True) if '연월' in df.columns else [datetime.now().strftime('%Y-%m')]
        sel_month = st.selectbox("조회할 월", month_list, key="main_month")
        
        view_df = df[df['연월'] == sel_month].copy()
        
        c_left, c_right = st.columns([1, 1.2])
        
        with c_left:
            st.markdown("### 📊 예산 달성률")
            if not budget_df.empty and col_cat:
                usage = view_df.groupby(col_cat)['금액'].sum().reset_index()
                usage.columns = ['항목', '사용금액']
                p_df = budget_df.rename(columns={'내용': '항목', '계획': '예산'})
                if '예산' not in p_df.columns: p_df['예산'] = 0 
                
                merged = pd.merge(p_df[['항목', '예산']], usage, on='항목', how='outer').fillna(0)
                merged['달성률'] = merged.apply(lambda x: x['사용금액']/x['예산'] if x['예산']>0 else 0, axis=1)
                
                st.dataframe(
                    merged[['항목', '달성률', '예산', '사용금액']],
                    column_config={
                        "달성률": st.column_config.ProgressColumn("소진율", format="%.0f%%", min_value=0, max_value=1),
                        "예산": st.column_config.NumberColumn(format="%d원"),
                        "사용금액": st.column_config.NumberColumn(format="%d원"),
                    },
                    hide_index=True, use_container_width=True, height=calc_height(merged)
                )
            else: st.info("예산 데이터 없음")

        with c_right:
            st.markdown("### 📝 상세 내역")
            view_df['날짜'] = view_df['날짜'].dt.strftime('%m.%d')
            show_cols = ['날짜', '내용', '금액', '누가']
            if col_cat: show_cols.insert(1, col_cat)
            
            final_df = view_df[show_cols].sort_values('날짜', ascending=False)
            
            if col_cat and col_cat in final_df.columns:
                def highlight_rows(row):
                    color_map = {
                        '식비': '#e8f3ff', '교통/차량': '#fdf2f2', '생필품': '#f0fdf4',
                        '경조사': '#f3e8ff', '육아': '#fff7ed', '문화/여가': '#fffbe6'
                    }
                    bg = color_map.get(row[col_cat], 'white')
                    return [f'background-color: {bg}'] * len(row)
                
                st.dataframe(
                    final_df.style.apply(highlight_rows, axis=1),
                    column_config={"금액": st.column_config.NumberColumn(format="%d원")},
                    hide_index=True, use_container_width=True, height=calc_height(final_df)
                )
            else:
                st.dataframe(
                    final_df,
                    column_config={"금액": st.column_config.NumberColumn(format="%d원")},
                    hide_index=True, use_container_width=True, height=calc_height(final_df)
                )

# ---------------------------------------------------------
# [탭 2] 캘린더 (파스텔 파랑 적용됨)
# ---------------------------------------------------------
with tabs[1]:
    all_events = g_events.copy()
    
    # 1. 수동 일정
    if not sch_df.empty and '날짜' in sch_df.columns:
        sch_df['dt'] = pd.to_datetime(sch_df['날짜'], errors='coerce')
        for _, row in sch_df.iterrows():
            if pd.notna(row['dt']):
                who = row.get('누가', '가족')
                # 은지: 연한 빨강, 요한: 연한 파랑
                bg = "#ff8e8e" if who == '은지' else "#90c2ff"
                all_events.append({
                    "title": f"[{who}] {row.get('내용')}",
                    "start": row['dt'].strftime('%Y-%m-%d'),
                    "allDay": True,
                    "backgroundColor": bg, "borderColor": bg, "textColor": "#333d4b"
                })

    # 2. 날짜별 지출 표시
    if not df.empty:
        df['date_str'] = df['날짜'].dt.strftime('%Y-%m-%d')
        daily_sum = df.groupby('date_str')['금액'].sum().reset_index()
        for _, row in daily_sum.iterrows():
            if row['금액'] > 0:
                all_events.append({
                    "title": f"-{row['금액']:,}",
                    "start": row['date_str'],
                    "allDay": True,
                    "backgroundColor": "transparent",
                    "borderColor": "transparent",
                    "textColor": "#f04452"
                })

    cc1, cc2 = st.columns([6, 1])
    with cc2:
        if st.button("🔄", help="새로고침", use_container_width=True):
            load_data.clear()
            st.rerun()

    cal_ops = {
        "initialView": "dayGridMonth", 
        "headerToolbar": {"left": "prev,next", "center": "title", "right": "today"}, 
        "height": 800, 
        "locale": "ko",
        "dayMaxEvents": 4
    }
    
    # custom_css 적용
    calendar(events=all_events, options=cal_ops, custom_css=calendar_css, key=f"cal_pastel_{len(all_events)}_{datetime.now().second}")

# ---------------------------------------------------------
# [탭 3] 고정지출
# ---------------------------------------------------------
with tabs[2]:
    if not fix_df.empty:
        col_month = sorted(fix_df['연월'].unique(), reverse=True)
        s_month = st.selectbox("기준 월", col_month, key="fix_m")
        f_sub = fix_df[fix_df['연월'] == s_month]
        
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("### 🤵 요한 고정지출")
            y_df = f_sub[f_sub['구분'] == '요한'][['날짜', '항목', '금액']]
            st.metric("총액", f"{y_df['금액'].sum():,}원")
            if not y_df.empty:
                y_df['날짜'] = y_df['날짜'].dt.strftime('%d일')
                st.dataframe(y_df.style.set_properties(**{'background-color': '#e3f2fd'}), hide_index=True, use_container_width=True, height=calc_height(y_df))
            else: st.caption("내역 없음")
            
        with c2:
            st.markdown("### 👰 은지 고정지출")
            e_df = f_sub[f_sub['구분'] == '은지'][['날짜', '항목', '금액']]
            st.metric("총액", f"{e_df['금액'].sum():,}원")
            if not e_df.empty:
                e_df['날짜'] = e_df['날짜'].dt.strftime('%d일')
                st.dataframe(e_df.style.set_properties(**{'background-color': '#ffebee'}), hide_index=True, use_container_width=True, height=calc_height(e_df))
            else: st.caption("내역 없음")

# ---------------------------------------------------------
# [탭 4] 대출
# ---------------------------------------------------------
with tabs[3]:
    if not loan_df.empty:
        st.metric("총 대출 잔액", f"{loan_df['잔액'].sum():,}원")
        
        fig = px.bar(loan_df, x='잔액', y='항목', orientation='h', text_auto=',', 
                     color='잔액', color_continuous_scale='Blues')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        st.dataframe(
            loan_df, column_config={"잔액": st.column_config.NumberColumn(format="%d원")},
            hide_index=True, use_container_width=True, height=calc_height(loan_df)
        )
    else: st.info("대출 내역이 없어요! 🎉")

# ---------------------------------------------------------
# [탭 5] 소비 분석
# ---------------------------------------------------------
with tabs[4]:
    if not df.empty:
        cat_col = get_cat_col(df)
        m_df = df[df['연월'] == datetime.now().strftime('%Y-%m')]
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 📂 어디에 가장 많이 썼을까?")
            if not m_df.empty and cat_col:
                pie_df = m_df.groupby(cat_col)['금액'].sum().reset_index()
                fig = px.pie(pie_df, values='금액', names=cat_col, hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
            else: st.caption("데이터 부족")
            
        with c2:
            st.markdown("### 📈 일별 지출 추이")
            if not m_df.empty:
                daily = m_df.groupby('날짜')['금액'].sum().reset_index()
                fig2 = px.bar(daily, x='날짜', y='금액', color_discrete_sequence=['#3182f6'])
                fig2.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=10, b=10))
                st.plotly_chart(fig2, use_container_width=True)
            else: st.caption("데이터 부족")

# ---------------------------------------------------------
# [탭 6] 식비 미션
# ---------------------------------------------------------
with tabs[5]:
    st.markdown("### 🍱 식비 줄이기 도전!")
    if not mission_df.empty:
        goal = mission_df['주간목표'].sum()
        used = mission_df['실제사용'].sum()
        rate = used / goal if goal > 0 else 0
        st.progress(min(rate, 1.0))
        
        c1, c2, c3 = st.columns(3)
        c1.metric("총 예산", f"{goal:,}원")
        c2.metric("사용함", f"{used:,}원")
        c3.metric("남음", f"{goal-used:,}원")
        
        st.dataframe(mission_df, hide_index=True, use_container_width=True, height=calc_height(mission_df))
    else: st.info("미션 없음")
