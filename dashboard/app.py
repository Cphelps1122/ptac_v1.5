
import re
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.set_page_config(
    page_title="PTAC Refurb LinkedIn Dashboard",
    page_icon="📊",
    layout="wide",
)

RED = "#9C0100"
BRIGHT_RED = "#C00000"
DARK = "#1F2328"
GRAY = "#666666"
LIGHT_BG = "#F5F5F5"

HEADER_KEYWORDS = [
    "date", "follower", "followers", "visitor", "visitors", "view", "views",
    "impression", "impressions", "click", "clicks", "reaction", "reactions",
    "comment", "comments", "share", "shares", "repost", "reposts",
    "engagement", "post", "content", "company", "competitor"
]


def css():
    st.markdown(
        f"""
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
        .week-label {{ color:{BRIGHT_RED}; font-weight:900; font-size:18px; }}
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
        """,
        unsafe_allow_html=True,
    )


def clean_sheet_id(value):
    value = str(value or "").strip()
    if "/spreadsheets/d/" in value:
        match = re.search(r"/spreadsheets/d/([^/]+)", value)
        return match.group(1) if match else value
    return value


def make_unique_headers(headers):
    seen = {}
    output = []
    for i, h in enumerate(headers):
        h = str(h).strip()
        if not h or h.lower() == "nan":
            h = f"Column {i+1}"
        if h in seen:
            seen[h] += 1
            h = f"{h} {seen[h]}"
        else:
            seen[h] = 1
        output.append(h)
    return output


def detect_header_row(raw):
    """
    LinkedIn exports often have title/metadata rows before the actual table.
    This finds the row that looks most like the real header.
    """
    best_idx = 0
    best_score = -1

    max_rows = min(40, len(raw))
    for idx in range(max_rows):
        row_values = [str(x).strip().lower() for x in raw.iloc[idx].tolist() if str(x).strip().lower() != "nan"]
        row_text = " ".join(row_values)

        keyword_score = sum(1 for kw in HEADER_KEYWORDS if kw in row_text)
        non_empty = len(row_values)

        # Header rows usually have several non-empty cells and multiple metric words.
        score = keyword_score * 10 + min(non_empty, 10)

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx


@st.cache_data(ttl=300, show_spinner=False)
def read_sheet(sheet_id_or_url):
    """
    Reads a public Google Sheet and normalizes LinkedIn export files
    even when Google Sheets has metadata rows above the real headers.
    """
    sheet_id = clean_sheet_id(sheet_id_or_url)
    if not sheet_id:
        return pd.DataFrame(), {"sheet_id": "", "header_row": None, "columns": [], "rows": 0}

    urls = [
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv",
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv",
    ]

    last_error = ""
    for url in urls:
        try:
            raw = pd.read_csv(url, header=None, dtype=str, on_bad_lines="skip")
            raw = raw.dropna(how="all")

            if raw.empty:
                return pd.DataFrame(), {"sheet_id": sheet_id, "header_row": None, "columns": [], "rows": 0}

            header_idx = detect_header_row(raw)
            headers = make_unique_headers(raw.iloc[header_idx].tolist())
            df = raw.iloc[header_idx + 1:].copy()
            df.columns = headers

            # Remove blank/nonsense columns and rows.
            df = df.dropna(axis=1, how="all")
            df = df.dropna(how="all")
            df = df.loc[:, [c for c in df.columns if not str(c).startswith("Column")]]

            # Strip text cells.
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str).str.strip()

            meta = {
                "sheet_id": sheet_id,
                "header_row": header_idx + 1,
                "columns": list(df.columns),
                "rows": len(df),
            }
            return df, meta

        except Exception as e:
            last_error = str(e)

    return pd.DataFrame(), {"sheet_id": sheet_id, "header_row": None, "columns": [], "rows": 0, "error": last_error}


