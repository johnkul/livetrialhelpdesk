"""Conservative, local beneficiary linkage. No source edits or shared PII cache.

Rule-based groups are estimates, not verified identities. Ambiguity fails closed.
The full eligible snapshot determines identity; selected rows determine the output.
"""
from collections import defaultdict
from itertools import combinations
import re
import unicodedata

import pandas as pd

from protected_exports import beneficiary_register, register_gender, register_profile


MISSING = {"", "nan", "none", "nat", "na", "n/a", "<na>", "missing", "not recorded",
           "not provided", "unknown", "not applicable", "null", "nil", "-", "not available",
           "not known", "unspecified", "n.a.", "not given", "prefer not to say", "don't know"}
AUDIT_COLUMNS = ["Group in this view", "Child / Beneficiary Name", "Individual number",
                 "Matching basis", "Review notes", "Entries in selected filters",
                 "Observed submission count", "Additional submissions after first",
                 "First recorded entry", "Latest recorded entry",
                 "Original age categories", "Reported visit history", "Source record references"]


def text(value):
    if value is None or pd.isna(value):
        return ""
    value = unicodedata.normalize("NFKC", str(value)).strip()
    return "" if value.casefold().strip("[] ") in MISSING else value


def normalized(value):
    return " ".join(re.sub(r"[^\w\s]", " ", text(value).casefold()).replace("_", " ").split())


def identifier(value):
    # Keep significant leading zeroes; never fuzzy-match individual numbers.
    value = re.sub(r"[\s\-/]", "", text(value)).casefold()
    return "" if not value or value == "no" or set(value) == {"0"} else value


def phone(value):
    value = text(value)
    if not value or re.search(r"[^\d\s()+.\-]", value):
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("00"):
        digits = digits[2:]
    # Only Kenyan mobile prefixes are canonicalised; foreign numbers are not guessed.
    if re.fullmatch(r"0[17]\d{8}", digits):
        digits = "254" + digits[1:]
    return digits if 7 <= len(digits) <= 15 and len(set(digits)) > 1 else ""


def source_age(value):
    """Normalise spelling only. Never use the dashboard age crosswalk."""
    value = text(value).casefold().replace("–", "-").replace("—", "-")
    value = re.sub(r"\b(years?|yrs?)\b", "", value)
    value = re.sub(r"\s+", "", value)
    return value.replace("andabove", "+").replace("and_above", "+")


def features(row):
    name = " ".join(sorted(normalized(row.get("information_seeker_name")).split()))
    gender = text(row.get("information_seeker_gender_raw")) or text(row.get("information_seeker_gender"))
    nationality = text(row.get("information_seeker_nationality"))
    if normalized(nationality) in {"", "other", "others", "other nationality", "other not listed", "not listed"}:
        nationality = text(row.get("information_seeker_nationality_other"))
    return {
        "name": name,
        "id": identifier(row.get("information_seeker_individual_number")),
        "gender": normalized(register_gender(gender)),
        "age": source_age(row.get("information_seeker_age")),
        "nationality": normalized(nationality),
        "profile": normalized(register_profile(row.get("household_type"))),
        "phone": phone(row.get("information_seeker_phone")),
        "alternative": phone(row.get("alternative_phone")),
        "home": normalized(row.get("residence_neighborhood_compound_house")),
        "camp": normalized(row.get("camp_location")),
    }


def consistent(items):
    return all(len({row[field] for row in items if row[field]}) <= 1
               for field in ("id", "name", "gender", "age", "nationality", "profile"))


def composite_match(left, right):
    # A full name, sex and *source* age category are mandatory without shared ID.
    if len(left["name"].split()) < 2 or not consistent([left, right]):
        return False
    if not all(left[field] and left[field] == right[field] for field in ("name", "gender", "age", "camp")):
        return False
    same_home = bool(left["home"] and left["home"] == right["home"])
    same_nationality = bool(left["nationality"] and left["nationality"] == right["nationality"])
    primary = bool(left["phone"] and left["phone"] == right["phone"])
    left_phones = {left["phone"], left["alternative"]} - {""}
    right_phones = {right["phone"], right["alternative"]} - {""}
    # Household/alternative phones need a recorded residence as extra corroboration.
    return (primary and (same_home or same_nationality)) or (bool(left_phones & right_phones) and same_home)


