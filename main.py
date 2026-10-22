
# 🎬 날짜별 박스오피스 조회 앱
# KOBIS API를 이용해 원하는 날짜의 영화 순위를 보여 줍니다.

import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# -----------------------------------------------
# 1. 기본 화면 설정
# -----------------------------------------------
st.set_page_config(
    page_title="날짜별 박스오피스",
    page_icon="🎬",
    layout="wide",
)

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# -----------------------------------------------
# 2. 한국 시간 기준 어제 날짜 계산
# -----------------------------------------------
def get_korea_yesterday():
    """서버 시간대와 상관없이 한국 시간 기준 어제를 계산합니다."""
    korea_now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    return korea_now.date() - datetime.timedelta(days=1)


# -----------------------------------------------
# 3. KOBIS API 요청
# -----------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(api_key, target_date):
    """선택한 날짜의 박스오피스 자료를 가져옵니다."""
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": target_date,
        },
        timeout=15,
    )

    # HTTP 통신 자체에서 오류가 발생했는지 확인합니다.
    response.raise_for_status()

    # JSON 형태로 응답을 읽습니다.
    return response.json()


# -----------------------------------------------
# 4. 숫자 표시용 함수
# -----------------------------------------------
def format_number(value):
    """숫자에 천 단위 쉼표를 붙입니다."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


def rank_change_label(value):
    """
    KOBIS rankInten 기준:
    양수 = 순위 상승
    음수 = 순위 하락
    0 = 순위 변화 없음
    """
    try:
        change = int(value)
    except (TypeError, ValueError):
        return "—"

    if change > 0:
        return f"🔺 +{change}"

    if change < 0:
        return f"🔻 {change}"

    return "—"


# -----------------------------------------------
# 5. 제목과 날짜 선택 달력
# -----------------------------------------------
yesterday = get_korea_yesterday()

st.title("🎬 날짜별 박스오피스")
st.write(
    "달력에서 날짜를 선택하면 "
    "그날의 영화 순위와 관객수를 확인할 수 있어요."
)

st.caption(
    "한국 시간 기준 어제까지 조회할 수 있습니다. "
    "오늘은 아직 집계 전이므로 선택할 수 없습니다."
)

# 시작 날짜는 2004년 1월 1일로 설정합니다.
# 가장 늦게 선택할 수 있는 날짜는 한국 시간 기준 어제입니다.
min_date = datetime.date(2004, 1, 1)

selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    min_value=min_date,
    max_value=yesterday,
    format="YYYY-MM-DD",
)

st.info(
    f"선택한 날짜: {selected_date:%Y년 %m월 %d일}"
)


# -----------------------------------------------
# 6. 비밀 금고에서 API 인증키 불러오기
# -----------------------------------------------
# 인증키를 코드에 직접 작성하지 않습니다.
try:
    api_key = st.secrets["KOBIS_KEY"]

except (KeyError, FileNotFoundError):
    st.error("🔑 KOBIS 인증키를 찾을 수 없습니다.")

    st.markdown(
        """
        **해결 방법**

        1. Streamlit Cloud에서 앱의 Settings → Secrets로 이동합니다.
        2. 아래 내용을 입력합니다.
        3. 실제 발급받은 인증키를 따옴표 안에 넣습니다.

        ```toml
        KOBIS_KEY = "본인의_발급받은_API_인증키"
        ```
        """
    )

    st.stop()


# -----------------------------------------------
# 7. 선택한 날짜의 박스오피스 가져오기
# -----------------------------------------------
# API는 날짜를 YYYYMMDD 형식으로 받습니다.
target_dt = selected_date.strftime("%Y%m%d")

try:
    with st.spinner("🎬 영화 정보를 불러오는 중입니다..."):
        data = fetch_boxoffice(api_key, target_dt)

except requests.exceptions.Timeout:
    st.error("KOBIS 서버의 응답 시간이 초과되었습니다.")
    st.info(
        "인터넷 연결을 확인하고 잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.RequestException as exc:
    st.error("KOBIS API에 연결하지 못했습니다.")
    st.info(
        "인터넷 연결, API 주소, KOBIS 서버 상태를 확인해 주세요."
    )
    st.caption(f"오류 종류: {type(exc).__name__}")
    st.stop()

except ValueError:
    st.error("KOBIS 응답을 JSON으로 읽을 수 없습니다.")
    st.info(
        "KOBIS API 서버 상태를 확인하고 다시 시도해 주세요."
    )
    st.stop()


# -----------------------------------------------
# 8. API 오류 응답 확인
# -----------------------------------------------
# 인증키가 잘못되어도 HTTP 상태코드는 200일 수 있습니다.
# 따라서 응답 안에 faultInfo가 있는지 반드시 확인합니다.

if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.info("KOBIS API 응답 구조를 확인해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo") or {}

    error_code = fault.get("errorCode", "오류 코드 없음")
    error_message = (
        fault.get("message")
        or fault.get("errorMessage")
        or "상세 오류 메시지가 없습니다."
    )

    st.error("KOBIS API에서 오류를 반환했습니다.")

    st.write(f"**오류 코드:** {error_code}")
    st.write(f"**오류 내용:** {error_message}")

    st.info(
        "Streamlit Cloud의 Secrets에 등록한 KOBIS_KEY가 "
        "정확한지 확인해 주세요. 인증키가 정상적으로 발급되었고 "
        "사용 가능한 상태인지도 확인해 주세요."
    )

    st.stop()


# -----------------------------------------------
# 9. 영화 목록 확인
# -----------------------------------------------
boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error("박스오피스 결과를 찾을 수 없습니다.")
    st.info(
        "KOBIS API 응답 구조와 서버 상태를 확인해 주세요."
    )
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

# 선택한 날짜에 영화 목록이 없을 때 안내합니다.
if not movies:
    st.warning("그날은 아직 집계 전입니다")
    st.info(
        "해당 날짜의 박스오피스 자료가 아직 제공되지 않을 수 있습니다. "
        "날짜를 다시 확인하거나 나중에 다시 조회해 주세요."
    )
    st.stop()


# -----------------------------------------------
# 10. 데이터를 표와 그래프에 맞게 정리
# -----------------------------------------------
df = pd.DataFrame(movies)

# API 숫자 데이터는 문자열로 오므로 정수로 변환합니다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
]

for column in numeric_columns:
    if column in df.columns:
        df[column] = (
            pd.to_numeric(df[column], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    else:
        df[column] = 0

# 영화 순위가 높은 순서대로 정렬합니다.
df = (
    df.sort_values("rank", ascending=True)
    .reset_index(drop=True)
)


# -----------------------------------------------
# 11. 누적 관객수 100만 명 초과 영화에 트로피 붙이기
# -----------------------------------------------
def make_movie_name(row):
    """누적 관객수가 100만 명을 넘으면 영화명에 트로피를 붙입니다."""
    movie_name = str(row.get("movieNm", "영화명 없음"))

    if row["audiAcc"] > 1_000_000:
        return f"{movie_name} 🏆"

    return movie_name


df["표시용 영화명"] = df.apply(make_movie_name, axis=1)


# -----------------------------------------------
# 12. 1위 영화 지표 카드 세 장
# -----------------------------------------------
first_movie = df.iloc[0]

st.subheader(
    f"🥇 {selected_date:%m월 %d일} 박스오피스 1위"
)

st.markdown(f"## {first_movie['표시용 영화명']}")

card1, card2, card3 = st.columns(3)

card1.metric(
    label="🎟️ 당일 관객수",
    value=f"{format_number(first_movie['audiCnt'])}명",
)

card2.metric(
    label="👥 누적 관객수",
    value=f"{format_number(first_movie['audiAcc'])}명",
)

card3.metric(
    label="🎥 스크린수",
    value=f"{format_number(first_movie['scrnCnt'])}개",
)

st.divider()


# -----------------------------------------------
# 13. 전체 박스오피스 순위표
# -----------------------------------------------
st.subheader("📋 일별 박스오피스 순위표")

# 순위 증감, 트로피, 관객수 등을 한국어 열 이름으로 표시합니다.
table = pd.DataFrame(
    {
        "순위": df["rank"].astype(str),
        "전일 대비 순위": df["rankInten"].map(
            rank_change_label
        ),
        "영화명": df["표시용 영화명"],
        "개봉일": df["openDt"].replace("", "정보 없음"),
        "관객수": df["audiCnt"].map(
            lambda number: f"{number:,}"
        ),
        "누적관객": df["audiAcc"].map(
            lambda number: f"{number:,}"
        ),
        "스크린수": df["scrnCnt"].map(
            lambda number: f"{number:,}"
        ),
    }
)

st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
)

st.caption(
    "🔺 빨간 위 화살표: 순위 상승 · "
    "🔻 파란 아래 화살표: 순위 하락 · "
    "🏆 누적 관객수 100만 명 초과"
)


# -----------------------------------------------
# 14. 관객수 상위 5편 막대그래프
# -----------------------------------------------
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.nlargest(5, "audiCnt")
    .sort_values("audiCnt", ascending=True)
    .copy()
)

chart = px.bar(
    top5,
    x="audiCnt",
    y="표시용 영화명",
    orientation="h",
    labels={
        "audiCnt": "관객수(명)",
        "표시용 영화명": "영화명",
    },
    text="audiCnt",
)

# 막대 끝에 관객수를 표시합니다.
chart.update_traces(
    texttemplate="%{text:,}",
    textposition="outside",
    cliponaxis=False,
)

chart.update_layout(
    yaxis_title="",
    xaxis_title="관객수(명)",
    showlegend=False,
    margin=dict(l=10, r=60, t=20, b=10),
)

st.plotly_chart(
    chart,
    use_container_width=True,
)


# -----------------------------------------------
# 15. 자료 출처
# -----------------------------------------------
st.caption(
    "자료 출처: 영화관입장권통합전산망(KOBIS) "
    "일별 박스오피스 API"
)
