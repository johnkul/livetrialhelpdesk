# Tdh Kenya Helpdesk Dashboard - KoboToolbox live integration

This package keeps the existing Helpdesk dashboard and replaces the normal Excel source with the KoboToolbox KPI v2 API. If Kobo credentials are absent, the original workbook path remains available as a local fallback.

## Configure

1. Open the visible `secrets.toml.example` template in the package root, add your settings, and save/copy it as `.streamlit/secrets.toml`.
2. Set `KOBO_BASE_URL` to the server host only, such as `https://eu.kobotoolbox.org`.
3. Set `KOBO_ASSET_UID` to the Helpdesk form asset UID (the `a...` identifier after `#/forms/` in the Kobo page URL).
4. Create/copy a private API token from the Kobo account that can view this project and set `KOBO_TOKEN`.
5. For production, configure Google OIDC in the `[auth]` and `[auth.google]` sections, set `AUTH_REQUIRED = true`, and list every permitted personal Google address in `AUTH_ALLOWED_EMAILS`.
6. Install dependencies and run:

```powershell
python -m pip install -r requirements.txt
streamlit run helpdesklive.py
```

The token is read from Streamlit secrets or environment variables and is never shown in the UI.

For local development without an identity provider, set `AUTH_REQUIRED = false`. Do not use that setting for an internet-accessible production deployment. The real `.streamlit/secrets.toml` is excluded by the package `.gitignore` and must never be committed.

## Production safety controls

- Normal dashboard views are generated from `PUBLIC_RECORD_COLUMNS`, an explicit fail-closed allowlist. A newly added Kobo column is private by default and cannot automatically appear in the Records view or its data flow.
- **Filtered Records** is read-only and has no standard CSV download.
- The separate non-PII DQA stream is captured before consent and completeness exclusions. It reconciles all source submissions to dashboard-eligible or excluded records and records the exclusion reason.
- Public dashboard record IDs are stable pseudonymous SHA-256-derived identifiers based on Kobo `_uuid`, with `_id` as the secondary source. Local workbooks use a clearly marked row-based fallback.
- Kobo form-schema and submission requests retry bounded transient failures (`429`, `500`, `502`, `503`, and `504`) with exponential backoff and `Retry-After` support. Authentication failures are still reported immediately.
- When enabled, Streamlit Google OIDC authentication runs before Kobo data is fetched. Personal Google accounts are authorised through an explicit email allowlist, while the existing PII workflow remains separately password-protected.

## How the field contract prevents shifting

- The app maps fields by raw survey label, transformed name, XML name, or full group/XML path—not by ordinal column position.
- Kobo's combined geopoint field labelled **GPS / GPS Location** is split automatically into `gps_latitude` and `gps_longitude`; older Excel exports with separate `_GPS Location_latitude` and `_GPS Location_longitude` columns remain supported.
- The Helpdesk Locations Map supports hover summaries and single-point click selection. Map points identify the harmonized CPV name(s) that submitted the records; beneficiary PII is not included in map payloads or tooltips.
- All 98 fields in the supplied `Column Mapping` sheet are embedded as an immutable analysis contract.
- Kobo select-multiple codes are expanded back into the existing `0/1` `concern_*`, `info_*`, and `ref_partner_*` columns.
- New Kobo attributes are retained as unmapped diagnostics and cannot displace an established field.
- `KOBO_COLUMN_MAP` provides an explicit override if a question label is renamed in Kobo.

After changing the deployed form, open **Live data & schema status**. Review “Unmapped new/source attributes” and “Contract fields absent from source” before adding the new field to analysis.

## Refresh and performance

- The dashboard date range and monthly trend use Kobo `_submission_time` converted to East Africa Time, so delayed offline uploads enter the reporting period when Kobo actually receives them. Kobo `today` is the first fallback and `Enter a date` is retained as the final legacy fallback and as the original activity/interview date.
- API downloads and fully transformed DataFrames use a 1,800-second (30-minute) refresh window shared across users.
- **Sync latest Kobo data** bypasses the cache immediately.
- A silent background check runs every 1,800 seconds, but the page reruns only when a Kobo submission is added, edited, or deleted.
- The API loader follows every pagination link, so it is not limited to the first page.
- Unchanged Kobo data never interrupts the current dashboard flow.

Kobo is a pull API, so this is near-live rather than a permanent streaming connection. For sub-minute updates or much larger volumes, use a Kobo webhook or scheduled incremental process to stage submissions in PostgreSQL, then point the dashboard at indexed database views.

## Further production enhancements

1. If the organisation later adopts a managed identity provider, map groups or application roles to separate Viewer, Operations/MEAL and DQA Administrator permissions.
2. Add audit logging for protected-table unlocks and downloads without recording beneficiary content.
3. Move protected PII workflows into a separate restricted application or case-management system.
4. When volume grows, stage incrementally using `_submission_time`, `_id`, and `_uuid` rather than re-downloading the full asset on every refresh.
5. Generate and maintain a tested deployment lockfile during the release process in addition to the constrained production requirements.

Official references: [KoboToolbox API](https://support.kobotoolbox.org/api.html), [Kobo API tokens](https://support.kobotoolbox.org/managing_api_tokens.html), [Streamlit OIDC authentication](https://docs.streamlit.io/develop/concepts/connections/authentication), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), and [Requests retry adapters](https://docs.python-requests.org/en/stable/user/advanced/).