def unique_beneficiary_register(frame, age_mapper, selected_positions=None):
    """Return (same-column register, protected evidence table, aggregate summary).

    No probability is claimed. Latest *whole* filtered entry represents a group;
    missing values are not filled from another entry to avoid constructing a person.
    """
    source = frame.reset_index(drop=True).copy()
    if "information_seeker_name" not in source:
        source["information_seeker_name"] = pd.NA
    selected = set(range(len(source))) if selected_positions is None else set(selected_positions)
    if not selected.issubset(set(range(len(source)))):
        raise ValueError("Invalid selected row positions")
    rows = source.to_dict("records")
    facts = [features(row) for row in rows]
    notes = [set() for _ in rows]
    groups = []
    bases = []
    blocked = set()
    id_buckets = defaultdict(list)
    for index, fact in enumerate(facts):
        if fact["id"]:
            id_buckets[fact["id"]].append(index)
    assigned = set()
    for members in id_buckets.values():
        if len(members) < 2:
            continue
        items = [facts[i] for i in members]
        # Same ID + same normalised name + at least one fully recorded demographic.
        corroborated = all(f["name"] for f in items) and any(all(f[k] for f in items) for k in ("gender", "age"))
        if consistent(items) and corroborated:
            groups.append(members)
            bases.append("Individual number + name + demographic corroboration")
            assigned.update(members)
        else:
            blocked.update(members)
            for i in members:
                notes[i].add("Shared individual number has conflicting or insufficient identity evidence; kept separate")
    for i in range(len(rows)):
        if i not in assigned:
            groups.append([i])
            fact = facts[i]
            well_recorded = fact["id"] and len(fact["name"].split()) >= 2 and fact["gender"] and fact["age"]
            bases.append("Single entry with recorded individual number and demographics" if well_recorded
                         else "Unlinked entry — insufficient corroboration")

    # Block candidate comparisons by exact full name, gender and source age.
    # Large/common blocks are held for review rather than quadratic fuzzy searches.
    owner = {i: g for g, members in enumerate(groups) for i in members}
    buckets = defaultdict(set)
    for i, fact in enumerate(facts):
        if i not in blocked and len(fact["name"].split()) >= 2 and fact["gender"] and fact["age"]:
            buckets[(fact["name"], fact["gender"], fact["age"])].add(owner[i])
    edges = defaultdict(set)
    for candidates in buckets.values():
        if len(candidates) > 150:
            for g in candidates:
                for i in groups[g]:
                    notes[i].add("Common-name comparison limit reached; review needed")
            continue
        for a, b in combinations(sorted(candidates), 2):
            if len(groups[a]) * len(groups[b]) > 20000:
                for i in groups[a] + groups[b]:
                    notes[i].add("Large comparison held for review")
                continue
            # Every cross-group pair must agree; a sparse bridging row cannot join people.
            if all(composite_match(facts[i], facts[j]) for i in groups[a] for j in groups[b]):
                edges[a].add(b)
                edges[b].add(a)
            else:
                for i in groups[a] + groups[b]:
                    notes[i].add("Similar identity details exist but evidence is insufficient or conflicting; not linked by these details")
    visited = set()
    merged, merged_bases = [], []
    for start in range(len(groups)):
        if start in visited:
            continue
        component, pending = set(), [start]
        while pending:
            g = pending.pop()
            if g in component:
                continue
            component.add(g)
            pending.extend(edges[g] - component)
        visited.update(component)
        members = [i for g in sorted(component) for i in groups[g]]
        clique = all(b in edges[a] for a, b in combinations(component, 2))
        if len(component) > 1 and clique and consistent([facts[i] for i in members]):
            merged.append(members)
            merged_bases.append("Exact full name + original age + gender + phone + camp + corroborating residence/nationality")
        else:
            for g in sorted(component):
                merged.append(groups[g])
                merged_bases.append(bases[g])
                if len(component) > 1:
                    for i in groups[g]:
                        notes[i].add("Ambiguous match to multiple groups; automatic linking withheld")

    def stamp(row):
        for name in ("interview_date", "reporting_date"):
            value = pd.to_datetime(row.get(name), errors="coerce", utc=True)
            if pd.notna(value):
                return value
        return pd.NaT

    stamps = [stamp(row) for row in rows]

    def ref(row):
        for name in ("kobo_submission_uuid", "kobo_submission_id", "record_id"):
            value = text(row.get(name))
            if value:
                return name + ":" + value
        return ""

    references_by_row = [ref(row) for row in rows]
    reference_rows = defaultdict(list)
    for i, reference in enumerate(references_by_row):
        if reference:
            reference_rows[reference].append(i)
    for members in reference_rows.values():
        if len(members) > 1:
            for i in members:
                notes[i].add("Repeated source reference in the eligible snapshot; check for duplicate or conflicting source rows")

    def order(i):
        # Stable tie break under row reordering, without writing an identity ID.
        return (stamps[i].value if pd.notna(stamps[i]) else -9223372036854775808,
                references_by_row[i], tuple(text(rows[i].get(c)) for c in (
                    "information_seeker_name", "information_seeker_individual_number",
                    "information_seeker_phone", "alternative_phone", "helpdesk_section_block",
                    "residence_neighborhood_compound_house", "information_seeker_gender",
                    "age_group", "information_seeker_age", "information_seeker_nationality",
                    "information_seeker_nationality_other", "disability_status", "disability_type", "household_type")))

    chosen_groups = [(sorted(set(members) & selected, key=order, reverse=True), basis)
                     for members, basis in zip(merged, merged_bases) if set(members) & selected]
    chosen_groups.sort(key=lambda item: order(item[0][0]), reverse=True)
    representatives = [members[0] for members, _ in chosen_groups]
    table = beneficiary_register(source.iloc[representatives], age_mapper)
    evidence = []
    for position, (members, basis) in enumerate(chosen_groups):
        head = table.iloc[position]
        references = [references_by_row[i] for i in members]
        count = len(set(r for r in references if r)) + sum(not r for r in references)
        review = set().union(*(notes[i] for i in members))
        if len(members) == 1 and basis.startswith("Unlinked"):
            review.add("Single entry retained; uniqueness is not verified")
        if count < len(members):
            review.add("Repeated source reference; duplicate rows are not counted as extra submissions")
        histories_by_row = {i: text(rows[i].get("visited_tdh_helpdesk_before_raw")) or text(rows[i].get("visited_tdh_helpdesk_before"))
                              or text(rows[i].get("helpdesk_visit_history")) for i in members}
        histories = sorted(set(histories_by_row.values()) - {""})
        first_rows = [i for i, history in histories_by_row.items()
                      if normalized(history) in {"no", "first time", "first time visitor", "first visit"}]
        first_refs = {references_by_row[i] or f"row:{i}" for i in first_rows}
        late_first = any(pd.notna(stamps[i]) and pd.notna(stamps[j]) and stamps[j] < stamps[i]
                         and (not references_by_row[i] or references_by_row[i] != references_by_row[j])
                         for i in first_rows for j in members)
        if len(first_refs) > 1 or late_first:
            review.add("Repeated or late first-visit responses; review visit history")
        dates = [stamps[i].tz_convert("Africa/Nairobi").tz_localize(None).normalize() for i in members if pd.notna(stamps[i])]
        evidence.append({
            "Group in this view": position + 1,
            "Child / Beneficiary Name": head["Child / Beneficiary Name"],
            "Individual number": head["Individual number"],
            "Matching basis": basis,
            "Review notes": "; ".join(sorted(review)) or "No conflicts detected by these rules",
            "Entries in selected filters": len(members), "Observed submission count": count,
            "Additional submissions after first": max(0, count - 1),
            "First recorded entry": min(dates) if dates else pd.NaT,
            "Latest recorded entry": max(dates) if dates else pd.NaT,
            "Original age categories": "; ".join(sorted({text(rows[i].get("information_seeker_age")) for i in members} - {""})) or "Not recorded",
            "Reported visit history": "; ".join(histories) or "Not recorded",
            "Source record references": "; ".join(sorted(set(references) - {""})) or "Not recorded",
        })
    audit = pd.DataFrame(evidence, columns=AUDIT_COLUMNS)
    summary = {"entries": len(selected), "groups": len(table), "linked_entries": len(selected) - len(table),
               "review_groups": sum(row["Review notes"] != "No conflicts detected by these rules" for row in evidence)}
    return table, audit, summary
