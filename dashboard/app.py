
import re
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.set_page_config(page_title="PTAC Refurb LinkedIn Dashboard", page_icon="📊", layout="wide")

RED = "#9C0100"
DARK = "#1F2328"
GRAY = "#666666"
LIGHT_BG = "#F5F5F5"


def css():
    st.markdown(f"""
    <style>
    .stApp {{ background: {LIGHT_BG}; }}
    .block-container {{ max-width: 1500px; padding-top: 1rem; }}
    .top-header {{
        background:#fff; border-bottom:4px solid {DARK}; padding:24px 28px;
        display:flex; align-items:center; justify-content:space-between;
    }}
    .brand {{ font-size:42px; font-weight:900; color:{DARK}; letter-spacing:-2px; }}
    .brand span {{ color:{RED}; }}
    .title-block h1 {{ margin:0; color:{DARK}; font-size:36px; font-weight:900; letter-spacing:-1px; }}
    .title-block p {{ margin:4px 0 0; color:{GRAY}; font-size:17px; }}
    .export-pill {{ background:{RED}; color:white; padding:16px 22px; border-radius:8px; font-weight:900; }}
    .week-bar {{
        background:linear-gradient(90deg,{DARK},#111); color:white; padding:16px 22px;
        margin:0 0 18px 0; border-radius:0 0 8px 8px; display:flex; justify-content:space-between;
    }}
    .week-label {{ color:#C00000; font-weight:900; font-size:18px; }}
    .section-title {{ color:{RED}; font-size:19px; font-weight:900; margin:18px 0 10px; text-transform:uppercase; }}
    div[data-testid="stMetric"] {{
        background:white; border:1px solid #ddd; border-radius:9px; padding:18px 16px;
        box-shadow:0 2px 8px rgba(0,0,0,.08); min-height:115px;
    }}
    div[data-testid="stMetricLabel"] {{ font-weight:900; color:{DARK}; text-transform:uppercase; }}
    div[data-testid="stMetricValue"] {{ font-size:34px; font-weight:900; color:{DARK}; }}
    .panel {{ background:white; border:1px solid #ddd; border-radius:9px; padding:16px; box-shadow:0 2px 8px rgba(0,0,0,.06); }}
    .summary-box {{
        background:white; border:1px solid #ddd; border-radius:9px; padding:16px 20px;
        box-shadow:0 2px 8px rgba(0,0,0,.06); line-height:1.6;
    }}
    .footer {{
        background:linear-gradient(90deg,{DARK},#111); color:white; padding:18px 24px;
        border-radius:8px; margin-top:20px; display:flex; justify-content:space-between;
    }}
    .stDownloadButton button {{ background-color:{RED}; color:white; border-radius:8px; font-weight:900; border:none; padding:12px 18px; }}
    </style>
    """, unsafe_allow_html=True)


def clean_sheet_id(value):
    value = str(value or "").strip()
    if "/spreadsheets/d/" in value:
        match = re.search(r"/spreadsheets/d/([^/]+)", value)
        return match.group(1) if match else value
    return value


@st.cache_data(ttl=300, show_spinner=False)
def read_sheet(sheet_id_or_url):
    sheet_id = clean_sheet_id(sheet_id_or_url)
    if not sheet_id:
        return pd.DataFrame()
    urls = [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
    ]
    for url in urls:
        try:
            df = pd.read_csv(url)
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception:
            pass
    return pd.DataFrame()


def detect_sheet_type(df):
    cols = " ".join([str(c).lower() for c in df.columns])
    if "competitor" in cols or "competitors" in cols or "company name" in cols:
        return "competitors"
    if "impressions" in cols or "clicks" in cols or "reactions" in cols or "engagement" in cols:
        return "content"
    if "visitor" in cols or "page views" in cols or "views" in cols:
        return "visitors"
    if "follower" in cols:
        return "followers"
    return "unknown"


def get_week_configs():
    weeks = []
    for key in st.secrets.keys():
        if str(key).lower().startswith("week_"):
            block = st.secrets[key]
            sheets = []
            for field in ["sheet_1", "sheet_2", "sheet_3", "sheet_4", "followers", "visitors", "content", "competitors"]:
                val = str(block.get(field, "")).strip()
                if val:
                    sheets.append(val)
            weeks.append({
                "key": key,
                "label": str(block.get("label", key.replace("_", " ").title())),
                "sheets": sheets,
            })
    def sort_key(w):
        nums = re.findall(r"\d+", w["key"])
        return int(nums[0]) if nums else 999
    return sorted(weeks, key=sort_key)