def detect_sheet_type(df):
    cols = " ".join([str(c).lower() for c in df.columns])

    if not cols:
        return "unknown"

    # Content exports have these performance columns.
    if any(x in cols for x in ["impressions", "clicks", "reactions", "engagement rate", "comments"]):
        return "content"

    # Visitor exports have visitor/page view terminology.
    if any(x in cols for x in ["unique visitors", "page views", "visitor metrics", "visitors"]):
        return "visitors"

    # Follower exports have total/new/organic/sponsored follower columns.
    if any(x in cols for x in ["total followers", "new followers", "organic followers", "sponsored followers", "followers gained"]):
        return "followers"

    # Competitor exports are less important for KPI math.
    if any(x in cols for x in ["competitor", "company name", "companies", "organization"]):
        return "competitors"

    if "follower" in cols:
        return "followers"

    return "unknown"


def get_week_configs():
    weeks = []
    for key in st.secrets.keys():
        if str(key).lower().startswith("week_"):
            block = st.secrets[key]
            sheets = []

            # Either style works:
            # sheet_1...sheet_4 OR named followers/visitors/content/competitors.
            for field in ["sheet_1", "sheet_2", "sheet_3", "sheet_4", "followers", "visitors", "content", "competitors"]:
                val = str(block.get(field, "")).strip()
                if val:
                    sheets.append(val)

            leads = block.get("leads", 0)
            try:
                leads = float(leads)
            except Exception:
                leads = 0

            weeks.append({
                "key": key,
                "label": str(block.get("label", key.replace("_", " ").title())),
                "sheets": sheets,
                "leads": leads,
            })

    def sort_key(w):
        nums = re.findall(r"\d+", w["key"])
        return int(nums[0]) if nums else 999

    return sorted(weeks, key=sort_key)


def clean_num_series(series):
    return pd.to_numeric(
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.strip(),
        errors="coerce"
    ).fillna(0)


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
    return clean_num_series(df[col]).sum()


def first_col(df, terms, exclude=None):
    col = find_col(df, terms, exclude)
    if not col:
        return 0
    s = clean_num_series(df[col])
    s = s[s.notna()]
    return float(s.iloc[0]) if len(s) else 0


def last_col(df, terms, exclude=None):
    col = find_col(df, terms, exclude)
    if not col:
        return 0
    s = clean_num_series(df[col])
    s = s[s.notna()]
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
    buckets = {
        "followers": pd.DataFrame(),
        "visitors": pd.DataFrame(),
        "content": pd.DataFrame(),
        "competitors": pd.DataFrame(),
        "unknown": pd.DataFrame(),
    }
    debug_rows = []

    for sheet in week["sheets"]:
        df, meta = read_sheet(sheet)
        kind = detect_sheet_type(df)

        debug_rows.append({
            "Week": week["label"],
            "Detected Type": kind,
            "Rows": meta.get("rows", 0),
            "Header Row": meta.get("header_row", ""),
            "Sheet ID": meta.get("sheet_id", ""),
            "Columns Found": ", ".join(meta.get("columns", [])[:8]),
        })

        if kind in buckets:
            buckets[kind] = df if buckets[kind].empty else pd.concat([buckets[kind], df], ignore_index=True)
        else:
            buckets["unknown"] = df if buckets["unknown"].empty else pd.concat([buckets["unknown"], df], ignore_index=True)

    followers = buckets["followers"]
    visitors = buckets["visitors"]
    content = buckets["content"]

    followers_start = first_col(followers, ["total followers", "followers"], ["organic", "sponsored", "new"])
    followers_end = last_col(followers, ["total followers", "followers"], ["organic", "sponsored", "new"])

    # LinkedIn often reports new followers as organic + sponsored, not as a column named "New Followers".
    new_followers = sum_col(followers, ["new followers", "followers gained", "gained"], ["total"])
    if new_followers == 0:
        new_followers = (
            sum_col(followers, ["organic followers"], ["total"]) +
            sum_col(followers, ["sponsored followers"], ["total"])
        )
    if new_followers == 0 and followers_end and followers_start:
        new_followers = followers_end - followers_start

    page_views = sum_col(visitors, ["total page views", "page views", "views"], ["unique"])
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
        "Leads": week.get("leads", 0),
        "Engagement Rate": engagement_rate,
        "content_df": content,
        "debug_df": pd.DataFrame(debug_rows),
    }


