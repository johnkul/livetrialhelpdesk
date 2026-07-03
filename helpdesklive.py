import re
import html
import base64
import json
import io
import os
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

import pandas as pd
import altair as alt
import streamlit as st

# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "tdh-logo.png"
DEVELOPER_LOGO_PATH = BASE_DIR / "assets" / "developer-logo.png"
STYLES_PATH = BASE_DIR / "assets" / "styles.css"
KOBO_CACHE_TTL_SECONDS = 300
APP_VERSION = "Version 1.0"
APP_VERSION_DATE = "June 2026"

logo_for_icon = LOGO_PATH
st.set_page_config(
    page_title="Tdh Kenya Helpdesk Dashboard",
    page_icon=str(logo_for_icon) if logo_for_icon.exists() else ":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "about": (
            "**Tdh Kenya Helpdesk Data Dashboard**\n\n"
            "Protection helpdesk monitoring for Turkana West & Dadaab.\n\n"
            "Developed by John Kul, MEAL Officer - Tdh · ImpactLens Africa."
        )
    },
)

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
PII_COLUMNS = [
    "information_seeker_name",
    "residence_neighborhood_compound_house",
    "information_seeker_phone",
    "alternative_phone",
    "information_seeker_individual_number",
    "information_seeker_ration_or_wristband_number",
]

AGE_GROUP_ORDER = [
    "0-5 Years",
    "6-11 Years",
    "12-17 Years",
    "18-35 Years",
    "36-49 Years",
    "50-64 Years",
    "65 Years and Above",
    "[Missing]",
]

CHILD_AGE_GROUPS = {"0-5 Years", "6-11 Years", "12-17 Years"}
ADULT_AGE_GROUPS = {"18-35 Years", "36-49 Years", "50-64 Years", "65 Years and Above"}

GENDER_ORDER = ["Girl", "Boy", "Woman", "Man", "Transgender", "[Missing]"]
GENDER_COLORS = {
    "Girl": "#7C3AED",
    "Boy": "#2563EB",
    "Woman": "#DB2777",
    "Man": "#059669",
    "Transgender": "#F59E0B",
    "[Missing]": "#9CA3AF",
}

WGQ_DISABILITY_DOMAINS = {
    "difficulty_seeing": "Visual Impairment",
    "difficulty_hearing": "Hearing Impairment",
    "difficulty_walking_or_climbing": "Physical/Mobility Impairment",
    "difficulty_walking_or_climbing_steps": "Physical/Mobility Impairment",
    "difficulty_remembering_or_concentrating": "Cognitive Impairment",
    "difficulty_self_care": "Self-Care Impairment",
    "difficulty_communicating": "Speech Impairment",
}

ADULT_DISABILITY_CATEGORY_COLUMNS = ["information_seeker_disability_type_other"]

DISABILITY_TYPE_STANDARD_MAP = {
    "visual impairment": "Visual Impairment",
    "visual disability": "Visual Impairment",
    "seeing impairment": "Visual Impairment",
    "seeing disability": "Visual Impairment",
    "hearing impairment": "Hearing Impairment",
    "hearing disability": "Hearing Impairment",
    "physical disability": "Physical/Mobility Impairment",
    "physical impairment": "Physical/Mobility Impairment",
    "physical/mobility disability": "Physical/Mobility Impairment",
    "physical/mobility impairment": "Physical/Mobility Impairment",
    "mobility disability": "Physical/Mobility Impairment",
    "mobility impairment": "Physical/Mobility Impairment",
    "walking disability": "Physical/Mobility Impairment",
    "walking impairment": "Physical/Mobility Impairment",
    "cognitive impairment": "Cognitive Impairment",
    "cognitive disability": "Cognitive Impairment",
    "remembering or concentrating difficulty": "Cognitive Impairment",
    "remembering/concentrating difficulty": "Cognitive Impairment",
    "self-care disability": "Self-Care Impairment",
    "self-care impairment": "Self-Care Impairment",
    "self care disability": "Self-Care Impairment",
    "self care impairment": "Self-Care Impairment",
    "communication disability": "Speech Impairment",
    "communication impairment": "Speech Impairment",
    "speech impairment": "Speech Impairment",
    "speech disability": "Speech Impairment",
    "speech difficulty": "Speech Impairment",
    "autism": "Cognitive Impairment",
    "adhd": "Cognitive Impairment",
    "neurological impairment": "Cognitive Impairment",
    "neurological impairments": "Cognitive Impairment",
    "multiple disabilities": "Multiple Impairments",
    "multiple disability": "Multiple Impairments",
    "multiple impairments": "Multiple Impairments",
    "multiple impairment": "Multiple Impairments",
}

FILTER_KEYS = [
    "camp_location_filter",
    "helpdesk_location_filter",
    "information_seeker_type_filter",
    "information_seeker_gender_filter",
    "age_group_filter",
    "request_category_filter",
]

CORE_RECORD_COLUMNS = [
    "record_id",
    "interview_date",
    "camp_location",
    "helpdesk_location",
    "household_type",
    "staff_name",
    "gps_latitude",
    "gps_longitude",
    "information_seeker_type",
    "information_seeker_gender",
    "age_group",
    "derived_life_stage",
    "information_seeker_type_raw",
    "information_seeker_gender_raw",
    "type_age_correction_flag",
    "gender_age_correction_flag",
    "disability_status",
    "disability_type",
    "adult_wgq_disability_status",
    "adult_wgq_disability_type",
    "adult_wgq_disability_domains",
    "adult_wgq_domain_count",
    "adult_wgq_impairment_count",
    "adult_duplicate_impairment_mentions",
    "adult_wgq_domain_count_category",
    "adult_wgq_multiplicity",
    "adult_wgq_max_score",
    "adult_wgq_severity",
    "adult_disability_exclusion_risk",
    "adult_additional_disability_category",
    "child_disability_status",
    "child_disability_type",
    "child_disability_type_other",
    "request_category",
    "referral_status",
    "follow_up_required_clean",
]

# Robust mapping table representing raw Kobo database fields to standard variables
KOBO_TO_DASHBOARD_COLUMN_MAP = {
    "consent_recording": "consent_recording",
    "staff_name": "staff_name",
    "interview_date": "interview_date",
    "information_seeker_type": "information_seeker_type",
    "information_seeker_name": "information_seeker_name",
    "child_unaccompanied_minor": "child_unaccompanied_minor",
    "respondent_relationship_to_child": "respondent_relationship_to_child",
    "respondent_relationship_other": "respondent_relationship_other",
    "household_type": "household_type",
    "camp_location": "camp_location",
    "helpdesk_camp_location": "helpdesk_camp_location",
    "helpdesk_section_block": "helpdesk_section_block",
    "helpdesk_village": "helpdesk_village",
    "residence_neighborhood_compound_house": "residence_neighborhood_compound_house",
    "information_seeker_gender": "information_seeker_gender",
    "information_seeker_age": "information_seeker_age",
    "information_seeker_nationality": "information_seeker_nationality",
    "information_seeker_nationality_other": "information_seeker_nationality_other",
    "has_operational_phone": "has_operational_phone",
    "information_seeker_phone": "information_seeker_phone",
    "alternative_phone": "alternative_phone",
    "registered_with_unhcr": "registered_with_unhcr",
    "information_seeker_individual_number": "information_seeker_individual_number",
    "information_seeker_ration_or_wristband_number": "information_seeker_ration_or_wristband_number",
    "has_disability": "has_disability",
    "child_disability_type": "child_disability_type",
    "child_disability_type_other": "child_disability_type_other",
    "difficulty_seeing": "difficulty_seeing",
    "difficulty_hearing": "difficulty_hearing",
    "difficulty_walking_or_climbing": "difficulty_walking_or_climbing",
    "difficulty_self_care": "difficulty_self_care",
    "difficulty_remembering_or_concentrating": "difficulty_remembering_or_concentrating",
    "difficulty_communicating": "difficulty_communicating",
    "information_seeker_disability_type_other": "information_seeker_disability_type_other",
    "visited_tdh_helpdesk_before": "visited_tdh_helpdesk_before",
    "last_visit_within_current_month": "last_visit_within_current_month",
    "request_type_protection_or_information": "request_type_protection_or_information",
    "main_protection_concern": "main_protection_concern",
    "general_information_type": "general_information_type",
    "action_taken": "action_taken",
    "action_taken_other_specify": "action_taken_other_specify",
    "referral_date": "referral_date",
    "referred_partner": "referred_partner",
    "referred_department": "referred_department",
    "external_agency_specify": "external_agency_specify",
    "follow_up_required": "follow_up_required",
    "follow_up_action": "follow_up_action",
    "gps_latitude": "gps_latitude",
    "gps_longitude": "gps_longitude",
    "gps_location_precision": "gps_location_precision"
}

RECORD_PREVIEW_LIMIT = 1000
SMALL_N_THRESHOLD = 5

# -----------------------------------------------------------------------------
# Styling and text helpers
# -----------------------------------------------------------------------------
def load_css():
    if STYLES_PATH.exists():
        css = STYLES_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.markdown(
            """
            <style>
            .stApp{background:#F8FAFC;}
            .app-header,.app-infobar,.kpi-card,.insight-card,.developer-footer{
                background:#fff;border:1px solid #E5E7EB;border-radius:18px;padding:16px;
                box-shadow:0 8px 24px rgba(15,23,42,.05);margin-bottom:14px;
            }
            .app-header{display:flex;gap:16px;align-items:center;}
            .app-header-logo{height:64px;object-fit:contain;}
            .app-header-title{font-size:28px;font-weight:850;color:#12312F;}
            .app-header-subtitle,.section-note,.kpi-context,.insight-detail{color:#64748B;}
            .app-infobar-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
            .app-pill{background:#F1F5F9;border-radius:999px;padding:7px 11px;font-weight:650;color:#12312F;}
            .app-pill-muted{color:#64748B;}.pill-key{color:#64748B;margin-right:6px;}
            .kpi-card{--accent:#2F7D69;border-left:6px solid var(--accent);}
            .kpi-label{font-size:13px;color:#64748B;text-transform:uppercase;font-weight:800;}
            .kpi-value{font-size:30px;font-weight:900;color:#0F172A;}
            .kpi-bar{height:8px;background:#E2E8F0;border-radius:999px;overflow:hidden;margin-top:8px;}
            .kpi-bar-fill{height:100%;background:var(--accent);}
            .kpi-group-caption{font-weight:800;color:#12312F;margin:10px 0 8px;}
            .section-header{display:flex;align-items:center;gap:8px;margin:12px 0 4px;}
            .section-accent{display:inline-block;width:8px;height:26px;background:#2F7D69;border-radius:99px;}
            .section-title{font-size:22px;font-weight:850;color:#12312F;}
            .insight-label{font-size:13px;font-weight:800;color:#64748B;}
            .insight-value{font-size:18px;font-weight:900;color:#12312F;margin-top:5px;}
            .insight-suppressed{color:#B45309;}.insight-suppressed-note{color:#B45309;}
            .developer-footer{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:24px;}
            .developer-brand{display:flex;align-items:center;gap:10px;}.developer-logo{height:42px;}
            .developer-brand-name{font-weight:900;color:#12312F;}.developer-brand-tagline,.developer-version{color:#64748B;font-size:13px;}
            </style>
            """,
            unsafe_allow_html=True,
        )

def clean_text(value):
    if pd.isna(value):
        return pd.NA
    value = str(value).strip()
    return pd.NA if value == "" else " ".join(value.split())

def normalize_response(value):
    value = clean_text(value)
    if pd.isna(value):
        return None
    value = str(value).strip().lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", value)

