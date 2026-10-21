```python
# 어제의 박스오피스 — KOBIS 일별 박스오피스 API
# 초보자도 이해하기 쉽도록 주요 단계마다 한국어 주석을 달았습니다.

import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# 브라우저 탭 제목과 화면 너비를 설정합니다.
st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide",
)

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


def get_korea_yesterday():
    """한국 시간 기준으로 어제 날짜를 반환합니다."""
    korea_now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    return korea_now.date() - datetime.timedelta(days=1)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(api_key, target_date):
    """KOBIS API를 호출하고 JSON 응답을 돌려줍니다."""
    response = requests.get(
        API_URL,
        params={"key": api_key, "targetDt": target_date},
        timeout=15,
    )
    # HTTP 오류가 발생하면 예외가 생깁니다.
    response.raise_for_status()
    return response.json()


def format_number(value):
    """숫자를 천 단위 쉼표가 있는 문자열로 표시합니다."""
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


# 제목과 조회 날짜를 표시합니다.
yesterday = get_korea_yesterday()
target_dt = yesterday.strftime("%Y%m%d")

st.title("🎬 어제의 박스오피스")
st.caption(
    f"조회 날짜: {yesterday:%Y년 %m월 %d일} · 한국 시간 기준 어제"
)
st.write(
    "영화관입장권통합전산망(KOBIS)의 "
    "일별 박스오피스 데이터를 보여 줍니다."
)

# 인증키는 소스 코드에 넣지 않고 Secrets에서 읽습니다.
try:
    api_key = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("KOBIS 인증키를 찾을 수 없습니다.")
    st.markdown(
        """
        **확인 방법**

        1. Streamlit Cloud에서 앱의 **Settings → Secrets**를 엽니다.
        2. 아래 설정을 추가하고 본인의 발급받은 키를 입력합니다.
        3. 저장한 뒤 앱을 다시 실행합니다.

        ```toml
        KOBIS_KEY = "발급받은_본인의_API_인증키"
        ```
        """
    )
    st.stop()

# KOBIS 서버에 요청하고 오류를 구분해서 안내합니다.
try:
    with st.spinner("어제의 박스오피스를 불러오는 중입니다..."):
        data = fetch_boxoffice(api_key, target_dt)

except requests.exceptions.Timeout:
    st.error("KOBIS 서버의 응답 시간이 초과되었습니다.")
    st.info("인터넷 연결을 확인한 뒤 잠시 후 새로고침해 주세요.")
    st.stop()

except requests.exceptions.RequestException as exc:
    st.error("KOBIS API에 연결하지 못했습니다.")
    st.info(
        "네트워크 연결과 KOBIS API 서버 상태를 확인한 뒤 "
        "다시 시도해 주세요."
    )
    st.caption(f"기술 정보: {type(exc).__name__}")
    st.stop()

except ValueError:
    st.error("KOBIS 응답을 JSON으로 읽을 수 없습니다.")
    st.info(
        "API 주소와 KOBIS 서버 상태를 확인한 뒤 "
        "잠시 후 다시 시도해 주세요."
    )
    st.stop()

# 인증키가 틀려도 HTTP 상태코드는 200일 수 있으므로
# 응답 안에 faultInfo가 있는지 별도로 확인합니다.
if not isinstance(data, dict):
    st.error("API 응답의 형식이 예상과 다릅니다.")
    st.info("KOBIS API의 응답 형식과 서버 상태를 확인해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo") or {}
    error_code = fault.get("errorCode", "오류 코드 없음")
    error_message = (
        fault.get("message")
        or fault.get("errorMessage")
        or "상세 메시지가 없습니다."
    )

    st.error("KOBIS API가 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {error_code}")
    st.write(f"**오류 내용:** {error_message}")
    st.info(
        "Streamlit Cloud의 Secrets에 저장한 KOBIS_KEY가 "
        "정확한지, 키가 발급·사용 가능한 상태인지 확인해 주세요."
    )
    st.stop()

# 응답에서 영화 목록을 꺼냅니다.
boxoffice_result = data.get("boxOfficeResult")

if not isinstance(boxoffice_result, dict):
    st.error("응답에 boxOfficeResult 항목이 없습니다.")
    st.info("KOBIS API의 응답 구조와 서버 상태를 확인해 주세요.")
    st.stop()

movies = boxoffice_result.get("dailyBoxOfficeList", [])

if not movies:
    st.warning("해당 날짜의 영화 목록이 비어 있습니다.")
    st.info(
        "아직 집계가 완료되지 않았거나 KOBIS에서 해당 날짜의 "
        "자료를 제공하지 않을 수 있습니다. "
        "조회 날짜가 한국 시간 기준 어제인지 확인하고 "
        "잠시 후 다시 새로고침해 주세요."
    )
    st.stop()

# 숫자 값도 문자열로 오므로 숫자로 변환합니다.
df = pd.DataFrame(movies)

numeric_columns = [
    "rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"
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

# 영화 순위 숫자 기준으로 정렬합니다.
df = df.sort_values("rank", ascending=True).reset_index(drop=True)
first_movie = df.iloc[0]

# 1위 영화의 핵심 지표 세 가지를 카드로 보여 줍니다.
st.subheader(f"🥇 1위 영화: {first_movie.get('movieNm', '영화명 없음')}")

card1, card2, card3 = st.columns(3)

card1.metric(
    "어제 관객수",
    f"{format_number(first_movie['audiCnt'])}명"
)
card2.metric(
    "누적 관객수",
    f"{format_number(first_movie['audiAcc'])}명"
)
card3.metric(
    "스크린수",
    f"{format_number(first_movie['scrnCnt'])}개"
)

st.divider()

# 전체 순위표를 만들고 열 이름을 한국어로 바꿉니다.
st.subheader("📋 어제의 박스오피스 순위표")

table_columns = [
    "rank", "movieNm", "openDt",
    "audiCnt", "audiAcc", "scrnCnt"
]
table = df[table_columns].copy()

table.columns = [
    "순위", "영화명", "개봉일",
    "관객수", "누적관객", "스크린수"
]

# 관객수와 스크린수를 읽기 쉽게 쉼표로 표시합니다.
for column in ["관객수", "누적관객", "스크린수"]:
    table[column] = table[column].map(
        lambda number: f"{number:,}"
    )

table["순위"] = table["순위"].astype(str)
table["개봉일"] = table["개봉일"].replace("", "정보 없음")

st.dataframe(
    table,
    hide_index=True,
    use_container_width=True
)

# 관객수가 많은 상위 5편을 막대그래프로 표시합니다.
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.nlargest(5, "audiCnt")
    .sort_values("audiCnt", ascending=True)
    .copy()
)

chart = px.bar(
    top5,
    x="audiCnt",
    y="movieNm",
    orientation="h",
    labels={
        "audiCnt": "어제 관객수(명)",
        "movieNm": "영화명"
    },
    text="audiCnt",
)

chart.update_traces(
    texttemplate="%{text:,}",
    textposition="outside",
    cliponaxis=False,
)

chart.update_layout(
    yaxis_title="",
    xaxis_title="어제 관객수(명)",
    showlegend=False,
    margin=dict(l=10, r=60, t=20, b=10),
)

st.plotly_chart(chart, use_container_width=True)

st.caption(
    "자료 출처: 영화관입장권통합전산망(KOBIS) 일별 박스오피스 API"
)
```
