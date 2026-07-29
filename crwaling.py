import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import urllib.parse
import time
import re
from collections import Counter
import math

# 웹페이지 기본 설정
st.set_page_config(page_title="디카갤 '니콘' 민심 대시보드", page_icon="📷", layout="wide")

# ----------------------------------------------------
# 0. 욕설 / 비속어 필터링 설정
# ----------------------------------------------------
SWEAR_WORDS = [
    "시발", "씨발", "씨팔", "개새끼", "병신", "븅신", "지랄", "존나", "좆",
    "존나게", "개같", "새끼", "쌍놈", "미친놈", "미친년", "뻐킹", "꺼져", "틀딱",
    "애자", "뇌절", "호구", "앰창", "느금", "새끼들"
]

# ----------------------------------------------------
# 0. 불용어(Stopwords) - "니콘" 제외 및 URL/웹 관련 단어 추가
# ----------------------------------------------------
STOPWORDS = {
    # 🌐 URL 및 웹 링크 관련 단어 (추가)
    "http", "https", "com", "net", "org", "co", "kr", "www", "gall", "dcinside", "dc", 
    "board", "view", "lists", "m", "html", "php", "asp", "jsp", "link", "url", "official",

    # 한국어 주어 / 대명사 / 의존명사
    "내가", "나는", "내", "너가", "너는", "니가", "자신", "저희", "우리", "그가", "그녀",
    "이거", "저거", "그거", "이것", "저것", "그것", "여기", "저기", "거기", "어디",
    
    # 영어 관사 / 대명사 / 기본 접속사 (소문자 기준)
    "the", "a", "an", "this", "that", "it", "they", "he", "she", "i", "my", "me",
    "your", "you", "we", "our", "is", "are", "was", "were", "in", "on", "at", "to",
    
    # 불필요한 조사 / 접속사 / 추임새
    "그리고", "하지만", "근데", "그래서", "그러면", "하여간", "암튼", "어차피", "아무튼",
    "대해", "위해", "때문", "가지", "생각", "관련", "정도", "대한", "해서", "아닌",
    
    # 디카갤 관련 공통 무의미 키워드 ("니콘"은 제거됨!)
    "디시", "디카갤", "갤러리", "오늘", "지금", "진짜", "그냥", "혹시",
    "있음", "없음", "있는", "없는", "추천", "질문", "후기", "게시글", "사진",
}

def sanitize_text(text, enable_filter=True):
    """비속어를 *** 로 변환하는 함수"""
    if not enable_filter or not isinstance(text, str):
        return text
    clean_text = text
    for swear in SWEAR_WORDS:
        pattern = re.compile(re.escape(swear), re.IGNORECASE)
        clean_text = pattern.sub("*" * len(swear), clean_text)
    return clean_text

# ----------------------------------------------------
# 1. 크롤링 함수 (본문까지 수집하도록 수정)
# ----------------------------------------------------
@st.cache_data(ttl=600)
def fetch_dc_posts(keyword="니콘", pages=2, fetch_body=True):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    encoded_kw = urllib.parse.quote(keyword)
    posts = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for page in range(1, pages + 1):
        status_text.text(f"📋 {page}페이지 목록 수집 중...")
        url = f"https://gall.dcinside.com/mgallery/board/lists/?id=digitalpicture&s_type=search_subject_memo&s_keyword={encoded_kw}&page={page}"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, "html.parser")
            tr_list = soup.select("table.gall_list tbody tr.ub-content")

            page_posts = []
            for tr in tr_list:
                gall_num = tr.select_one(".gall_num")
                if not gall_num or gall_num.text.strip() in ["공지", "설문", "광고"]:
                    continue

                title_tag = tr.select_one(".gall_tit a")
                if not title_tag:
                    continue
                
                href = title_tag.get("href", "").strip()
                if not href or href.startswith("javascript:") or "javascript" in href or "/board/view" not in href:
                    continue

                link = href if href.startswith("http") else "https://gall.dcinside.com" + href
                title = title_tag.text.strip()
                date = tr.select_one(".gall_date").text.strip() if tr.select_one(".gall_date") else ""
                views = tr.select_one(".gall_count").text.strip() if tr.select_one(".gall_count") else "0"
                recom = tr.select_one(".gall_recommend").text.strip() if tr.select_one(".gall_recommend") else "0"

                page_posts.append({
                    "원문제목": title,
                    "작성일": date,
                    "조회수": views,
                    "추천수": recom,
                    "링크": link,
                    "본문": ""
                })

            # 💡 본문 크롤링 옵션이 켜져있을 경우 각 게시글 본문 수집
            if fetch_body:
                total_in_page = len(page_posts)
                for idx, post in enumerate(page_posts):
                    status_text.text(f"📖 {page}페이지 게시글 본문 수집 중... ({idx+1}/{total_in_page})")
                    try:
                        b_res = requests.get(post["링크"], headers=headers, timeout=5)
                        if b_res.status_code == 200:
                            b_soup = BeautifulSoup(b_res.text, "html.parser")
                            # 디시인사이드 본문 영역
                            body_tag = b_soup.select_one(".write_div")
                            if body_tag:
                                post["본문"] = body_tag.get_text(separator=" ", strip=True)
                        time.sleep(0.3)  # 차단 방지 딜레이
                    except Exception:
                        pass
                    
                    # 프로그레스 바 업데이트
                    prog = ((page - 1) + (idx + 1) / max(total_in_page, 1)) / pages
                    progress_bar.progress(min(prog, 1.0))

            posts.extend(page_posts)
            time.sleep(0.3)
        except Exception as e:
            st.warning(f"{page}페이지 수집 중 오류: {e}")

    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(posts)

