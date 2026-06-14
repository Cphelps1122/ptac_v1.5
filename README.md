# PTAC Refurb Visual LinkedIn Dashboard

Main file path:

dashboard/app.py

## Correct Streamlit Secrets

Use this. The app auto-detects which sheet is followers, visitors, content, and competitors, so this avoids the wrong-order problem.

```toml
[week_1]
label = "June 9 - June 15, 2026"
sheet_1 = "1NYwZOGeNBLB0P6C-x9TYoI9HuDEuxuCm"
sheet_2 = "11zCP2ksfcpC9xlAn5MIS_miqalwVxDSs"
sheet_3 = "1kXmfr1Ot74TexLTBeLMqRJKAg9js4IUe"
sheet_4 = "1rjsmobT-srby4JAVz2Oa0qZ69RwREa7J"
```

Each week, add another block:

```toml
[week_2]
label = "June 16 - June 22, 2026"
sheet_1 = "NEW_SHEET_ID_OR_URL"
sheet_2 = "NEW_SHEET_ID_OR_URL"
sheet_3 = "NEW_SHEET_ID_OR_URL"
sheet_4 = "NEW_SHEET_ID_OR_URL"
```

Each Google Sheet must be shared as:
Anyone with the link -> Viewer
