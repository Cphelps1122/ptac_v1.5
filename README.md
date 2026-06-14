# PTAC Refurb Visual LinkedIn Dashboard v2

This version fixes inaccurate data pulling from LinkedIn exports by:
- scanning the Google Sheet for the real header row
- handling LinkedIn metadata rows
- auto-detecting Followers / Visitors / Content / Competitor sheets
- calculating new followers from New Followers OR Organic + Sponsored Followers OR Total Followers difference
- adding a debug data check section

## Main file path

dashboard/app.py

## Streamlit Secrets

Use this format:

```toml
[week_1]
label = "June 9 - June 15, 2026"
sheet_1 = "1NYwZOGeNBLB0P6C-x9TYoI9HuDEuxuCm"
sheet_2 = "11zCP2ksfcpC9xlAn5MIS_miqalwVxDSs"
sheet_3 = "1kXmfr1Ot74TexLTBeLMqRJKAg9js4IUe"
sheet_4 = "1rjsmobT-srby4JAVz2Oa0qZ69RwREa7J"
leads = 0
```

Every week, add a new block:

```toml
[week_2]
label = "June 16 - June 22, 2026"
sheet_1 = "NEW_GOOGLE_SHEET_ID_OR_URL"
sheet_2 = "NEW_GOOGLE_SHEET_ID_OR_URL"
sheet_3 = "NEW_GOOGLE_SHEET_ID_OR_URL"
sheet_4 = "NEW_GOOGLE_SHEET_ID_OR_URL"
leads = 0
```

Each Google Sheet must be shared as:

Anyone with the link -> Viewer
