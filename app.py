# (기존 import 부분 생략, 147번 줄 get_credentials 함수부터 수정된 부분입니다)

def get_credentials():
    try:
        scope = [
            'https://spreadsheets.google.com/feeds', 
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/calendar.readonly'
        ]
        # 금고(Secrets)에서 키 읽기
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return creds
    except Exception as e:
        st.error(f"❌ 인증 오류 발생: {e}")
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
            try: 
                return pd.DataFrame(doc.worksheet(name).get_all_records())
            except Exception as e:
                # 탭 이름을 못 찾으면 화면에 에러를 띄웁니다.
                st.warning(f"⚠️ '{name}' 탭을 찾을 수 없습니다. 시트의 탭 이름을 확인하세요! (에러: {e})")
                return pd.DataFrame()

        # 각 시트 읽어오기
        exp = get_df("지출내역")
        inc = get_df("수입내역")
        fix = get_df("고정지출")
        sch = get_df("일정")
        loan = get_df("대출")
        mission = get_df("식비미션")
        budget_plan = get_df("예산계획")
        
        # (이하 전처리 로직은 동일...)
