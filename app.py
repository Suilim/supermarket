import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yaml
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader

st.set_page_config(
    page_title="超市銷售儀表板",
    page_icon="🛒",
    layout="wide",
)

# ── 讀取帳號設定 ──────────────────────────────────────────────
# 雲端用 st.secrets，本機用 config.yaml
def load_config():
    import os
    if os.path.exists("config.yaml"):
        with open("config.yaml") as f:
            return yaml.load(f, Loader=SafeLoader)
    # Streamlit Cloud Secrets
    return {
        "credentials": {
            "usernames": {
                k: dict(v) for k, v in st.secrets["credentials"]["usernames"].items()
            }
        },
        "cookie": dict(st.secrets["cookie"]),
    }

config = load_config()

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
    auto_hash=False,
)

# ── 登入頁面 ──────────────────────────────────────────────────
name, authentication_status, username = authenticator.login(location="main")

if authentication_status is False:
    st.error("帳號或密碼錯誤，請重試。")
    st.stop()

if authentication_status is None:
    st.title("🛒 超市銷售儀表板")
    st.info("請輸入帳號密碼登入。")
    st.stop()

# ── 登入成功：儀表板 ──────────────────────────────────────────
with st.sidebar:
    st.markdown(f"👋 歡迎，**{name}**")
    authenticator.logout("登出", location="sidebar")
    st.divider()

    # 篩選器
    st.header("篩選條件")

    @st.cache_data
    def load_data():
        df = pd.read_csv("supermarket_sales.csv")
        df["Date"] = pd.to_datetime(df["Date"])
        return df

    df_all = load_data()

    branch_options = ["全部"] + sorted(df_all["Branch"].unique().tolist())
    selected_branch = st.selectbox("分店", branch_options)

    product_options = ["全部"] + sorted(df_all["Product line"].unique().tolist())
    selected_product = st.multiselect("產品類別", product_options[1:], default=product_options[1:])

    min_date = df_all["Date"].min().date()
    max_date = df_all["Date"].max().date()
    date_range = st.date_input("日期區間", value=(min_date, max_date), min_value=min_date, max_value=max_date)

# ── 資料篩選 ──────────────────────────────────────────────────
df = df_all.copy()

if selected_branch != "全部":
    df = df[df["Branch"] == selected_branch]

if selected_product:
    df = df[df["Product line"].isin(selected_product)]

if len(date_range) == 2:
    df = df[(df["Date"].dt.date >= date_range[0]) & (df["Date"].dt.date <= date_range[1])]

# ── 標題 ──────────────────────────────────────────────────────
st.title("🛒 超市銷售儀表板")
st.caption(f"資料範圍：{df['Date'].min().date()} ～ {df['Date'].max().date()}　｜　共 {len(df):,} 筆交易")
st.divider()

# ── KPI 指標卡 ────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("總銷售額", f"${df['Total'].sum():,.0f}")
col2.metric("交易筆數", f"{len(df):,}")
col3.metric("平均評分", f"{df['Rating'].mean():.2f} / 10")
col4.metric("毛利總額", f"${df['gross income'].sum():,.0f}")

st.divider()

# ── 圖表 ──────────────────────────────────────────────────────
row1_col1, row1_col2 = st.columns([3, 2])

with row1_col1:
    st.subheader("每日銷售趨勢")
    daily = df.groupby("Date")["Total"].sum().reset_index()
    fig = px.line(daily, x="Date", y="Total", markers=True,
                  labels={"Total": "銷售額 ($)", "Date": "日期"})
    fig.update_traces(line_color="#4F8EF7", marker_color="#4F8EF7")
    fig.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

with row1_col2:
    st.subheader("付款方式分佈")
    payment = df["Payment"].value_counts().reset_index()
    payment.columns = ["方式", "筆數"]
    fig2 = px.pie(payment, names="方式", values="筆數",
                  color_discrete_sequence=px.colors.qualitative.Pastel)
    fig2.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.subheader("各產品線銷售額")
    product_sales = df.groupby("Product line")["Total"].sum().sort_values().reset_index()
    fig3 = px.bar(product_sales, x="Total", y="Product line", orientation="h",
                  labels={"Total": "銷售額 ($)", "Product line": "產品線"},
                  color="Total", color_continuous_scale="Blues")
    fig3.update_layout(margin=dict(t=10, b=10), coloraxis_showscale=False)
    st.plotly_chart(fig3, use_container_width=True)

with row2_col2:
    st.subheader("顧客類型 × 性別")
    cross = df.groupby(["Customer type", "Gender"])["Total"].sum().reset_index()
    fig4 = px.bar(cross, x="Customer type", y="Total", color="Gender",
                  barmode="group",
                  labels={"Total": "銷售額 ($)", "Customer type": "顧客類型"},
                  color_discrete_map={"Female": "#F4A1A1", "Male": "#A1C4F4"})
    fig4.update_layout(margin=dict(t=10, b=10))
    st.plotly_chart(fig4, use_container_width=True)

# ── 各分店表現 ────────────────────────────────────────────────
st.subheader("各分店銷售摘要")
branch_summary = (
    df.groupby("Branch")
    .agg(銷售額=("Total", "sum"), 交易筆數=("Invoice ID", "count"),
         平均評分=("Rating", "mean"), 毛利=("gross income", "sum"))
    .round(2)
    .reset_index()
)
branch_summary.columns = ["分店", "銷售額 ($)", "交易筆數", "平均評分", "毛利 ($)"]
st.dataframe(branch_summary, use_container_width=True, hide_index=True)