def find_col(df, terms, exclude=None):
    exclude = exclude or []
    for col in df.columns:
        low = str(col).lower()
        if any(e.lower() in low for e in exclude):
            continue
        if any(t.lower() in low for t in terms):
            return col
    return None


def sum_col(df, terms, exclude=None):
    col = find_col(df, terms, exclude)
    if not col:
        return 0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def first_col(df, terms, exclude=None):
    col = find_col(df, terms, exclude)
    if not col:
        return 0
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(s.iloc[0]) if len(s) else 0


def last_col(df, terms, exclude=None):
    col = find_col(df, terms, exclude)
    if not col:
        return 0
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(s.iloc[-1]) if len(s) else 0


def fmt_int(v):
    try:
        return f"{int(round(float(v))):,}"
    except Exception:
        return "0"


def fmt_pct(v):
    try:
        v = float(v)
        if v <= 1:
            v = v * 100
        return f"{v:.1f}%"
    except Exception:
        return "0.0%"


def delta(current, previous):
    try:
        current = float(current)
        previous = float(previous)
        if previous == 0:
            return None
        return f"{((current - previous) / previous) * 100:+.1f}%"
    except Exception:
        return None


def build_week_data(week):
    buckets = {"followers": pd.DataFrame(), "visitors": pd.DataFrame(), "content": pd.DataFrame(), "competitors": pd.DataFrame()}
    for sheet in week["sheets"]:
        df = read_sheet(sheet)
        kind = detect_sheet_type(df)
        if kind in buckets:
            buckets[kind] = df if buckets[kind].empty else pd.concat([buckets[kind], df], ignore_index=True)

    followers = buckets["followers"]
    visitors = buckets["visitors"]
    content = buckets["content"]

    followers_start = first_col(followers, ["total followers", "followers"], ["organic", "sponsored"])
    followers_end = last_col(followers, ["total followers", "followers"], ["organic", "sponsored"])
    new_followers = sum_col(followers, ["new followers", "followers gained", "gained"], ["total"])
    if new_followers == 0 and followers_end and followers_start:
        new_followers = followers_end - followers_start

    page_views = sum_col(visitors, ["page views", "total page views", "views"], ["unique"])
    unique_visitors = sum_col(visitors, ["unique visitors", "unique"], [])
    impressions = sum_col(content, ["impressions"], [])
    clicks = sum_col(content, ["clicks"], [])
    reactions = sum_col(content, ["reactions"], [])
    comments = sum_col(content, ["comments"], [])
    shares = sum_col(content, ["shares", "reposts"], [])
    posts = len(content) if not content.empty else 0
    engagement_total = clicks + reactions + comments + shares
    engagement_rate = engagement_total / impressions if impressions else 0

    return {
        "Week": week["label"],
        "Followers Start": followers_start,
        "Followers End": followers_end,
        "New Followers": new_followers,
        "Page Views": page_views,
        "Unique Visitors": unique_visitors,
        "Impressions": impressions,
        "Clicks": clicks,
        "Reactions": reactions,
        "Comments": comments,
        "Shares": shares,
        "Posts": posts,
        "Engagement Rate": engagement_rate,
        "content_df": content,
    }


def content_table(df, label):
    if df.empty:
        return pd.DataFrame(columns=["Week", "Post Topic", "Impressions", "Clicks", "Reactions", "Comments", "Shares", "Engagement Rate"])
    topic_col = find_col(df, ["post title", "post", "content", "update", "share commentary", "text"]) or df.columns[0]
    out = pd.DataFrame()
    out["Week"] = label
    out["Post Topic"] = df[topic_col].astype(str).str.slice(0, 80)
    for name, terms in {
        "Impressions": ["impressions"],
        "Clicks": ["clicks"],
        "Reactions": ["reactions"],
        "Comments": ["comments"],
        "Shares": ["shares", "reposts"],
    }.items():
        col = find_col(df, terms)
        out[name] = pd.to_numeric(df[col], errors="coerce").fillna(0) if col else 0
    out["Engagement Total"] = out[["Clicks", "Reactions", "Comments", "Shares"]].sum(axis=1)
    out["Engagement Rate"] = out["Engagement Total"] / out["Impressions"].replace(0, pd.NA)
    out["Engagement Rate"] = out["Engagement Rate"].fillna(0)
    return out.sort_values("Impressions", ascending=False)


