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

- Click a chart category, slice or monthly point, or select a summary-table row, to open a compact selection summary. Choose **View breakdown** for Age & gender, Referrals, Locations or Submission trend, or **View matching records**. Only the requested detail is built. Main report totals remain unchanged. Drill-down records are deduplicated by stable submission ID; they are not unique-beneficiary counts.
- Referral details count distinct submission/partner pairs. One submission may include multiple partners. CPV charts represent submission volume, not service quality.
- Summary search is always visible. **Table display** offers Compact, Comfortable and Wrapped layouts; long descriptions default to Wrapped. Interactive grids support sorting and resizing. **Open row details** provides a searchable keyboard-accessible selector, including in Wrapped mode. **Explore chart** offers the equivalent keyboard path for chart categories. A new grid/chart click takes precedence over an earlier keyboard choice.
- **Records** starts with eight essential columns with friendly labels. Demographics, Follow-up and Custom presets let viewers choose more. Search and deterministic sorting apply to the entire approved dataset before pagination; there is no 1,000-record preview cutoff. Choose 25, 50 or 100 rows per page. Record browsing and chart/detail exploration use local fragments to avoid rebuilding unrelated report sections.
- Service-map clicks and table selections resolve by a stable exact-coordinate point ID, not a helpdesk label. A helpdesk with multiple points cannot silently broaden the selected records; multiple helpdesks at the same coordinates remain grouped consistently. Stale point IDs return no records.
- Overview opens with four headline measures, submission trend and request mix. Visits, Demographics, Locations and Disability breakdowns are available through **Overview detail**; request tables and prior-period comparison remain optional.
- Collapsed findings and prior-period comparisons do no analysis until opened. Selection summaries identify submitting CPVs, helpdesks and submission dates before a viewer opens a breakdown or matching records.
- Map detail matching applies coordinates before deduplication, preventing an inconsistent duplicate ID from substituting a row from another point. Duplicate IDs remain an issue to investigate in Data Quality.
- Neutral cards, less decorative weight, visible keyboard focus and narrow-screen stacking improve readability. Small-count ranking messages no longer promise privacy suppression: aggregate tables are not a universal small-cell disclosure-control system. Keep authentication and the public-column allowlist in place.
- **Clear selection** resets only its own chart or table; other selections and report totals stay unchanged. **Reset filters** resets reporting dates, locations and exploration while keeping the current dashboard section. Selection keys are invalidated when search results, chart contents or the underlying report context change.
- **All dates**, **Today**, **This week** (Monday onward), **This month**, **Last 30 days**, and **Custom** are available. Presets use the East Africa calendar and recalculate on a full interaction or applied update. Custom dates stay fixed. Empty periods are not silently shortened to match available data.
- The Overview includes an expandable comparison against the preceding equal-length calendar period, using the same location filters. A warning identifies incomplete historical coverage. Zero baselines do not produce infinite percentage changes.
- The DQA quick check links issues to audit records across all source submissions, including exclusions. CPV matching status flags missing, ambiguous and unmatched names; original-name audit details and approval controls are restricted to the protected CPV Work section.

### Roster-based CPV name matching

Deploy **all three files together**: `helpdesklive.py`, `cpv_matching.py` and `cpv_name_registry.json`, in the same directory. No new dependency or secret is needed. Keep your real Kobo/authentication secrets, stylesheet and 1,800-second refresh setting unchanged.

The established aliases in the application remain authoritative. The registry adds full names supplied in the staff list that were missing from the existing map; it is a maintained reference list, not a list inferred from incoming records. Review this seed roster against your official staff register. Ambiguous or unmatched entries do not become roster members automatically.

Matching runs locally, before filters, aggregations and map preparation. It uses Python's standard-library text comparison, so staff names are not sent to an external AI service. Rules are deterministic:

1. Confirmed aliases and canonical names take precedence.
2. Exact reordered/respaced names and partial names match only when they identify one distinct roster person.
3. Fuzzy full-name matches require a similarity score of at least 0.90, token-level checks (or a strong joined-name match), and a margin of at least 0.12 over the next candidate. These are conservative heuristic thresholds, not calibrated probabilities of identity.
4. Short misspellings, competing candidates and unsupported entries remain unchanged for review. For example, `David` cannot automatically choose between David Otifo and Safari David; `Peter` has multiple roster candidates. A confirmed alias resolves that ambiguity once.
5. Automatic predictions never become approved aliases. Record-level raw names, matching reasons, scores and suggestions remain on the secure frame. Public tables/charts use the resolved name; unresolved display names remain visible without creating a roster entry. The protected audit includes counts from incomplete/excluded submissions as well as eligible ones.

Open **CPV Work → CPV name matching · review and approve** and unlock with the existing `DQA_PII_PASSWORD`. Search the audit or select **All matching decisions** to inspect automatic corrections. For a correction, select the original entry and the confirmed main name, verify the identity checkbox, then choose **Prepare approved alias**.

