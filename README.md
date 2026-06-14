# PTAC Refurb Weekly LinkedIn Dashboard

This is the correct setup for your weekly LinkedIn analytics workflow.

Each week has 4 Google Sheets:
1. Followers
2. Visitors
3. Content
4. Competitors

Streamlit reads each weekly group, combines the data, and shows:
- Weekly KPI cards
- Growth metrics
- Content performance summary
- Totals since tracking started
- Boss-ready PDF export

## Main Streamlit file path

```text
dashboard/app.py
```

## Streamlit Secrets Setup

In Streamlit Cloud > App > Settings > Secrets, use this structure:

```toml
[week_1]
label = "Week 1"
followers = "1NYwZOGeNBLB0P6C-x9TYoI9HuDEuxuCm"
visitors = "11zCP2ksfcpC9xlAn5MIS_miqalwVxDSs"
content = "1kXmfr1Ot74TexLTBeLMqRJKAg9js4IUe"
competitors = "1rjsmobT-srby4JAVz2Oa0qZ69RwREa7J"

[week_2]
label = "Week 2"
followers = "PASTE_WEEK_2_FOLLOWERS_SHEET_ID"
visitors = "PASTE_WEEK_2_VISITORS_SHEET_ID"
content = "PASTE_WEEK_2_CONTENT_SHEET_ID"
competitors = "PASTE_WEEK_2_COMPETITORS_SHEET_ID"
```

You can paste either:
- the Google Sheet ID only, OR
- the full Google Sheet link.

The app will pull the ID automatically.

## Google Sheet Sharing

Each weekly Google Sheet must be:

```text
Anyone with the link -> Viewer
```

## Weekly Workflow

1. Export LinkedIn analytics.
2. Upload/open each export as a Google Sheet.
3. Set each Google Sheet to Anyone with the link -> Viewer.
4. Add the 4 sheet IDs to Streamlit Secrets under a new week block.
5. Reboot/refresh Streamlit.
6. Download the PDF report.

## Notes

No Apps Script.
No Google Cloud.
No service account.
No tokens.

This is read-only and designed to avoid the Apps Script issues.