# ----------------------------------------------------
# 2. 본문 포함 감성 분석 함수 (개선)
# ----------------------------------------------------
def analyze_sentiment(row):
    """제목 + 본문 전체 텍스트 기반 감성 분석"""
    # 본문 가중치 적용 (제목보다 본물 글 분량이 크므로)
    full_text = f"{row['원문제목']} {row['원문제목']} {row.get('본문', '')}"

    pos_words = ["좋음", "좋다", "갓", "지름", "추천", "만족", "명기", "대박", "예쁨", "이쁨", "성능", "굿", "우수", "산다", "샀다", "신형", "종결", "지렀다", "개쩐다", "쩐다", "지렸다", "지리네", "최고"]
    neg_words = ["망함", "별로", "아쉽", "비추", "쓰레기", "고장", "단점", "비쌈", "개판", "거품", "후회", "걸러", "망", "발열", "무겁", "까는"]

    pos_score = sum(1 for w in pos_words if w in full_text)
    neg_score = sum(1 for w in neg_words if w in full_text)

    if pos_score > neg_score:
        return "긍정"
    elif neg_score > pos_score:
        return "부정"
    else:
        return "중립"

def extract_top_keywords(texts, top_n=15):
    """제목 및 본문에서 쓸데없는 단어(주어, 관사, 불용어)를 지우고 순수 키워드만 추출"""
    words = []
    for text in texts:
        # 한글, 영문, 숫자 단어 단위 추출 (2글자 이상)
        extracted = re.findall(r'[가-힣a-zA-Z0-9]{2,}', text)
        for w in extracted:
            w_lower = w.lower()  # 영문 대소문자 통일 (The -> the)
            
            # 불용어, 비속어에 해당하지 않는 정제된 단어만 추가
            if w_lower not in STOPWORDS and w not in STOPWORDS and w not in SWEAR_WORDS:
                words.append(w)
                
    return Counter(words).most_common(top_n)
# ----------------------------------------------------
# 3. 마인드맵 그래프 생성 함수
# ----------------------------------------------------
def create_mindmap_chart(center_node, top_keywords):
    if not top_keywords:
        return None

    labels = [center_node] + [word for word, _ in top_keywords]
    counts = [sum([c for _, c in top_keywords])] + [count for _, count in top_keywords]
    
    node_x = [0]
    node_y = [0]
    
    n = len(top_keywords)
    radius = 2.5
    
    for i in range(n):
        angle = (2 * math.pi / n) * i
        node_x.append(radius * math.cos(angle))
        node_y.append(radius * math.sin(angle))

    edge_x, edge_y = [], []
    for i in range(1, len(labels)):
        edge_x.extend([0, node_x[i], None])
        edge_y.extend([0, node_y[i], None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1.5, color='#BDC3C7'),
        hoverinfo='none',
        mode='lines'
    )

    max_count = max(counts[1:]) if len(counts) > 1 else 1
    node_sizes = [45] + [18 + (c / max_count) * 22 for c in counts[1:]]
    node_colors = ['#E74C3C'] + ['#3498DB'] * len(top_keywords)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        hoverinfo='text',
        text=labels,
        textposition="top center",
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color='white')
        ),
        hovertext=[f"<b>{label}</b>: {count}회 언급" for label, count in zip(labels, counts)]
    )

    fig = go.Figure(data=[edge_trace, node_trace],
                 layout=go.Layout(
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20, l=20, r=20, t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=500
                 ))
    return fig