def staff_name_key(value):
    """Create a robust matching key for CPV/staff names."""
    value = normalize_response(value)
    if value is None:
        return ""
    value = value.replace('"', " ").replace("'", " ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

# CPV/staff name harmonization map. Keys must use staff_name_key() format.
CPV_NAME_STANDARD_MAP = {
    "abdullahi yussuf": "Abdullahi Yussuf Mohamed",
    "abdullahi yussuf mohamed": "Abdullahi Yussuf Mohamed",
    "mahat abdullahi": "Mahat Abdullahi Aden",
    "mahat abdullahi aden": "Mahat Abdullahi Aden",
    "hussein mohamud": "Hussein Mohamud",
    "hussein mohamed": "Hussein Mohamud",
    "oliek omot": "Oliek Omot",
    "john wani": "John Wani",
    "lokwang lino ubai": "Lokwang Lino Ubai",
    "hellen doki": "Hellen Doki Omar",
    "hellen doki omar": "Hellen Doki Omar",
    "lotari alfred": "Lotari Alfred",
    "alfred lotari": "Lotari Alfred",
    "clement akio": "Clement Akio Marino",
    "clement akio marino": "Clement Akio Marino",
    "clement skio marino": "Clement Akio Marino",
    "mulimbi_kalangiro": "Mulimbi Kalangiro Vainqueur",
    "mulimbi kalagiro": "Mulimbi Kalangiro Vainqueur",
    "mulimbi kalangiro vainqueur": "Mulimbi Kalangiro Vainqueur",
    "leer biel": "Leer Biel Leer",
    "leer biel leer": "Leer Biel Leer",
    "godfrey ojok": "Godfrey Ojok",
    "dual ador": "Dual Ador Arok",
    "dual ador arok": "Dual Ador Arok",
    "arme": "Armele Ngakani",
    "armele": "Armele Ngakani",
    "armele ngakani": "Armele Ngakani",
    "habiba mohamed": "Habiba Mohamed",
    "habibo mohamed": "Habiba Mohamed",
    "omar": "Omar Dekow",
    "omar dekow": "Omar Dekow",
    "oweteshe 3": "Oweteshe Mirindi",
    "oweteshe_mirindi": "Oweteshe Mirindi",
    "ndayikeje ferdinand": "Ndayikeje Ferdinand",
    "ferdinand ndayikeje": "Ndayikeje Ferdinand",
    "hassan ibrahim": "Hassan Ibrahim",
    "marwo mohamed": "Marwo Mohamed",
    "aden mohamed hassan": "Aden Mohamed Hassan",
    "kyanza louis": "Louis Kyanza",
    "louis kyanza": "Louis Kyanza",
    "rose akii": "Rose Akii",
    "jean claude": "Jean Claude",
    "claude jean": "Jean Claude",
    "claude": "Jean Claude",
    "belick": "Belick Uwisero",
    "belick uwisero": "Belick Uwisero",
    "belick uwusero": "Belick Uwisero",
    "be ick uwisero": "Belick Uwisero",
    "bekucknuwisero": "Belick Uwisero",
    "wardere mohamed": "Wardere Mohamed",
    "habibo abdi": "Habibo Abdi",
    "noor aden saman": "Noor Aden Saman",
    "suleiman ali": "Suleiman Ali",
    "maslah mohamed hassan": "Maslah Mohamed Hassan",
    "bakar": "Bakar",
    "kennedy johnpapa": "Kennedy Johnpapa",
    "kizito simon": "Kizito Simon",
    "ihisa mary": "Mary Ihisa",
    "mary_ihisa": "Mary Ihisa",
    "ahmed abdullahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed abdullahi_hussein": "Ahmed Abdullahi Hussein",
    "ahmed abdullah hussien": "Ahmed Abdullahi Hussein",
    "ahmed_abdulahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed adullahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed abdllahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed mohamed": "Ahmed Abdullahi Hussein",
    "fowzia omar": "Fowzia Omar Muse",
    "fowzi omar_muse": "Fowzia Omar Muse",
    "fowzia omar_muse": "Fowzia Omar Muse",
    "fowzi_omar": "Fowzia Omar Muse",
    "zahara": "Zahara Issack",
    "zahara issack": "Zahara Issack",
    "zahra issack": "Zahara Issack",
    "zara issack": "Zahara Issack",
    "ongoro": "Ongoro John",
    "ongoro_john": "Ongoro John",
    "peter kingombe": "Peter Kingombe",
    "safari david": "Safari David",
    "yop doboul": "Yop Doboul",
    "agustino achaka": "Augustino Achaka",
    "augustino achaka": "Augustino Achaka",
    "hirwa gentille": "Hirwa Gentille",
    "lobono peter": "Lobono Peter",
    "peter lobono": "Lobono Peter",
    "agnes ingiara oreste": "Agnes Ingiara Oreste",
    "adam": "Adam Owda Peter",
    "adam owda peter": "Adam Owda Peter",
    "lino lotino": "Lino Lotino",
    "madut_malul akon": "Madut Malul Akon",
    "beatrice akwero": "Beatrice Akwero",
    "anita munane": "Anita Munane",
    "abdifatah mohamednoor": "Abdifatah Mohamednoor",
    "abdifatah mohamed noor": "Abdifatah Mohamednoor",
    "dominic nangiro lomil": "Dominic Nangiro Lomil",
    "epusie brenda": "Epusie Brenda",
    "chumase edward ekalale": "Chumase Edward Ekalale",
    "mugishu eugene": "Mugishu Eugene",
    "both liem tang": "Both Liem Tang",
    "uju": "Uju",
}

def normalize_staff_name(value):
    value = clean_text(value)
    if pd.isna(value):
        return "[Not recorded]"
    value = str(value).strip().strip('"').strip("'")
    value = re.sub(r"\s+", " ", value)
    normalized_empty_values = {"", "nan", "none", "missing", "not recorded", "[not recorded]"}
    if value.lower() in normalized_empty_values:
        return "[Not recorded]"
    key = staff_name_key(value)
    if key in CPV_NAME_STANDARD_MAP:
        return CPV_NAME_STANDARD_MAP[key]
    key_tokens = key.split()
    for alias_key, canonical_name in CPV_NAME_STANDARD_MAP.items():
        alias_tokens = alias_key.split()
        if len(key_tokens) >= 2 and len(alias_tokens) >= 2 and sorted(key_tokens) == sorted(alias_tokens):
            return canonical_name
    return value.title()

def standardize_disability_type(value):
    value = clean_text(value)
    if pd.isna(value):
        return "None"
    normalized = normalize_response(value)
    if normalized in {"none", "none of the above", "no", "not applicable", "n/a", "na", "nil"}:
        return "None"
    if normalized in DISABILITY_TYPE_STANDARD_MAP:
        return DISABILITY_TYPE_STANDARD_MAP[normalized]
    if "multiple" in normalized:
        return "Multiple Impairments"
    if "visual" in normalized or "seeing" in normalized:
        return "Visual Impairment"
    if "hearing" in normalized:
        return "Hearing Impairment"
    if any(token in normalized for token in ["physical", "mobility", "walking", "climbing"]):
        return "Physical/Mobility Impairment"
    if any(token in normalized for token in ["cognitive", "remember", "concentrat", "autism", "adhd", "neurological"]):
        return "Cognitive Impairment"
    if "self care" in normalized or "self-care" in normalized:
        return "Self-Care Impairment"
    if "speech" in normalized or "communication" in normalized or "communicat" in normalized:
        return "Speech Impairment"
    return str(value)

def safe_label_from_code(value):
    value = str(value)
    value = value.replace("concern_", "").replace("info_", "").replace("ref_partner_", "")
    value = value.replace("_", " ")
    return value.title()

def harmonize_free_text(text, main_category_labels, default="Other Not Listed"):
    if pd.isna(text):
        return default
    txt = str(text).strip()
    if not txt:
        return default
    txt_norm = normalize_response(txt)
    if txt_norm in ["other", "other not listed", "others", "other specify", "none", "na", "n/a", "nil"]:
        return default
    clean_labels = []
    for label in main_category_labels:
        if not label or pd.isna(label):
            continue
        label_norm = normalize_response(label)
        if label_norm in ["other", "other not listed", "others", "other specify"]:
            continue
        clean_labels.append(str(label))
    for label in clean_labels:
        if txt_norm == normalize_response(label) or txt.lower() == label.lower():
            return label
    for label in clean_labels:
        label_norm = normalize_response(label)
        if label_norm and (label_norm in txt_norm or txt_norm in label_norm):
            return label
    txt_words = set(word for word in txt_norm.split() if len(word) > 2)
    for label in clean_labels:
        label_norm = normalize_response(label)
        label_words = set(word for word in label_norm.split() if len(word) > 2)
        if not label_words:
            continue
        overlap = label_words & txt_words
        if len(overlap) >= 1 and len(overlap) / len(label_words) >= 0.5:
            return label
    cleaned = safe_label_from_code(txt)
    if cleaned and normalize_response(cleaned) not in ["other", "other not listed", "others", "other specify"]:
        return cleaned
    return default

def canonical_organization_label(value):
    key = organization_match_key(value)
    if not key:
        return None
    if (
        "krcs" in key.split()
        or "red cross" in key
        or "redcross" in key
        or "kenya red cross" in key
        or "kenya redcross" in key
    ):
        return "KRCS"
    if "police" in key.split() or "police station" in key:
        return "POLICE"
    canonical_patterns = [
        ("unhcr", "UNHCR"),
        ("united nations high commissioner for refugees", "UNHCR"),
        ("tdh", "TDH"),
        ("terre des hommes", "TDH"),
        ("department of refugee services", "DRS"),
        ("drs", "DRS"),
        ("refugee affairs secretariat", "RAS"),
        ("ras", "RAS"),
        ("danish refugee council", "DRC"),
        ("drc", "DRC"),
        ("norwegian refugee council", "NRC"),
        ("nrc", "NRC"),
        ("international rescue committee", "IRC"),
        ("irc", "IRC"),
        ("lutheran world federation", "LWF"),
        ("lwf", "LWF"),
        ("humanity inclusion", "HI"),
        ("humanity and inclusion", "HI"),
        ("handicap international", "HI"),
        ("hi", "HI"),
        ("world food programme", "WFP"),
        ("world food program", "WFP"),
        ("wfp", "WFP"),
        ("unicef", "UNICEF"),
        ("save the children", "SAVE THE CHILDREN"),
        ("rck", "RCK"),
        ("refugee consortium of kenya", "RCK"),
        ("msf", "MSF"),
        ("medecins sans frontieres", "MSF"),
        ("doctors without borders", "MSF"),
    ]
    key_tokens = set(key.split())
    for pattern, canonical in canonical_patterns:
        if len(pattern) <= 4:
            if pattern in key_tokens:
                return canonical
        elif pattern in key:
            return canonical
    return None

def normalize_organization_label(value):
    value = clean_text(value)
    if pd.isna(value):
        return "OTHER NOT LISTED"
    canonical = canonical_organization_label(value)
    if canonical:
        return canonical
    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value.upper()

def organization_match_key(value):
    value = normalize_response(value)
    if value is None:
        return ""
    value = value.replace("&amp;", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def organization_acronyms(value):
    if pd.isna(value):
        return set()
    text = str(value)
    acronyms = set()
    for match in re.findall(r"\(([A-Za-z0-9]{2,12})\)", text):
        acronyms.add(match.lower())
    words = re.findall(r"[A-Za-z0-9]+", text)
    stop_words = {"and", "of", "the", "for", "to", "in", "on", "with", "kenya", "agency", "organization", "organisation"}
    initials = "".join(word[0] for word in words if word.lower() not in stop_words and not word.isdigit())
    if 2 <= len(initials) <= 12:
        acronyms.add(initials.lower())
    for word in words:
        if word.isupper() and 2 <= len(word) <= 12:
            acronyms.add(word.lower())
    return acronyms

def harmonize_organization_text(text, organization_labels, default="OTHER NOT LISTED"):
    if pd.isna(text):
        return default
    txt = str(text).strip()
    if not txt:
        return default
    canonical = canonical_organization_label(txt)
    if canonical:
        return canonical
    txt_key = organization_match_key(txt)
    if txt_key in ["other", "other not listed", "others", "other specify", "none", "na", "n a", "nil"]:
        return default
    clean_labels = []
    for label in organization_labels:
        if not label or pd.isna(label):
            continue
        label_key = organization_match_key(label)
        if label_key in ["other", "other not listed", "others", "other specify"]:
            continue
        clean_labels.append(str(label))
    txt_tokens = set(txt_key.split())
    for label in clean_labels:
        label_key = organization_match_key(label)
        label_acronyms = organization_acronyms(label)
        if txt_key == label_key or (label_key and (label_key in txt_key or txt_key in label_key)):
            return normalize_organization_label(label)
        if txt_key in label_acronyms or label_acronyms.intersection(txt_tokens):
            return normalize_organization_label(label)
    for label in clean_labels:
        label_tokens = set(word for word in organization_match_key(label).split() if len(word) > 2)
        if not label_tokens:
            continue
        overlap = label_tokens & set(word for word in txt_tokens if len(word) > 2)
        if len(overlap) >= 1 and len(overlap) / len(label_tokens) >= 0.5:
            return normalize_organization_label(label)
    cleaned = safe_label_from_code(txt)
    return normalize_organization_label(cleaned) if cleaned else default

def short_axis_label(value, max_chars=28):
    value = str(value)
    return value if len(value) <= max_chars else value[: max_chars - 3] + "..."

def escape_text(value):
    return html.escape(str(value))

def format_number(value):
    return f"{int(value):,}"

def format_rate(numerator, denominator):
    if denominator == 0:
        return "0.0%"
    return f"{numerator / denominator:.1%}"

def safe_share(numerator, denominator):
    return (numerator / denominator) if denominator else 0.0

# -----------------------------------------------------------------------------
# Data derivation helpers
# -----------------------------------------------------------------------------
def age_group_life_stage(age_group):
    age_group = clean_text(age_group)
    if pd.isna(age_group):
        return pd.NA
    if age_group in CHILD_AGE_GROUPS:
        return "Child"
    if age_group in ADULT_AGE_GROUPS:
        return "Adult"
    numbers = [int(number) for number in re.findall(r"\d+", str(age_group))]
    if numbers:
        return "Child" if numbers[0] < 18 else "Adult"
    return pd.NA

def standardize_age_group(value):
    value = clean_text(value)
    if pd.isna(value):
        return pd.NA
    if str(value) in AGE_GROUP_ORDER:
        return str(value)
    match = re.search(r"\d+", str(value))
    if not match:
        return value
    age = int(match.group(0))
    if age <= 5:
        return "0-5 Years"
    if age <= 11:
        return "6-11 Years"
    if age <= 17:
        return "12-17 Years"
    if age <= 35:
        return "18-35 Years"
    if age <= 49:
        return "36-49 Years"
    if age <= 64:
        return "50-64 Years"
    return "65 Years and Above"

def normalize_request_category(value):
    value = clean_text(value)
    if pd.isna(value):
        return pd.NA
    normalized = normalize_response(value)
    if normalized is None:
        return pd.NA
    if "general" in normalized and "information" in normalized:
        return "Seeking general protection information"
    if "information" in normalized and "concern" not in normalized:
        return "Seeking general protection information"
    if "protection" in normalized and "concern" in normalized:
        return "Reporting a protection concern"
    if normalized in {"concern", "protection", "reporting protection concern"}:
        return "Reporting a protection concern"
    return str(value)

def is_selected_indicator(value):
    value = clean_text(value)
    if pd.isna(value):
        return False
    normalized = normalize_response(value)
    if normalized is None:
        return False
    return normalized in {"1", "true", "yes", "y", "selected", "checked"} or normalized not in {
        "0",
        "false",
        "no",
        "n",
        "none",
        "nan",
        "not selected",
        "unchecked",
    }

def normalize_gender_by_life_stage(gender, life_stage):
    gender = clean_text(gender)
    life_stage = clean_text(life_stage)
    if pd.isna(gender):
        return "[Missing]"
    if pd.isna(life_stage):
        return gender
    if life_stage == "Adult":
        return {"Girl": "Woman", "Boy": "Man"}.get(gender, gender)
    if life_stage == "Child":
        return {"Woman": "Girl", "Man": "Boy"}.get(gender, gender)
    return gender

def is_host_community(value):
    value = normalize_response(value)
    return bool(value and "host" in value and "community" in value)

def derive_linked_helpdesk_location(row):
    household_type = row.get("household_type")
    camp_location = clean_text(row.get("camp_location"))
    helpdesk_camp = clean_text(row.get("helpdesk_camp_location"))
    helpdesk_village = clean_text(row.get("helpdesk_village"))
    if is_host_community(household_type):
        return f"Host community - {camp_location}" if not pd.isna(camp_location) else "Host community"
    if not pd.isna(helpdesk_camp):
        return helpdesk_camp
    if not pd.isna(helpdesk_village):
        return helpdesk_village
    return "[Not recorded]"

def extract_coordinate_numbers(value):
    if pd.isna(value):
        return []
    return [float(match) for match in re.findall(r"[-+]?\d+(?:\.\d+)?", str(value))]

def derive_gps_coordinates(row):
    latitude_values = extract_coordinate_numbers(row.get("gps_latitude"))
    longitude_values = extract_coordinate_numbers(row.get("gps_longitude"))
    gps_location_longitude_values = extract_coordinate_numbers(row.get("_GPS Location_longitude"))
    latitude = pd.NA
    longitude = pd.NA
    if len(latitude_values) >= 2:
        latitude = latitude_values[0]
        longitude = latitude_values[1]
    else:
        if latitude_values:
            latitude = latitude_values[0]
        if longitude_values:
            longitude = longitude_values[0]
        if gps_location_longitude_values and (pd.isna(longitude) or (not pd.isna(latitude) and longitude == latitude)):
            longitude = gps_location_longitude_values[0]
    if not pd.isna(latitude) and not pd.isna(longitude):
        if abs(latitude) > 90 and abs(longitude) <= 90:
            latitude, longitude = longitude, latitude
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            latitude = pd.NA
            longitude = pd.NA
    return pd.Series({"gps_latitude": latitude, "gps_longitude": longitude})

def is_adult(row):
    age_group = clean_text(row.get("age_group"))
    if not pd.isna(age_group):
        return age_group in ADULT_AGE_GROUPS
    return normalize_response(row.get("information_seeker_type")) == "adult"

def is_child(row):
    age_group = clean_text(row.get("age_group"))
    if not pd.isna(age_group):
        return age_group in CHILD_AGE_GROUPS
    return normalize_response(row.get("information_seeker_type")) == "child"

def wgq_score(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not pd.isna(value):
        score = int(value)
        return score if score in [1, 2, 3, 4] else None
    response = normalize_response(value)
    if response is None:
        return None
    response = response.replace("can not", "cannot")
    if response.startswith("1") or response == "no difficulty":
        return 1
    if response.startswith("2") or response == "some difficulty":
        return 2
    if response.startswith("3") or response == "a lot of difficulty":
        return 3
    if response.startswith("4") or response == "cannot do at all":
        return 4
    return None

def adult_wgq_domain_scores(row):
    scores = {}
    if not is_adult(row):
        return scores
    for column, impairment_type in WGQ_DISABILITY_DOMAINS.items():
        if column not in row.index:
            continue
        score = wgq_score(row[column])
        if score is None:
            continue
        standardized_type = standardize_disability_type(impairment_type)
        scores[standardized_type] = max(scores.get(standardized_type, 0), score)
    return scores

def derive_adult_wgq_disability_domains(row):
    impairment_types = [impairment for impairment, score in adult_wgq_domain_scores(row).items() if score in [3, 4]]
    return "; ".join(sorted(set(impairment_types))) if impairment_types else "None"

def derive_adult_additional_disability_category(row):
    if not is_adult(row):
        return "None"
    for column in ADULT_DISABILITY_CATEGORY_COLUMNS:
        if column in row.index:
            standardized_value = standardize_disability_type(row[column])
            if standardized_value != "None":
                return standardized_value
    return "None"

def split_impairment_types(value):
    if pd.isna(value):
        return []
    value = str(value).strip()
    if value in ["", "None", "No Disability", "[Missing]"]:
        return []
    impairment_types = [item.strip() for item in value.split(";") if item.strip()]
    standardized_types = [standardize_disability_type(item) for item in impairment_types]
    return list(dict.fromkeys(item for item in standardized_types if item != "None"))

def derive_adult_disability_domains(row):
    impairment_types = []
    wgq_domains = derive_adult_wgq_disability_domains(row)
    additional_category = derive_adult_additional_disability_category(row)
    if wgq_domains != "None":
        impairment_types.extend(split_impairment_types(wgq_domains))
    if additional_category != "None":
        impairment_types.append(standardize_disability_type(additional_category))
    impairment_types = sorted(set(value for value in impairment_types if value != "None"))
    return "; ".join(impairment_types) if impairment_types else "None"

def adult_row_impairment_types(row):
    if not is_adult(row):
        return []
    return split_impairment_types(derive_adult_disability_domains(row))

def derive_adult_wgq_disability_status(row):
    return "Has Disability" if adult_row_impairment_types(row) else "No Disability"

def derive_adult_wgq_disability_type(row):
    impairment_types = adult_row_impairment_types(row)
    if not impairment_types:
        return "No Disability"
    return "Multiple Impairments" if len(impairment_types) > 1 else impairment_types[0]

def derive_adult_wgq_domain_count(row):
    return len(adult_row_impairment_types(row))

def derive_adult_wgq_domain_count_category(row):
    count = derive_adult_wgq_domain_count(row)
    if count == 0:
        return "No Disability"
    if count == 1:
        return "One Impairment"
    if count == 2:
        return "Two Impairments"
    return "Three or More Impairments"

def derive_adult_wgq_multiplicity(row):
    count = derive_adult_wgq_domain_count(row)
    if count == 0:
        return "No Disability"
    if count == 1:
        return "One Impairment"
    return "Multiple Impairments"

def derive_adult_wgq_max_score(row):
    scores = adult_wgq_domain_scores(row)
    return max(scores.values()) if scores else 1

def derive_adult_wgq_severity(row):
    max_score = derive_adult_wgq_max_score(row)
    if max_score in [1, 2]:
        return "No Disability"
    if max_score == 3:
        return "Disability"
    if max_score == 4:
        return "Severe Disability"
    return "No Disability"

def derive_adult_disability_exclusion_risk(row):
    scores = adult_wgq_domain_scores(row)
    if any(score in [2, 3, 4] for score in scores.values()):
        return "At risk of disability-related exclusion"
    if derive_adult_additional_disability_category(row) != "None":
        return "At risk of disability-related exclusion"
    return "Not at risk"

def derive_child_disability_status(row):
    if not is_child(row):
        return "No Disability"
    response = normalize_response(row.get("has_disability"))
    return "Has Disability" if response in ["yes", "y", "true", "1"] else "No Disability"

def derive_child_disability_type(row):
    if not is_child(row) or derive_child_disability_status(row) != "Has Disability":
        return "No Disability"
    disability_type = clean_text(row.get("child_disability_type"))
    disability_type_other = clean_text(row.get("child_disability_type_other"))
    invalid = {"other", "others", "other specify", "other specified", "none", "none of the above", "not applicable", "n/a", "na", "nil"}
    if not pd.isna(disability_type) and normalize_response(disability_type) not in invalid:
        return standardize_disability_type(disability_type)
    if not pd.isna(disability_type_other) and normalize_response(disability_type_other) not in invalid:
        return standardize_disability_type(disability_type_other)
    return "Not specified"

def derive_combined_disability_status(row):
    if is_adult(row):
        return row.get("adult_wgq_disability_status", "No Disability")
    if is_child(row):
        return row.get("child_disability_status", "No Disability")
    return "No Disability"

def derive_combined_disability_type(row):
    if is_child(row):
        child_type = row.get("child_disability_type", "No Disability")
        return child_type if child_type not in ["", "None", "No Disability"] else "No Disability"
    if is_adult(row):
        adult_type = row.get("adult_wgq_disability_type", "No Disability")
        return adult_type if adult_type not in ["", "None", "Not specified"] else "No Disability"
    return "No Disability"

def adult_person_impairment_frame(frame):
    rows = []
    if frame.empty:
        return pd.DataFrame()
    adult_frame = frame[frame["derived_life_stage"].astype(str).eq("Adult")].copy()
    for _, row in adult_frame.iterrows():
        impairment_types = adult_row_impairment_types(row)
        impairment_count = len(impairment_types)
        if impairment_count == 0:
            disability_status = "No Disability"
            person_impairment_type = "No Disability"
        elif impairment_count == 1:
            disability_status = "Has Disability"
            person_impairment_type = impairment_types[0]
        else:
            disability_status = "Has Disability"
            person_impairment_type = "Multiple Impairments"

        if impairment_count == 0:
            impairment_count_category = "No Disability"
        elif impairment_count == 1:
            impairment_count_category = "One Impairment"
        elif impairment_count == 2:
            impairment_count_category = "Two Impairments"
        else:
            impairment_count_category = "Three or More Impairments"

        rows.append(
            {
                "record_id": row.get("record_id"),
                "information_seeker_gender": row.get("information_seeker_gender"),
                "adult_disability_status": disability_status,
                "adult_person_impairment_type": person_impairment_type,
                "adult_impairment_count": impairment_count,
                "adult_impairment_count_category": impairment_count_category,
                "adult_impairment_multiplicity": (
                    "No Disability" if impairment_count == 0 else "Single Impairment" if impairment_count == 1 else "Multiple Impairments"
                ),
                "duplicate_impairment_mentions": max(impairment_count - 1, 0),
            }
        )
    return pd.DataFrame(rows)

# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
def get_kobo_config():
    """Return KoboToolbox settings from Streamlit secrets, if configured."""
    try:
        kobo_secrets = st.secrets.get("kobo", {})
    except Exception:
        return {}
    export_url = kobo_secrets.get("export_url", "") if kobo_secrets else ""
    api_token = kobo_secrets.get("api_token", "") if kobo_secrets else ""
    if not export_url:
        export_url = st.secrets.get("export_url", "")
    if not api_token:
        api_token = st.secrets.get("api_token", "")
    return {
        "export_url": str(export_url).strip(),
        "api_token": str(api_token).strip(),
    }

def kobo_configured():
    config = get_kobo_config()
    return bool(config.get("export_url") and config.get("api_token"))

def normalize_kobo_export_url(export_url):
    """Accept either a direct Kobo API/export URL or a Kobo form page URL."""
    if "#/forms/" not in export_url:
        return export_url
    parsed = urllib.parse.urlparse(export_url)
    match = re.search(r"/forms/([^/]+)/data", parsed.fragment)
    if not match:
        return export_url
    asset_uid = match.group(1)
    return f"{parsed.scheme}://{parsed.netloc}/api/v2/assets/{asset_uid}/data/?format=json"

def data_source_signature():
    if not kobo_configured():
        st.error(
            "KoboToolbox is not configured. Add export_url and api_token in Streamlit Secrets."
        )
        st.stop()
    config = get_kobo_config()
    return ("kobo", normalize_kobo_export_url(config["export_url"]), None, "Kobo live data")

@st.cache_data(ttl=KOBO_CACHE_TTL_SECONDS, show_spinner="Downloading latest KoboToolbox data...")
def fetch_kobo_payload(export_url, api_token):
    export_url = normalize_kobo_export_url(export_url)
    def read_url(url):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Token {api_token}",
                "Accept": "application/json, text/csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, */*",
                "User-Agent": "tdh-helpdesk-streamlit-dashboard/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            return {
                "content": response.read(),
                "content_type": response.headers.get("Content-Type", ""),
                "url": response.geturl(),
            }
    try:
        payload = read_url(export_url)
        if "json" not in payload.get("content_type", "").lower() and "format=json" not in payload.get("url", "").lower():
            return payload
        try:
            parsed = json.loads(payload["content"].decode("utf-8"))
        except Exception:
            return payload
        if not isinstance(parsed, dict) or "results" not in parsed:
            return payload
        all_results = list(parsed.get("results") or [])
        next_url = parsed.get("next")
        current_url = payload["url"]
        page_guard = 0
        while next_url and page_guard < 500:
            page_guard += 1
            next_url = urllib.parse.urljoin(current_url, next_url)
            page_payload = read_url(next_url)
            current_url = page_payload["url"]
            page = json.loads(page_payload["content"].decode("utf-8"))
            all_results.extend(page.get("results") or [])
            next_url = page.get("next")
        return {
            "content": json.dumps({"results": all_results}).encode("utf-8"),
            "content_type": "application/json",
            "url": payload["url"],
        }
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"KoboToolbox returned HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Could not reach KoboToolbox: {error.reason}") from error

def open_kobo_records_from_payload(payload):
    content = payload["content"]
    content_type = payload.get("content_type", "").lower()
    source_url = payload.get("url", "").lower()
    if "json" in content_type or "format=json" in source_url:
        try:
            parsed = json.loads(content.decode("utf-8"))
        except Exception as error:
            raise RuntimeError(f"KoboToolbox returned invalid JSON: {error}") from error
        if isinstance(parsed, dict) and "results" in parsed:
            return pd.json_normalize(parsed["results"]), None
        if isinstance(parsed, list):
            return pd.json_normalize(parsed), None
        return pd.json_normalize(parsed), None
    if "csv" in content_type or source_url.endswith(".csv"):
        return pd.read_csv(io.BytesIO(content)), None
    try:
        workbook = pd.ExcelFile(io.BytesIO(content), engine="openpyxl")
    except Exception as error:
        raise RuntimeError(
            "Could not read KoboToolbox response as Excel, CSV, or JSON. "
            "Use a direct Kobo API data URL or a saved export data_url_xlsx/data_url_csv."
        ) from error
    data_sheet = "cleaned_data" if "cleaned_data" in workbook.sheet_names else workbook.sheet_names[0]
    records = workbook.parse(data_sheet)
    mapping = None
    if "Column Mapping" in workbook.sheet_names:
        try:
            mapping = workbook.parse("Column Mapping")
        except Exception:
            mapping = None
    return records, mapping

def copy_column_by_suffix(frame, target_column):
    if target_column in frame.columns:
        return
    suffix = f"_{target_column}"
    candidates = [column for column in frame.columns if column.endswith(suffix)]
    if not candidates:
        return
    candidates = sorted(
        candidates,
        key=lambda column: (frame[column].notna().sum(), -len(column)),
        reverse=True,
    )
    frame[target_column] = frame[candidates[0]]

def expose_prefixed_select_multiple_columns(frame):
    expected_prefixes = ("concern_", "info_", "ref_partner_")
    existing = set(frame.columns)
    for column in list(frame.columns):
        for prefix in expected_prefixes:
            marker = f"_{prefix}"
            if marker not in column:
                continue
            exposed_name = column[column.index(marker) + 1 :]
            if exposed_name and exposed_name not in existing:
                frame[exposed_name] = frame[column]
                existing.add(exposed_name)

def build_label_map(mapping, prefix):
    if mapping is None or mapping.empty or "cleaned_column_name" not in mapping.columns:
        return {}
    label_map = {}
    selected = mapping[mapping["cleaned_column_name"].astype(str).str.startswith(prefix)]
    for _, row in selected.iterrows():
        cleaned_name = row["cleaned_column_name"]
        if str(cleaned_name).endswith("_specify"):
            continue
        original_name = clean_text(row.get("original_column_name"))
        if pd.isna(original_name):
            label = safe_label_from_code(cleaned_name)
        elif "/" in str(original_name):
            label = str(original_name).split("/", 1)[1].strip()
        else:
            label = str(original_name).strip()
        label_map[cleaned_name] = label
    return label_map

@st.cache_data(ttl=KOBO_CACHE_TTL_SECONDS, show_spinner="Loading latest helpdesk dataset...")
def load_data(source_signature):
    config = get_kobo_config()
    try:
        payload = fetch_kobo_payload(config["export_url"], config["api_token"])
        records, mapping = open_kobo_records_from_payload(payload)
    except Exception as error:
        st.error(f"Could not load KoboToolbox data: {error}")
        st.stop()

    if mapping is None:
        mapping = pd.DataFrame()
    try:
        records = records.copy()
    except Exception as error:
        st.error(f"Could not prepare source records: {error}")
        st.stop()

    if records.empty:
        st.error("The selected data source returned no records.")
        st.stop()

    # 1. Clean and normalize the incoming Kobo API column names to safe lowercase underscore formats
    # Also strip slash structures often exported by Kobo
    records.columns = [str(column).replace("/", "_").strip() for column in records.columns]
    records.columns = [re.sub(r"[^A-Za-z0-9_]+", "_", column).strip("_") for column in records.columns]
    records.columns = [re.sub(r"_+", "_", column).lower() for column in records.columns]

    # Let's print columns to st.write under an expander for user troubleshooting
    with st.expander("Troubleshooting: Raw Columns in Kobo Database"):
        st.write(sorted(records.columns.tolist()))

    # 2. Map Kobo API raw column names to dashboard expected names
    records = records.rename(columns=KOBO_TO_DASHBOARD_COLUMN_MAP)

    # 3. Fallback group suffix matcher for prefixes introduced by Kobo Collect Group/Repeat fields
    for raw_kobo_col, dashboard_target_col in KOBO_TO_DASHBOARD_COLUMN_MAP.items():
        if dashboard_target_col not in records.columns:
            candidates = [col for col in records.columns if col.endswith(f"_{dashboard_target_col}") or col.endswith(f"_{raw_kobo_col}")]
            if candidates:
                records[dashboard_target_col] = records[candidates[0]]

    # Expected list of fields utilized inside data processing loops
    expected_source_columns = [
        "interview_date",
        "staff_name",
        "gps_latitude",
        "gps_longitude",
        "household_type",
        "camp_location",
        "helpdesk_camp_location",
        "helpdesk_village",
        "information_seeker_age",
        "information_seeker_type",
        "information_seeker_gender",
        "request_type_protection_or_information",
        "main_protection_concern",
        "general_information_type",
        "action_taken",
        "follow_up_required",
        "has_disability",
        "child_disability_type",
        "child_disability_type_other",
    ]
    expected_source_columns.extend(WGQ_DISABILITY_DOMAINS.keys())
    expected_source_columns.extend(ADULT_DISABILITY_CATEGORY_COLUMNS)

    for column in expected_source_columns:
        copy_column_by_suffix(records, column)

    expose_prefixed_select_multiple_columns(records)

    if "interview_date" not in records.columns and "submission_time" in records.columns:
        records["interview_date"] = records["submission_time"]

    if "record_id" not in records.columns:
        records["record_id"] = records.get("id", records.index.astype(str))

    for column in expected_source_columns:
        if column not in records.columns:
            records[column] = pd.NA

    records["source_row_number"] = records.index + 2
    records["record_id"] = records["source_row_number"].map(lambda row: f"HD-{row:05d}")
    records["interview_date"] = pd.to_datetime(records["interview_date"], errors="coerce")
    records["year"] = records["interview_date"].dt.year
    records["month_number"] = records["interview_date"].dt.month
    records["year_month"] = records["interview_date"].dt.to_period("M").astype(str)
    records["month_label"] = records["interview_date"].dt.strftime("%b %Y")

    parsed_gps = records.apply(derive_gps_coordinates, axis=1)
    records["gps_latitude"] = pd.to_numeric(parsed_gps["gps_latitude"], errors="coerce")
    records["gps_longitude"] = pd.to_numeric(parsed_gps["gps_longitude"], errors="coerce")

    records["staff_name"] = records["staff_name"].map(normalize_staff_name)
    records["household_type"] = records["household_type"].map(clean_text)
    records["age_group"] = records["information_seeker_age"].map(standardize_age_group)
    records["derived_life_stage"] = records["age_group"].map(age_group_life_stage)
    records["information_seeker_type_raw"] = records["information_seeker_type"].map(clean_text)
    records["information_seeker_gender_raw"] = records["information_seeker_gender"].map(clean_text)
    records["information_seeker_type"] = records["derived_life_stage"].fillna(records["information_seeker_type_raw"])
    records["information_seeker_gender"] = records.apply(
        lambda row: normalize_gender_by_life_stage(row["information_seeker_gender_raw"], row["information_seeker_type"]),
        axis=1,
    ).fillna("[Missing]")

    records["type_age_correction_flag"] = records["information_seeker_type_raw"].fillna("[Missing]") != records[
        "information_seeker_type"
    ].fillna("[Missing]")
    records["gender_age_correction_flag"] = records["information_seeker_gender_raw"].fillna("[Missing]") != records[
        "information_seeker_gender"
    ].fillna("[Missing]")

    records["request_category"] = records["request_type_protection_or_information"].map(normalize_request_category)
    request_missing = records["request_category"].isna()
    protection_indicator_cols = [
        col for col in records.columns if col.startswith("concern_") and not col.endswith("_specify")
    ]
    information_indicator_cols = [
        col for col in records.columns if col.startswith("info_") and not col.endswith("_specify")
    ]

    has_protection_detail = records.get("main_protection_concern", pd.Series(pd.NA, index=records.index)).map(clean_text).notna()
    if protection_indicator_cols:
        protection_selected = records[protection_indicator_cols].apply(lambda column: column.map(is_selected_indicator))
        has_protection_detail = has_protection_detail | protection_selected.any(axis=1)

    has_information_detail = records.get("general_information_type", pd.Series(pd.NA, index=records.index)).map(clean_text).notna()
    if information_indicator_cols:
        information_selected = records[information_indicator_cols].apply(lambda column: column.map(is_selected_indicator))
        has_information_detail = has_information_detail | information_selected.any(axis=1)

    records.loc[request_missing & has_protection_detail, "request_category"] = "Reporting a protection concern"
    records.loc[request_missing & ~has_protection_detail & has_information_detail, "request_category"] = "Seeking general protection information"

    records["action_taken_clean"] = records["action_taken"].map(clean_text)
    records["follow_up_required_clean"] = records["follow_up_required"].map(clean_text)
    records["helpdesk_location"] = records.apply(derive_linked_helpdesk_location, axis=1)

    records["adult_wgq_disability_domains"] = records.apply(derive_adult_wgq_disability_domains, axis=1)
    records["adult_additional_disability_category"] = records.apply(derive_adult_additional_disability_category, axis=1)
    records["adult_wgq_disability_status"] = records.apply(derive_adult_wgq_disability_status, axis=1)
    records["adult_wgq_disability_type"] = records.apply(derive_adult_wgq_disability_type, axis=1)
    records["adult_wgq_domain_count"] = records.apply(derive_adult_wgq_domain_count, axis=1)
    records["adult_wgq_impairment_count"] = records["adult_wgq_domain_count"]
    records["adult_duplicate_impairment_mentions"] = records["adult_wgq_impairment_count"].map(lambda x: max(int(x) - 1, 0))
    records["adult_wgq_domain_count_category"] = records.apply(derive_adult_wgq_domain_count_category, axis=1)
    records["adult_wgq_multiplicity"] = records.apply(derive_adult_wgq_multiplicity, axis=1)
    records["adult_wgq_max_score"] = records.apply(derive_adult_wgq_max_score, axis=1)
    records["adult_wgq_severity"] = records.apply(derive_adult_wgq_severity, axis=1)
    records["adult_disability_exclusion_risk"] = records.apply(derive_adult_disability_exclusion_risk, axis=1)
    records["child_disability_status"] = records.apply(derive_child_disability_status, axis=1)
    records["child_disability_type"] = records.apply(derive_child_disability_type, axis=1)
    records["disability_status"] = records.apply(derive_combined_disability_status, axis=1)
    records["disability_type"] = records.apply(derive_combined_disability_type, axis=1)

    records["referral_status"] = "No referral"
    records.loc[records["action_taken_clean"].eq("Case referred to Tdh national staff") | records["action_taken_clean"].eq("Case referrred to Tdh national staff"), "referral_status"] = "Referred to Tdh national staff"
    records.loc[records["action_taken_clean"].eq("Case referred to partner agencies"), "referral_status"] = "Referred to partner agency"
    records.loc[
        records["action_taken_clean"].eq("Case not referred to any partner BUT information counselling provided"),
        "referral_status",
    ] = "Information counselling only"
    records.loc[records["action_taken_clean"].eq("Action not taken at all"), "referral_status"] = "No action taken"

    # CRITICAL WORKAROUND: Instead of hard-failing and stopping the dashboard, 
    # we dynamically fall back to raw data if required fields aren't 100% matched,
    # or print a diagnostic expander so the user can immediately see what failed to map.
    core_fields = ["interview_date", "information_seeker_type", "camp_location", "information_seeker_gender", "age_group", "request_category"]
    for col in core_fields:
        if col not in records.columns:
            records[col] = pd.NA

    valid_core_mask = records[core_fields].notna().all(axis=1)
    if not valid_core_mask.any():
        missing_summary = records[core_fields].isna().sum().reset_index()
        missing_summary.columns = ["Required field", "Missing rows"]
        
        # Friendly Diagnostic Warning Screen
        st.error(
            "⚠️ Kobo data was received, but no rows had all required dashboard fields. "
            "Below is a diagnostic panel showing which required variables failed to map from your Kobo database. "
            "Please check the 'Available Kobo columns' panel below to verify question names."
        )
        st.dataframe(missing_summary, use_container_width=True, hide_index=True)
        
        # Display sample data to help user inspect
        st.markdown("### Sample Row Received from Kobo (Raw Columns):")
        st.dataframe(records.head(5), use_container_width=True)

        with st.expander("Available Kobo columns"):
            st.write(sorted(records.columns.tolist()))
        st.stop()

    records = records[valid_core_mask].copy()
    id_cols = [col for col in CORE_RECORD_COLUMNS if col in records.columns]
    protection_cols = [col for col in records.columns if col.startswith("concern_") and not col.endswith("_specify")]
    information_cols = [col for col in records.columns if col.startswith("info_") and not col.endswith("_specify")]
    referral_cols = [col for col in records.columns if col.startswith("ref_partner_") and not col.endswith("_specify")]
    protection_label_map = build_label_map(mapping, "concern_")
    information_label_map = build_label_map(mapping, "info_")
    referral_label_map = build_label_map(mapping, "ref_partner_")

    def melt_selected(cols, code_name, label_name, label_map):
        if not cols:
            return pd.DataFrame(columns=id_cols + [code_name, label_name])
        long = records[id_cols + cols].melt(id_vars=id_cols, value_vars=cols, var_name=code_name, value_name="selected")
        long = long[long["selected"].map(is_selected_indicator)].drop(columns="selected")
        long[label_name] = long[code_name].map(label_map).fillna(long[code_name].map(safe_label_from_code))
        return long

    protection = melt_selected(protection_cols, "protection_concern_code", "protection_concern", protection_label_map)
    information = melt_selected(information_cols, "general_information_code", "general_information_need", information_label_map)
    referrals = melt_selected(referral_cols, "referral_partner_code", "referral_partner", referral_label_map)

    main_protection_labels = [
        value for value in protection_label_map.values()
        if value and normalize_response(value) not in ["other", "other not listed", "others", "other specify"]
    ]
    main_information_labels = [
        value for value in information_label_map.values()
        if value and normalize_response(value) not in ["other", "other not listed", "others", "other specify"]
    ]

    if not protection.empty and "concern_other_specify" in records.columns:
        concern_specify_values = records.set_index("record_id")["concern_other_specify"].to_dict()
        concern_other_mask = protection["protection_concern_code"].astype(str).eq("concern_other_not_listed")
        protection.loc[concern_other_mask, "protection_concern"] = protection.loc[
            concern_other_mask, "record_id"
        ].map(
            lambda record_id: harmonize_free_text(
                clean_text(concern_specify_values.get(record_id)),
                main_protection_labels,
                default="Other Not Listed",
            )
        )

    if not information.empty and "info_other_specify" in records.columns:
        info_specify_values = records.set_index("record_id")["info_other_specify"].to_dict()
        info_other_mask = information["general_information_code"].astype(str).eq("info_other_not_listed")
        information.loc[info_other_mask, "general_information_need"] = information.loc[
            info_other_mask, "record_id"
        ].map(
            lambda record_id: harmonize_free_text(
                clean_text(info_specify_values.get(record_id)),
                main_information_labels,
                default="Other Not Listed",
            )
        )

    main_referral_labels = [
        value for value in referral_label_map.values()
        if value and organization_match_key(value) not in ["other", "other not listed", "others", "other specify"]
    ]
    if not referrals.empty and "ref_partner_other_specify" in records.columns:
        referral_specify_values = records.set_index("record_id")["ref_partner_other_specify"].to_dict()
        referral_other_mask = referrals["referral_partner_code"].astype(str).str.contains(
            r"^ref_partner_.*other",
            case=False,
            na=False,
            regex=True,
        )
        referrals.loc[referral_other_mask, "referral_partner"] = referrals.loc[
            referral_other_mask, "record_id"
        ].map(
            lambda record_id: harmonize_organization_text(
                clean_text(referral_specify_values.get(record_id)),
                main_referral_labels,
                default="OTHER NOT LISTED",
            )
        )
        referrals.loc[referral_other_mask, "referral_partner_other_specify_raw"] = referrals.loc[
            referral_other_mask, "record_id"
        ].map(referral_specify_values)
        referrals.loc[referral_other_mask, "referral_partner_harmonized_from_other"] = True
        referrals["referral_partner_harmonized_from_other"] = referrals[
            "referral_partner_harmonized_from_other"
        ].fillna(False)

    if not referrals.empty and "referral_partner" in referrals.columns:
        referrals["referral_partner"] = referrals["referral_partner"].map(normalize_organization_label)

    secure_records = records.copy()
    dashboard_records = records.drop(columns=[col for col in PII_COLUMNS if col in records.columns], errors="ignore")
    
    kpis = pd.DataFrame(
        {
            "metric": [
                "valid_dashboard_records",
                "protection_concern_records",
                "general_information_records",
                "partner_referral_records",
                "follow_up_required_records",
                "mapped_gps_records",
                "staff_recorded_records",
                "disability_records",
                "adult_disability_records",
                "child_disability_records",
                "adult_multiple_impairment_records",
                "gender_age_corrected_records",
                "type_age_corrected_records",
            ],
            "value": [
                len(dashboard_records),
                dashboard_records["request_category"].eq("Reporting a protection concern").sum(),
                dashboard_records["request_category"].eq("Seeking general protection information").sum(),
                dashboard_records["referral_status"].eq("Referred to partner agency").sum(),
                dashboard_records["follow_up_required_clean"].eq("Yes").sum(),
                dashboard_records[["gps_latitude", "gps_longitude"]].notna().all(axis=1).sum(),
                dashboard_records["staff_name"].ne("[Not recorded]").sum(),
                dashboard_records["disability_status"].eq("Has Disability").sum(),
                dashboard_records["adult_wgq_disability_status"].eq("Has Disability").sum(),
                dashboard_records["child_disability_status"].eq("Has Disability").sum(),
                dashboard_records["adult_wgq_multiplicity"].eq("Multiple Impairments").sum(),
                dashboard_records["gender_age_correction_flag"].sum(),
                dashboard_records["type_age_correction_flag"].sum(),
            ],
        }
    )
    return (dashboard_records, secure_records, protection, information, referrals, kpis)

# -----------------------------------------------------------------------------
# Filter, chart, table, and UI helpers
# -----------------------------------------------------------------------------
def filter_options_with_counts(series, ordered_values=None):
    if series.empty:
        return []
    counts = series.dropna().astype(str).value_counts()
    if ordered_values:
        ordered = [(v, int(counts.get(v, 0))) for v in ordered_values if v in counts]
        remaining = sorted([(v, int(counts.get(v, 0))) for v in counts.index if v not in ordered_values], key=lambda x: x[1], reverse=True)
        return ordered + remaining
    return [(v, int(counts.get(v, 0))) for v in counts.index]

def sanitize_multiselect_state(key, options):
    current = st.session_state.get(key, [])
    cleaned = [value for value in current if value in set(options)]
    if cleaned != current:
        st.session_state[key] = cleaned

def reset_filters(default_from_date, max_date):
    st.session_state["from_date_filter"] = default_from_date
    st.session_state["to_date_filter"] = max_date
    for key in FILTER_KEYS:
        st.session_state[key] = []
    st.session_state["records_search"] = ""

def apply_filters(frame, filters):
    filtered = frame.copy()
    if "interview_date" in filtered.columns:
        start_date = filters["start_date"]
        end_exclusive = filters["end_date"] + pd.Timedelta(days=1)
        filtered = filtered[filtered["interview_date"].ge(start_date) & filtered["interview_date"].lt(end_exclusive)]
    for column, selected in [
        ("camp_location", filters["camp_location"]),
        ("helpdesk_location", filters["helpdesk_location"]),
        ("information_seeker_type", filters["information_seeker_type"]),
        ("information_seeker_gender", filters["information_seeker_gender"]),
        ("age_group", filters["age_group"]),
        ("request_category", filters["request_category"]),
    ]:
        if selected and column in filtered.columns:
            filtered = filtered[filtered[column].astype(str).isin(selected)]
    return filtered

def gender_color(field, available=None):
    available = [gender for gender in (available or GENDER_ORDER) if gender in GENDER_COLORS]
    return alt.Color(
        field,
        title="Gender",
        scale=alt.Scale(domain=available, range=[GENDER_COLORS[g] for g in available]),
        sort=available,
    )

def polish_chart(chart):
    return (
        chart.configure_axis(labelColor="#334155", titleColor="#1E293B", gridColor="#E2E8F0", domainColor="#CBD5D1", tickColor="#CBD5D1", labelFontSize=12, titleFontSize=13, titleFontWeight=600, labelLimit=1000)
        .configure_legend(labelColor="#1E293B", titleColor="#1E293B", labelFontSize=12, titleFontSize=13, titleFontWeight=600, orient="bottom", symbolType="circle", symbolSize=120)
        .configure_view(strokeWidth=0)
        .configure(background="transparent", font="Inter, Segoe UI, system-ui, sans-serif")
    )

def gender_pivot_table(frame, category_column, category_label, top_n=None):
    if frame.empty or category_column not in frame.columns:
        return pd.DataFrame()
    table = frame.groupby([category_column, "information_seeker_gender"], dropna=False).size().reset_index(name="records")
    if top_n:
        top_values = table.groupby(category_column)["records"].sum().sort_values(ascending=False).head(top_n).index
        table = table[table[category_column].isin(top_values)]
    pivot = table.pivot_table(index=category_column, columns="information_seeker_gender", values="records", aggfunc="sum", fill_value=0)
    pivot["Total"] = pivot.sum(axis=1)
    pivot = pivot.reset_index().rename(columns={category_column: category_label})
    ordered_columns = [category_label] + [g for g in GENDER_ORDER if g in pivot.columns]
    ordered_columns += [col for col in pivot.columns if col not in ordered_columns and col != "Total"] + ["Total"]
    pivot = pivot[ordered_columns]
    if category_column == "age_group":
        age_order_map = {age: index for index, age in enumerate(AGE_GROUP_ORDER)}
        pivot["_sort_order"] = pivot[category_label].map(age_order_map).fillna(999)
        pivot = pivot.sort_values("_sort_order").drop(columns="_sort_order")
    else:
        pivot = pivot.sort_values("Total", ascending=False)
    numeric_columns = [col for col in pivot.columns if col != category_label]
    total_row = {category_label: "Total"}
    for col in numeric_columns:
        total_row[col] = pivot[col].sum()
    return pd.concat([pivot, pd.DataFrame([total_row])], ignore_index=True)

def style_total_table(table, label_column):
    numeric_columns = [col for col in table.columns if col != label_column]
    def highlight_total_row(row):
        if row[label_column] == "Total":
            return ["background-color: #DDEDE5; color: #102A2A; font-weight: 800;" for _ in row]
        background = "#FFFFFF" if row.name % 2 == 0 else "#F7FAF8"
        return [f"background-color: {background};" for _ in row]

    def highlight_total_column(column):
        if column.name == "Total":
            return ["background-color: #FFF4D8; color: #102A2A; font-weight: 800;" for _ in column]
        return ["" for _ in column]

    return (
        table.style.format({col: "{:,.0f}" for col in numeric_columns})
        .apply(highlight_total_row, axis=1)
        .apply(highlight_total_column, axis=0)
        .set_properties(subset=[label_column], **{"text-align": "left", "font-weight": "650", "white-space": "normal"})
        .set_properties(subset=numeric_columns, **{"text-align": "center", "font-variant-numeric": "tabular-nums"})
        .set_table_styles([
            {"selector": "th", "props": [("background-color", "#12312F"), ("color", "#FFFFFF"), ("font-weight", "800"), ("text-align", "center"), ("border", "1px solid #D8E2DC")]},
            {"selector": "td", "props": [("border", "1px solid #E5E7EB"), ("padding", "7px 9px")]},
        ])
    )

def style_records_table(table):
    display_table = table.copy()
    date_columns = [col for col in display_table.columns if "date" in col.lower()]
    numeric_columns = display_table.select_dtypes(include="number").columns.tolist()
    gps_columns = [col for col in display_table.columns if col in ["gps_latitude", "gps_longitude", "lat", "lon"]]
    formatters = {col: (lambda value: "" if pd.isna(value) else pd.to_datetime(value).strftime("%d %b %Y")) for col in date_columns}
    for col in numeric_columns:
        if col in gps_columns:
            formatters[col] = "{:,.6f}"
        elif "percentage" in str(col).lower():
            formatters[col] = "{:,.1f}"
        else:
            formatters[col] = "{:,.0f}"

    def zebra_rows(row):
        background = "#FFFFFF" if row.name % 2 == 0 else "#F7FAF8"
        return [f"background-color: {background};" for _ in row]

    return (
        display_table.style.format(formatters)
        .apply(zebra_rows, axis=1)
        .set_properties(**{"border": "1px solid #E5E7EB", "padding": "7px 9px", "white-space": "normal"})
        .set_table_styles([{"selector": "th", "props": [("background-color", "#12312F"), ("color", "#FFFFFF"), ("font-weight", "800"), ("text-align", "left"), ("border", "1px solid #D8E2DC")]}])
    )

def show_gender_table(frame, category_column, category_label, top_n=None):
    table = gender_pivot_table(frame, category_column, category_label, top_n=top_n)
    if table.empty:
        st.info("No records match the selected filters.")
        return
    st.dataframe(style_total_table(table, category_label), use_container_width=True, hide_index=True)

def gender_wide_chart_data(frame, category_column, top_n=None, ascending=False):
    table = gender_pivot_table(frame, category_column, category_column, top_n=None)
    if table.empty:
        return pd.DataFrame()
    table = table[table[category_column] != "Total"]
    if top_n:
        gender_cols = [col for col in table.columns if col != category_column]
        table["_total"] = table[gender_cols].sum(axis=1)
        table = table.nsmallest(top_n, "_total") if ascending else table.nlargest(top_n, "_total")
        table = table.drop(columns="_total")
    chart_data = table.set_index(category_column)
    if "Total" in chart_data.columns:
        chart_data = chart_data.drop(columns="Total")
    return chart_data

def draw_gender_bar(frame, category_column, top_n=None, height=430, ascending=False):
    chart_data = gender_wide_chart_data(frame, category_column, top_n=top_n, ascending=ascending)
    if chart_data.empty:
        st.info("No records match the selected filters.")
        return
    chart_data = chart_data.reset_index()
    gender_columns = [col for col in chart_data.columns if col != category_column]
    totals = chart_data.assign(_total=chart_data[gender_columns].sum(axis=1))
    category_order = totals.sort_values("_total", ascending=ascending)[category_column].astype(str).tolist()
    long_chart = chart_data.melt(id_vars=[category_column], value_vars=gender_columns, var_name="Gender", value_name="Records")
    chart_height = max(height, min(900, 36 * len(category_order) + 80))
    chart = (
        alt.Chart(long_chart)
        .mark_bar(cornerRadiusEnd=2, stroke="#FFFFFF", strokeWidth=0.5)
        .encode(
            y=alt.Y(f"{category_column}:N", sort=category_order, title=None, axis=alt.Axis(labelLimit=700, labelFontSize=11, labelPadding=6)),
            x=alt.X("Records:Q", title="Records", stack="zero"),
            color=gender_color("Gender:N"),
            tooltip=[alt.Tooltip(f"{category_column}:N", title="Category"), alt.Tooltip("Gender:N", title="Gender"), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Records:Q", title="Records", format=",")],
        )
        .properties(height=chart_height)
    )
    st.altair_chart(polish_chart(chart), use_container_width=True)

def draw_gender_column_bar(frame, category_column, top_n=None, height=360):
    chart_data = gender_wide_chart_data(frame, category_column, top_n=top_n)
    if chart_data.empty:
        st.info("No records match the selected filters.")
        return
    chart_data = chart_data.reset_index()
    gender_columns = [col for col in chart_data.columns if col != category_column]
    category_order = chart_data.assign(Total=chart_data[gender_columns].sum(axis=1)).sort_values("Total", ascending=False)[category_column].astype(str).tolist()
    max_chars = 18 if category_column in ["age_group", "helpdesk_location"] else 24
    chart_data["axis_label"] = chart_data[category_column].map(lambda value: short_axis_label(value, max_chars=max_chars))
    axis_order = [chart_data.loc[chart_data[category_column].astype(str).eq(value), "axis_label"].iloc[0] for value in category_order if not chart_data.loc[chart_data[category_column].astype(str).eq(value)].empty]
    long_chart = chart_data.melt(id_vars=[category_column, "axis_label"], value_vars=gender_columns, var_name="Gender", value_name="Records")
    chart = (
        alt.Chart(long_chart)
        .mark_bar(cornerRadiusEnd=2, stroke="#FFFFFF", strokeWidth=0.5)
        .encode(
            x=alt.X("axis_label:N", sort=axis_order, title=None, axis=alt.Axis(labelAngle=-30, labelLimit=150, labelFontSize=10)),
            y=alt.Y("Records:Q", title="Records", stack="zero"),
            color=gender_color("Gender:N"),
            tooltip=[alt.Tooltip(f"{category_column}:N", title="Category"), alt.Tooltip("Gender:N", title="Gender"), alt.Tooltip("Records:Q", title="Records", format=",")],
        )
        .properties(height=height)
    )
    st.altair_chart(polish_chart(chart), use_container_width=True)

def draw_total_donut(frame, category_column, category_label, height=320, min_label_share=0.04):
    if frame.empty or category_column not in frame.columns:
        st.info("No records match the selected filters.")
        return
    summary = frame.groupby(category_column, dropna=False).size().reset_index(name="Records").sort_values("Records", ascending=False)
    if summary.empty or summary["Records"].sum() == 0:
        st.info("No summary data for the selected filters.")
        return
    summary[category_column] = summary[category_column].fillna("[Missing]").astype(str)
    summary["Share"] = summary["Records"] / summary["Records"].sum()
    summary["Share label"] = summary["Share"].map(lambda value: f"{value:.1%}" if value >= min_label_share else "")
    donut = (
        alt.Chart(summary)
        .mark_arc(innerRadius=72, outerRadius=120, stroke="#FFFFFF", strokeWidth=2)
        .encode(
            theta=alt.Theta("Records:Q", stack=True),
            color=alt.Color(f"{category_column}:N", title=category_label, scale=alt.Scale(range=["#2F7D69", "#D9A441", "#2563EB", "#DB2777", "#7C3AED", "#64748B"])),
            tooltip=[alt.Tooltip(f"{category_column}:N", title=category_label), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Share:Q", title="Share", format=".1%")],
        )
    )
    labels = alt.Chart(summary[summary["Share label"].ne("")]).mark_text(radius=145, fontSize=12, fontWeight=700, color="#334155").encode(theta=alt.Theta("Records:Q", stack=True), text=alt.Text("Share label:N"))
    st.altair_chart(polish_chart((donut + labels).properties(height=height)), use_container_width=True)

def draw_request_type_bar(frame, height=190):
    if frame.empty or "request_category" not in frame.columns:
        st.info("No records match the selected filters.")
        return
    summary = (
        frame.groupby("request_category", dropna=False)
        .size()
        .reset_index(name="Records")
        .sort_values("Records", ascending=False)
    )
    if summary.empty or summary["Records"].sum() == 0:
        st.info("No request type data for the selected filters.")
        return
    display_labels = {
        "Reporting a protection concern": "Protection concern",
        "Seeking general protection information": "General information",
    }
    summary["request_category"] = summary["request_category"].fillna("[Missing]").astype(str)
    summary["Request type"] = summary["request_category"].replace(display_labels)
    summary["Share"] = summary["Records"] / summary["Records"].sum()
    summary["Label"] = summary.apply(
        lambda row: f"{row['Records']:,.0f} ({row['Share']:.1%})",
        axis=1,
    )
    type_order = summary["Request type"].tolist()
    type_colors = ["#2F7D69", "#D9A441", "#2563EB", "#DB2777", "#64748B"]
    base = alt.Chart(summary).encode(
        y=alt.Y(
            "Request type:N",
            sort=type_order,
            title=None,
            axis=alt.Axis(labelLimit=360, labelFontSize=12, labelPadding=8),
        ),
        x=alt.X("Records:Q", title="Records"),
    )
    bars = base.mark_bar(cornerRadiusEnd=4).encode(
        color=alt.Color(
            "Request type:N",
            legend=None,
            scale=alt.Scale(domain=type_order, range=type_colors[: len(type_order)]),
        ),
        tooltip=[
            alt.Tooltip("Request type:N", title="Request type"),
            alt.Tooltip("Records:Q", title="Records", format=","),
            alt.Tooltip("Share:Q", title="Share", format=".1%"),
        ],
    )
    labels = base.mark_text(
        align="left",
        baseline="middle",
        dx=8,
        fontSize=12,
        fontWeight=800,
        color="#1E293B",
    ).encode(
        text=alt.Text("Label:N"),
    )
    st.altair_chart(polish_chart((bars + labels).properties(height=height)), use_container_width=True)

def draw_status_donut_pair(frame, status_column, height=300):
    if frame.empty or status_column not in frame.columns:
        st.info("No records match the selected filters.")
        return
    status_cols = st.columns(2)
    for column, status in zip(status_cols, ["No Disability", "Has Disability"]):
        with column:
            st.caption(status)
            status_frame = frame[frame[status_column].astype(str).eq(status)]
            draw_total_donut(status_frame, "information_seeker_gender", "Gender", height=height, min_label_share=0.06)

def draw_monthly_gender_column_bar(frame, height=340):
    if frame.empty:
        st.info("No records match the selected filters.")
        return
    monthly = (
        frame.groupby(["year_month", "information_seeker_gender"], dropna=False)
        .size()
        .reset_index(name="Records")
    )
    if monthly.empty:
        st.info("No monthly trend data for the selected filters.")
        return
    monthly["information_seeker_gender"] = monthly["information_seeker_gender"].fillna("[Missing]").astype(str)
    available_genders = [
        gender
        for gender in GENDER_ORDER
        if gender in set(monthly["information_seeker_gender"].tolist())
    ]
    month_order = sorted(monthly["year_month"].dropna().astype(str).unique().tolist())
    line = (
        alt.Chart(monthly)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("year_month:N", sort=month_order, title=None, axis=alt.Axis(labelAngle=-30, labelFontSize=11)),
            y=alt.Y("Records:Q", title="Records"),
            color=gender_color("information_seeker_gender:N", available=available_genders),
            tooltip=[
                alt.Tooltip("year_month:N", title="Month"),
                alt.Tooltip("information_seeker_gender:N", title="Gender"),
                alt.Tooltip("Records:Q", title="Records", format=","),
            ],
        )
        .properties(height=height)
    )
    st.altair_chart(polish_chart(line), use_container_width=True)

def draw_count_bar(frame, category_column, category_label, height=360):
    if frame.empty or category_column not in frame.columns:
        st.info("No records match the selected filters.")
        return
    chart_data = frame.groupby(category_column, dropna=False).size().reset_index(name="Records").rename(columns={category_column: category_label}).sort_values("Records", ascending=False)
    chart_data["axis_label"] = chart_data[category_label].map(lambda value: short_axis_label(value, max_chars=24))
    axis_order = chart_data["axis_label"].tolist()
    base = alt.Chart(chart_data).encode(x=alt.X("axis_label:N", sort=axis_order, title=None, axis=alt.Axis(labelAngle=-30, labelLimit=160, labelFontSize=11)), y=alt.Y("Records:Q", title="Records"))
    bars = base.mark_bar(cornerRadiusEnd=3, color="#2F7D69").encode(tooltip=[alt.Tooltip(f"{category_label}:N", title=category_label), alt.Tooltip("Records:Q", title="Records", format=",")])
    labels = base.mark_text(dy=-6, fontSize=11, fontWeight=700, color="#1E293B").encode(text=alt.Text("Records:Q", format=","))
    st.altair_chart(polish_chart((bars + labels).properties(height=height)), use_container_width=True)

def basic_count_table(frame, category_column, category_label):
    if frame.empty or category_column not in frame.columns:
        return pd.DataFrame()
    table = frame.groupby(category_column, dropna=False).size().reset_index(name="Records").rename(columns={category_column: category_label}).sort_values("Records", ascending=False)
    total = pd.DataFrame([{category_label: "Total", "Records": table["Records"].sum()}])
    return pd.concat([table, total], ignore_index=True)

def multi_choice_selector(label, options, key, help_text=None):
    options = list(options)
    if not options:
        st.session_state[key] = []
        st.caption(f"No {label.lower()} options available.")
        return []
    sanitize_multiselect_state(key, options)
    if hasattr(st, "pills"):
        try:
            selected = st.pills(label, options=options, selection_mode="multi", key=key, help=help_text)
            return selected or []
        except Exception:
            pass
    return st.multiselect(label, options=options, key=key, help=help_text)

def filter_label(values, max_items=3):
    if not values:
        return "All"
    values = list(values)
    shown = values[:max_items]
    suffix = "" if len(values) <= max_items else f" +{len(values) - max_items} more"
    return ", ".join(shown) + suffix

def selection_pill(label, values):
    return '<div class="app-pill app-pill-filter">' f'<span class="pill-key">{escape_text(label)}</span>' f'<span class="pill-val">{escape_text(filter_label(values))}</span>' "</div>"

def section_header(title, note=None):
    st.markdown(f"""<div class="section-header"><span class="section-accent"></span><span class="section-title">{escape_text(title)}</span></div>""", unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="section-note">{escape_text(note)}</div>', unsafe_allow_html=True)

def kpi_group_caption(text):
    st.markdown(f'<div class="kpi-group-caption">{escape_text(text)}</div>', unsafe_allow_html=True)

def show_kpi_card(column, label, value, context, share=None, accent="var(--accent-base)"):
    bar_html = ""
    if share is not None:
        pct = max(0.0, min(100.0, float(share) * 100.0))
        bar_html = f'<div class="kpi-bar" role="img" aria-label="{pct:.0f} percent"><div class="kpi-bar-fill" style="width:{pct:.1f}%;"></div></div>'
    with column:
        st.markdown(
            f"""
            <div class="kpi-card" style="--accent:{accent};" role="group" aria-label="{escape_text(label)}: {escape_text(value)}. {escape_text(context)}">
                <div class="kpi-label">{escape_text(label)}</div>
                <div class="kpi-value">{escape_text(value)}</div>
                <div class="kpi-context">{escape_text(context)}</div>
                {bar_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

def show_insight_card(column, label, value, detail, icon="", count=None):
    icon_html = f'<span class="insight-icon">{escape_text(icon)}</span>' if icon else ""
    suppressed = count is not None and 0 < count < SMALL_N_THRESHOLD
    if suppressed:
        value_html = '<div class="insight-value insight-suppressed">Suppressed</div>'
        detail_html = f'<div class="insight-detail insight-suppressed-note">&#9888; Fewer than {SMALL_N_THRESHOLD} records &mdash; hidden to protect identity</div>'
    else:
        value_html = f'<div class="insight-value">{escape_text(value)}</div>'
        detail_html = f'<div class="insight-detail">{escape_text(detail)}</div>'
    with column:
        st.markdown(f"""<div class="insight-card"><div class="insight-head">{icon_html}<div class="insight-label">{escape_text(label)}</div></div>{value_html}{detail_html}</div>""", unsafe_allow_html=True)

def top_value(frame, column):
    if frame.empty or column not in frame.columns:
        return "None", 0
    counts = frame[column].dropna().astype(str).value_counts()
    if counts.empty:
        return "None", 0
    return counts.index[0], int(counts.iloc[0])

def insight_detail(count, denominator, unit="records", denom_label="total"):
    if denominator:
        return f"{format_number(count)} {unit} ({format_rate(count, denominator)} of {denom_label})"
    return f"{format_number(count)} {unit}"

def encode_image_data_uri(path_str, mtime):
    path = Path(path_str)
    if not path.exists():
        return None
    suffix = path.suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else f"image/{suffix or 'png'}"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"

def tdh_logo_html():
    if not LOGO_PATH.exists():
        return ""
    data_uri = encode_image_data_uri(str(LOGO_PATH), LOGO_PATH.stat().st_mtime_ns)
    return f'<img class="app-header-logo" src="{data_uri}" alt="Tdh logo" />' if data_uri else ""

def resolve_developer_logo():
    if DEVELOPER_LOGO_PATH.exists():
        return DEVELOPER_LOGO_PATH
    assets_dir = DEVELOPER_LOGO_PATH.parent
    if not assets_dir.exists():
        return None
    for candidate in sorted(assets_dir.iterdir()):
        if candidate.is_file() and candidate.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"} and candidate.stem.lower() == "developer-logo":
            return candidate
    return None

def developer_logo_html():
    logo_path = resolve_developer_logo()
    if logo_path is None:
        return ""
    data_uri = encode_image_data_uri(str(logo_path), logo_path.stat().st_mtime_ns)
    return f'<img class="developer-logo" src="{data_uri}" alt="Developer logo" />' if data_uri else ""

def show_footer():
    st.markdown(
        f"""
        <div class="developer-footer">
            <div class="developer-brand">
                {developer_logo_html()}
                <div><div class="developer-brand-name">ImpactLens Africa</div><div class="developer-brand-tagline">Turning Data Into Human Impact</div></div>
            </div>
            <div class="developer-credit"><div>Developed by <strong>John Kul</strong>, MEAL Officer-Tdh</div><div class="developer-version">{APP_VERSION} &middot; {APP_VERSION_DATE}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def search_records(frame, query):
    if not query:
        return frame
    searchable = frame.copy()
    mask = pd.Series(False, index=searchable.index)
    for column in searchable.columns:
        mask = mask | searchable[column].astype(str).str.contains(query, case=False, regex=False, na=False)
    return searchable[mask]

def configured_pii_password():
    try:
        password = st.secrets.get("DQA_PII_PASSWORD", None)
        if password:
            return str(password)
    except Exception:
        pass
    return os.environ.get("DQA_PII_PASSWORD")

def pii_access_granted(key="pii_access_password"):
    password = configured_pii_password()
    if not password:
        st.warning(
            "PII table is locked. Configure DQA_PII_PASSWORD in Streamlit secrets "
            "or as an environment variable to enable access."
        )
        st.code('DQA_PII_PASSWORD = "your-strong-password"', language="toml")
        return False
    granted_key = f"{key}_granted"
    if st.session_state.get(granted_key):
        return True
    entered = st.text_input(
        "Enter password to unlock PII table",
        type="password",
        key=key,
        help="This protects visibility in the app UI. It is not a substitute for server-level access control.",
    )
    if entered:
        if entered == password:
            st.session_state[granted_key] = True
            st.success("PII table unlocked for this session.")
            return True
        st.error("Incorrect password.")
    return False

def education_concern_followup_table(frame, referrals_frame):
    concern_cols = [
        "concern_educational_support",
        "concern_school_dropout_risk_or_dropped_out",
    ]
    available_concern_cols = [col for col in concern_cols if col in frame.columns]
    output_columns = [
        "record_id",
        "interview_date",
        "staff_name",
        "information_seeker_name",
        "information_seeker_individual_number",
        "information_seeker_phone",
        "alternative_phone",
        "camp_location",
        "helpdesk_camp_location",
        "helpdesk_village",
        "helpdesk_section_block",
        "residence_neighborhood_compound_house",
        "education_concern_selected",
        "referred_agency",
        "referral_status",
        "follow_up_required_clean",
    ]
    if frame.empty or not available_concern_cols:
        return pd.DataFrame(columns=output_columns)
    working = frame.copy()
    concern_mask = pd.Series(False, index=working.index)
    for col in available_concern_cols:
        concern_mask = concern_mask | pd.to_numeric(working[col], errors="coerce").eq(1)
    working = working[concern_mask].copy()
    if working.empty:
        return pd.DataFrame(columns=output_columns)

    def selected_concern_labels(row):
        labels = []
        if "concern_educational_support" in row.index:
            if pd.to_numeric(pd.Series([row.get("concern_educational_support")]), errors="coerce").iloc[0] == 1:
                labels.append("Educational Support")
        if "concern_school_dropout_risk_or_dropped_out" in row.index:
            if pd.to_numeric(pd.Series([row.get("concern_school_dropout_risk_or_dropped_out")]), errors="coerce").iloc[0] == 1:
                labels.append("School Dropout Risk / Dropped Out")
        return "; ".join(labels)

    working["education_concern_selected"] = working.apply(selected_concern_labels, axis=1)
    if not referrals_frame.empty and {"record_id", "referral_partner"}.issubset(referrals_frame.columns):
        referral_lookup = (
            referrals_frame.dropna(subset=["referral_partner"])
            .groupby("record_id")["referral_partner"]
            .apply(lambda values: "; ".join(sorted(set(str(value) for value in values if str(value).strip()))))
            .reset_index(name="referred_agency")
        )
        working = working.merge(referral_lookup, on="record_id", how="left")
    else:
        working["referred_agency"] = pd.NA
    for col in output_columns:
        if col not in working.columns:
            working[col] = pd.NA
    return working[output_columns].sort_values(["interview_date", "staff_name"], ascending=[False, True])

def map_data(frame):
    if frame.empty or not {"gps_latitude", "gps_longitude"}.issubset(frame.columns):
        return pd.DataFrame()
    mapped = frame.dropna(subset=["gps_latitude", "gps_longitude"]).copy()
    mapped = mapped[mapped["gps_latitude"].between(-90, 90) & mapped["gps_longitude"].between(-180, 180)]
    if mapped.empty:
        return pd.DataFrame()
    return mapped.rename(columns={"gps_latitude": "lat", "gps_longitude": "lon"})

def cpv_work_summary(frame):
    columns = ["CPV", "Records", "Protection concerns", "Information requests", "Partner referrals", "Follow-up required", "Disability records", "Mapped records", "Helpdesk locations", "First interview date", "Latest interview date"]
    if frame.empty or "staff_name" not in frame.columns:
        return pd.DataFrame(columns=columns)
    rows = []
    work = frame.copy()
    work["staff_name"] = work["staff_name"].map(normalize_staff_name)
    for staff_name, group in work.groupby("staff_name", dropna=False):
        if str(staff_name) == "[Not recorded]":
            continue
        mapped_count = int(group[["gps_latitude", "gps_longitude"]].notna().all(axis=1).sum()) if {"gps_latitude", "gps_longitude"}.issubset(group.columns) else 0
        helpdesk_locations = int(group["helpdesk_location"].replace("[Not recorded]", pd.NA).dropna().astype(str).nunique()) if "helpdesk_location" in group.columns else 0
        rows.append(
            {
                "CPV": staff_name,
                "Records": len(group),
                "Protection concerns": int(group["request_category"].astype(str).eq("Reporting a protection concern").sum()),
                "Information requests": int(group["request_category"].astype(str).eq("Seeking general protection information").sum()),
                "Partner referrals": int(group["referral_status"].astype(str).eq("Referred to partner agency").sum()),
                "Follow-up required": int(group["follow_up_required_clean"].astype(str).eq("Yes").sum()),
                "Disability records": int(group["disability_status"].astype(str).eq("Has Disability").sum()),
                "Mapped records": mapped_count,
                "Helpdesk locations": helpdesk_locations,
                "First interview date": group["interview_date"].min() if "interview_date" in group.columns else pd.NaT,
                "Latest interview date": group["interview_date"].max() if "interview_date" in group.columns else pd.NaT,
            }
        )
    return pd.DataFrame(rows).sort_values("Records", ascending=False) if rows else pd.DataFrame(columns=columns)

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
load_css()
source_signature = data_source_signature()
records, secure_records, protection, information, referrals, kpis = load_data(source_signature)
if records.empty:
    st.error("No valid dashboard records were found in the source file.")
    st.stop()

min_date = records["interview_date"].min().date()
max_date = records["interview_date"].max().date()
default_from_date = min_date
calendar_min_date = pd.Timestamp(year=min_date.year, month=1, day=1).date()
calendar_max_date = pd.Timestamp(year=max_date.year, month=12, day=31).date()

if "from_date_filter" not in st.session_state:
    st.session_state["from_date_filter"] = default_from_date
if "to_date_filter" not in st.session_state:
    st.session_state["to_date_filter"] = max_date

with st.sidebar:
    st.header("Filters")
    if st.button("Reset all", use_container_width=True, key="sidebar_reset_all"):
        reset_filters(default_from_date, max_date)
        st.rerun()
    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("↻ Refresh", use_container_width=True, help="Reload latest data from Excel"):
            st.cache_data.clear()
            st.rerun()
    with action_col2:
        st.button("Clear filters", use_container_width=True, on_click=reset_filters, args=(default_from_date, max_date))
    with st.expander("Date range", expanded=True):
        date_cols = st.columns(2)
        with date_cols[0]:
            selected_from_date = st.date_input("From", min_value=calendar_min_date, max_value=calendar_max_date, key="from_date_filter")
        with date_cols[1]:
            selected_to_date = st.date_input("To", min_value=calendar_min_date, max_value=calendar_max_date, key="to_date_filter")
    if selected_from_date > selected_to_date:
        st.error("From date cannot be after To date.")
        st.stop()
    from_date = max(selected_from_date, min_date)
    to_date = min(selected_to_date, max_date)
    start_date = pd.to_datetime(from_date)
    end_date = pd.to_datetime(to_date)
    date_filtered_records = records[records["interview_date"].ge(start_date) & records["interview_date"].lt(end_date + pd.Timedelta(days=1))].copy()

    selected_camp_locations = []
    selected_helpdesk_locations = []
    selected_information_seeker_types = []
    selected_genders = []
    selected_age_groups = []
    selected_request_categories = []

    with st.expander("Location", expanded=True):
        camp_options = [v for v, _ in filter_options_with_counts(date_filtered_records["camp_location"])]
        st.markdown("**Camp location**")
        selected_camp_locations = multi_choice_selector("Camp", camp_options, key="camp_location_filter", help_text="Select one or more camps")
        camp_filtered_records = date_filtered_records[date_filtered_records["camp_location"].astype(str).isin(selected_camp_locations)].copy() if selected_camp_locations else date_filtered_records.copy()
        helpdesk_options = [v for v, _ in filter_options_with_counts(camp_filtered_records["helpdesk_location"])]
        st.markdown("**Helpdesk location**")
        selected_helpdesk_locations = multi_choice_selector("Helpdesk location", helpdesk_options, key="helpdesk_location_filter", help_text="Select helpdesk locations")
    helpdesk_filtered_records = camp_filtered_records[camp_filtered_records["helpdesk_location"].astype(str).isin(selected_helpdesk_locations)].copy() if selected_helpdesk_locations else camp_filtered_records.copy()

    with st.expander("Demographics", expanded=True):
        type_options = [v for v, _ in filter_options_with_counts(helpdesk_filtered_records["information_seeker_type"])]
        selected_information_seeker_types = multi_choice_selector("Information seeker type", type_options, key="information_seeker_type_filter")
        seeker_filtered_records = helpdesk_filtered_records[helpdesk_filtered_records["information_seeker_type"].astype(str).isin(selected_information_seeker_types)].copy() if selected_information_seeker_types else helpdesk_filtered_records.copy()
        gender_options = [v for v, _ in filter_options_with_counts(seeker_filtered_records["information_seeker_gender"], ordered_values=GENDER_ORDER)]
        selected_genders = multi_choice_selector("Gender", gender_options, key="information_seeker_gender_filter")
        gender_filtered_records = seeker_filtered_records[seeker_filtered_records["information_seeker_gender"].astype(str).isin(selected_genders)].copy() if selected_genders else seeker_filtered_records.copy()
        age_options = [v for v, _ in filter_options_with_counts(gender_filtered_records["age_group"], ordered_values=AGE_GROUP_ORDER)]
        selected_age_groups = multi_choice_selector("Age group", age_options, key="age_group_filter")
    age_filtered_records = gender_filtered_records[gender_filtered_records["age_group"].astype(str).isin(selected_age_groups)].copy() if selected_age_groups else gender_filtered_records.copy()

    with st.expander("Request type", expanded=True):
        request_options = [v for v, _ in filter_options_with_counts(age_filtered_records["request_category"])]
        selected_request_categories = multi_choice_selector("Request category", request_options, key="request_category_filter")

filters = {
    "start_date": start_date,
    "end_date": end_date,
    "camp_location": selected_camp_locations,
    "helpdesk_location": selected_helpdesk_locations,
    "information_seeker_type": selected_information_seeker_types,
    "information_seeker_gender": selected_genders,
    "age_group": selected_age_groups,
    "request_category": selected_request_categories,
}

filtered_records = apply_filters(records, filters)
filtered_protection = apply_filters(protection, filters)
filtered_information = apply_filters(information, filters)
filtered_referrals = apply_filters(referrals, filters)

total_records = len(filtered_records)
all_records = len(records)
protection_records = filtered_records["request_category"].eq("Reporting a protection concern").sum()
information_records = filtered_records["request_category"].eq("Seeking general protection information").sum()
partner_referrals = filtered_records["referral_status"].eq("Referred to partner agency").sum()
follow_up = filtered_records["follow_up_required_clean"].eq("Yes").sum()
disability_records = filtered_records["disability_status"].eq("Has Disability").sum()

if "staff_name" in filtered_records.columns:
    harmonized_staff = filtered_records["staff_name"].map(normalize_staff_name)
    staff_no = int(harmonized_staff[harmonized_staff.ne("[Not recorded]")].nunique())
else:
    staff_no = 0

last_updated = source_signature[3] if source_signature[3] else "Unknown"

st.markdown(
    f"""
    <div class="app-header">
        {tdh_logo_html()}
        <div class="app-header-text">
            <div class="app-header-title">Tdh Kenya Helpdesk Data Dashboard</div>
            <div class="app-header-subtitle">Protection helpdesk monitoring &middot; Turkana West & Dadaab</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

selection_pills_html = "".join([
    selection_pill("Camp", selected_camp_locations),
    selection_pill("Helpdesk", selected_helpdesk_locations),
    selection_pill("Gender", selected_genders),
    selection_pill("Age", selected_age_groups),
])

st.markdown(
    f"""
    <div class="app-infobar">
        <div class="app-infobar-row">
            <div class="app-pill">&#128202; {format_number(total_records)} of {format_number(all_records)} records</div>
            <div class="app-pill">&#128197; {escape_text(from_date.strftime('%d %b %Y'))} &ndash; {escape_text(to_date.strftime('%d %b %Y'))}</div>
            <div class="app-pill app-pill-muted">&#128260; Updated {escape_text(last_updated)}</div>
        </div>
        <div class="app-infobar-row"><span class="app-infobar-tag">&#128269; Current selection</span>{selection_pills_html}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

kpi_group_caption("Volume, staffing & request mix — request types are mutually exclusive")
mix_cols = st.columns(4)
show_kpi_card(mix_cols[0], "Staff No.", format_number(staff_no), "Unique harmonized CPVs in current selection", accent="#2F7D69")
show_kpi_card(mix_cols[1], "Valid records", format_number(total_records), f"of {format_number(all_records)} in source", accent="#2F7D69")
show_kpi_card(mix_cols[2], "Protection concerns", format_number(protection_records), f"{format_rate(protection_records, total_records)} of requests", share=safe_share(protection_records, total_records), accent="#2563EB")
show_kpi_card(mix_cols[3], "Information requests", format_number(information_records), f"{format_rate(information_records, total_records)} of requests", share=safe_share(information_records, total_records), accent="#2563EB")

kpi_group_caption("Case outcomes — overlapping subsets of records")
outcome_cols = st.columns(3)
show_kpi_card(outcome_cols[0], "Partner referrals", format_number(partner_referrals), f"{format_rate(partner_referrals, total_records)} of all records", share=safe_share(partner_referrals, total_records), accent="#2F7D69")
show_kpi_card(outcome_cols[1], "Follow-up required", format_number(follow_up), f"{format_rate(follow_up, total_records)} of all records", share=safe_share(follow_up, total_records), accent="#D9A441")
show_kpi_card(outcome_cols[2], "Disability records", format_number(disability_records), f"{format_rate(disability_records, total_records)} of all records", share=safe_share(disability_records, total_records), accent="#7C3AED")

if filtered_records.empty:
    st.info("No records match the selected filters.")
    show_footer()
    st.stop()

# Quick insights
disability_type_records = filtered_records[filtered_records["disability_status"].eq("Has Disability")]
follow_up_records = filtered_records[filtered_records["follow_up_required_clean"].eq("Yes")]
top_location, top_location_count = top_value(filtered_records, "helpdesk_location")
top_concern, top_concern_count = top_value(filtered_protection, "protection_concern")
top_disability, top_disability_count = top_value(disability_type_records, "disability_type")
top_followup_site, top_followup_site_count = top_value(follow_up_records, "helpdesk_location")

section_header("Quick Insights", "Leading categories within each dimension.")
insight_cols = st.columns(4)
show_insight_card(insight_cols[0], "Busiest helpdesk", top_location, insight_detail(top_location_count, total_records, denom_label="all records"), icon="🏢", count=top_location_count)
show_insight_card(insight_cols[1], "Top protection concern", top_concern, insight_detail(top_concern_count, len(filtered_protection), unit="mentions", denom_label="concerns"), icon="🛡️", count=top_concern_count)
show_insight_card(insight_cols[2], "Most common impairment", top_disability, insight_detail(top_disability_count, len(disability_type_records), denom_label="disability records"), icon="♿", count=top_disability_count)
show_insight_card(insight_cols[3], "Most follow-up activity", top_followup_site, insight_detail(top_followup_site_count, len(follow_up_records), unit="follow-ups", denom_label="follow-ups"), icon="🔄", count=top_followup_site_count)

st.divider()
section_header("Explore by Section", "Select a section below to dive into the detailed analysis.")
selected_tab = st.radio("Dashboard section", ["Overview", "Disability", "Concerns", "Information", "Referrals", "Map", "CPV Work", "DQA", "Records"], horizontal=True, label_visibility="collapsed")

# -----------------------------------------------------------------------------
# Overview tab
# -----------------------------------------------------------------------------
if selected_tab == "Overview":
    st.subheader("Monthly Requests by Gender")
    draw_monthly_gender_column_bar(filtered_records, height=390)
    st.subheader("Requests by Type")
    draw_request_type_bar(filtered_records, height=190)
    st.subheader("Request Type Table")
    show_gender_table(filtered_records, "request_category", "Request type")
    st.divider()
    st.subheader("Demographics by gender")
    st.caption("Information seeker type")
    draw_gender_column_bar(filtered_records, "information_seeker_type", height=300)
    show_gender_table(filtered_records, "information_seeker_type", "Information seeker type")
    st.markdown("#### Age group")
    draw_gender_column_bar(filtered_records, "age_group", height=420)
    show_gender_table(filtered_records, "age_group", "Age group")
    st.divider()
    st.subheader("Location by gender")
    st.caption("Camp location")
    draw_gender_column_bar(filtered_records, "camp_location", height=320)
    show_gender_table(filtered_records, "camp_location", "Camp location")
    st.markdown("#### Helpdesk location")
    draw_gender_column_bar(filtered_records, "helpdesk_location", height=460)
    show_gender_table(filtered_records, "helpdesk_location", "Helpdesk location")
    st.divider()
    st.subheader("Overall Disability Status")
    st.markdown('<div class="section-note">Uses "Has Disability / No Disability". Full impairment analysis is available in the Disability tab.</div>', unsafe_allow_html=True)
    draw_status_donut_pair(filtered_records, "disability_status", height=280)
    show_gender_table(filtered_records, "disability_status", "Disability status")

# -----------------------------------------------------------------------------
# Disability tab — ONLY disability data (no "No Disability" rows at all)
# -----------------------------------------------------------------------------
if selected_tab == "Disability":
    st.subheader("Disability Analysis")
    st.markdown(
        '<div class="section-note">This tab shows <strong>only records with disability</strong>. '
        'All "No Disability" values are excluded. Overall prevalence is shown in the Overview tab. '
        'Impairment types are standardized across adults and children.</div>',
        unsafe_allow_html=True,
    )
    disability_only = filtered_records[
        filtered_records["disability_status"].astype(str).eq("Has Disability")
    ].copy()

    non_disability_labels = ["No Disability", "None", "", "[Missing]"]
    if "disability_type" in disability_only.columns:
        disability_only = disability_only[
            ~disability_only["disability_type"].astype(str).isin(non_disability_labels)
        ].copy()

    if disability_only.empty:
        st.info("No disability records match the current filters.")
    else:
        st.caption("Impairment types (all ages with disability)")
        draw_gender_column_bar(disability_only, "disability_type", height=380)
        show_gender_table(
            disability_only,
            "disability_type",
            "Impairment type",
            top_n=None,
        )

    st.divider()
    st.markdown("### Adult Impairment Analysis")
    adult_disability = disability_only[
        disability_only["derived_life_stage"].astype(str).eq("Adult")
    ].copy()
    if not adult_disability.empty:
        adult_person = adult_person_impairment_frame(adult_disability)
        if not adult_person.empty:
            adult_person = adult_person[
                adult_person["adult_disability_status"].astype(str).eq("Has Disability")
            ].copy()
            adult_person = adult_person[
                ~adult_person["adult_person_impairment_type"]
                .astype(str)
                .isin(non_disability_labels)
            ].copy()

        if not adult_person.empty:
            st.caption("Most common impairments among adults with disability")
            draw_gender_column_bar(
                adult_person,
                "adult_person_impairment_type",
                height=360,
            )
            show_gender_table(
                adult_person,
                "adult_person_impairment_type",
                "Adult impairment type",
                top_n=None,
            )
            st.caption("Single vs Multiple Impairments")
            draw_total_donut(
                adult_person,
                "adult_impairment_multiplicity",
                "Number of impairments",
                height=280,
            )
            show_gender_table(
                adult_person,
                "adult_impairment_multiplicity",
                "Number of impairments",
            )
        else:
            st.info("No adult disability records match the current filters.")
    else:
        st.info("No adult disability records match the current filters.")

    st.divider()
    st.markdown("### Child Impairment Analysis")
    child_disability = disability_only[
        disability_only["derived_life_stage"].astype(str).eq("Child")
    ].copy()
    if not child_disability.empty:
        if "child_disability_status" in child_disability.columns:
            child_disability = child_disability[
                child_disability["child_disability_status"].astype(str).eq("Has Disability")
            ].copy()
        if "child_disability_type" in child_disability.columns:
            child_disability = child_disability[
                ~child_disability["child_disability_type"]
                .astype(str)
                .isin(non_disability_labels)
            ].copy()

        if not child_disability.empty:
            st.caption("Most common impairments among children with disability")
            draw_gender_column_bar(
                child_disability,
                "child_disability_type",
                height=340,
            )
            show_gender_table(
                child_disability,
                "child_disability_type",
                "Child impairment type",
                top_n=None,
            )
        else:
            st.info("No child disability records match the current filters.")
    else:
        st.info("No child disability records match the current filters.")

# -----------------------------------------------------------------------------
# Concerns tab
# -----------------------------------------------------------------------------
if selected_tab == "Concerns":
    st.subheader("Top Protection Concerns by gender")
    concern_rank = st.radio("Rank", ["Highest values", "Lowest values"], horizontal=True, index=0, key="concern_rank")
    concern_top_n = st.radio("Number of categories", [5, 10, 15, 20, 25], horizontal=True, index=2, key="concern_top_n")
    draw_gender_bar(filtered_protection, "protection_concern", top_n=concern_top_n, height=640, ascending=concern_rank == "Lowest values")
    st.caption("Full table (all categories, unaffected by chart slicing)")
    show_gender_table(filtered_protection, "protection_concern", "Protection concern", top_n=None)

# -----------------------------------------------------------------------------
# Information tab
# -----------------------------------------------------------------------------
if selected_tab == "Information":
    st.subheader("Top General Information Needs by Gender")
    information_rank = st.radio("Rank", ["Highest values", "Lowest values"], horizontal=True, index=0, key="information_rank")
    information_top_n = st.radio("Number of categories", [5, 10, 15, 20, 25], horizontal=True, index=2, key="information_top_n")
    draw_gender_bar(filtered_information, "general_information_need", top_n=information_top_n, height=640, ascending=information_rank == "Lowest values")
    st.caption("Full table (all categories, unaffected by chart slicing)")
    show_gender_table(filtered_information, "general_information_need", "General information need", top_n=None)

# -----------------------------------------------------------------------------
# Referrals tab
# -----------------------------------------------------------------------------
if selected_tab == "Referrals":
    st.subheader("Action and Follow-up by Gender")
    st.caption("Referral status")
    draw_gender_column_bar(filtered_records, "referral_status", height=360)
    show_gender_table(filtered_records, "referral_status", "Referral status")
    st.markdown("#### Follow-up required")
    draw_gender_column_bar(filtered_records, "follow_up_required_clean", height=360)
    show_gender_table(filtered_records, "follow_up_required_clean", "Follow-up required")
    st.divider()
    st.subheader("Referral Partners by Gender")
    referral_rank = st.radio("Rank", ["Highest values", "Lowest values"], horizontal=True, index=0, key="referral_rank")
    referral_top_n = st.radio("Number of categories", [10, 15, 25], horizontal=True, index=1, key="referral_top_n")
    draw_gender_bar(filtered_referrals, "referral_partner", top_n=referral_top_n, height=560, ascending=referral_rank == "Lowest values")
    st.caption("Full table (all categories, unaffected by chart slicing)")
    show_gender_table(filtered_referrals, "referral_partner", "Referral partner", top_n=None)

# -----------------------------------------------------------------------------
# Map tab
# -----------------------------------------------------------------------------
if selected_tab == "Map":
    st.subheader("Helpdesk Locations Map")
    mapped_records = map_data(filtered_records)
    if mapped_records.empty:
        st.info("No valid GPS coordinates are available for the selected filters.")
    else:
        st.map(mapped_records[["lat", "lon"]], use_container_width=True)
        map_summary = mapped_records.groupby(["camp_location", "helpdesk_location", "lat", "lon"], dropna=False).size().reset_index(name="records").sort_values("records", ascending=False)
        st.subheader("Mapped Helpdesk Points")
        st.dataframe(style_records_table(map_summary), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# CPV Work tab
# -----------------------------------------------------------------------------
if selected_tab == "CPV Work":
    st.subheader("CPV Work Summary")
    st.markdown(
        '<div class="section-note">Use the chart slicers to choose the metric, ranking direction, and number of CPVs displayed. The table below remains the full CPV summary for the selected dashboard filters.</div>',
        unsafe_allow_html=True,
    )
    cpv_records = filtered_records[filtered_records["staff_name"].astype(str).ne("[Not recorded]")].copy()
    cpv_summary = cpv_work_summary(filtered_records)
    if cpv_summary.empty:
        st.info("No CPV work summary data match the selected filters.")
    else:
        chart_metric_options = [
            "Records",
            "Protection concerns",
            "Information requests",
            "Partner referrals",
            "Follow-up required",
            "Disability records",
            "Mapped records",
            "Helpdesk locations",
        ]
        chart_metric_options = [
            metric for metric in chart_metric_options if metric in cpv_summary.columns
        ]
        slicer_col1, slicer_col2, slicer_col3 = st.columns([2.2, 1.6, 1.8])
        with slicer_col1:
            cpv_chart_metric = st.selectbox(
                "Chart metric",
                chart_metric_options,
                index=0,
                key="cpv_chart_metric",
                help="Choose which CPV workload/outcome metric to visualize.",
            )
        with slicer_col2:
            cpv_rank = st.radio(
                "Rank",
                ["Highest values", "Lowest values"],
                horizontal=True,
                index=0,
                key="cpv_chart_rank",
                help="Choose whether to show the highest or lowest values first.",
            )
        with slicer_col3:
            max_cpv_display = max(1, len(cpv_summary))
            default_cpv_display = min(15, max_cpv_display)
            cpv_top_n = st.slider(
                "Number of CPVs",
                min_value=1,
                max_value=max_cpv_display,
                value=default_cpv_display,
                step=1,
                key="cpv_chart_top_n",
                help="Limit the number of CPVs shown in the chart for easier visualization.",
            )

        cpv_ascending = cpv_rank == "Lowest values"
        cpv_chart_data = cpv_summary.copy()
        cpv_chart_data[cpv_chart_metric] = pd.to_numeric(
            cpv_chart_data[cpv_chart_metric],
            errors="coerce",
        ).fillna(0)

        if cpv_ascending:
            cpv_chart_data = cpv_chart_data.nsmallest(cpv_top_n, cpv_chart_metric)
        else:
            cpv_chart_data = cpv_chart_data.nlargest(cpv_top_n, cpv_chart_metric)

        cpv_chart_data = cpv_chart_data.sort_values(
            cpv_chart_metric,
            ascending=cpv_ascending,
        )

        cpv_order = cpv_chart_data["CPV"].astype(str).tolist()
        cpv_chart_height = max(280, min(760, 34 * len(cpv_order) + 80))
        cpv_chart = (
            alt.Chart(cpv_chart_data)
            .mark_bar(cornerRadiusEnd=3, color="#2F7D69")
            .encode(
                y=alt.Y(
                    "CPV:N",
                    sort=cpv_order,
                    title=None,
                    axis=alt.Axis(labelLimit=360, labelFontSize=11, labelPadding=6),
                ),
                x=alt.X(
                    f"{cpv_chart_metric}:Q",
                    title=cpv_chart_metric,
                ),
                tooltip=[
                    alt.Tooltip("CPV:N", title="CPV"),
                    alt.Tooltip(f"{cpv_chart_metric}:Q", title=cpv_chart_metric, format=","),
                    alt.Tooltip("Records:Q", title="Total records", format=","),
                    alt.Tooltip("Protection concerns:Q", title="Protection concerns", format=","),
                    alt.Tooltip("Information requests:Q", title="Information requests", format=","),
                    alt.Tooltip("Partner referrals:Q", title="Partner referrals", format=","),
                    alt.Tooltip("Follow-up required:Q", title="Follow-up required", format=","),
                    alt.Tooltip("Disability records:Q", title="Disability records", format=","),
                ],
            )
            .properties(height=cpv_chart_height)
        )

        cpv_labels = (
            alt.Chart(cpv_chart_data)
            .mark_text(
                align="left",
                baseline="middle",
                dx=5,
                fontSize=11,
                fontWeight=700,
                color="#1E293B",
            )
            .encode(
                y=alt.Y("CPV:N", sort=cpv_order, title=None),
                x=alt.X(f"{cpv_chart_metric}:Q"),
                text=alt.Text(f"{cpv_chart_metric}:Q", format=","),
            )
        )

        st.altair_chart(
            polish_chart(cpv_chart + cpv_labels),
            use_container_width=True,
        )
        st.caption("Full table — all CPVs, unaffected by the chart slicers")
        st.dataframe(style_records_table(cpv_summary), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# DQA tab
# -----------------------------------------------------------------------------
if selected_tab == "DQA":
    st.subheader("Data Quality Assurance (DQA)")
    st.markdown(
        '<div class="section-note">DQA checks use the current dashboard filters. PII-sensitive follow-up tables are password-protected.</div>',
        unsafe_allow_html=True,
    )
    dqa_total = len(filtered_records)
    duplicate_records = int(filtered_records["record_id"].duplicated().sum()) if "record_id" in filtered_records.columns else 0
    gps_missing = int(filtered_records[["gps_latitude", "gps_longitude"]].isna().any(axis=1).sum()) if {"gps_latitude", "gps_longitude"}.issubset(filtered_records.columns) else 0
    staff_missing = int(filtered_records["staff_name"].astype(str).eq("[Not recorded]").sum()) if "staff_name" in filtered_records.columns else 0
    followup_missing = int(filtered_records["follow_up_required_clean"].isna().sum()) if "follow_up_required_clean" in filtered_records.columns else 0

    dqa_cols = st.columns(5)
    show_kpi_card(dqa_cols[0], "Filtered records", format_number(dqa_total), "Records in current selection", accent="#2F7D69")
    show_kpi_card(dqa_cols[1], "Duplicate IDs", format_number(duplicate_records), "Repeated record_id values", accent="#D9A441")
    show_kpi_card(dqa_cols[2], "Missing GPS", format_number(gps_missing), f"{format_rate(gps_missing, dqa_total)} of records", share=safe_share(gps_missing, dqa_total), accent="#D9A441")
    show_kpi_card(dqa_cols[3], "Missing staff", format_number(staff_missing), f"{format_rate(staff_missing, dqa_total)} of records", share=safe_share(staff_missing, dqa_total), accent="#DB2777")
    show_kpi_card(dqa_cols[4], "Missing follow-up", format_number(followup_missing), f"{format_rate(followup_missing, dqa_total)} of records", share=safe_share(followup_missing, dqa_total), accent="#7C3AED")

    st.divider()
    st.markdown("### Missingness by core DQA field")
    dqa_fields = [
        "interview_date",
        "staff_name",
        "camp_location",
        "helpdesk_location",
        "information_seeker_type",
        "information_seeker_gender",
        "age_group",
        "request_category",
        "referral_status",
        "follow_up_required_clean",
        "gps_latitude",
        "gps_longitude",
    ]
    missing_rows = []
    for col in dqa_fields:
        if col in filtered_records.columns:
            missing_count = int(filtered_records[col].isna().sum())
            if col == "staff_name":
                missing_count += int(filtered_records[col].astype(str).eq("[Not recorded]").sum())
            missing_rows.append(
                {
                    "Field": col,
                    "Missing / not recorded": missing_count,
                    "Completeness %": round(((dqa_total - missing_count) / dqa_total) * 100, 1) if dqa_total else 0,
                }
            )
    missing_table = pd.DataFrame(missing_rows).sort_values("Missing / not recorded", ascending=False)
    st.dataframe(style_records_table(missing_table), use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("### Protected education-concern follow-up table")
    st.markdown(
        '<div class="section-note">Includes records where concern_educational_support and/or concern_school_dropout_risk_or_dropped_out was selected. This table contains PII and requires a password.</div>',
        unsafe_allow_html=True,
    )
    st.caption("Unlock the table to calculate and display matching PII records.")
    if pii_access_granted("dqa_pii_password"):
        filtered_secure_records = apply_filters(secure_records, filters)
        protected_education_table = education_concern_followup_table(filtered_secure_records, filtered_referrals)
        st.caption(f"Matching education-concern records: {format_number(len(protected_education_table))}")
        if protected_education_table.empty:
            st.info("No matching education-concern records for the current filters.")
        else:
            st.dataframe(style_records_table(protected_education_table), use_container_width=True, hide_index=True)
            st.download_button(
                "Download protected education-concern table",
                data=protected_education_table.to_csv(index=False).encode("utf-8"),
                file_name="protected_education_concern_followup_table.csv",
                mime="text/csv",
                use_container_width=True,
            )

# -----------------------------------------------------------------------------
# Records tab
# -----------------------------------------------------------------------------
if selected_tab == "Records":
    st.subheader("Filtered Records")
    ordered_columns = [col for col in CORE_RECORD_COLUMNS if col in filtered_records.columns] + [col for col in filtered_records.columns if col not in CORE_RECORD_COLUMNS]
    default_columns = [col for col in CORE_RECORD_COLUMNS if col in ordered_columns]
    if "record_columns" not in st.session_state:
        st.session_state["record_columns"] = default_columns
    st.session_state["record_columns"] = [col for col in st.session_state["record_columns"] if col in ordered_columns]
    selected_columns = st.multiselect("Columns", ordered_columns, key="record_columns")
    if not selected_columns:
        selected_columns = default_columns

    query = st.text_input("Search filtered records", placeholder="Search by record ID, location, category, status...", key="records_search")
    searched_records = search_records(filtered_records, query)
    preview_records = searched_records[selected_columns].head(RECORD_PREVIEW_LIMIT)
    st.caption(f"Showing {format_number(len(preview_records))} preview records from {format_number(len(searched_records))} matching records. The download still includes all matching records.")
    st.dataframe(style_records_table(preview_records), use_container_width=True, hide_index=True)
    st.download_button("Download filtered records", data=searched_records.to_csv(index=False).encode("utf-8"), file_name="filtered_helpdesk_records.csv", mime="text/csv", use_container_width=True)

    with st.expander("Protected DQA table: education concerns with PII", expanded=False):
        st.markdown(
            '<div class="section-note">Password-protected table for concern_educational_support and/or concern_school_dropout_risk_or_dropped_out. Includes CPV, child/name, individual number, phone, location detail, selected concern, and referred agency.</div>',
            unsafe_allow_html=True,
        )
        st.caption("Unlock the table to calculate and display matching PII records.")
        if pii_access_granted("records_pii_password"):
            filtered_secure_records = apply_filters(secure_records, filters)
            protected_education_table = education_concern_followup_table(filtered_secure_records, filtered_referrals)
            st.caption(f"Matching education-concern records: {format_number(len(protected_education_table))}")
            if protected_education_table.empty:
                st.info("No matching education-concern records for the current filters.")
            else:
                protected_query = st.text_input(
                    "Search protected table",
                    placeholder="Search by CPV, child/name, individual number, phone, location, agency...",
                    key="protected_records_search",
                )
                protected_searched = search_records(protected_education_table, protected_query)
                st.dataframe(
                    style_records_table(protected_searched.head(RECORD_PREVIEW_LIMIT)),
                    use_container_width=True,
                    hide_index=True,
                )
                st.download_button(
                    "Download protected education-concern table",
                    data=protected_searched.to_csv(index=False).encode("utf-8"),
                    file_name="protected_education_concern_followup_table.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    with st.expander("Source KPI summary"): 
        st.dataframe(style_records_table(kpis), use_container_width=True, hide_index=True)

show_footer()