**Prepared approvals do not change the active dashboard.** Download the approved registry, replace `cpv_name_registry.json` in the deployed repository and redeploy. The registry fingerprint invalidates processed caches and pinned snapshots so the new rules apply across tables, charts, filters and maps. Keep this file in version control: browser drafts and Streamlit's local filesystem are not reliable cross-user durable storage. Predictions are excluded from the exported aliases. You can remove an unexported draft from the review section. Changing an already confirmed mapping requires deliberate review of the deployed registry/code; the UI will not silently override it.

The registry export contains staff names but no beneficiary records; restrict repository and review access appropriately. The password gate is an additional UI restriction, not a replacement for hosting-level authentication. Neither matching nor approval changes the original Kobo submissions.

For future data collection, replace the Kobo free-text CPV question with a searchable **Select One** roster, using a permanent staff ID as each choice's stored `name` and the official full name as its `label`. Do not regenerate or recycle IDs when a label changes. The form owner must review and publish this change, including compatibility with existing records and offline devices. This delivery does not modify or redeploy the Kobo form. See [Kobo choice-list documentation](https://support.kobotoolbox.org/option_choices_xls.html).

### Simplified Dashboard Controls

- Navigation, reporting period, Camp, Helpdesk and Reset filters appear first. Help, synchronization, technical status and account controls sit below the filters. Synchronization still checks at 1,800 seconds and never forces a full-page update when new data arrives.
- From/To calendars appear only for Custom. Other presets show their dates in one compact line.
- Camp and Helpdesk are searchable multiselects. Helpdesks can be selected directly without choosing a camp; choosing a camp narrows the available helpdesks. Clearing the camp preserves valid helpdesk selections. Incompatible helpdesks are cleared with an explanation.
- Location choices span the current data snapshot, not just the reporting period, so an empty period cannot silently broaden a location filter.
- Every report section shows its dates, full selected locations and matching submission count above the results, including empty results. The DQA context explicitly states that its source audit includes all submissions, while report filters still apply to protected follow-up tables.
- Selected chart/table details stay next to their source and are labelled **Details for ...**. Their local Clear selection button does not clear a different chart/table.

### Update the deployed app

Replace `helpdesklive.py` and `assets/styles.css` for the version 1.2 UI/UX improvements. Keep the corrected `requirements.txt` (Altair 6), and retain `.streamlit/config.toml` (merge its `[client]` setting if a config already exists). This upgrade is tested with Streamlit 1.63 and requires `streamlit>=1.63,<1.64` for the export control and current interactive-table APIs. Keep the other assets, data files and real secrets unchanged. It does not require new secrets.

Run `python -m unittest discover -s tests -v` after installing requirements. The interaction tests use synthetic data and stub the source loader and authentication; they never call Kobo or load a real beneficiary workbook. Live authentication and API permissions must still be verified in the deployment.

### Python 3.14 startup compatibility

Use the updated `requirements.txt`, which requires Altair 6 and `typing_extensions>=4.15`. Altair 5.5 can fail at import on Python 3.14 in `StepKwds(TypedDict, closed=True, ...)`; this is fixed in [Altair 6](https://github.com/vega/altair/releases/tag/v6.0.0). Updating only `helpdesklive.py` or only `typing_extensions` does not resolve the Altair 5 import path.

Validation uses Windows with Python 3.14.7, Altair 6.2.2, Streamlit 1.63.0 and pandas 2.3.3. The synthetic-data regression suite covers controls, exact map matching (including conflicting duplicate IDs), all Overview modes, local-selection resets, full-dataset pagination and on-demand findings/comparisons. The desktop and 390-pixel-wide layouts were checked with synthetic data during the version 1.2 draft. These checks do not connect to the live Kobo database, benchmark live-data latency, certify full accessibility compliance or deploy the app.

For Streamlit Community Cloud, commit the updated `requirements.txt` beside `helpdesklive.py` and let dependency installation finish. If the app still uses the old environment, reboot it from **Manage app**. No Python downgrade or new secrets are needed for this fix. See [Streamlit's dependency update guidance](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-streamlit). If another dependency file such as `uv.lock` or `Pipfile` controls your deployment, update that file too; Community Cloud uses only the first supported dependency file it finds.

## Further production enhancements

1. If the organisation later adopts a managed identity provider, map groups or application roles to separate Viewer, Operations/MEAL and DQA Administrator permissions.
2. Add audit logging for protected-table unlocks and downloads without recording beneficiary content.
3. Move protected PII workflows into a separate restricted application or case-management system.
4. When volume grows, stage incrementally using `_submission_time`, `_id`, and `_uuid` rather than re-downloading the full asset on every refresh.
5. Generate and maintain a tested deployment lockfile during the release process in addition to the constrained production requirements.

Official references: [KoboToolbox API](https://support.kobotoolbox.org/api.html), [Kobo API tokens](https://support.kobotoolbox.org/managing_api_tokens.html), [Streamlit OIDC authentication](https://docs.streamlit.io/develop/concepts/connections/authentication), [Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect), and [Requests retry adapters](https://docs.python-requests.org/en/stable/user/advanced/).