def make_pdf(selected_week, week_row, totals, top_content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title", parent=styles["Title"], textColor=colors.HexColor(RED), fontSize=22, leading=26)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=colors.HexColor(DARK), fontSize=14, leading=18)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontSize=9, leading=13)
    story = [
        Paragraph("PTAC Refurb LinkedIn Performance Report", title),
        Paragraph(f"Reporting Week: {selected_week}", h2),
        Spacer(1, 10),
    ]
    rows = [
        ["Metric", "This Week", "Total / Current"],
        ["Followers", fmt_int(week_row["Followers End"]), fmt_int(totals["Followers End"])],
        ["New Followers", fmt_int(week_row["New Followers"]), fmt_int(totals["New Followers"])],
        ["Page Views", fmt_int(week_row["Page Views"]), fmt_int(totals["Page Views"])],
        ["Impressions", fmt_int(week_row["Impressions"]), fmt_int(totals["Impressions"])],
        ["Clicks", fmt_int(week_row["Clicks"]), fmt_int(totals["Clicks"])],
        ["Reactions", fmt_int(week_row["Reactions"]), fmt_int(totals["Reactions"])],
    ]
    t = Table(rows, colWidths=[160, 140, 140])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(RED)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#D9D9D9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))
    story.append(Paragraph("Executive Summary", h2))
    story.append(Paragraph("Review follower growth, impressions, page views, engagement, and top-performing content weekly to identify which marketing strategies are creating the strongest results.", body))
    doc.build(story)
    buffer.seek(0)
    return buffer


def main():
    css()

    st.markdown("""
    <div class="top-header">
        <div class="brand">PTAC<span>REFURB</span></div>
        <div class="title-block">
            <h1>LINKEDIN PERFORMANCE DASHBOARD</h1>
            <p>Data Driven. Relationships Focused. Results Delivered.</p>
        </div>
        <div class="export-pill">EXPORT PDF</div>
    </div>
    """, unsafe_allow_html=True)

    weeks = get_week_configs()
    if not weeks:
        st.error("No weekly sheet groups found in Streamlit secrets.")
        st.code("""
[week_1]
label = "June 9 - June 15, 2026"
sheet_1 = "Google Sheet URL or ID"
sheet_2 = "Google Sheet URL or ID"
sheet_3 = "Google Sheet URL or ID"
sheet_4 = "Google Sheet URL or ID"
        """, language="toml")
        st.stop()

    with st.spinner("Reading Google Sheets..."):
        week_rows = []
        content_rows = []
        for week in weeks:
            row = build_week_data(week)
            content_rows.append(content_table(row["content_df"], row["Week"]))
            week_rows.append({k: v for k, v in row.items() if k != "content_df"})
        weekly = pd.DataFrame(week_rows)
        content_all = pd.concat(content_rows, ignore_index=True) if content_rows else pd.DataFrame()

    selected_week = st.selectbox("Select reporting week", weekly["Week"].tolist(), index=len(weekly) - 1)
    selected_idx = weekly[weekly["Week"] == selected_week].index[0]
    week_row = weekly.iloc[selected_idx]
    prev = weekly.iloc[selected_idx - 1] if selected_idx > 0 else None
    content_week = content_all[content_all["Week"] == selected_week].sort_values("Impressions", ascending=False)

    totals = {
        "Followers End": weekly["Followers End"].iloc[-1],
        "New Followers": weekly["New Followers"].sum(),
        "Page Views": weekly["Page Views"].sum(),
        "Impressions": weekly["Impressions"].sum(),
        "Clicks": weekly["Clicks"].sum(),
        "Reactions": weekly["Reactions"].sum(),
        "Comments": weekly["Comments"].sum(),
        "Shares": weekly["Shares"].sum(),
    }

    st.markdown(f"""
    <div class="week-bar">
        <div><span class="week-label">WEEKLY SNAPSHOT</span> &nbsp; | &nbsp; {selected_week}</div>
        <div>Data Source: LinkedIn Analytics Company Page Exports</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Followers", fmt_int(week_row["Followers End"]), f"+{fmt_int(week_row['New Followers'])}")
    c2.metric("Impressions", fmt_int(week_row["Impressions"]), delta(week_row["Impressions"], prev["Impressions"]) if prev is not None else None)
    c3.metric("Page Views", fmt_int(week_row["Page Views"]), delta(week_row["Page Views"], prev["Page Views"]) if prev is not None else None)
    c4.metric("Posts", fmt_int(week_row["Posts"]))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Clicks", fmt_int(week_row["Clicks"]), delta(week_row["Clicks"], prev["Clicks"]) if prev is not None else None)
    c6.metric("Reactions", fmt_int(week_row["Reactions"]), delta(week_row["Reactions"], prev["Reactions"]) if prev is not None else None)
    c7.metric("Comments", fmt_int(week_row["Comments"]), delta(week_row["Comments"], prev["Comments"]) if prev is not None else None)
    c8.metric("Shares", fmt_int(week_row["Shares"]), delta(week_row["Shares"], prev["Shares"]) if prev is not None else None)

    left, right = st.columns(2)
    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        fig = px.line(weekly, x="Week", y="Followers End", markers=True, title="Follower Growth")
        fig.update_traces(line_color=RED, marker_color=RED)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        fig = px.bar(weekly, x="Week", y="Impressions", title="Impressions Trend")
        fig.update_traces(marker_color=RED)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    left, right = st.columns([1.15, .85])
    with left:
        st.markdown('<div class="section-title">Top Performing Content This Week</div>', unsafe_allow_html=True)
        if content_week.empty:
            st.info("No content data found for this week.")
        else:
            display = content_week[["Post Topic", "Impressions", "Clicks", "Engagement Rate"]].head(8).copy()
            display["Engagement Rate"] = display["Engagement Rate"].apply(fmt_pct)
            st.dataframe(display, use_container_width=True, hide_index=True)

    with right:
        st.markdown('<div class="section-title">Engagement Rate This Week</div>', unsafe_allow_html=True)
        st.metric("Engagement Rate", fmt_pct(week_row["Engagement Rate"]), delta(week_row["Engagement Rate"], prev["Engagement Rate"]) if prev is not None else None)

        st.markdown('<div class="section-title">Totals Since Tracking Started</div>', unsafe_allow_html=True)
        totals_table = pd.DataFrame({
            "Metric": ["Followers", "Impressions", "Page Views", "Clicks", "Reactions", "Comments", "Shares"],
            "Total": [
                fmt_int(totals["Followers End"]),
                fmt_int(totals["Impressions"]),
                fmt_int(totals["Page Views"]),
                fmt_int(totals["Clicks"]),
                fmt_int(totals["Reactions"]),
                fmt_int(totals["Comments"]),
                fmt_int(totals["Shares"]),
            ],
        })
        st.dataframe(totals_table, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    best_post = content_week.iloc[0]["Post Topic"] if not content_week.empty else "No content data yet"
    st.markdown(f"""
    <div class="summary-box">
    <ul>
        <li>Followers ended the week at <b>{fmt_int(week_row["Followers End"])}</b>.</li>
        <li>This week generated <b>{fmt_int(week_row["Impressions"])}</b> impressions and <b>{fmt_int(week_row["Clicks"])}</b> clicks.</li>
        <li>Top-performing content this week: <b>{best_post}</b>.</li>
        <li>Use weekly trends to identify which content themes are driving follower growth, page views, and engagement.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Export Report</div>', unsafe_allow_html=True)
    pdf = make_pdf(selected_week, week_row, totals, content_week)
    st.download_button(
        "Download boss-ready PDF report",
        data=pdf,
        file_name=f"PTAC_Refurb_LinkedIn_Report_{selected_week.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )

    st.markdown("""
    <div class="footer">
        <div><b>PTAC REFURB</b> | Expert Refurbishment. Maximum Uptime.</div>
        <div>ptacrefurb.com</div>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
