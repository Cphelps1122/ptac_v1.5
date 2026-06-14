
import re
from io import BytesIO
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


st.set_page_config(
    page_title="PTAC Refurb LinkedIn Weekly Dashboard",
    page_icon="📊",
    layout="wide",
)

RED = "#9C0100"
DARK = "#343434"
GRAY = "#666666"
LIGHT = "#F7F7F7"

DATA_TYPES = ["followers", "visitors", "content", "competitors"]


# -----------------------------
# Styling
# -----------------------------

def css():
    st.markdown(
        f"""
        <style>
        .block-container {{
            max-width: 1500px;
            padding-top: 1rem;
        }}

        .hero {{
            background: linear-gradient(135deg, #ffffff 0%, #ffffff 68%, {DARK} 68%, {RED} 100%);
            border: 1px solid #ddd;
            border-radius: 18px;
            padding: 24px 28px;
            margin-bottom: 18px;
            box-shadow: 0 2px 10px rgba(0,0,0,.06);
        }}

        .hero h1 {{
            margin: 0;
            color: {DARK};
            font-size: 40px;
            font-weight: 900;
            letter-spacing: -1px;
        }}

        .hero p {{
            margin: 6px 0 0;
            color: {RED};
            font-weight: 800;
            letter-spacing: .5px;
        }}

        .section-title {{
            background: linear-gradient(90deg,{RED},{DARK});
            color: white;
            padding: 8px 12px;
            border-radius: 10px;
            font-weight: 800;
            margin: 16px 0 10px;
        }}

        div[data-testid="stMetric"] {{
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 14px;
            box-shadow: 0 2px 8px rgba(0,0,0,.04);
        }}

        .info-box {{
            background: white;
            border: 1px solid #e5e7eb;
            border-left: 5px solid """ + RED + """;
            border-radius: 12px;
            padding: 14px 16px;
            margin: 10px 0 16px;
        }}

        .footer {{
            color: #666;
            font-size: 12px;
            margin-top: 18px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header():
    st.markdown(
        """
        <div class="hero">
            <h1>PTAC Refurb LinkedIn Performance Dashboard</h1>
            <p>Weekly Analytics • Growth Trends • Content Performance • Executive Export</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------
# Helpers
# -----------------------------

def clean_sheet_id(value: str) -> str:
    """Accepts either a Google Sheet ID or full URL and returns the ID."""
    value = str(value or "").strip()
    if "/spreadsheets/d/" in value:
        match = re.search(r"/spreadsheets/d/([^/]+)", value)
        if match:
            return match.group(1)
    return value


def csv_url(sheet_id: str, gid: str | None = None) -> str:
    sheet_id = clean_sheet_id(sheet_id)
    if gid:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"


def get_week_configs():
    """
    Reads Streamlit secrets in this format:

    [week_1]
    label = "Week 1"
    followers = "sheet id or full google sheet url"
    visitors = "sheet id or full google sheet url"
    content = "sheet id or full google sheet url"
    competitors = "sheet id or full google sheet url"

    [week_2]
    ...
    """
    weeks = []

    for key in st.secrets.keys():
        if str(key).lower().startswith("week_"):
            block = st.secrets[key]
            item = {
                "key": key,
                "label": str(block.get("label", key.replace("_", " ").title())),
                "followers": str(block.get("followers", "")).strip(),
                "visitors": str(block.get("visitors", "")).strip(),
                "content": str(block.get("content", "")).strip(),
                "competitors": str(block.get("competitors", "")).strip(),
            }
            weeks.append(item)

    def week_sort(item):
        nums = re.findall(r"\d+", item["key"])
        return int(nums[0]) if nums else 9999

    return sorted(weeks, key=week_sort)


@st.cache_data(ttl=300, show_spinner=False)
def read_public_sheet(sheet_id_or_url: str) -> pd.DataFrame:
    """Reads a public Google Sheet as CSV."""
    sheet_id = clean_sheet_id(sheet_id_or_url)
    if not sheet_id:
        return pd.DataFrame()

    try:
        df = pd.read_csv(csv_url(sheet_id))
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        st.warning(f"Could not read Google Sheet {sheet_id}: {e}")
        return pd.DataFrame()


def find_col(df: pd.DataFrame, contains_any: list[str], exclude_any: list[str] | None = None):
    if df.empty:
        return None

    exclude_any = exclude_any or []
    cols = list(df.columns)

    for col in cols:
        low = str(col).lower()
        if all(ex.lower() not in low for ex in exclude_any):
            if any(term.lower() in low for term in contains_any):
                return col

    return None


def sum_col(df: pd.DataFrame, terms: list[str], exclude: list[str] | None = None) -> float:
    col = find_col(df, terms, exclude)
    if col is None:
        return 0
    return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()


def last_col(df: pd.DataFrame, terms: list[str], exclude: list[str] | None = None) -> float:
    col = find_col(df, terms, exclude)
    if col is None:
        return 0
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(s.iloc[-1]) if len(s) else 0


def first_col(df: pd.DataFrame, terms: list[str], exclude: list[str] | None = None) -> float:
    col = find_col(df, terms, exclude)
    if col is None:
        return 0
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    return float(s.iloc[0]) if len(s) else 0


def fmt_int(value):
    try:
        return f"{int(round(float(value))):,}"
    except Exception:
        return "0"


def fmt_pct(value):
    try:
        value = float(value)
        if value <= 1:
            value *= 100
        return f"{value:.1f}%"
    except Exception:
        return "0.0%"


def calc_change(current, previous):
    try:
        current = float(current)
        previous = float(previous)
        if previous == 0:
            return None
        return (current - previous) / previous
    except Exception:
        return None


def metric_delta(current, previous, suffix=""):
    change = calc_change(current, previous)
    if change is None:
        return None
    return f"{change * 100:+.1f}%{suffix}"


def infer_week_kpis(week):
    followers = read_public_sheet(week.get("followers", ""))
    visitors = read_public_sheet(week.get("visitors", ""))
    content = read_public_sheet(week.get("content", ""))
    competitors = read_public_sheet(week.get("competitors", ""))

    followers_start = first_col(followers, ["total followers", "followers"], ["organic", "sponsored"])
    followers_end = last_col(followers, ["total followers", "followers"], ["organic", "sponsored"])
    new_followers = sum_col(followers, ["new followers", "followers gained", "gained"], ["total"])
    if new_followers == 0 and followers_end and followers_start:
        new_followers = followers_end - followers_start

    page_views = sum_col(visitors, ["page views", "views"], ["unique"])
    unique_visitors = sum_col(visitors, ["unique visitors", "unique"], [])

    impressions = sum_col(content, ["impressions"], [])
    clicks = sum_col(content, ["clicks"], [])
    reactions = sum_col(content, ["reactions"], [])
    comments = sum_col(content, ["comments"], [])
    shares = sum_col(content, ["shares", "reposts"], [])
    posts = len(content) if not content.empty else 0

    engagement_total = clicks + reactions + comments + shares
    engagement_rate = (engagement_total / impressions) if impressions else 0

    return {
        "Week": week.get("label", ""),
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
        "Engagement Total": engagement_total,
        "Engagement Rate": engagement_rate,
        "Leads": 0,
        "followers_df": followers,
        "visitors_df": visitors,
        "content_df": content,
        "competitors_df": competitors,
    }


def make_content_table(content_df: pd.DataFrame, week_label: str) -> pd.DataFrame:
    if content_df.empty:
        return pd.DataFrame(columns=[
            "Week", "Post Topic", "Impressions", "Clicks", "Reactions", "Comments", "Shares", "Engagement Rate"
        ])

    df = content_df.copy()

    topic_col = (
        find_col(df, ["post title", "post", "content", "update title", "text", "share commentary"])
        or df.columns[0]
    )
    impressions_col = find_col(df, ["impressions"])
    clicks_col = find_col(df, ["clicks"])
    reactions_col = find_col(df, ["reactions"])
    comments_col = find_col(df, ["comments"])
    shares_col = find_col(df, ["shares", "reposts"])

    out = pd.DataFrame()
    out["Week"] = week_label
    out["Post Topic"] = df[topic_col].astype(str).str.slice(0, 80)

    for name, col in [
        ("Impressions", impressions_col),
        ("Clicks", clicks_col),
        ("Reactions", reactions_col),
        ("Comments", comments_col),
        ("Shares", shares_col),
    ]:
        out[name] = pd.to_numeric(df[col], errors="coerce").fillna(0) if col else 0

    out["Engagement Total"] = out[["Clicks", "Reactions", "Comments", "Shares"]].sum(axis=1)
    out["Engagement Rate"] = out["Engagement Total"] / out["Impressions"].replace(0, pd.NA)
    out["Engagement Rate"] = out["Engagement Rate"].fillna(0)

    return out.sort_values("Impressions", ascending=False)


def build_report_pdf(selected_week, week_row, totals, top_content):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleRed",
        parent=styles["Title"],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor(RED),
    )

    heading_style = ParagraphStyle(
        "HeadingDark",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=colors.HexColor(DARK),
    )

    body_style = ParagraphStyle(
        "BodySmall",
        parent=styles["BodyText"],
        fontSize=9,
        leading=13,
    )

    story = []
    story.append(Paragraph("PTAC Refurb LinkedIn Performance Report", title_style))
    story.append(Paragraph(f"Reporting Period: {selected_week}", heading_style))
    story.append(Spacer(1, 10))

    kpi_rows = [
        ["Metric", "This Week", "Total / Current"],
        ["Followers", fmt_int(week_row["Followers End"]), fmt_int(totals["Followers End"])],
        ["New Followers", fmt_int(week_row["New Followers"]), fmt_int(totals["New Followers"])],
        ["Page Views", fmt_int(week_row["Page Views"]), fmt_int(totals["Page Views"])],
        ["Impressions", fmt_int(week_row["Impressions"]), fmt_int(totals["Impressions"])],
        ["Clicks", fmt_int(week_row["Clicks"]), fmt_int(totals["Clicks"])],
        ["Reactions", fmt_int(week_row["Reactions"]), fmt_int(totals["Reactions"])],
        ["Comments", fmt_int(week_row["Comments"]), fmt_int(totals["Comments"])],
        ["Shares", fmt_int(week_row["Shares"]), fmt_int(totals["Shares"])],
    ]

    t = Table(kpi_rows, colWidths=[165, 140, 140])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(RED)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F7F7")]),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(t)
    story.append(Spacer(1, 14))

    story.append(Paragraph("Top Content", heading_style))
    if top_content.empty:
        story.append(Paragraph("No content performance data available for this week.", body_style))
    else:
        rows = [["Post Topic", "Impressions", "Clicks", "Reactions", "Eng. Rate"]]
        for _, r in top_content.head(5).iterrows():
            rows.append([
                str(r.get("Post Topic", ""))[:45],
                fmt_int(r.get("Impressions", 0)),
                fmt_int(r.get("Clicks", 0)),
                fmt_int(r.get("Reactions", 0)),
                fmt_pct(r.get("Engagement Rate", 0)),
            ])

        t2 = Table(rows, colWidths=[240, 70, 55, 65, 65])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(DARK)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t2)

    story.append(Spacer(1, 14))
    story.append(Paragraph("Executive Notes", heading_style))
    story.append(Paragraph(
        "Use this weekly report to compare LinkedIn activity, follower growth, content engagement, and audience interest over time. "
        "The strongest marketing insights will come from comparing weekly content themes against follower growth, page views, clicks, and leads.",
        body_style,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer


# -----------------------------
# App
# -----------------------------

def main():
    css()
    header()

    weeks = get_week_configs()

    with st.sidebar:
        st.markdown("## PTAC Refurb")
        st.caption("Weekly LinkedIn Analytics")
        st.markdown("---")

        if weeks:
            st.success(f"{len(weeks)} week(s) configured")
        else:
            st.error("No weeks configured")

        st.markdown("### Required weekly files")
        st.write("1. Followers")
        st.write("2. Visitors")
        st.write("3. Content")
        st.write("4. Competitors")

    if not weeks:
        st.markdown(
            """
            <div class="info-box">
            <b>No weekly Google Sheets are configured yet.</b><br><br>
            Add this to Streamlit Secrets:
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(
            """
[week_1]
label = "Week 1"
followers = "GOOGLE_SHEET_ID_OR_URL"
visitors = "GOOGLE_SHEET_ID_OR_URL"
content = "GOOGLE_SHEET_ID_OR_URL"
competitors = "GOOGLE_SHEET_ID_OR_URL"
            """,
            language="toml",
        )
        st.stop()

    with st.spinner("Reading weekly Google Sheets..."):
        week_rows = []
        content_rows = []

        for week in weeks:
            kpis = infer_week_kpis(week)
            content_table = make_content_table(kpis["content_df"], kpis["Week"])
            content_rows.append(content_table)

            row = {k: v for k, v in kpis.items() if not k.endswith("_df")}
            week_rows.append(row)

        weekly = pd.DataFrame(week_rows)
        content_all = pd.concat(content_rows, ignore_index=True) if content_rows else pd.DataFrame()

    st.markdown("<div class='section-title'>Report View</div>", unsafe_allow_html=True)

    selected_week = st.selectbox("Select week", weekly["Week"].tolist(), index=len(weekly) - 1)
    view_mode = st.radio("View", ["Weekly Summary", "Totals"], horizontal=True)

    week_row = weekly[weekly["Week"] == selected_week].iloc[0]
    selected_index = weekly[weekly["Week"] == selected_week].index[0]
    previous_row = weekly.iloc[selected_index - 1] if selected_index > 0 else None

    totals = {
        "Followers End": weekly["Followers End"].iloc[-1],
        "New Followers": weekly["New Followers"].sum(),
        "Page Views": weekly["Page Views"].sum(),
        "Unique Visitors": weekly["Unique Visitors"].sum(),
        "Impressions": weekly["Impressions"].sum(),
        "Clicks": weekly["Clicks"].sum(),
        "Reactions": weekly["Reactions"].sum(),
        "Comments": weekly["Comments"].sum(),
        "Shares": weekly["Shares"].sum(),
        "Posts": weekly["Posts"].sum(),
        "Engagement Total": weekly["Engagement Total"].sum(),
        "Leads": weekly["Leads"].sum(),
    }

    content_week = content_all[content_all["Week"] == selected_week].copy()
    content_week = content_week.sort_values("Impressions", ascending=False)

    if view_mode == "Weekly Summary":
        st.markdown("<div class='section-title'>Weekly KPI Snapshot</div>", unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Followers",
            fmt_int(week_row["Followers End"]),
            f"+{fmt_int(week_row['New Followers'])}",
        )
        c2.metric(
            "Impressions",
            fmt_int(week_row["Impressions"]),
            metric_delta(week_row["Impressions"], previous_row["Impressions"]) if previous_row is not None else None,
        )
        c3.metric(
            "Page Views",
            fmt_int(week_row["Page Views"]),
            metric_delta(week_row["Page Views"], previous_row["Page Views"]) if previous_row is not None else None,
        )
        c4.metric(
            "Posts",
            fmt_int(week_row["Posts"]),
        )

        c5, c6, c7, c8 = st.columns(4)
        c5.metric(
            "Clicks",
            fmt_int(week_row["Clicks"]),
            metric_delta(week_row["Clicks"], previous_row["Clicks"]) if previous_row is not None else None,
        )
        c6.metric(
            "Reactions",
            fmt_int(week_row["Reactions"]),
            metric_delta(week_row["Reactions"], previous_row["Reactions"]) if previous_row is not None else None,
        )
        c7.metric(
            "Comments",
            fmt_int(week_row["Comments"]),
            metric_delta(week_row["Comments"], previous_row["Comments"]) if previous_row is not None else None,
        )
        c8.metric(
            "Engagement Rate",
            fmt_pct(week_row["Engagement Rate"]),
            metric_delta(week_row["Engagement Rate"], previous_row["Engagement Rate"]) if previous_row is not None else None,
        )

        st.markdown("<div class='section-title'>Growth Metrics</div>", unsafe_allow_html=True)

        left, right = st.columns(2)
        with left:
            fig = px.line(weekly, x="Week", y="Followers End", markers=True, title="Follower Growth")
            fig.update_traces(line_color=RED, marker_color=RED)
            st.plotly_chart(fig, use_container_width=True)

        with right:
            fig = px.bar(weekly, x="Week", y="Impressions", title="Weekly Impressions")
            fig.update_traces(marker_color=RED)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='section-title'>Content Performance Summary</div>", unsafe_allow_html=True)

        if content_week.empty:
            st.info("No content data found for this week.")
        else:
            display = content_week[[
                "Post Topic",
                "Impressions",
                "Clicks",
                "Reactions",
                "Comments",
                "Shares",
                "Engagement Rate",
            ]].copy()
            display["Engagement Rate"] = display["Engagement Rate"].apply(fmt_pct)
            st.dataframe(display, use_container_width=True, hide_index=True)

            fig = px.bar(
                content_week.head(10),
                x="Post Topic",
                y="Impressions",
                title="Top Posts by Impressions",
            )
            fig.update_traces(marker_color=RED)
            fig.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.markdown("<div class='section-title'>Totals Since Tracking Started</div>", unsafe_allow_html=True)

        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Current Followers", fmt_int(totals["Followers End"]))
        t2.metric("Total New Followers", fmt_int(totals["New Followers"]))
        t3.metric("Total Impressions", fmt_int(totals["Impressions"]))
        t4.metric("Total Page Views", fmt_int(totals["Page Views"]))

        t5, t6, t7, t8 = st.columns(4)
        t5.metric("Total Clicks", fmt_int(totals["Clicks"]))
        t6.metric("Total Reactions", fmt_int(totals["Reactions"]))
        t7.metric("Total Comments", fmt_int(totals["Comments"]))
        t8.metric("Total Shares", fmt_int(totals["Shares"]))

        st.markdown("<div class='section-title'>Trend Dashboard</div>", unsafe_allow_html=True)

        left, right = st.columns(2)
        with left:
            fig = px.line(weekly, x="Week", y=["Followers End", "New Followers"], markers=True, title="Follower Trend")
            st.plotly_chart(fig, use_container_width=True)

        with right:
            fig = px.line(weekly, x="Week", y=["Impressions", "Clicks", "Reactions"], markers=True, title="Engagement Trend")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("<div class='section-title'>All Content Performance</div>", unsafe_allow_html=True)
        if not content_all.empty:
            display = content_all.copy()
            display["Engagement Rate"] = display["Engagement Rate"].apply(fmt_pct)
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("<div class='section-title'>Executive Export</div>", unsafe_allow_html=True)

    pdf = build_report_pdf(selected_week, week_row, totals, content_week)
    st.download_button(
        "Download boss-ready PDF report",
        data=pdf,
        file_name=f"PTAC_Refurb_LinkedIn_Report_{selected_week.replace(' ', '_')}.pdf",
        mime="application/pdf",
    )

    st.download_button(
        "Download combined weekly data CSV",
        data=weekly.to_csv(index=False).encode("utf-8"),
        file_name="PTAC_Refurb_Combined_Weekly_Data.csv",
        mime="text/csv",
    )

    st.markdown(
        """
        <div class="footer">
        Data updates automatically when you add the next week's four Google Sheet IDs to Streamlit Secrets and reboot/refresh the app.
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