# ----------------------------------------------------
# 4. Streamlit 대시보드 화면 구성
# ----------------------------------------------------
st.title("📷 디시인사이드 디카갤 '니콘' 반응 대시보드")
st.caption("디지털카메라 마이너 갤러리의 게시글(제목+본문)을 실시간 수집하여 긍정/부정/중립 여부를 분석합니다.")

st.sidebar.header("⚙️ 설정")
page_count = st.sidebar.slider("수집할 페이지 수", min_value=1, max_value=10, value=10)
fetch_body_option = st.sidebar.checkbox("게시글 본문까지 상세 수집 (정확도 UP, 속도 DOWN)", value=True)
enable_profanity_filter = st.sidebar.checkbox("비속어/욕설 클린 필터 적용", value=True)

if st.sidebar.button("데이터 다시 불러오기"):
    st.cache_data.clear()

# 데이터 수집
df = fetch_dc_posts(keyword="니콘", pages=page_count, fetch_body=fetch_body_option)

if df.empty:
    st.error("데이터를 불러오지 못했거나 수집된 글이 없습니다.")
else:
    # 💡 본문 기반 감성 분석 적용
    df["감성"] = df.apply(analyze_sentiment, axis=1)
    df["제목"] = df["원문제목"].apply(lambda x: sanitize_text(x, enable_filter=enable_profanity_filter))

    total_cnt = len(df)
    pos_cnt = len(df[df["감성"] == "긍정"])
    neg_cnt = len(df[df["감성"] == "부정"])
    neu_cnt = len(df[df["감성"] == "중립"])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("전체 수집 게시글", f"{total_cnt}개")
    col2.metric("긍정 게시글", f"{pos_cnt}개", delta=f"{pos_cnt/total_cnt*100:.1f}%" if total_cnt else "0%")
    col3.metric("부정 게시글", f"{neg_cnt}개", delta=f"-{neg_cnt/total_cnt*100:.1f}%" if total_cnt else "0%", delta_color="inverse")
    col4.metric("중립 게시글", f"{neu_cnt}개")

    st.markdown("---")

    col_map, col_pie = st.columns([3, 2])

    with col_map:
        st.subheader("🧠 연관 키워드 마인드맵 (TOP 15)")
        # 제목 + 본문 통합 키워드 분석
        all_texts = df["원문제목"].tolist() + df["본문"].tolist()
        top_kws = extract_top_keywords(all_texts, top_n=15)
        
        if top_kws:
            mindmap_fig = create_mindmap_chart("니콘", top_kws)
            st.plotly_chart(mindmap_fig, use_container_width=True)
        else:
            st.info("추출된 키워드가 없습니다.")

    with col_pie:
        st.subheader("📊 감성 분석 비율")
        fig_pie = px.pie(
            df, 
            names="감성", 
            color="감성",
            color_discrete_map={"긍정": "#2ECC71", "부정": "#E74C3C", "중립": "#95A5A6"},
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("---")

    st.subheader("📝 수집된 게시글 목록")
    selected_sentiment = st.multiselect(
        "감성 필터 선택", 
        options=["긍정", "부정", "중립"], 
        default=["긍정", "부정", "중립"]
    )

    filtered_df = df[df["감성"].isin(selected_sentiment)]
    
    st.dataframe(
        filtered_df[["감성", "제목", "작성일", "조회수", "추천수", "링크"]],
        column_config={
            "링크": st.column_config.LinkColumn("원문 링크"),
            "감성": st.column_config.TextColumn("감성 구분")
        },
        use_container_width=True,
        hide_index=True
    )