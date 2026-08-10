# Tdh Kenya Helpdesk Dashboard — KoboToolbox live integration

This package keeps the existing Helpdesk dashboard and replaces the normal Excel source with the KoboToolbox KPI v2 API. If Kobo credentials are absent, the original workbook path remains available as a local fallback.

## Configure

1. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
2. Set `KOBO_BASE_URL` to the server host only, such as `https://eu.kobotoolbox.org`.
3. Set `KOBO_ASSET_UID` to the Helpdesk form asset UID (the `a...` identifier after `#/forms/` in the Kobo page URL).
4. Create/copy a private API token from the Kobo account that can view this project and set `KOBO_TOKEN`.
5. Install dependencies and run:

```powershell
python -m pip install -r requirements.txt
streamlit run helpdesklive.py
```

The token is read from Streamlit secrets or environment variables and is never shown in the UI.

## How the field contract prevents shifting

- The app maps fields by raw survey label, transformed name, XML name, or full group/XML path—not by ordinal column position.
- Kobo's combined geopoint field labelled **GPS / GPS Location** is split automatically into `gps_latitude` and `gps_longitude`; older Excel exports with separate `_GPS Location_latitude` and `_GPS Location_longitude` columns remain supported.
- The Helpdesk Locations Map supports hover summaries and single-point click selection. Selected points show aggregated operational details only; beneficiary PII is not included in map payloads or tooltips.
- All 98 fields in the supplied `Column Mapping` sheet are embedded as an immutable analysis contract.
- Kobo select-multiple codes are expanded back into the existing `0/1` `concern_*`, `info_*`, and `ref_partner_*` columns.
- New Kobo attributes are retained as unmapped diagnostics and cannot displace an established field.
- `KOBO_COLUMN_MAP` provides an explicit override if a question label is renamed in Kobo.

After changing the deployed form, open **Live data & schema status**. Review “Unmapped new/source attributes” and “Contract fields absent from source” before adding the new field to analysis.

## Refresh and performance

- API downloads and fully transformed DataFrames are cached for 60 seconds and shared across users.
- **Sync latest Kobo data** bypasses the cache immediately.
- A silent background check runs every minute, but the page reruns only when a Kobo submission is added, edited, or deleted.
- The API loader follows every pagination link, so it is not limited to the first page.
- Unchanged Kobo data never interrupts the current dashboard flow.

Kobo is a pull API, so this is near-live rather than a permanent streaming connection. For sub-minute updates or much larger volumes, use a Kobo webhook or scheduled incremental process to stage submissions in PostgreSQL, then point the dashboard at indexed database views.

## Recommended production enhancements

1. Add hosting-level authentication (Microsoft Entra ID/Google OIDC) and role-based access; do not expose child-level or PII data publicly.
2. Add a “new submissions since last refresh” KPI based on `_submission_time` and a visible last-fetch timestamp.
3. Add alerts for missing interview date, camp/helpdesk location, gender/age, duplicated UUIDs, and unresolved schema fields.
4. Store only aggregate or non-PII data in shared download features; keep row-level PII behind a separate authorised workflow.
5. When volume grows, stage incrementally using `_submission_time`, `_id`, and `_uuid` rather than re-downloading the full asset on every refresh.

Official references: [KoboToolbox API](https://support.kobotoolbox.org/api.html) and [API tokens](https://support.kobotoolbox.org/managing_api_tokens.html).