def content_table(df, label):
    if df.empty:
        return pd.DataFrame(columns=["Week", "Post Topic", "Impressions", "Clicks", "Reactions", "Comments", "Shares", "Engagement Rate"])

    topic_col = (
        find_col(df, ["post title", "post", "content", "update", "share commentary", "text", "post link"])
        or df.columns[0]
    )

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
        out[name] = clean_num_series(df[col]) if col else 0

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
        ["Impressions", fmt_int(week_row["Impressions"]), fmt_int(totals["Impressions"])],
        ["Page Views", fmt_int(week_row["Page Views"]), fmt_int(totals["Page Views"])],
        ["Clicks", fmt_int(week_row["Clicks"]), fmt_int(totals["Clicks"])],
        ["Reactions", fmt_int(week_row["Reactions"]), fmt_int(totals["Reactions"])],
        ["Comments", fmt_int(week_row["Comments"]), fmt_int(totals["Comments"])],
        ["Shares", fmt_int(week_row["Shares"]), fmt_int(totals["Shares"])],
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

    story.append(Paragraph("Top Performing Content", h2))
    if top_content.empty:
        story.append(Paragraph("No content data found for this week.", body))
    else:
        rows2 = [["Post Topic", "Impressions", "Clicks", "Eng. Rate"]]
        for _, r in top_content.head(5).iterrows():
            rows2.append([str(r["Post Topic"])[:45], fmt_int(r["Impressions"]), fmt_int(r["Clicks"]), fmt_pct(r["Engagement Rate"])])
        t2 = Table(rows2, colWidths=[260, 80, 60, 80])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), .5, colors.HexColor("#D9D9D9")),
        ]))
        story.append(t2)

    story.append(Spacer(1, 12))
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
leads = 0
        """, language="toml")
        st.stop()

    with st.spinner("Reading Google Sheets..."):
        week_rows = []
        content_rows = []
        debug_rows = []

        for week in weeks:
            row = build_week_data(week)
            content_rows.append(content_table(row["content_df"], row["Week"]))
            debug_rows.append(row["debug_df"])
            week_rows.append({k: v for k, v in row.items() if k not in ["content_df", "debug_df"]})

        weekly = pd.DataFrame(week_rows)
        content_all = pd.concat(content_rows, ignore_index=True) if content_rows else pd.DataFrame()
        debug_all = pd.concat(debug_rows, ignore_index=True) if debug_rows else pd.DataFrame()

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
        "Leads": weekly["Leads"].sum(),
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
    c4.metric("Leads", fmt_int(week_row["Leads"]))

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
            "Metric": ["Followers", "New Followers", "Impressions", "Page Views", "Clicks", "Reactions", "Comments", "Shares", "Leads"],
            "Total": [
                fmt_int(totals["Followers End"]),
                fmt_int(totals["New Followers"]),
                fmt_int(totals["Impressions"]),
                fmt_int(totals["Page Views"]),
                fmt_int(totals["Clicks"]),
                fmt_int(totals["Reactions"]),
                fmt_int(totals["Comments"]),
                fmt_int(totals["Shares"]),
                fmt_int(totals["Leads"]),
            ],
        })
        st.dataframe(totals_table, use_container_width=True, hide_index=True)

    st.markdown('<div class="section-title">Executive Summary</div>', unsafe_allow_html=True)
    best_post = content_week.iloc[0]["Post Topic"] if not content_week.empty else "No content data yet"
    st.markdown(f"""
    <div class="summary-box">
    <ul>
        <li>Followers ended the week at <b>{fmt_int(week_row["Followers End"])}</b> with <b>{fmt_int(week_row["New Followers"])}</b> new followers.</li>
        <li>This week generated <b>{fmt_int(week_row["Impressions"])}</b> impressions and <b>{fmt_int(week_row["Clicks"])}</b> clicks.</li>
        <li>Top-performing content this week: <b>{best_post}</b>.</li>
        <li>Use weekly trends to identify which content themes are driving follower growth, page views, and engagement.</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("Debug data check: detected sheet types and columns"):
        st.dataframe(debug_all, use_container_width=True, hide_index=True)
        st.caption("This section is here so you can quickly see whether each Google Sheet is being classified correctly.")

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
