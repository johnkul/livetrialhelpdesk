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
- **Filtered Records** and new drill-down records are read-only. Built-in CSV/clipboard export is disabled in code and `.streamlit/config.toml`; existing password-authorised explicit downloads remain available. On-screen content can still be captured, so this is a UI restriction, not a replacement for authentication and the public-column allowlist.
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
- **Sync latest Kobo data** bypasses the cache immediately. It replaces the current snapshot only after a successful fetch and transformation; failures retain the last successful version.
- A background check runs every 1,800 seconds while a browser session is active. Additions, edits and deletions produce an **Apply update** notice, not an automatic full-page rerun.
- Each session pins all related tables to the same snapshot until the user applies an update or explicitly synchronizes. Dates and location filters are retained. Chart/table selections reset when their underlying snapshot or report context changes, preventing stale row positions from identifying a different record.
- A failed check shows a controlled warning without exposing API responses or credentials.
- The API loader follows every pagination link, so it is not limited to the first page.
- Unchanged Kobo data never interrupts the current dashboard flow.

This is a 30-minute change-checking dashboard, not instantaneous streaming. A separate receiving service/data store would be needed for faster push ingestion. Kobo REST Services sends newly created submissions but not edits, so that future architecture must also reconcile edits and deletions periodically. No receiving service is provisioned by this upgrade.

## Interactive reporting (September 2026)

- Click a chart category, slice or monthly point, or select a summary-table row, to open linked **Age & gender**, **Referrals**, **Locations**, **Submission trend**, and **Records** panels. Main report totals remain unchanged. Drill-down records are deduplicated by stable submission ID; they are not unique-beneficiary counts.
- Referral details count distinct submission/partner pairs. One submission may include multiple partners. CPV charts represent submission volume, not service quality.
- Use **Table options** to search a summary or switch to a page-width **Wrapped reading view** for long descriptions. Interactive grids support sorting, resizing and native column controls. Row selection is disabled in the wrapped reading view.
- **Clear selection** clears exploration; **Reset view** also resets report filters and navigation. Selection keys are invalidated when search results, chart contents or the underlying report context change.
- **All dates**, **Today**, **This week** (Monday onward), **This month**, **Last 30 days**, and **Custom** are available. Presets use the East Africa calendar and recalculate on a full interaction or applied update. Custom dates stay fixed. Empty periods are not silently shortened to match available data.
- The Overview includes an expandable comparison against the preceding equal-length calendar period, using the same location filters. A warning identifies incomplete historical coverage. Zero baselines do not produce infinite percentage changes.
- The DQA quick check links issues to non-PII audit records across all source submissions, including exclusions. CPV names outside the existing harmonization map are flagged for review, not automatically merged or classified as incorrect.

### Update the deployed app

Replace `helpdesklive.py` and `requirements.txt`, and add `.streamlit/config.toml` (merge its `[client]` setting if a config already exists). This upgrade is tested with Streamlit 1.63 and requires `streamlit>=1.63,<1.64` for the export control and current interactive-table APIs. Keep the existing assets, data files and real secrets unchanged. It does not require new secrets.

Run `python -m unittest discover -s tests -v` after installing requirements. The interaction tests use synthetic data and stub the source loader and authentication; they never call Kobo or load a real beneficiary workbook. Live authentication and API permissions must still be verified in the deployment.

### Python 3.14 startup compatibility

Use the updated `requirements.txt`, which requires Altair 6 and `typing_extensions>=4.15`. Altair 5.5 can fail at import on Python 3.14 in `StepKwds(TypedDict, closed=True, ...)`; this is fixed in [Altair 6](https://github.com/vega/altair/releases/tag/v6.0.0). Updating only `helpdesklive.py` or only `typing_extensions` does not resolve the Altair 5 import path.

Verified locally on Windows with Python 3.14.7, Altair 6.2.2, Streamlit 1.63.0 and pandas 2.3.3: all 22 synthetic-data regression tests pass, compilation succeeds and `pip check` reports no dependency conflicts. These checks do not connect to the live Kobo database or deploy the app.

For Streamlit Community Cloud, commit the updated `requirements.txt` beside `helpdesklive.py` and let dependency installation finish. If the app still uses the old environment, reboot it from **Manage app**. No Python downgrade or new secrets are needed for this fix. See [Streamlit's dependency update guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-streamlit). If another dependency file such as `uv.lock` or `Pipfile` controls your deployment, update that file too; Community Cloud uses only the first supported dependency file it finds.

## Further production enhancements

1. If the organisation later adopts a managed identity provider, map groups or application roles to separate Viewer, Operations/MEAL and DQA Administrator permissions.
2. Add audit logging for protected-table unlocks and downloads without recording beneficiary content.
3. Move protected PII workflows into a separate restricted application or case-management system.
4. When volume grows, stage incrementally using `_submission_time`, `_id`, and `_uuid` rather than re-downloading the full asset on every refresh.
5. Generate and maintain a tested deployment lockfile during the release process in addition to the constrained production requirements.

Official references: [KoboToolbox API](https://support.kobotoolbox.org/api.html), [Kobo API tokens](https://support.kobotoolbox.org/managing_api_tokens.html), [Streamlit OIDC authentication](https://docs.streamlit.io/develop/concepts/connections/authentication), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), and [Requests retry adapters](https://docs.python-requests.org/en/stable/user/advanced/).