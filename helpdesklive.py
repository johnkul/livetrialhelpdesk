from pathlib import Path
import base64
import hashlib
import html
import json
import os
import pickle
import re
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from urllib.parse import urlsplit

import altair as alt
import pandas as pd
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# Page configuration
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "tdh-logo.png"
DEVELOPER_LOGO_PATH = BASE_DIR / "assets" / "developer-logo.png"
STYLES_PATH = BASE_DIR / "assets" / "styles.css"
DATA_FILE_PATH = Path(os.environ.get("HELPDESK_DATA_PATH") or (BASE_DIR / "data" / "HELPDESK_DashboardData_Tdh_Kenya_D2.xlsx"))
PROCESSED_CACHE_PATH = BASE_DIR / "data" / "processed" / "helpdesk_processed_cache.pkl"
PROCESSED_CACHE_VERSION = "2026-08-04-kobo-v2"
KOBO_CACHE_TTL_SECONDS = 60
KOBO_SCHEMA_CACHE_TTL_SECONDS = 300
KOBO_CHANGE_CHECK_SECONDS = 60
KOBO_REQUEST_TIMEOUT_SECONDS = 45
KOBO_PAGE_SAFETY_LIMIT = 10000

# Immutable schema contract: Kobo fields are matched by XML name/path or by
# their survey label, never by column position. New form attributes remain
# available for diagnostics without shifting any established dashboard field.
COLUMN_MAPPING_RECORDS = [{'original_column_name': 'Having understood the information provided, do you consent to having your information '
                          'recorded?',
  'cleaned_column_name': 'consent_recording',
  'field_group': 'collection_metadata',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Name of staff filling form',
  'cleaned_column_name': 'staff_name',
  'field_group': 'collection_metadata',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Enter a date',
  'cleaned_column_name': 'interview_date',
  'field_group': 'collection_metadata',
  'recommended_data_type': 'date',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Who is the information seeker?',
  'cleaned_column_name': 'information_seeker_type',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Name of the information seeker at the help desk',
  'cleaned_column_name': 'information_seeker_name',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Is the child Unaccompanied minor? ',
  'cleaned_column_name': 'child_unaccompanied_minor',
  'field_group': 'other',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Relationship of the respondent to the child',
  'cleaned_column_name': 'respondent_relationship_to_child',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'If relationship is not listed, please specify the relationship to child.',
  'cleaned_column_name': 'respondent_relationship_other',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Household type',
  'cleaned_column_name': 'household_type',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Camp location',
  'cleaned_column_name': 'camp_location',
  'field_group': 'location',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Specific Camp location hosting the helpdesk',
  'cleaned_column_name': 'helpdesk_camp_location',
  'field_group': 'location',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Section/Block hosting the helpdesk.',
  'cleaned_column_name': 'helpdesk_section_block',
  'field_group': 'location',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Village location hosting the helpdesk',
  'cleaned_column_name': 'helpdesk_village',
  'field_group': 'location',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'In which Neighborhood, Compound and House do you come from?',
  'cleaned_column_name': 'residence_neighborhood_compound_house',
  'field_group': 'location',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Gender of the information seeker',
  'cleaned_column_name': 'information_seeker_gender',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Age of the information seeker.',
  'cleaned_column_name': 'information_seeker_age',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'number',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Nationality of the information seeker',
  'cleaned_column_name': 'information_seeker_nationality',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'If nationality not listed above, please specify the nationality',
  'cleaned_column_name': 'information_seeker_nationality_other',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Do you have a phone number that is in operation?',
  'cleaned_column_name': 'has_operational_phone',
  'field_group': 'other',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Phone number of the information seeker',
  'cleaned_column_name': 'information_seeker_phone',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Alternative phone number',
  'cleaned_column_name': 'alternative_phone',
  'field_group': 'other',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Are you registered with the UNHCR.',
  'cleaned_column_name': 'registered_with_unhcr',
  'field_group': 'other',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Individual Number of the information seeker',
  'cleaned_column_name': 'information_seeker_individual_number',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Ration Card Number/ Wrist Band Number of the information seeker',
  'cleaned_column_name': 'information_seeker_ration_or_wristband_number',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': 'Do you have any disability?',
  'cleaned_column_name': 'has_disability',
  'field_group': 'disability',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': "What is the child's type of disability?",
  'cleaned_column_name': 'child_disability_type',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'If Other disability, please specify the type of disability for the child',
  'cleaned_column_name': 'child_disability_type_other',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': '[Do/Does] [you/he/she] have difficulty seeing, even if wearing glasses? Would you say… ',
  'cleaned_column_name': 'difficulty_seeing',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': '[Do/Does] [you/he/she] have difficulty hearing, even if using a hearing aid(s)? Would you '
                          'say… ',
  'cleaned_column_name': 'difficulty_hearing',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': '[Do/Does] [you/he/she] have difficulty walking or climbing steps? Would you say… ',
  'cleaned_column_name': 'difficulty_walking_or_climbing',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': '[Do/does] [you/he/she] have difficulty with self-care, such as washing all over or '
                          'dressing? Would you say…',
  'cleaned_column_name': 'difficulty_self_care',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': '[Do/does] [you/he/she] have difficulty remembering or concentrating? Would you say… ',
  'cleaned_column_name': 'difficulty_remembering_or_concentrating',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Using [your/his/her] usual language, [do/does] [you/he/she] have difficulty communicating, '
                          'for example understanding or being understood? Would you say…',
  'cleaned_column_name': 'difficulty_communicating',
  'field_group': 'disability',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Other disability type of the information seeker if not answered by the Questions provided?',
  'cleaned_column_name': 'information_seeker_disability_type_other',
  'field_group': 'respondent_profile',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Have you been to any of Tdh`s helpdesks before?',
  'cleaned_column_name': 'visited_tdh_helpdesk_before',
  'field_group': 'other',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Was your last visit made within the month we are in?',
  'cleaned_column_name': 'last_visit_within_current_month',
  'field_group': 'other',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Is the individual reporting a protection concern or seeking general protection information',
  'cleaned_column_name': 'request_type_protection_or_information',
  'field_group': 'protection_concern',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk',
  'cleaned_column_name': 'main_protection_concern',
  'field_group': 'protection_concern',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Families with limited / No access to '
                          'non-food items (Beddings, Mats, Plastic jerrycans)',
  'cleaned_column_name': 'concern_no_access_nfi',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Children in need of disability assistive '
                          'devices',
  'cleaned_column_name': 'concern_child_needs_assistive_devices',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren)/ Families with limited / No '
                          'access to food commodities',
  'cleaned_column_name': 'concern_no_access_food',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Parental Neglect',
  'cleaned_column_name': 'concern_parental_neglect',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child Abandonment',
  'cleaned_column_name': 'concern_child_abandonment',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child custody related concerns',
  'cleaned_column_name': 'concern_child_custody',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child at risk of / experiencing physical '
                          'violence',
  'cleaned_column_name': 'concern_physical_violence',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) at risk of / experiencing '
                          'sexual violence (Child marriage, FGM, Indecent touch, Sodomy)',
  'cleaned_column_name': 'concern_sexual_violence',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Children in need of educational support',
  'cleaned_column_name': 'concern_educational_support',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) at the risk of dropping out '
                          'of school/ Have already dropped out',
  'cleaned_column_name': 'concern_school_dropout_risk_or_dropped_out',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Intimate partner violence',
  'cleaned_column_name': 'concern_intimate_partner_violence',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) engaging in dangerous work '
                          'for pay',
  'cleaned_column_name': 'concern_dangerous_child_work',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) in contact with the law',
  'cleaned_column_name': 'concern_child_contact_with_law',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) in conflict with the law',
  'cleaned_column_name': 'concern_child_conflict_with_law',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child in need of civil registration '
                          'services (E.g. Birth certificates)',
  'cleaned_column_name': 'concern_civil_registration_services',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) / families in need of shelter',
  'cleaned_column_name': 'concern_shelter_need',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child (ren) in need of medical support',
  'cleaned_column_name': 'concern_medical_support',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child lacking parental care / '
                          'Unaccompanied minors',
  'cleaned_column_name': 'concern_lacking_parental_care_unaccompanied',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Persons in need of profiling/registration '
                          'by UNHCR',
  'cleaned_column_name': 'concern_unhcr_profiling_registration',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Child(ren) in need of psychosocial '
                          'support services',
  'cleaned_column_name': 'concern_psychosocial_support',
  'field_group': 'protection_concern',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'MAIN protection concern presented at the helpdesk/Protection_concerns not listed',
  'cleaned_column_name': 'concern_other_not_listed',
  'field_group': 'protection_concern',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'If protection_concerns not listed, specify the protection concerns presented.',
  'cleaned_column_name': 'concern_other_specify',
  'field_group': 'protection_concern',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Protection concern field renamed with concern_ prefix.'},
 {'original_column_name': 'Type of general protection information sought',
  'cleaned_column_name': 'general_information_type',
  'field_group': 'general_information',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to Child Protective '
                          'services',
  'cleaned_column_name': 'info_child_protection_services',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to Gender based '
                          'Violence (GBV) support services',
  'cleaned_column_name': 'info_gbv_support_services',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to legal services',
  'cleaned_column_name': 'info_legal_services',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to durable solutions '
                          '(Resettlement, Voluntary Repatriation, Local intergration)',
  'cleaned_column_name': 'info_durable_solutions',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to core -relief items '
                          '(NFI)',
  'cleaned_column_name': 'info_core_relief_items',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to food from WFP and '
                          'relevant partners.',
  'cleaned_column_name': 'info_food_access',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to shelter',
  'cleaned_column_name': 'info_shelter_access',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to livelihood and '
                          'empowerment opportunities',
  'cleaned_column_name': 'info_livelihood_empowerment',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to medical services',
  'cleaned_column_name': 'info_medical_services',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on disability support services',
  'cleaned_column_name': 'info_disability_support_services',
  'field_group': 'disability',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/Information on access to WASH',
  'cleaned_column_name': 'info_wash_access',
  'field_group': 'general_information',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Type of general protection information sought/General_protection not in the list',
  'cleaned_column_name': 'info_other_not_listed',
  'field_group': 'general_information',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'If general_protection not in the list, please specify the general protection information '
                          'sought.',
  'cleaned_column_name': 'info_other_specify',
  'field_group': 'general_information',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'General information field renamed with info_ prefix.'},
 {'original_column_name': 'Action Taken',
  'cleaned_column_name': 'action_taken',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'If Action taken is Other, please specify',
  'cleaned_column_name': 'action_taken_other_specify',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'On what date was the case referred',
  'cleaned_column_name': 'referral_date',
  'field_group': 'referral_action',
  'recommended_data_type': 'date',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Which partner has the case been referred to',
  'cleaned_column_name': 'referred_partner',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Which partner has the case been referred to/Department of Refugee Services (DRS)',
  'cleaned_column_name': 'ref_partner_drs',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/UNHCR',
  'cleaned_column_name': 'ref_partner_unhcr',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Save the Children (SCI)',
  'cleaned_column_name': 'ref_partner_sci',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Norwegian Refugee Council (NRC)',
  'cleaned_column_name': 'ref_partner_nrc',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/International Rescue Commitee (IRC)',
  'cleaned_column_name': 'ref_partner_irc',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Refugee Consortium of Kenya (RCK)',
  'cleaned_column_name': 'ref_partner_rck',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Lutheran World Federation (LWF)',
  'cleaned_column_name': 'ref_partner_lwf',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Humanity and Inclusion (HI)',
  'cleaned_column_name': 'ref_partner_hi',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Danish Refugee Council (DRC)',
  'cleaned_column_name': 'ref_partner_drc',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Peace Winds Japan',
  'cleaned_column_name': 'ref_partner_pwj',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Directorate of Children Services (DCS)',
  'cleaned_column_name': 'ref_partner_dcs',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Film Aid Kenya (FAK)',
  'cleaned_column_name': 'ref_partner_fak',
  'field_group': 'referral_action',
  'recommended_data_type': 'multi_select_indicator',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which partner has the case been referred to/Other partners',
  'cleaned_column_name': 'ref_partner_other',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'If Other, please specify the partner the case was referred to.',
  'cleaned_column_name': 'ref_partner_other_specify',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Referral partner field renamed with ref_partner_ prefix.'},
 {'original_column_name': 'Which department has the case been referred to?',
  'cleaned_column_name': 'referred_department',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'If External, please specify the name of the agency referred to.',
  'cleaned_column_name': 'external_agency_specify',
  'field_group': 'referral_action',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'Any follow up action required ?',
  'cleaned_column_name': 'follow_up_required',
  'field_group': 'follow_up',
  'recommended_data_type': 'yes_no',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': 'If Yes, what is the follow up action?',
  'cleaned_column_name': 'follow_up_action',
  'field_group': 'follow_up',
  'recommended_data_type': 'text/category',
  'sensitive_or_pii': 'No',
  'transformation_note': 'Renamed to concise snake_case for dashboard/model use.'},
 {'original_column_name': '_GPS Location_latitude',
  'cleaned_column_name': 'gps_latitude',
  'field_group': 'location',
  'recommended_data_type': 'decimal',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'},
 {'original_column_name': '_GPS Location_longitude',
  'cleaned_column_name': 'gps_longitude',
  'field_group': 'location',
  'recommended_data_type': 'decimal',
  'sensitive_or_pii': 'Yes',
  'transformation_note': 'Sensitive/PII field; review before dashboard publication.'}]
RAW_TO_TRANSFORMED_COLUMNS = {'Having understood the information provided, do you consent to having your information recorded?': 'consent_recording',
 'Name of staff filling form': 'staff_name',
 'Enter a date': 'interview_date',
 'Who is the information seeker?': 'information_seeker_type',
 'Name of the information seeker at the help desk': 'information_seeker_name',
 'Is the child Unaccompanied minor? ': 'child_unaccompanied_minor',
 'Relationship of the respondent to the child': 'respondent_relationship_to_child',
 'If relationship is not listed, please specify the relationship to child.': 'respondent_relationship_other',
 'Household type': 'household_type',
 'Camp location': 'camp_location',
 'Specific Camp location hosting the helpdesk': 'helpdesk_camp_location',
 'Section/Block hosting the helpdesk.': 'helpdesk_section_block',
 'Village location hosting the helpdesk': 'helpdesk_village',
 'In which Neighborhood, Compound and House do you come from?': 'residence_neighborhood_compound_house',
 'Gender of the information seeker': 'information_seeker_gender',
 'Age of the information seeker.': 'information_seeker_age',
 'Nationality of the information seeker': 'information_seeker_nationality',
 'If nationality not listed above, please specify the nationality': 'information_seeker_nationality_other',
 'Do you have a phone number that is in operation?': 'has_operational_phone',
 'Phone number of the information seeker': 'information_seeker_phone',
 'Alternative phone number': 'alternative_phone',
 'Are you registered with the UNHCR.': 'registered_with_unhcr',
 'Individual Number of the information seeker': 'information_seeker_individual_number',
 'Ration Card Number/ Wrist Band Number of the information seeker': 'information_seeker_ration_or_wristband_number',
 'Do you have any disability?': 'has_disability',
 "What is the child's type of disability?": 'child_disability_type',
 'If Other disability, please specify the type of disability for the child': 'child_disability_type_other',
 '[Do/Does] [you/he/she] have difficulty seeing, even if wearing glasses? Would you say… ': 'difficulty_seeing',
 '[Do/Does] [you/he/she] have difficulty hearing, even if using a hearing aid(s)? Would you say… ': 'difficulty_hearing',
 '[Do/Does] [you/he/she] have difficulty walking or climbing steps? Would you say… ': 'difficulty_walking_or_climbing',
 '[Do/does] [you/he/she] have difficulty with self-care, such as washing all over or dressing? Would you say…': 'difficulty_self_care',
 '[Do/does] [you/he/she] have difficulty remembering or concentrating? Would you say… ': 'difficulty_remembering_or_concentrating',
 'Using [your/his/her] usual language, [do/does] [you/he/she] have difficulty communicating, for example understanding or being understood? Would you say…': 'difficulty_communicating',
 'Other disability type of the information seeker if not answered by the Questions provided?': 'information_seeker_disability_type_other',
 'Have you been to any of Tdh`s helpdesks before?': 'visited_tdh_helpdesk_before',
 'Was your last visit made within the month we are in?': 'last_visit_within_current_month',
 'Is the individual reporting a protection concern or seeking general protection information': 'request_type_protection_or_information',
 'MAIN protection concern presented at the helpdesk': 'main_protection_concern',
 'MAIN protection concern presented at the helpdesk/Families with limited / No access to non-food items (Beddings, Mats, Plastic jerrycans)': 'concern_no_access_nfi',
 'MAIN protection concern presented at the helpdesk/Children in need of disability assistive devices': 'concern_child_needs_assistive_devices',
 'MAIN protection concern presented at the helpdesk/Child (ren)/ Families with limited / No access to food commodities': 'concern_no_access_food',
 'MAIN protection concern presented at the helpdesk/Parental Neglect': 'concern_parental_neglect',
 'MAIN protection concern presented at the helpdesk/Child Abandonment': 'concern_child_abandonment',
 'MAIN protection concern presented at the helpdesk/Child custody related concerns': 'concern_child_custody',
 'MAIN protection concern presented at the helpdesk/Child at risk of / experiencing physical violence': 'concern_physical_violence',
 'MAIN protection concern presented at the helpdesk/Child (ren) at risk of / experiencing sexual violence (Child marriage, FGM, Indecent touch, Sodomy)': 'concern_sexual_violence',
 'MAIN protection concern presented at the helpdesk/Children in need of educational support': 'concern_educational_support',
 'MAIN protection concern presented at the helpdesk/Child (ren) at the risk of dropping out of school/ Have already dropped out': 'concern_school_dropout_risk_or_dropped_out',
 'MAIN protection concern presented at the helpdesk/Intimate partner violence': 'concern_intimate_partner_violence',
 'MAIN protection concern presented at the helpdesk/Child (ren) engaging in dangerous work for pay': 'concern_dangerous_child_work',
 'MAIN protection concern presented at the helpdesk/Child (ren) in contact with the law': 'concern_child_contact_with_law',
 'MAIN protection concern presented at the helpdesk/Child (ren) in conflict with the law': 'concern_child_conflict_with_law',
 'MAIN protection concern presented at the helpdesk/Child in need of civil registration services (E.g. Birth certificates)': 'concern_civil_registration_services',
 'MAIN protection concern presented at the helpdesk/Child (ren) / families in need of shelter': 'concern_shelter_need',
 'MAIN protection concern presented at the helpdesk/Child (ren) in need of medical support': 'concern_medical_support',
 'MAIN protection concern presented at the helpdesk/Child lacking parental care / Unaccompanied minors': 'concern_lacking_parental_care_unaccompanied',
 'MAIN protection concern presented at the helpdesk/Persons in need of profiling/registration by UNHCR': 'concern_unhcr_profiling_registration',
 'MAIN protection concern presented at the helpdesk/Child(ren) in need of psychosocial support services': 'concern_psychosocial_support',
 'MAIN protection concern presented at the helpdesk/Protection_concerns not listed': 'concern_other_not_listed',
 'If protection_concerns not listed, specify the protection concerns presented.': 'concern_other_specify',
 'Type of general protection information sought': 'general_information_type',
 'Type of general protection information sought/Information on access to Child Protective services': 'info_child_protection_services',
 'Type of general protection information sought/Information on access to Gender based Violence (GBV) support services': 'info_gbv_support_services',
 'Type of general protection information sought/Information on access to legal services': 'info_legal_services',
 'Type of general protection information sought/Information on access to durable solutions (Resettlement, Voluntary Repatriation, Local intergration)': 'info_durable_solutions',
 'Type of general protection information sought/Information on access to core -relief items (NFI)': 'info_core_relief_items',
 'Type of general protection information sought/Information on access to food from WFP and relevant partners.': 'info_food_access',
 'Type of general protection information sought/Information on access to shelter': 'info_shelter_access',
 'Type of general protection information sought/Information on access to livelihood and empowerment opportunities': 'info_livelihood_empowerment',
 'Type of general protection information sought/Information on access to medical services': 'info_medical_services',
 'Type of general protection information sought/Information on disability support services': 'info_disability_support_services',
 'Type of general protection information sought/Information on access to WASH': 'info_wash_access',
 'Type of general protection information sought/General_protection not in the list': 'info_other_not_listed',
 'If general_protection not in the list, please specify the general protection information sought.': 'info_other_specify',
 'Action Taken': 'action_taken',
 'If Action taken is Other, please specify': 'action_taken_other_specify',
 'On what date was the case referred': 'referral_date',
 'Which partner has the case been referred to': 'referred_partner',
 'Which partner has the case been referred to/Department of Refugee Services (DRS)': 'ref_partner_drs',
 'Which partner has the case been referred to/UNHCR': 'ref_partner_unhcr',
 'Which partner has the case been referred to/Save the Children (SCI)': 'ref_partner_sci',
 'Which partner has the case been referred to/Norwegian Refugee Council (NRC)': 'ref_partner_nrc',
 'Which partner has the case been referred to/International Rescue Commitee (IRC)': 'ref_partner_irc',
 'Which partner has the case been referred to/Refugee Consortium of Kenya (RCK)': 'ref_partner_rck',
 'Which partner has the case been referred to/Lutheran World Federation (LWF)': 'ref_partner_lwf',
 'Which partner has the case been referred to/Humanity and Inclusion (HI)': 'ref_partner_hi',
 'Which partner has the case been referred to/Danish Refugee Council (DRC)': 'ref_partner_drc',
 'Which partner has the case been referred to/Peace Winds Japan': 'ref_partner_pwj',
 'Which partner has the case been referred to/Directorate of Children Services (DCS)': 'ref_partner_dcs',
 'Which partner has the case been referred to/Film Aid Kenya (FAK)': 'ref_partner_fak',
 'Which partner has the case been referred to/Other partners': 'ref_partner_other',
 'If Other, please specify the partner the case was referred to.': 'ref_partner_other_specify',
 'Which department has the case been referred to?': 'referred_department',
 'If External, please specify the name of the agency referred to.': 'external_agency_specify',
 'Any follow up action required ?': 'follow_up_required',
 'If Yes, what is the follow up action?': 'follow_up_action',
 '_GPS Location_latitude': 'gps_latitude',
 '_GPS Location_longitude': 'gps_longitude',
 '_id': 'kobo_submission_id',
 '_uuid': 'kobo_submission_uuid',
 '_submission_time': 'kobo_submission_time',
 '_validation_status': 'kobo_validation_status',
 '_status': 'kobo_status',
 '_submitted_by': 'kobo_submitted_by',
 '_notes': 'kobo_notes',
 '_tags': 'kobo_tags',
 '_index': 'kobo_index',
 'today': 'kobo_today',
 'username': 'kobo_username',
 'deviceid': 'kobo_device_id',
 'phonenumber': 'kobo_phone_number'}
ANALYSIS_COLUMN_NAMES = frozenset(['action_taken',
 'action_taken_other_specify',
 'alternative_phone',
 'camp_location',
 'child_disability_type',
 'child_disability_type_other',
 'child_unaccompanied_minor',
 'concern_child_abandonment',
 'concern_child_conflict_with_law',
 'concern_child_contact_with_law',
 'concern_child_custody',
 'concern_child_needs_assistive_devices',
 'concern_civil_registration_services',
 'concern_dangerous_child_work',
 'concern_educational_support',
 'concern_intimate_partner_violence',
 'concern_lacking_parental_care_unaccompanied',
 'concern_medical_support',
 'concern_no_access_food',
 'concern_no_access_nfi',
 'concern_other_not_listed',
 'concern_other_specify',
 'concern_parental_neglect',
 'concern_physical_violence',
 'concern_psychosocial_support',
 'concern_school_dropout_risk_or_dropped_out',
 'concern_sexual_violence',
 'concern_shelter_need',
 'concern_unhcr_profiling_registration',
 'consent_recording',
 'difficulty_communicating',
 'difficulty_hearing',
 'difficulty_remembering_or_concentrating',
 'difficulty_seeing',
 'difficulty_self_care',
 'difficulty_walking_or_climbing',
 'external_agency_specify',
 'follow_up_action',
 'follow_up_required',
 'general_information_type',
 'gps_latitude',
 'gps_longitude',
 'has_disability',
 'has_operational_phone',
 'helpdesk_camp_location',
 'helpdesk_section_block',
 'helpdesk_village',
 'household_type',
 'info_child_protection_services',
 'info_core_relief_items',
 'info_disability_support_services',
 'info_durable_solutions',
 'info_food_access',
 'info_gbv_support_services',
 'info_legal_services',
 'info_livelihood_empowerment',
 'info_medical_services',
 'info_other_not_listed',
 'info_other_specify',
 'info_shelter_access',
 'info_wash_access',
 'information_seeker_age',
 'information_seeker_disability_type_other',
 'information_seeker_gender',
 'information_seeker_individual_number',
 'information_seeker_name',
 'information_seeker_nationality',
 'information_seeker_nationality_other',
 'information_seeker_phone',
 'information_seeker_ration_or_wristband_number',
 'information_seeker_type',
 'interview_date',
 'kobo_device_id',
 'kobo_index',
 'kobo_notes',
 'kobo_phone_number',
 'kobo_status',
 'kobo_submission_id',
 'kobo_submission_time',
 'kobo_submission_uuid',
 'kobo_submitted_by',
 'kobo_tags',
 'kobo_today',
 'kobo_username',
 'kobo_validation_status',
 'last_visit_within_current_month',
 'main_protection_concern',
 'ref_partner_dcs',
 'ref_partner_drc',
 'ref_partner_drs',
 'ref_partner_fak',
 'ref_partner_hi',
 'ref_partner_irc',
 'ref_partner_lwf',
 'ref_partner_nrc',
 'ref_partner_other',
 'ref_partner_other_specify',
 'ref_partner_pwj',
 'ref_partner_rck',
 'ref_partner_sci',
 'ref_partner_unhcr',
 'referral_date',
 'referred_department',
 'referred_partner',
 'registered_with_unhcr',
 'request_type_protection_or_information',
 'residence_neighborhood_compound_house',
 'respondent_relationship_other',
 'respondent_relationship_to_child',
 'staff_name',
 'visited_tdh_helpdesk_before'])

APP_VERSION = "Version 1.0"
APP_VERSION_DATE = "June 2026"

_logo_for_icon = LOGO_PATH
st.set_page_config(
    page_title="Tdh Kenya Helpdesk Dashboard",
    page_icon=str(_logo_for_icon) if _logo_for_icon.exists() else ":bar_chart:",
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
VISIT_HISTORY_ORDER = ["First-time visitor", "Repeat visitor", "[Missing]"]
REPEAT_VISIT_TIMING_ORDER = [
    "Repeat — within current month",
    "Repeat — before current month",
    "Repeat — timing not recorded",
]
CHILD_ACCOMPANIMENT_ORDER = ["Unaccompanied", "Not unaccompanied", "[Missing]"]
GENDER_COLORS = {
    "Girl": "#8B5CF6",
    "Boy": "#2563EB",
    "Woman": "#DB2777",
    "Man": "#059669",
    "Transgender": "#D9A441",
    "[Missing]": "#94A3B8",
}

CHART_CATEGORY_COLORS = [
    "#2F7D69",
    "#1F6FB2",
    "#D9A441",
    "#8B5CF6",
    "#DB2777",
    "#059669",
    "#F97316",
    "#14B8A6",
    "#64748B",
    "#A855F7",
]

STATUS_COLORS = {
    "Has Disability": "#2F7D69",
    "No Disability": "#94A3B8",
    "Has disability": "#2F7D69",
    "No disability": "#94A3B8",
    "Has Impairment": "#2F7D69",
    "No Impairment": "#94A3B8",
}

CPV_METRIC_COLORS = {
    "Records": "#2F7D69",
    "Protection concerns": "#1F6FB2",
    "Information requests": "#6D5BD0",
    "Partner referrals": "#059669",
    "Follow-up required": "#D9A441",
    "Disability records": "#DB2777",
    "Mapped records": "#14B8A6",
    "Helpdesk locations": "#64748B",
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
ADULT_DISABILITY_CATEGORY_COLUMNS = [
    "information_seeker_disability_type_other",
    "information_seeker_disability_type_other_specify",
    "information_seeker_disability_other_specify",
]
CHILD_DISABILITY_OTHER_COLUMNS = [
    "child_disability_type_other",
    "child_disability_type_other_specify",
    "child_disability_other_specify",
]

DISABILITY_TYPE_STANDARD_MAP = {
    "chronic illnesses": "Chronic Illnesses",
    "chronic illness": "Chronic Illnesses",
    "chronic illnesses (any disease that is dependent on medicines e.g. diabetes, blood pressure etc.)": "Chronic Illnesses",
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
    "helpdesk_visit_history",
    "visited_tdh_helpdesk_before_raw",
    "repeat_visit_timing",
    "last_visit_within_current_month_raw",
    "visit_history_consistency",
    "visit_history_inconsistency_flag",
    "child_accompaniment_status",
    "child_unaccompanied_minor_raw",
    "respondent_relationship_to_child_raw",
    "respondent_relationship_other_raw",
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


def consent_is_declined(value):
    """Return True only for an explicit refusal of consent."""
    normalized = normalize_response(value)
    if normalized is None:
        return False
    return normalized in {
        "no", "n", "0", "false", "declined", "decline", "refused",
        "refuse", "not consented", "do not consent", "dont consent",
        "i do not consent", "i dont consent", "consent not given",
    }


def derive_helpdesk_visit_history(value):
    """Classify prior-helpdesk responses into first-time versus repeat visits."""
    normalized = normalize_response(value)
    if normalized is None:
        return "[Missing]"
    if normalized in {
        "yes", "y", "1", "true", "visited before", "yes visited before",
        "repeat", "repeat visit", "returning", "returning visitor",
    }:
        return "Repeat visitor"
    if normalized in {
        "no", "n", "0", "false", "not visited before", "never visited",
        "first time", "first visit", "new visitor",
    }:
        return "First-time visitor"
    if any(term in normalized for term in ["first time", "never visited", "not visited before"]):
        return "First-time visitor"
    if any(term in normalized for term in ["repeat", "returning", "visited before"]):
        return "Repeat visitor"
    return "[Missing]"


def yes_no_response(value):
    """Return True/False for a clear yes/no response, otherwise None."""
    normalized = normalize_response(value)
    if normalized in {"yes", "y", "1", "true"}:
        return True
    if normalized in {"no", "n", "0", "false"}:
        return False
    return None


def derive_repeat_visit_timing(row):
    """Use the follow-up question only for confirmed repeat visitors."""
    visit_history = row.get("helpdesk_visit_history")
    within_month = yes_no_response(row.get("last_visit_within_current_month"))
    if visit_history != "Repeat visitor":
        return pd.NA
    if within_month is True:
        return "Repeat — within current month"
    if within_month is False:
        return "Repeat — before current month"
    return "Repeat — timing not recorded"


def derive_visit_history_consistency(row):
    """Audit skip logic between prior-visit and last-visit timing fields."""
    visit_history = row.get("helpdesk_visit_history")
    within_month = yes_no_response(row.get("last_visit_within_current_month"))
    if visit_history == "First-time visitor" and within_month is not None:
        return "Review — first-time visitor has a last-visit response"
    if visit_history == "Repeat visitor" and within_month is None:
        return "Review — repeat visit timing is missing"
    if visit_history == "[Missing]" and within_month is not None:
        return "Review — visit history missing but timing was answered"
    if visit_history == "[Missing]":
        return "Visit history missing"
    return "Consistent"


def derive_child_accompaniment_status(row):
    """Harmonize unaccompanied-child status from direct and relationship fields."""
    if not is_child(row):
        return "[Missing]"

    direct = normalize_response(row.get("child_unaccompanied_minor"))
    if direct in {"yes", "y", "1", "true", "unaccompanied", "unaccompanied minor"}:
        return "Unaccompanied"
    if direct in {"no", "n", "0", "false", "accompanied", "not unaccompanied"}:
        return "Not unaccompanied"

    relationship_values = [
        normalize_response(row.get("respondent_relationship_to_child")),
        normalize_response(row.get("respondent_relationship_other")),
    ]
    relationship = " ".join(value for value in relationship_values if value)
    if not relationship:
        return "[Missing]"

    unaccompanied_terms = [
        "unaccompanied", "alone", "no caregiver", "without caregiver",
        "without parent",
    ]
    accompanied_terms = [
        "mother", "father", "parent", "caregiver", "guardian", "aunt",
        "uncle", "grandmother", "grandfather", "grandparent", "brother",
        "sister", "sibling", "relative", "stepmother", "stepfather",
    ]
    if any(term in relationship for term in unaccompanied_terms):
        return "Unaccompanied"
    if any(term in relationship for term in accompanied_terms):
        return "Not unaccompanied"
    if relationship.strip() in {"self", "child", "the child", "beneficiary"}:
        return "Unaccompanied"
    return "[Missing]"


def staff_name_key(value):
    """Create a robust matching key for CPV/staff names."""
    value = normalize_response(value)
    if value is None:
        return ""
    value = value.replace('"', " ").replace("'", " ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


# CPV/staff name harmonization map. Keys must use staff_name_key() format.
# This groups observed spelling, spacing, casing, partial-name, reversed-name,
# and typo variants to one main CPV name for charts and CPV Work Summary tables.
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
    "mulimbi kalangiro": "Mulimbi Kalangiro Vainqueur",
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
    "oweteshe mirindi": "Oweteshe Mirindi",
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
    "mary ihisa": "Mary Ihisa",
    "ahmed abdullahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed abdullahi hussein": "Ahmed Abdullahi Hussein",
    "ahmed abdullah hussien": "Ahmed Abdullahi Hussein",
    "ahmed abdulahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed adullahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed abdllahi hussien": "Ahmed Abdullahi Hussein",
    "ahmed mohamed": "Ahmed Abdullahi Hussein",
    "fowzia omar": "Fowzia Omar Muse",
    "fowzi omar muse": "Fowzia Omar Muse",
    "fowzia omar muse": "Fowzia Omar Muse",
    "fowzi omar": "Fowzia Omar Muse",
    "zahara": "Zahara Issack",
    "zahara issack": "Zahara Issack",
    "zahra issack": "Zahara Issack",
    "zara issack": "Zahara Issack",
    "ongoro": "Ongoro John",
    "ongoro john": "Ongoro John",
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
    "madut malul akon": "Madut Malul Akon",
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

    # Catch reversed two/three-name entries where the exact spelling was not
    # listed in the alias map but the same tokens are present.
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
    if any(token in normalized for token in ["visual", "seeing", "sight", "blind"]):
        return "Visual Impairment"
    if any(token in normalized for token in ["hearing", "deaf"]):
        return "Hearing Impairment"
    if any(token in normalized for token in ["physical", "mobility", "walking", "climbing", "limb", "paralys", "wheelchair"]):
        return "Physical/Mobility Impairment"
    if any(token in normalized for token in ["cognitive", "remember", "concentrat", "autism", "adhd", "neurological", "intellectual", "mental", "psychosocial", "learning", "epilep"]):
        return "Cognitive Impairment"
    if "self care" in normalized or "self-care" in normalized:
        return "Self-Care Impairment"
    if any(token in normalized for token in ["speech", "communication", "communicat", "mute"]):
        return "Speech Impairment"
    if "chronic illness" in normalized:
        return "Chronic Illnesses"
    return str(value)


def specified_disability_type(row, columns):
    """Return a usable harmonized value from disability 'Other' detail fields."""
    generic_values = {
        "other", "others", "other disability", "other disabilities",
        "other specify", "other specified", "yes", "y", "true", "1",
        "none", "none of the above", "not applicable", "n/a", "na", "nil",
    }
    for column in columns:
        if column not in row.index:
            continue
        value = clean_text(row.get(column))
        if pd.isna(value):
            continue
        normalized = normalize_response(value)
        if normalized in generic_values:
            continue
        # Some exports repeat the option label inside the specification, for
        # example "Other disability: epilepsy". Harmonize the actual detail.
        if normalized.startswith("other disability"):
            value = re.sub(
                r"^other\s+disabilit(?:y|ies)\s*[:;\-–—]?\s*",
                "",
                str(value),
                flags=re.IGNORECASE,
            ).strip()
            if not value:
                continue
        standardized = standardize_disability_type(value)
        if standardized != "None":
            return standardized
    return "None"


def is_other_disability_response(value):
    """Recognize Other Disability despite Kobo/export formatting variations."""
    normalized = normalize_response(value)
    if normalized is None:
        return False
    generic = {
        "other", "others", "other disability", "other disabilities",
        "other specify", "other specified",
    }
    return normalized in generic or ("other" in normalized and "disabil" in normalized)


def safe_label_from_code(value):
    value = str(value)
    value = value.replace("concern_", "").replace("info_", "").replace("ref_partner_", "")
    value = value.replace("_", " ")
    return value.title()


def harmonize_free_text(text, main_category_labels, default="Other Not Listed"):
    """Map an 'Other specify' free-text response to the closest existing category.

    If the free text clearly matches an existing label, return that existing label.
    If it does not match but contains usable text, return a cleaned version of the
    free text so the dashboard shows the actual specified content instead of the
    generic 'Other Not Listed' bucket.
    """
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

    # 1) Exact / near-exact match to an existing category label.
    for label in clean_labels:
        if txt_norm == normalize_response(label) or txt.lower() == label.lower():
            return label

    # 2) Substring match, useful where free text contains the category wording.
    for label in clean_labels:
        label_norm = normalize_response(label)
        if label_norm and (label_norm in txt_norm or txt_norm in label_norm):
            return label

    # 3) Strong word-overlap match.
    txt_words = set(word for word in txt_norm.split() if len(word) > 2)
    for label in clean_labels:
        label_norm = normalize_response(label)
        label_words = set(word for word in label_norm.split() if len(word) > 2)
        if not label_words:
            continue
        overlap = label_words & txt_words
        if len(overlap) >= 1 and len(overlap) / len(label_words) >= 0.5:
            return label

    # 4) Fallback: keep the actual free-text response, cleaned for display.
    cleaned = safe_label_from_code(txt)
    if cleaned and normalize_response(cleaned) not in ["other", "other not listed", "others", "other specify"]:
        return cleaned

    return default


# Extensible concept taxonomy for free-text protection concerns. Each rule maps
# commonly used words, phrases and spelling variants to an existing listed
# concern. Rules are evaluated before generic fuzzy label matching.
PROTECTION_CONCERN_TEXT_RULES = [
    {
        "category_aliases": ["School dropout risk or dropped out", "School dropout", "Dropout risk"],
        "keywords": ["dropout", "drop out", "dropped out", "not attending school", "left school", "school absenteeism"],
    },
    {
        "category_aliases": ["Education support", "Educational support"],
        "keywords": [
            "scholastic material", "scholatic material", "scholastic matetial", "school material",
            "learning material", "education material", "exercise book",
            "textbook", "text book", "book", "uniform", "stationery",
            "school supplies", "school fees", "school fee", "material support for school", "pencil", "pen",
        ],
    },
    {
        "category_aliases": ["Pre-Registration", "Pre Registration"],
        "keywords": ["pre registration", "preregistration", "waiting for registration", "new arrival registration"],
    },
    {
        "category_aliases": ["Unhcr Profiling Registration", "UNHCR registration", "Profiling registration"],
        "keywords": ["unhcr registration", "unhcr profiling", "not appearing in the system", "profiling registration"],
    },
    {
        "category_aliases": ["Card Separation", "Separation Card"],
        "keywords": ["card separation", "separation card", "separate ration card", "card separated"],
    },
    {
        "category_aliases": ["Bamba Chakula Issues", "Food card issue"],
        "keywords": ["bamba chakula", "bamba pin", "pin issue", "card deactivation", "deactivation card", "deactivated card", "card desactivated", "card merging", "card marging", "card margin"],
    },
    {
        "category_aliases": ["Alternative Food Collector"],
        "keywords": ["alternative food collector", "alternative food collection", "alternative food collect", "altanative food collector", "food collector"],
    },
    {
        "category_aliases": ["No Access Nfi", "NFI support", "Non food items"],
        "keywords": ["clothes", "clothing", "shoe", "sandal", "sandle", "crocks", "soap", "sanitary pad", "sleeping material", "mattress", "blanket"],
    },
    {
        "category_aliases": ["Basic Needs", "Material Support"],
        "keywords": ["basic need", "bassic need", "material support", "need of material"],
    },
    {
        "category_aliases": ["Child Abandonment"],
        "keywords": ["child abandonment", "abandoned child", "child abandoned", "parent left child"],
    },
    {
        "category_aliases": ["Lacking Parental Care Unaccompanied", "Unaccompanied child"],
        "keywords": ["orphan", "orpha", "no parental care", "lacking parental care", "unaccompanied child", "no caregiver"],
    },
    {
        "category_aliases": ["Child Pregnancy", "Teenage pregnancy"],
        "keywords": ["child pregnancy", "teenage pregnancy", "teenage mother", "pregnant child"],
    },
    {
        "category_aliases": ["No Access Food", "Food insecurity", "Food assistance", "Lack of food"],
        "keywords": ["food", "hunger", "hungry", "ration", "starvation", "malnutrition", "no meals", "lack of meals"],
    },
    {
        "category_aliases": ["Medical Support", "Health support", "Health services", "Health concern"],
        "keywords": ["medical", "medicine", "medication", "hospital", "clinic", "health care", "healthcare", "treatment", "sick", "illness"],
    },
    {
        "category_aliases": ["Shelter Need", "No Access Nfi", "Shelter support", "Shelter concern", "Inadequate shelter", "Shelter and NFI"],
        "keywords": ["shelter", "tent", "house", "housing", "roof", "tarpaulin"],
    },
    {
        "category_aliases": ["WASH support", "Water sanitation and hygiene", "Water and sanitation"],
        "keywords": ["water", "latrine", "toilet", "sanitation", "hygiene", "soap", "bathing", "wash facility", "jerrycan"],
    },
    {
        "category_aliases": ["Civil Registration Services", "Undocumented", "Documentation support", "Civil documentation", "Legal documentation"],
        "keywords": ["documentation", "document", "birth certificate", "identity card", "id card", "registration", "ration card", "alien card"],
    },
    {
        "category_aliases": ["Legal assistance", "Legal support", "Access to justice"],
        "keywords": ["legal", "court", "justice", "lawyer", "police case", "arrest", "detention"],
    },
    {
        "category_aliases": ["Sexual Violence", "Gender based violence", "GBV", "Sexual and gender based violence", "SGBV"],
        "keywords": ["gbv", "sgbv", "rape", "defilement", "sexual violence", "sexual abuse", "domestic violence", "intimate partner violence", "physical violence by partner"],
    },
    {
        "category_aliases": ["Dangerous Child Work", "Child labour", "Child labor", "Economic exploitation"],
        "keywords": ["child labour", "child labor", "working child", "forced work", "economic exploitation"],
    },
    {
        "category_aliases": ["Child marriage", "Early marriage", "Forced marriage"],
        "keywords": ["child marriage", "early marriage", "forced marriage", "underage marriage", "married early"],
    },
    {
        "category_aliases": ["Joining Family", "Family separation", "Unaccompanied or separated child", "Separated child"],
        "keywords": ["family separation", "separated from family", "unaccompanied", "separated child", "missing child", "lost child", "child lost", "child got lost", "child disappeared", "looking for her children", "looking for children", "joining familly", "joining jamily", "family tracing"],
    },
    {
        "category_aliases": ["Parental Neglect", "Child Neglect", "Neglect"],
        "keywords": [
            "neglect", "neglet", "abandoned", "abandonment",
            "lack of parental care", "no caregiver", "poor care",
            "mother left the children", "mother left children",
            "father left the children", "father left children",
            "parent left the children", "parent left children",
            "leave two children", "left two children",
            "went back to country of origin", "returned to country of origin",
        ],
    },
    {
        "category_aliases": ["Physical Violence", "Child abuse", "Violence against children", "Physical abuse"],
        "keywords": ["child abuse", "beating child", "beaten child", "physical abuse", "emotional abuse", "violence against child", "corporal punishment"],
    },
    {
        "category_aliases": ["Child exploitation", "Exploitation"],
        "keywords": ["exploitation", "forced begging", "begging", "used for work"],
    },
    {
        "category_aliases": ["Trafficking", "Human trafficking"],
        "keywords": ["trafficking", "trafficked", "smuggling", "abduction", "kidnapping"],
    },
    {
        "category_aliases": ["Psychosocial support", "Mental health and psychosocial support", "MHPSS"],
        "keywords": ["psychosocial", "mental health", "stress", "distress", "trauma", "depression", "anxiety", "counselling", "counseling"],
    },
    {
        "category_aliases": ["Physical Violence", "Safety and security", "Security concern", "Threats or violence"],
        "keywords": ["insecurity", "unsafe", "security", "threat", "treatened", "treatened", "harassment", "attack", "community violence", "conflict"],
    },
    {
        "category_aliases": ["Livelihood support", "Livelihood concern", "Cash assistance"],
        "keywords": ["livelihood", "income", "employment", "job", "business", "cash assistance", "financial support", "money"],
    },
    {
        "category_aliases": ["Child Needs Assistive Devices", "Disability support", "Disability inclusion", "Assistive devices"],
        "keywords": ["disability", "wheelchair", "assistive device", "walking aid", "hearing aid", "disability support", "special needs"],
    },
]


def harmonize_protection_concern_text(text, main_category_labels, default="Other Not Listed"):
    """Map protection free text to the closest canonical listed concern."""
    cleaned = clean_text(text)
    if pd.isna(cleaned):
        return default
    normalized = normalize_response(cleaned)
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized or "")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    normalized_labels = {
        normalize_response(label): str(label)
        for label in main_category_labels
        if label and not pd.isna(label)
    }
    for rule in PROTECTION_CONCERN_TEXT_RULES:
        if not any(keyword in normalized for keyword in rule["keywords"]):
            continue
        for alias in rule["category_aliases"]:
            alias_normalized = normalize_response(alias)
            if alias_normalized in normalized_labels:
                return normalized_labels[alias_normalized]
        # If the workbook label contains extra wording, reuse that exact label.
        for label_normalized, label in normalized_labels.items():
            if any(normalize_response(alias) in label_normalized for alias in rule["category_aliases"]):
                return label
        # Token-overlap handles workbook labels with qualifiers or slightly
        # different wording, while still limiting output to a listed concern.
        best_label = None
        best_score = 0.0
        for label_normalized, label in normalized_labels.items():
            label_tokens = set(re.findall(r"[a-z0-9]+", label_normalized or ""))
            for alias in rule["category_aliases"]:
                alias_tokens = set(re.findall(r"[a-z0-9]+", normalize_response(alias) or ""))
                if not alias_tokens:
                    continue
                score = len(label_tokens & alias_tokens) / len(alias_tokens)
                if score > best_score:
                    best_label, best_score = label, score
        if best_label is not None and best_score >= 0.5:
            return best_label
        # The concept was recognised, but no corresponding listed category was
        # found. Preserve the text for review instead of inventing a category.
        return harmonize_free_text(cleaned, main_category_labels, default=default)

    return harmonize_free_text(cleaned, main_category_labels, default=default)


def standardize_protection_concern_label(value):
    """Apply preferred Child Protection terminology to concern labels."""
    cleaned = clean_text(value)
    if pd.isna(cleaned):
        return cleaned
    normalized = normalize_response(cleaned)
    family_reunification_terms = {
        "joining family", "joining familly", "joining jamily",
        "family reunion", "family reunification", "reunification with family",
    }
    if normalized in family_reunification_terms:
        return "Family Reunification"
    if normalized in {
        "separation card", "card separation", "card separation with the children because the father was died",
    }:
        return "Card Separation"
    if (
        "bamba chakula" in normalized
        or "bamba pin" in normalized
        or normalized in {
            "pin issue", "card deactivation", "deactivation card",
            "card desactivated", "card merging", "card marging", "card margin",
        }
    ):
        return "Bamba Chakula Issues"
    if normalized in {"child contact with law", "child conflict with law"}:
        return "Children in Contact with the Law"
    if normalized in {
        "sexual violence", "intimate partner violence", "gender based violence",
        "gender-based violence", "gbv", "sgbv",
    }:
        return "Gender Based Violence"
    if normalized == "age correction":
        return "Civil Registration Services"
    if "breast feeding is not enough" in normalized or "breastfeeding is not enough" in normalized:
        return "No Access Food"
    if (
        "went back to country of origin" in normalized
        and any(term in normalized for term in ["leave two children", "left two children", "leave the children"])
    ):
        return "Parental Neglect"
    return cleaned


def migrate_processed_cache_data(processed_data):
    """Apply display-rule migrations even when the fast processed cache is used."""
    if not isinstance(processed_data, tuple) or len(processed_data) != 6:
        return processed_data
    dashboard_records, secure_records, protection, information, referrals, kpis = processed_data
    if isinstance(protection, pd.DataFrame) and "protection_concern" in protection.columns:
        protection = protection.copy()
        protection["protection_concern"] = protection["protection_concern"].map(
            standardize_protection_concern_label
        )
    if isinstance(information, pd.DataFrame) and "general_information_need" in information.columns:
        information = information.copy()
        information["general_information_need"] = information["general_information_need"].map(
            standardize_information_need_label
        )
    return dashboard_records, secure_records, protection, information, referrals, kpis


def standardize_information_need_label(value):
    """Consolidate high-confidence information-request synonyms."""
    cleaned = clean_text(value)
    if pd.isna(cleaned):
        return cleaned
    normalized = normalize_response(cleaned)

    if normalized in {"scholastic materials", "scholatic materials"} or any(
        phrase in normalized for phrase in ["senior school", "sunior school", "school information"]
    ):
        return "Education"
    if normalized in {
        "need unhcr registration", "unhcr registration", "need of unhcr registration",
        "in need of unhcr registration", "unhcr profiling registration",
    }:
        return "UNHCR Registration"
    if normalized in {
        "undocumented child", "card managing", "card management", "card separation",
    }:
        return "Legal Services"
    if normalized in {"materials support", "material support", "basic needs", "basic need"}:
        return "Core Relief Items"
    if normalized in {"disability", "disability services", "assistive device support"}:
        return "Disability Support Services"
    if normalized in {"dcs", "department of children services", "children services"}:
        return "Child Protection Services"
    if normalized in {"shelter request", "shelter need", "shelter services"}:
        return "Shelter Access"
    if normalized in {"gbv support services", "gender based violence support services"}:
        return "GBV Support Services"
    if normalized in {"wash access", "water sanitation and hygiene access"}:
        return "WASH Access"
    return cleaned


def canonical_organization_label(value):
    """Return the preferred umbrella organization label for known aliases.

    This is intentionally used before generic uppercase formatting so that
    variants such as 'KENYA REDCROSS', 'RED CROSS', and 'KRCS' are consistently
    grouped as 'KRCS', and location-specific values such as 'POLICE STATION V3'
    are grouped as 'POLICE'.
    """
    key = organization_match_key(value)
    if not key:
        return None

    # Kenya Red Cross Society — use KRCS throughout the app.
    if (
        "krcs" in key.split()
        or "red cross" in key
        or "redcross" in key
        or "kenya red cross" in key
        or "kenya redcross" in key
    ):
        return "KRCS"

    # Police / police station variants, including site-specific text like V3.
    if "police" in key.split() or "police station" in key:
        return "POLICE"

    # Common umbrella/acronym clean-ups. These help group free-text variants
    # where respondents type the organization name in different ways.
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
        # Short acronyms must match as full tokens to avoid false matches
        # e.g. HI should not match the letters inside an unrelated word.
        if len(pattern) <= 4:
            if pattern in key_tokens:
                return canonical
        elif pattern in key:
            return canonical

    return None


def normalize_organization_label(value):
    """Standardize organization labels for display as uppercase acronyms/names."""
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
    """Normalize organization text for matching labels and free-text entries."""
    value = normalize_response(value)
    if value is None:
        return ""
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def organization_acronyms(value):
    """Return likely acronyms from an organization label.

    Handles labels such as 'International Rescue Committee (IRC)' and also
    creates an initialism from multi-word organization names.
    """
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
    """Map referral 'Other specify' text to umbrella organization labels where possible.

    The function first tries to match the free text to existing referral partner
    labels/acronyms, then falls back to the cleaned free-text value. All returned
    labels are uppercase for consistent organization/acronym display.
    """
    if pd.isna(text):
        return default

    txt = str(text).strip()
    if not txt:
        return default

    # If multiple organizations are typed in one cell, use the first strong
    # canonical match found anywhere in the full text. This still groups entries
    # like 'Police station V3', 'Kenya Redcross', or 'Red Cross office' correctly.
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

    # 1) Exact/substring/acronym match against existing umbrella organization labels.
    for label in clean_labels:
        label_key = organization_match_key(label)
        label_acronyms = organization_acronyms(label)
        if txt_key == label_key or (label_key and (label_key in txt_key or txt_key in label_key)):
            return normalize_organization_label(label)
        if txt_key in label_acronyms or label_acronyms.intersection(txt_tokens):
            return normalize_organization_label(label)

    # 2) Strong word-overlap match.
    for label in clean_labels:
        label_tokens = set(word for word in organization_match_key(label).split() if len(word) > 2)
        if not label_tokens:
            continue
        overlap = label_tokens & set(word for word in txt_tokens if len(word) > 2)
        if len(overlap) >= 1 and len(overlap) / len(label_tokens) >= 0.5:
            return normalize_organization_label(label)

    # 3) Fallback: keep the actual specified organization/content in CAPS.
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
    return specified_disability_type(row, ADULT_DISABILITY_CATEGORY_COLUMNS)


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
    if response not in ["yes", "y", "true", "1"]:
        return "No Disability"

    disability_type = clean_text(row.get("child_disability_type"))
    normalized_type = normalize_response(disability_type) if not pd.isna(disability_type) else None
    is_other_or_missing = normalized_type is None or is_other_disability_response(disability_type)
    if is_other_or_missing:
        specified_type = specified_disability_type(row, ["child_disability_type_other"])
        if specified_type == "None":
            return "No Disability"

    return "Has Disability"


def derive_child_disability_type(row):
    if not is_child(row) or derive_child_disability_status(row) != "Has Disability":
        return "No Disability"
    disability_type = clean_text(row.get("child_disability_type"))
    invalid = {"other", "others", "other disability", "other disabilities", "other specify", "other specified", "none", "none of the above", "not applicable", "n/a", "na", "nil"}
    normalized_type = normalize_response(disability_type) if not pd.isna(disability_type) else None
    is_other_disability = normalized_type in invalid or is_other_disability_response(disability_type)
    if normalized_type is not None and not is_other_disability:
        return standardize_disability_type(disability_type)

    # The form's authoritative detail field for the Other Disability option.
    specified_type = specified_disability_type(row, ["child_disability_type_other"])
    if specified_type != "None":
        return specified_type

    # Retain compatibility with alternate Kobo export suffixes only if the
    # authoritative field is absent or blank.
    child_other_columns = list(CHILD_DISABILITY_OTHER_COLUMNS)
    child_other_columns.extend(
        column
        for column in row.index
        if column not in child_other_columns
        and "child" in str(column).lower()
        and "disability" in str(column).lower()
        and any(token in str(column).lower() for token in ["other", "specif"])
    )
    specified_type = specified_disability_type(row, child_other_columns)
    if specified_type != "None":
        return specified_type
    return "Other Disability"


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
# KoboToolbox live source and schema contract
# -----------------------------------------------------------------------------
def setting(name, default=None):
    """Read configuration from Streamlit secrets first, then environment."""
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return os.environ.get(name, value)


def normalize_kobo_base_url(value):
    """Accept a Kobo server URL or a copied form page and retain only its host."""
    raw = str(value or "https://eu.kobotoolbox.org").strip()
    if not re.match(r"^https?://", raw, flags=re.I):
        raw = "https://" + raw
    parsed = urlsplit(raw)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def normalize_kobo_asset_uid(value):
    """Accept either the asset UID itself or a copied Kobo form URL."""
    raw = str(value or "").strip()
    match = re.search(r"(?:#/)?forms/([^/?#]+)", raw, flags=re.I)
    if not match:
        match = re.search(r"assets/([^/?#]+)", raw, flags=re.I)
    return match.group(1) if match else raw


def kobo_configured():
    return bool(setting("KOBO_TOKEN") and normalize_kobo_asset_uid(setting("KOBO_ASSET_UID")))


def configured_kobo_column_map():
    """Optional XML name/path overrides for fields whose labels were renamed."""
    raw = setting("KOBO_COLUMN_MAP", {})
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("KOBO_COLUMN_MAP must be a JSON object or TOML table.")
        return parsed
    return {}


def contract_norm(value):
    value = str(value or "").strip().casefold()
    value = value.replace("`", "'").replace("’", "'")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def metadata_labels(value):
    if isinstance(value, dict):
        values = list(value.values())
    elif isinstance(value, list):
        values = value
    else:
        values = [value]
    return [str(item).strip() for item in values if str(item).strip()]


def question_list_name(question):
    list_name = str(question.get("select_from_list_name", "") or "").strip()
    if list_name:
        return list_name
    match = re.search(r"select_(?:one|multiple)\s+(.+)$", str(question.get("type", "") or "").strip())
    return match.group(1).strip() if match else ""


def question_aliases(question):
    name = str(question.get("name", "") or "").strip().lstrip("/")
    xpath = str(question.get("$xpath", "") or "").strip().lstrip("/")
    aliases = []
    for value in (name, xpath):
        if value and value not in aliases:
            aliases.append(value)
        if "/" in value:
            without_root = value.split("/", 1)[1]
            if without_root and without_root not in aliases:
                aliases.append(without_root)
    return aliases


def resolve_contract_target(candidates):
    exact = {str(key).strip(): value for key, value in RAW_TO_TRANSFORMED_COLUMNS.items()}
    normalized = {contract_norm(key): value for key, value in RAW_TO_TRANSFORMED_COLUMNS.items()}
    for candidate in candidates:
        raw = str(candidate or "").strip()
        target = exact.get(raw) or normalized.get(contract_norm(raw))
        if target:
            return target
        if raw in ANALYSIS_COLUMN_NAMES:
            return raw
    return None


def flatten_kobo_record(record, prefix=""):
    flat = {}
    for key, value in record.items():
        full_key = f"{prefix}/{key}" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(flatten_kobo_record(value, full_key))
        else:
            flat[full_key] = value
    return flat


@st.cache_data(show_spinner=False, ttl=KOBO_SCHEMA_CACHE_TTL_SECONDS, max_entries=4)
def fetch_kobo_form_contract(base_url, asset_uid, token):
    """Build field and choice mappings from the currently deployed XLSForm."""
    url = f"{base_url.rstrip('/')}/api/v2/assets/{asset_uid}/"
    response = requests.get(
        url,
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
        timeout=KOBO_REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code in {401, 403}:
        raise RuntimeError("Kobo rejected the token or this account cannot view the form schema.")
    response.raise_for_status()
    payload = response.json()
    content = payload.get("content", {}) or {}
    survey = content.get("survey", []) or []
    choices = content.get("choices", []) or []
    choices_by_list = {}
    for choice in choices:
        if isinstance(choice, dict):
            choices_by_list.setdefault(str(choice.get("list_name", "") or "").strip(), []).append(choice)

    schema_map = {}
    single_choice_maps = {}
    multiple_expansions = []
    unresolved_questions = []

    for question in survey:
        if not isinstance(question, dict):
            continue
        aliases = question_aliases(question)
        labels = metadata_labels(question.get("label", ""))
        target = resolve_contract_target([*labels, *aliases])
        if target:
            for alias in aliases:
                schema_map[alias] = target

        question_type = str(question.get("type", "") or "").strip().lower()
        list_name = question_list_name(question)
        question_choices = choices_by_list.get(list_name, [])
        if question_type.startswith("select_one") and target and question_choices:
            translated = {}
            for choice in question_choices:
                code = str(choice.get("name", "") or "").strip()
                labels_for_choice = metadata_labels(choice.get("label", ""))
                if code and labels_for_choice:
                    translated[code] = labels_for_choice[0]
                    translated[contract_norm(code)] = labels_for_choice[0]
            if translated:
                single_choice_maps[target] = translated

        if question_type.startswith("select_multiple") and question_choices:
            for choice in question_choices:
                code = str(choice.get("name", "") or "").strip()
                choice_labels = metadata_labels(choice.get("label", ""))
                expanded_candidates = []
                for question_label in labels:
                    for choice_label in choice_labels:
                        expanded_candidates.append(f"{question_label}/{choice_label}")
                binary_target = resolve_contract_target(expanded_candidates)
                if code and binary_target:
                    multiple_expansions.append(
                        {"aliases": aliases, "code": code, "target": binary_target}
                    )

        if labels and not target and question_type not in {"begin_group", "end_group", "note"}:
            if not any(item.get("aliases") == aliases for item in multiple_expansions):
                unresolved_questions.append(labels[0])

    # Explicit overrides win over schema inference and can point nested XML
    # paths to any established transformed analysis column.
    schema_map.update(configured_kobo_column_map())
    return {
        "asset_name": payload.get("name") or payload.get("settings", {}).get("form_title") or asset_uid,
        "schema_map": schema_map,
        "single_choice_maps": single_choice_maps,
        "multiple_expansions": multiple_expansions,
        "unresolved_questions": sorted(set(unresolved_questions)),
    }


def selected_choice(value, code):
    if value is None or (not isinstance(value, (list, tuple, set)) and pd.isna(value)):
        return 0
    if isinstance(value, (list, tuple, set)):
        tokens = {str(item).strip() for item in value}
    else:
        tokens = {item for item in re.split(r"[\s;,|]+", str(value).strip()) if item}
    return int(str(code).strip() in tokens)


def coalesce_duplicate_columns(frame):
    if not frame.columns.duplicated().any():
        return frame
    combined = {}
    for position, column in enumerate(frame.columns):
        series = frame.iloc[:, position]
        if column not in combined:
            combined[column] = series.copy()
        else:
            current = combined[column]
            missing = current.isna() | current.astype(str).str.strip().isin(["", "nan", "None"])
            combined[column] = current.where(~missing, series)
    return pd.DataFrame(combined, index=frame.index)


def harmonize_input_columns(frame):
    """Apply the immutable label/name contract without relying on positions."""
    out = frame.copy()
    out.columns = [str(column).strip() for column in out.columns]
    original_columns = list(out.columns)
    exact = {str(key).strip(): value for key, value in RAW_TO_TRANSFORMED_COLUMNS.items()}
    normalized = {contract_norm(key): value for key, value in RAW_TO_TRANSFORMED_COLUMNS.items()}
    rename_map = {}
    for column in out.columns:
        target = exact.get(column) or normalized.get(contract_norm(column))
        if target:
            rename_map[column] = target
        elif column in ANALYSIS_COLUMN_NAMES:
            rename_map[column] = column
    if rename_map:
        out = out.rename(columns=rename_map)
    out = coalesce_duplicate_columns(out)
    mapped_sources = set(rename_map)
    out.attrs["unmapped_source_columns"] = sorted(
        column for column in original_columns if column not in mapped_sources and not str(column).startswith("_")
    )
    out.attrs["missing_contract_columns"] = sorted(set(ANALYSIS_COLUMN_NAMES) - set(out.columns))
    return out


@st.cache_data(show_spinner=False, ttl=KOBO_CACHE_TTL_SECONDS, max_entries=4)
def fetch_kobo_submissions(base_url, asset_uid, token, refresh_nonce=0):
    """Fetch all Kobo KPI v2 pages and convert them to the dashboard contract."""
    del refresh_nonce
    url = f"{base_url.rstrip('/')}/api/v2/assets/{asset_uid}/data/"
    headers = {"Authorization": f"Token {token}", "Accept": "application/json"}
    submissions = []
    page_count = 0
    with requests.Session() as session:
        while url:
            response = session.get(url, headers=headers, timeout=KOBO_REQUEST_TIMEOUT_SECONDS)
            if response.status_code in {401, 403}:
                raise RuntimeError("Kobo rejected the token or this account cannot view submissions.")
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                submissions.extend(payload)
                url = None
            else:
                submissions.extend(payload.get("results", []))
                url = payload.get("next")
            page_count += 1
            if page_count > KOBO_PAGE_SAFETY_LIMIT:
                raise RuntimeError("Kobo pagination exceeded the safety limit.")

    # Hash the complete raw response so additions, edits, and deletions are all
    # detected. The monitor can then avoid disrupting the page when nothing
    # has changed.
    canonical_submissions = sorted(
        json.dumps(
            submission,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        for submission in submissions
    )
    data_fingerprint = hashlib.sha256(
        "\n".join(canonical_submissions).encode("utf-8")
    ).hexdigest()

    flattened = [flatten_kobo_record(item) for item in submissions]
    raw = pd.json_normalize(flattened, sep="/") if flattened else pd.DataFrame()
    contract = fetch_kobo_form_contract(base_url, asset_uid, token)

    # Recreate Kobo export's expanded binary columns from select_multiple
    # response codes before field renaming.
    for expansion in contract["multiple_expansions"]:
        source = next((alias for alias in expansion["aliases"] if alias in raw.columns), None)
        if source:
            values = raw[source].map(lambda value, code=expansion["code"]: selected_choice(value, code))
            target = expansion["target"]
            if target in raw.columns:
                raw[target] = pd.to_numeric(raw[target], errors="coerce").fillna(values)
            else:
                raw[target] = values

    applicable = {
        source: target
        for source, target in contract["schema_map"].items()
        if source in raw.columns
    }
    if applicable:
        raw = raw.rename(columns=applicable)
    raw = coalesce_duplicate_columns(raw)

    for target, choice_map in contract["single_choice_maps"].items():
        if target in raw.columns:
            raw[target] = raw[target].map(
                lambda value, mapping=choice_map: mapping.get(str(value).strip())
                or mapping.get(contract_norm(value))
                or value
            )

    raw = harmonize_input_columns(raw)
    metadata = {
        "mode": "KoboToolbox API",
        "asset_uid": asset_uid,
        "asset_name": contract["asset_name"],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "api_pages": page_count,
        "raw_records": len(raw),
        "data_fingerprint": data_fingerprint,
        "unmapped_source_columns": raw.attrs.get("unmapped_source_columns", []),
        "missing_contract_columns": raw.attrs.get("missing_contract_columns", []),
        "unresolved_schema_questions": contract["unresolved_questions"],
    }
    return raw, metadata


if hasattr(st, "fragment"):
    @st.fragment(run_every=f"{KOBO_CHANGE_CHECK_SECONDS}s")
    def live_change_monitor(base_url, asset_uid, known_fingerprint):
        """Check Kobo quietly and rerun the page only when its data changes."""
        try:
            _, current_metadata = fetch_kobo_submissions(
                base_url,
                asset_uid,
                str(setting("KOBO_TOKEN")),
                st.session_state.get("helpdesk_kobo_refresh_nonce", 0),
            )
        except Exception:
            # A temporary monitoring failure must not interrupt dashboard use.
            return

        current_fingerprint = current_metadata.get("data_fingerprint")
        if (
            known_fingerprint
            and current_fingerprint
            and current_fingerprint != known_fingerprint
        ):
            load_data.clear()
            st.rerun()
else:
    def live_change_monitor(base_url, asset_uid, known_fingerprint):
        del base_url, asset_uid, known_fingerprint
        return None


# -----------------------------------------------------------------------------
# Data loading
# -----------------------------------------------------------------------------
def data_file_signature(path):
    if not path.exists():
        return str(path), None, None, None
    stat = path.stat()
    return (
        str(path.resolve()),
        stat.st_mtime_ns,
        stat.st_size,
        pd.to_datetime(stat.st_mtime, unit="s").strftime("%d %b %Y %H:%M:%S"),
    )


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


@st.cache_resource(show_spinner="Loading latest helpdesk dataset...", ttl=KOBO_CACHE_TTL_SECONDS, max_entries=4)
def load_data(source_signature):
    source_mode = source_signature[0]
    file_signature = source_signature[1:] if source_mode == "local" else (None, None, None, None)
    if source_mode == "local" and not DATA_FILE_PATH.exists():
        raise FileNotFoundError(f"File not found: {DATA_FILE_PATH}")

    # Fast path for deployed apps: load already-processed data if a matching
    # processed cache exists. This avoids reparsing Excel and rerunning all
    # transformations on Streamlit Cloud cold starts. Generate this cache once
    # locally by running the app, then commit data/processed/helpdesk_processed_cache.pkl.
    processed_cache_key = {
        "version": PROCESSED_CACHE_VERSION,
        # Use file size, not modified time, so a cache generated locally and
        # committed to GitHub can still match after Streamlit Cloud checkout
        # changes file timestamps.
        "source_size": file_signature[2],
    }
    if source_mode == "local" and PROCESSED_CACHE_PATH.exists():
        try:
            with PROCESSED_CACHE_PATH.open("rb") as cache_file:
                cached_payload = pickle.load(cache_file)
            if cached_payload.get("cache_key") == processed_cache_key:
                return migrate_processed_cache_data(cached_payload["data"])
        except Exception:
            # If the processed cache is stale/corrupt, fall back to rebuilding
            # from Excel rather than blocking the app.
            pass

    source_metadata = {"mode": "Local Excel fallback"}
    if source_mode == "kobo":
        base_url, asset_uid, refresh_nonce = source_signature[1:4]
        token = str(setting("KOBO_TOKEN"))
        records, source_metadata = fetch_kobo_submissions(
            base_url, asset_uid, token, refresh_nonce
        )
    else:
        try:
            if DATA_FILE_PATH.suffix.lower() == ".csv":
                records = pd.read_csv(DATA_FILE_PATH)
            else:
                records = pd.read_excel(DATA_FILE_PATH)
        except Exception as error:
            raise RuntimeError(f"Could not read the workbook: {error}") from error
        records = harmonize_input_columns(records)
        source_metadata.update(
            {
                "raw_records": len(records),
                "fetched_at": file_signature[3],
                "unmapped_source_columns": records.attrs.get("unmapped_source_columns", []),
                "missing_contract_columns": records.attrs.get("missing_contract_columns", []),
            }
        )

    # Consent is an eligibility gate, not a dashboard category. Exclude only
    # explicit refusals before deriving fields or calculating any result.
    consent_priority = [
        "consent",
        "do_you_consent",
        "consent_to_participate",
        "information_statement",
    ]
    consent_column = next((column for column in consent_priority if column in records.columns), None)
    if consent_column is None:
        consent_column = next(
            (column for column in records.columns if "consent" in str(column).lower()),
            None,
        )
    if consent_column is not None:
        records["consent_raw"] = records[consent_column].map(clean_text)
        records["consent_declined"] = records[consent_column].map(consent_is_declined)
        records = records.loc[~records["consent_declined"]].copy()
    else:
        records["consent_raw"] = pd.NA
        records["consent_declined"] = False

    mapping = pd.DataFrame(COLUMN_MAPPING_RECORDS)

    required_columns = [
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
        "visited_tdh_helpdesk_before",
        "last_visit_within_current_month",
        "child_unaccompanied_minor",
        "respondent_relationship_to_child",
        "respondent_relationship_other",
        "request_type_protection_or_information",
        "action_taken",
        "follow_up_required",
        "has_disability",
        "child_disability_type",
        "child_disability_type_other",
    ]
    required_columns.extend(WGQ_DISABILITY_DOMAINS.keys())
    required_columns.extend(ADULT_DISABILITY_CATEGORY_COLUMNS)
    required_columns.extend(CHILD_DISABILITY_OTHER_COLUMNS)
    for column in required_columns:
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
    records["age_group"] = records["information_seeker_age"].map(clean_text)
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
    records["visited_tdh_helpdesk_before_raw"] = records[
        "visited_tdh_helpdesk_before"
    ].map(clean_text)
    records["helpdesk_visit_history"] = records[
        "visited_tdh_helpdesk_before"
    ].map(derive_helpdesk_visit_history)
    records["last_visit_within_current_month_raw"] = records[
        "last_visit_within_current_month"
    ].map(clean_text)
    records["repeat_visit_timing"] = records.apply(
        derive_repeat_visit_timing,
        axis=1,
    )
    records["visit_history_consistency"] = records.apply(
        derive_visit_history_consistency,
        axis=1,
    )
    records["visit_history_inconsistency_flag"] = records[
        "visit_history_consistency"
    ].astype(str).str.startswith("Review")
    records["child_unaccompanied_minor_raw"] = records[
        "child_unaccompanied_minor"
    ].map(clean_text)
    records["respondent_relationship_to_child_raw"] = records[
        "respondent_relationship_to_child"
    ].map(clean_text)
    records["respondent_relationship_other_raw"] = records[
        "respondent_relationship_other"
    ].map(clean_text)
    records["child_accompaniment_status"] = records.apply(
        derive_child_accompaniment_status,
        axis=1,
    )

    records["request_category"] = records["request_type_protection_or_information"].map(clean_text)
    records["action_taken_clean"] = records["action_taken"].map(clean_text)
    records["follow_up_required_clean"] = records["follow_up_required"].map(clean_text)
    records["helpdesk_location"] = records.apply(derive_linked_helpdesk_location, axis=1)
    records["has_disability_raw"] = records["has_disability"].map(clean_text)
    records["child_disability_type_raw"] = records["child_disability_type"].map(clean_text)

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
    # Apply the correction to the working source field as well as the derived
    # status. This ensures every downstream KPI, chart, table and export counts
    # an unsubstantiated child "Other Disability" response alongside No.
    child_other_without_detail = (
        records.apply(is_child, axis=1)
        & records["has_disability_raw"].map(lambda value: normalize_response(value) in ["yes", "y", "true", "1"])
        & records["child_disability_type_raw"].map(is_other_disability_response)
        & records.apply(
            lambda row: specified_disability_type(row, ["child_disability_type_other"]) == "None",
            axis=1,
        )
    )
    records["child_disability_reclassified_no"] = child_other_without_detail
    records.loc[child_other_without_detail, "has_disability"] = "No"
    records["child_disability_type"] = records.apply(derive_child_disability_type, axis=1)
    records["disability_status"] = records.apply(derive_combined_disability_status, axis=1)
    records["disability_type"] = records.apply(derive_combined_disability_type, axis=1)

    records["referral_status"] = "No referral"
    records.loc[records["action_taken_clean"].eq("Case referrred to Tdh national staff"), "referral_status"] = "Referred to Tdh national staff"
    records.loc[records["action_taken_clean"].eq("Case referred to partner agencies"), "referral_status"] = "Referred to partner agency"
    records.loc[
        records["action_taken_clean"].eq("Case not referred to any partner BUT information counselling provided"),
        "referral_status",
    ] = "Information counselling only"
    records.loc[records["action_taken_clean"].eq("Action not taken at all"), "referral_status"] = "No action taken"

    core_fields = ["interview_date", "information_seeker_type", "camp_location", "information_seeker_gender", "age_group", "request_category"]
    for col in core_fields:
        if col not in records.columns:
            records[col] = pd.NA
    records = records[records[core_fields].notna().all(axis=1)].copy()

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
        long = long[pd.to_numeric(long["selected"], errors="coerce").eq(1)].drop(columns="selected")
        long[label_name] = long[code_name].map(label_map).fillna(long[code_name].map(safe_label_from_code))
        return long

    protection = melt_selected(protection_cols, "protection_concern_code", "protection_concern", protection_label_map)
    information = melt_selected(information_cols, "general_information_code", "general_information_need", information_label_map)
    referrals = melt_selected(referral_cols, "referral_partner_code", "referral_partner", referral_label_map)

    # ------------------------------------------------------------------
    # Harmonize explicit "Other Not Listed" selections with their paired
    # free-text specify columns.
    #
    # Protection:
    #   concern_other_not_listed  -> use text from concern_other_specify
    # Information:
    #   info_other_not_listed     -> use text from info_other_specify
    #
    # This prevents charts/tables from keeping a generic "Other Not Listed"
    # bucket when the respondent actually specified a meaningful value.
    # ------------------------------------------------------------------
    protection_other_codes = protection["protection_concern_code"].astype(str).str.contains(
        r"^concern_.*other", case=False, na=False, regex=True
    ) if not protection.empty else pd.Series(dtype=bool)
    observed_protection_labels = (
        protection.loc[~protection_other_codes, "protection_concern"].dropna().astype(str).tolist()
        if not protection.empty
        else []
    )
    main_protection_labels = list(dict.fromkeys([
        value
        for value in list(protection_label_map.values()) + observed_protection_labels
        if value and normalize_response(value) not in ["other", "other not listed", "others", "other specify"]
    ]))
    main_information_labels = [
        value
        for value in information_label_map.values()
        if value and normalize_response(value) not in ["other", "other not listed", "others", "other specify"]
    ]

    concern_specify_columns = [
        column
        for column in records.columns
        if str(column).startswith("concern_") and str(column).endswith("_specify")
    ]
    if "concern_other_specify" in concern_specify_columns:
        concern_specify_columns.remove("concern_other_specify")
        concern_specify_columns.insert(0, "concern_other_specify")

    if not protection.empty and concern_specify_columns:
        concern_specify_values = records.set_index("record_id")[concern_specify_columns].apply(
            lambda row: next(
                (clean_text(value) for value in row if not pd.isna(clean_text(value))),
                pd.NA,
            ),
            axis=1,
        ).to_dict()
        concern_other_mask = protection["protection_concern_code"].astype(str).str.contains(
            r"^concern_.*other",
            case=False,
            na=False,
            regex=True,
        )
        protection.loc[concern_other_mask, "protection_concern"] = protection.loc[
            concern_other_mask, "record_id"
        ].map(
            lambda record_id: harmonize_protection_concern_text(
                clean_text(concern_specify_values.get(record_id)),
                main_protection_labels,
                default="Other Not Listed",
            )
        )

    if not protection.empty and "protection_concern" in protection.columns:
        protection["protection_concern"] = protection["protection_concern"].map(
            standardize_protection_concern_label
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

    if not information.empty and "general_information_need" in information.columns:
        information["general_information_need"] = information["general_information_need"].map(
            standardize_information_need_label
        )

    # Referral partner harmonization:
    #   ref_partner_other -> use text from ref_partner_other_specify
    # Then return organization labels in CAPS for consistent acronym display.
    main_referral_labels = [
        value
        for value in referral_label_map.values()
        if value and organization_match_key(value) not in ["other", "other not listed", "others", "other specify"]
    ]

    if not referrals.empty and "ref_partner_other_specify" in records.columns:
        referral_specify_values = records.set_index("record_id")["ref_partner_other_specify"].to_dict()

        # Be intentionally broad here. Some exports may keep the exact code
        # as ref_partner_other, while others may label it as something like
        # ref_partner_other_not_listed. Both should be replaced by the paired
        # ref_partner_other_specify text.
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

        # Optional audit fields are useful in the Records tab / debugging and
        # do not affect the charts. They make it clear what was replaced.
        referrals.loc[referral_other_mask, "referral_partner_other_specify_raw"] = referrals.loc[
            referral_other_mask, "record_id"
        ].map(referral_specify_values)
        referrals.loc[referral_other_mask, "referral_partner_harmonized_from_other"] = True
        referrals["referral_partner_harmonized_from_other"] = referrals[
            "referral_partner_harmonized_from_other"
        ].fillna(False)

    if not referrals.empty and "referral_partner" in referrals.columns:
        referrals["referral_partner"] = referrals["referral_partner"].map(normalize_organization_label)
        # Partner selections are valid only for cases whose final action was a
        # partner-agency referral. Keep one row per case-partner assignment;
        # a case sent to two partners legitimately contributes two mentions.
        partner_referred_ids = set(
            records.loc[
                records["referral_status"].eq("Referred to partner agency"),
                "record_id",
            ].astype(str)
        )
        referrals = referrals[
            referrals["record_id"].astype(str).isin(partner_referred_ids)
        ].copy()
        referrals = referrals.drop_duplicates(
            subset=["record_id", "referral_partner"],
            keep="first",
        )

    # Keep two record frames:
    # - secure_records keeps PII for password-protected DQA follow-up tables.
    # - dashboard_records removes PII and is used by normal dashboard views/downloads.
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
                "first_time_visitor_records",
                "repeat_visitor_records",
                "repeat_visits_within_current_month",
                "visit_history_inconsistency_records",
                "unaccompanied_child_records",
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
                dashboard_records["helpdesk_visit_history"].eq("First-time visitor").sum(),
                dashboard_records["helpdesk_visit_history"].eq("Repeat visitor").sum(),
                dashboard_records["repeat_visit_timing"].eq("Repeat — within current month").sum(),
                dashboard_records["visit_history_inconsistency_flag"].sum(),
                dashboard_records["child_accompaniment_status"].eq("Unaccompanied").sum(),
            ],
        }
    )

    processed_data = (dashboard_records, secure_records, protection, information, referrals, kpis)
    if source_mode == "local":
        try:
            PROCESSED_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with PROCESSED_CACHE_PATH.open("wb") as cache_file:
                pickle.dump(
                    {
                        "cache_key": processed_cache_key,
                        "data": processed_data,
                    },
                    cache_file,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
        except Exception:
            # Processed-cache writing is an optimization only; the app should
            # still work when the filesystem is read-only.
            pass

    migrated = migrate_processed_cache_data(processed_data)
    for frame in migrated:
        if hasattr(frame, "attrs"):
            frame.attrs["source_metadata"] = source_metadata
    return migrated

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
    st.session_state.pop("date_range_filter", None)
    for key in FILTER_KEYS:
        st.session_state[key] = []
    st.session_state["records_search"] = ""
    st.session_state["helpdesk_section_category"] = "Summary"
    st.session_state["helpdesk_section"] = "Overview"


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
    legend_columns = max(1, min(5, len(available)))
    return alt.Color(
        field,
        title="Gender",
        scale=alt.Scale(domain=available, range=[GENDER_COLORS[g] for g in available]),
        sort=available,
        legend=alt.Legend(
            symbolType="circle",
            orient="bottom",
            direction="horizontal",
            columns=legend_columns,
            labelLimit=140,
            columnPadding=18,
            rowPadding=4,
        ),
    )


def category_color(field, title=None, domain=None, legend=True):
    color_kwargs = {
        "title": title,
        "scale": alt.Scale(range=CHART_CATEGORY_COLORS),
    }

    if domain:
        color_kwargs["scale"] = alt.Scale(
            domain=domain,
            range=CHART_CATEGORY_COLORS[: len(domain)],
        )

    if legend:
        color_kwargs["legend"] = alt.Legend(symbolType="circle", orient="bottom", columns=3, labelLimit=120)
    else:
        color_kwargs["legend"] = None

    return alt.Color(field, **color_kwargs)


def polish_chart(chart):
    return (
        chart.configure_axis(
            labelColor="#334155",
            titleColor="#1E293B",
            gridColor="#E2E8F0",
            domainColor="#CBD5D1",
            tickColor="#CBD5D1",
            labelFontSize=12,
            titleFontSize=13,
            titleFontWeight=700,
            labelLimit=1000,
            labelPadding=6,
            titlePadding=10,
        )
        .configure_axisY(grid=True)
        .configure_axisX(
            grid=False,
            labelBound=True,
            labelFlush=True,
            labelFlushOffset=4,
            labelOverlap="parity",
            labelLimit=160,
        )
        .configure_legend(
            labelColor="#1E293B",
            titleColor="#1E293B",
            labelFontSize=12,
            titleFontSize=13,
            titleFontWeight=700,
            orient="bottom",
            symbolType="circle",
            symbolSize=125,
        )
        .configure_header(
            labelColor="#12312F",
            titleColor="#12312F",
            labelFontSize=12,
            titleFontSize=13,
            labelFontWeight=700,
            titleFontWeight=800,
        )
        .configure_title(
            color="#12312F",
            fontSize=15,
            fontWeight=800,
            anchor="start",
            offset=10,
        )
        .configure_view(strokeWidth=0)
        .configure(background="transparent", font="Inter, Segoe UI, system-ui, sans-serif")
    )


def display_category_value(value):
    """Apply concise presentation labels without altering retained raw values."""
    if pd.isna(value):
        return value
    normalized = normalize_response(value)
    if normalized and "chronic illness" in normalized:
        return "Chronic Illnesses"
    return value


def chart_headroom(values, fraction=0.18):
    """Return a safe quantitative upper bound for labels drawn beyond marks."""
    numeric = pd.to_numeric(pd.Series(values), errors="coerce").fillna(0)
    maximum = float(numeric.max()) if not numeric.empty else 0.0
    return max(1.0, maximum * (1.0 + fraction))


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
    label_columns = [label_column] if label_column in table.columns else []

    formatters = {}
    for col in numeric_columns:
        if pd.api.types.is_numeric_dtype(table[col]):
            formatters[col] = "{:,.0f}"

    def highlight_total_row(row):
        if row[label_column] == "Total":
            return [
                "background-color: #DCEBE4; color: #0B2523; font-weight: 850; "
                "border-top: 2px solid #2F7D69;"
                for _ in row
            ]

        background = "#FFFFFF" if row.name % 2 == 0 else "#F6FAF8"
        return [f"background-color: {background}; color: #1E293B;" for _ in row]

    def highlight_total_column(column):
        if column.name == "Total":
            return [
                "background-color: #FFF1CC; color: #0B2523; font-weight: 850; "
                "border-left: 2px solid #E3B341;"
                for _ in column
            ]
        return ["" for _ in column]

    def mute_missing(value):
        if str(value) in ["[Missing]", "[Not recorded]", "None", "nan", "NaT"]:
            return "color: #94A3B8; font-style: italic;"
        return ""

    styled = (
        table.style.format(formatters)
        .apply(highlight_total_row, axis=1)
        .apply(highlight_total_column, axis=0)
    )
    styled = styled.map(mute_missing) if hasattr(styled, "map") else styled.applymap(mute_missing)

    return (
        styled
        .set_properties(
            subset=label_columns,
            **{
                "text-align": "left",
                "font-weight": "700",
                "white-space": "normal",
                "min-width": "180px",
            },
        )
        .set_properties(
            subset=numeric_columns,
            **{
                "text-align": "right",
                "font-variant-numeric": "tabular-nums",
                "font-feature-settings": '"tnum"',
                "min-width": "72px",
            },
        )
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#12312F"),
                        ("color", "#FFFFFF"),
                        ("font-weight", "850"),
                        ("text-align", "center"),
                        ("border", "1px solid #D8E2DC"),
                        ("border-bottom", "3px solid #D9A441"),
                        ("padding", "10px 12px"),
                        ("white-space", "normal"),
                    ],
                },
                {
                    "selector": "td",
                    "props": [
                        ("border", "1px solid #E3ECE7"),
                        ("padding", "8px 10px"),
                        ("vertical-align", "middle"),
                    ],
                },
                {
                    "selector": "tbody tr:hover td",
                    "props": [
                        ("background-color", "#FFF8E7"),
                    ],
                },
            ]
        )
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

    descriptor_columns = [
        col
        for col in display_table.columns
        if col not in numeric_columns and col not in date_columns
    ]

    def zebra_rows(row):
        background = "#FFFFFF" if row.name % 2 == 0 else "#F6FAF8"
        return [f"background-color: {background}; color: #1E293B;" for _ in row]

    def highlight_total_like_rows(row):
        first_value = str(row.iloc[0]) if len(row) else ""
        if first_value == "Total":
            return [
                "background-color: #DCEBE4; color: #0B2523; font-weight: 850; "
                "border-top: 2px solid #2F7D69;"
                for _ in row
            ]
        return ["" for _ in row]

    def mute_missing(value):
        if str(value) in ["[Missing]", "[Not recorded]", "None", "nan", "NaT"]:
            return "color: #94A3B8; font-style: italic;"
        return ""

    styled = (
        display_table.style.format(formatters)
        .apply(zebra_rows, axis=1)
        .apply(highlight_total_like_rows, axis=1)
    )
    styled = styled.map(mute_missing) if hasattr(styled, "map") else styled.applymap(mute_missing)

    return (
        styled
        .set_properties(
            subset=descriptor_columns,
            **{
                "text-align": "left",
                "white-space": "normal",
                "min-width": "150px",
            },
        )
        .set_properties(
            subset=numeric_columns,
            **{
                "text-align": "right",
                "font-variant-numeric": "tabular-nums",
                "font-feature-settings": '"tnum"',
                "min-width": "72px",
            },
        )
        .set_properties(
            subset=date_columns,
            **{
                "text-align": "left",
                "white-space": "nowrap",
                "min-width": "112px",
            },
        )
        .set_table_styles(
            [
                {
                    "selector": "th",
                    "props": [
                        ("background-color", "#12312F"),
                        ("color", "#FFFFFF"),
                        ("font-weight", "850"),
                        ("text-align", "left"),
                        ("border", "1px solid #D8E2DC"),
                        ("border-bottom", "3px solid #D9A441"),
                        ("padding", "10px 12px"),
                        ("white-space", "normal"),
                    ],
                },
                {
                    "selector": "td",
                    "props": [
                        ("border", "1px solid #E3ECE7"),
                        ("padding", "8px 10px"),
                        ("vertical-align", "middle"),
                    ],
                },
                {
                    "selector": "tbody tr:hover td",
                    "props": [
                        ("background-color", "#FFF8E7"),
                    ],
                },
            ]
        )
    )


def display_table_value(value):
    if pd.isna(value):
        return ""

    if isinstance(value, pd.Timestamp):
        return value.strftime("%d %b %Y")

    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return value.strftime("%d %b %Y")
        except Exception:
            pass

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value).is_integer():
            return f"{int(value):,}"
        return f"{value:,.1f}"

    return str(value)


def render_dashboard_table(table, label_column=None, max_height=560):
    if table.empty:
        st.info("No records match the selected filters.")
        return

    display_table = table.copy()
    columns = display_table.columns.tolist()
    numeric_columns = display_table.select_dtypes(include="number").columns.tolist()

    header_cells = []
    for column in columns:
        classes = []
        if column in numeric_columns:
            classes.append("numeric")
        if column == "Total":
            classes.append("total-col")
        class_attr = f' class="{" ".join(classes)}"' if classes else ""
        header_cells.append(f"<th{class_attr}>{escape_text(column)}</th>")

    body_rows = []
    for _, row in display_table.iterrows():
        first_value = str(row.iloc[0]) if len(row) else ""
        is_total_row = first_value == "Total" or (
            label_column in display_table.columns and str(row.get(label_column)) == "Total"
        )
        row_class = ' class="total-row"' if is_total_row else ""
        cells = []

        for column in columns:
            value = row[column]
            display_value = display_table_value(value)
            classes = []

            if column == label_column or column == columns[0]:
                classes.append("label-cell")
            if column in numeric_columns:
                classes.append("numeric")
            if column == "Total":
                classes.append("total-col")
            if display_value in ["[Missing]", "[Not recorded]", "None", "nan", "NaT", ""]:
                classes.append("missing")

            class_attr = f' class="{" ".join(classes)}"' if classes else ""
            cells.append(f"<td{class_attr}>{escape_text(display_value)}</td>")

        body_rows.append(f"<tr{row_class}>{''.join(cells)}</tr>")

    # Reserve the table's rendered height explicitly. Relying only on
    # max-height can let Streamlit measure the Markdown block before the custom
    # table finishes laying out, causing the following subsection to overlap it.
    natural_height = 50 + (len(display_table) * 41)
    wrapper_height = min(int(max_height), max(92, natural_height))
    table_html = (
        f'<div class="dashboard-table-wrap" '
        f'style="height: {wrapper_height}px; max-height: {int(max_height)}px;">'
        + '<table class="dashboard-table">'
        + f"<thead><tr>{''.join(header_cells)}</tr></thead>"
        + f"<tbody>{''.join(body_rows)}</tbody>"
        + "</table></div>"
    )

    if hasattr(st, "html"):
        st.html(table_html)
    else:
        st.markdown(table_html, unsafe_allow_html=True)


def show_gender_table(frame, category_column, category_label, top_n=None):
    table = gender_pivot_table(frame, category_column, category_label, top_n=top_n)
    if table.empty:
        st.info("No records match the selected filters.")
        return
    render_dashboard_table(table, label_column=category_label)


def age_breakdown_options(frame, category_column):
    if frame.empty or category_column not in frame.columns:
        return []

    return (
        frame[category_column]
        .dropna()
        .astype(str)
        .value_counts()
        .index
        .tolist()
    )


def age_gender_breakdown_table(frame, category_column, selected_categories, category_label):
    if (
        frame.empty
        or category_column not in frame.columns
        or "age_group" not in frame.columns
        or "information_seeker_gender" not in frame.columns
    ):
        return pd.DataFrame()

    if not selected_categories:
        return pd.DataFrame()

    selected = frame.copy()
    selected[category_column] = selected[category_column].map(clean_text).fillna("[Missing]")
    selected["age_group"] = selected["age_group"].map(clean_text).fillna("[Missing]")
    selected["information_seeker_gender"] = (
        selected["information_seeker_gender"].map(clean_text).fillna("[Missing]")
    )
    selected = selected[selected[category_column].astype(str).isin(selected_categories)]

    if selected.empty:
        return pd.DataFrame()

    grouped = (
        selected.groupby(["age_group", "information_seeker_gender"], dropna=False)
        .size()
        .reset_index(name="Records")
    )

    table = grouped.pivot_table(
        index="age_group",
        columns="information_seeker_gender",
        values="Records",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    gender_columns = [gender for gender in GENDER_ORDER if gender in table.columns]
    other_gender_columns = [
        col
        for col in table.columns
        if col not in ["age_group"] + gender_columns
    ]
    numeric_columns = gender_columns + other_gender_columns
    table["Total"] = table[numeric_columns].sum(axis=1)

    age_order_map = {age: index for index, age in enumerate(AGE_GROUP_ORDER)}
    table["_sort_order"] = table["age_group"].map(age_order_map).fillna(999)
    table = table.sort_values(["_sort_order", "age_group"]).drop(columns="_sort_order")

    table = table.rename(columns={"age_group": "Age group"})
    ordered_columns = ["Age group"] + numeric_columns + ["Total"]
    table = table[ordered_columns]

    total_row = {"Age group": "Total"}
    for col in numeric_columns + ["Total"]:
        total_row[col] = table[col].sum()

    return pd.concat([table, pd.DataFrame([total_row])], ignore_index=True)


def draw_age_gender_breakdown_bar(
    frame,
    category_column,
    selected_categories,
    category_label,
    height=340,
):
    table = age_gender_breakdown_table(
        frame,
        category_column,
        selected_categories,
        category_label,
    )

    if table.empty:
        st.info("No age breakdown is available for the selected option.")
        return

    chart_data = table[table["Age group"] != "Total"].copy()

    if chart_data.empty:
        st.info("No age breakdown is available for the selected option.")
        return

    gender_columns = [
        col
        for col in chart_data.columns
        if col not in ["Age group", "Total"]
    ]

    long_chart = chart_data.melt(
        id_vars=["Age group"],
        value_vars=gender_columns,
        var_name="Gender",
        value_name="Records",
    )
    long_chart = long_chart[long_chart["Records"] > 0]

    if long_chart.empty:
        st.info("No age breakdown is available for the selected option.")
        return

    row_order = chart_data["Age group"].tolist()
    chart_height = max(height, min(850, 30 * len(row_order) + 90))

    chart = (
        alt.Chart(long_chart)
        .mark_bar(cornerRadiusEnd=5, opacity=0.92, stroke="#FFFFFF", strokeWidth=0.7)
        .encode(
            y=alt.Y(
                "Age group:N",
                sort=row_order,
                title=None,
                axis=alt.Axis(labelFontSize=11),
            ),
            x=alt.X("Records:Q", title="Records", stack="zero"),
            color=gender_color(
                "Gender:N",
                available=[gender for gender in GENDER_ORDER if gender in set(long_chart["Gender"].astype(str))],
            ),
            tooltip=[
                alt.Tooltip("Age group:N", title="Age group"),
                alt.Tooltip("Gender:N", title="Gender"),
                alt.Tooltip("Records:Q", title="Records", format=","),
            ],
        )
        .properties(height=chart_height)
    )

    st.altair_chart(polish_chart(chart), use_container_width=True)


def show_age_gender_breakdown_table(frame, category_column, selected_categories, category_label):
    table = age_gender_breakdown_table(
        frame,
        category_column,
        selected_categories,
        category_label,
    )

    if table.empty:
        st.info("No age breakdown is available for the selected option.")
        return

    render_dashboard_table(table, label_column="Age group")


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
    if category_column == "general_information_need":
        chart_data[category_column] = chart_data[category_column].map(display_category_value)
        chart_data = chart_data.groupby(category_column, as_index=False).sum(numeric_only=True)
    gender_columns = [
        col
        for col in chart_data.columns
        if col != category_column and pd.to_numeric(chart_data[col], errors="coerce").fillna(0).sum() > 0
    ]
    totals = chart_data.assign(_total=chart_data[gender_columns].sum(axis=1))
    x_upper = chart_headroom(totals["_total"])
    category_order = totals.sort_values("_total", ascending=ascending)[category_column].astype(str).tolist()
    long_chart = chart_data.melt(id_vars=[category_column], value_vars=gender_columns, var_name="Gender", value_name="Records")
    long_chart["Category total"] = long_chart.groupby(category_column)["Records"].transform("sum")
    long_chart["Gender share"] = long_chart["Records"].div(long_chart["Category total"].where(long_chart["Category total"].ne(0)))
    chart_height = max(height, min(900, 36 * len(category_order) + 80))
    chart = (
        alt.Chart(long_chart)
        .mark_bar(cornerRadiusEnd=5, opacity=0.92, stroke="#FFFFFF", strokeWidth=0.7)
        .encode(
            y=alt.Y(f"{category_column}:N", sort=category_order, title=None, axis=alt.Axis(labelLimit=420, labelFontSize=11, labelPadding=6)),
            x=alt.X("Records:Q", title="Records", stack="zero", scale=alt.Scale(domain=[0, x_upper], nice=False)),
            color=gender_color("Gender:N", available=gender_columns),
            tooltip=[alt.Tooltip(f"{category_column}:N", title="Category"), alt.Tooltip("Gender:N", title="Gender"), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Gender share:Q", title="Share of category", format=".1%"), alt.Tooltip("Category total:Q", title="Category total", format=",")],
        )
        .properties(height=chart_height)
    )
    totals_layer = (
        alt.Chart(totals)
        .mark_text(align="left", baseline="middle", dx=7, fontSize=11, fontWeight=800, color="#1E293B")
        .encode(
            y=alt.Y(f"{category_column}:N", sort=category_order, title=None),
            x=alt.X("_total:Q", title="Records", scale=alt.Scale(domain=[0, x_upper], nice=False)),
            text=alt.Text("_total:Q", format=","),
        )
    )
    st.altair_chart(polish_chart(chart + totals_layer), use_container_width=True)


def draw_gender_column_bar(frame, category_column, top_n=None, height=360):
    chart_data = gender_wide_chart_data(frame, category_column, top_n=top_n)
    if chart_data.empty:
        st.info("No records match the selected filters.")
        return
    chart_data = chart_data.reset_index()
    if category_column in {"disability_type", "adult_person_impairment_type", "child_disability_type"}:
        chart_data[category_column] = chart_data[category_column].map(display_category_value)
        chart_data = chart_data.groupby(category_column, as_index=False).sum(numeric_only=True)
    gender_columns = [
        col
        for col in chart_data.columns
        if col != category_column and pd.to_numeric(chart_data[col], errors="coerce").fillna(0).sum() > 0
    ]
    chart_data["Total"] = chart_data[gender_columns].sum(axis=1)
    if category_column == "age_group":
        available_categories = set(chart_data[category_column].astype(str))
        category_order = [age for age in AGE_GROUP_ORDER if age in available_categories]
        category_order += [value for value in chart_data[category_column].astype(str) if value not in category_order]
        long_chart = chart_data.melt(
            id_vars=[category_column, "Total"],
            value_vars=gender_columns,
            var_name="Gender",
            value_name="Records",
        )
        long_chart["Gender share"] = long_chart["Records"].div(
            long_chart["Total"].where(long_chart["Total"].ne(0))
        )
        age_chart = (
            alt.Chart(long_chart)
            .mark_bar(cornerRadiusEnd=5, opacity=0.92, stroke="#FFFFFF", strokeWidth=0.7)
            .encode(
                x=alt.X(
                    f"{category_column}:N",
                    sort=category_order,
                    title=None,
                    axis=alt.Axis(
                        labelAngle=-20,
                        labelLimit=125,
                        labelFontSize=10,
                        labelBound=True,
                        labelOverlap="parity",
                    ),
                ),
                y=alt.Y("Records:Q", title="Records", stack="zero"),
                color=gender_color("Gender:N", available=gender_columns),
                tooltip=[
                    alt.Tooltip(f"{category_column}:N", title="Age group"),
                    alt.Tooltip("Gender:N", title="Gender"),
                    alt.Tooltip("Records:Q", title="Records", format=","),
                    alt.Tooltip("Gender share:Q", title="Share of age group", format=".1%"),
                    alt.Tooltip("Total:Q", title="Age-group total", format=","),
                ],
            )
            .properties(height=height)
        )
        st.altair_chart(polish_chart(age_chart), use_container_width=True)
        return
    else:
        category_order = chart_data.sort_values("Total", ascending=False)[category_column].astype(str).tolist()
    long_chart = chart_data.melt(id_vars=[category_column, "Total"], value_vars=gender_columns, var_name="Gender", value_name="Records")
    long_chart["Gender share"] = long_chart["Records"].div(long_chart["Total"].where(long_chart["Total"].ne(0)))
    chart_height = max(height, min(850, 34 * len(category_order) + 80))
    x_upper = chart_headroom(chart_data["Total"])
    chart = (
        alt.Chart(long_chart)
        .mark_bar(cornerRadiusEnd=5, opacity=0.92, stroke="#FFFFFF", strokeWidth=0.7)
        .encode(
            y=alt.Y(f"{category_column}:N", sort=category_order, title=None, axis=alt.Axis(labelLimit=420, labelFontSize=11, labelPadding=6)),
            x=alt.X("Records:Q", title="Records", stack="zero", scale=alt.Scale(domain=[0, x_upper], nice=False)),
            color=gender_color("Gender:N", available=gender_columns),
            tooltip=[alt.Tooltip(f"{category_column}:N", title="Category"), alt.Tooltip("Gender:N", title="Gender"), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Gender share:Q", title="Share of category", format=".1%"), alt.Tooltip("Total:Q", title="Category total", format=",")],
        )
        .properties(height=chart_height)
    )
    total_labels = (
        alt.Chart(chart_data)
        .mark_text(align="left", baseline="middle", dx=7, fontSize=11, fontWeight=800, color="#1E293B")
        .encode(
            y=alt.Y(f"{category_column}:N", sort=category_order, title=None),
            x=alt.X("Total:Q", title="Records", scale=alt.Scale(domain=[0, x_upper], nice=False)),
            text=alt.Text("Total:Q", format=","),
        )
    )
    st.altair_chart(polish_chart(chart + total_labels), use_container_width=True)


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
    summary["Slice order"] = range(len(summary))

    category_values = summary[category_column].astype(str).tolist()

    if category_column == "information_seeker_gender":
        available_genders = [gender for gender in GENDER_ORDER if gender in category_values]
        color_encoding = gender_color(f"{category_column}:N", available=available_genders)
    elif all(value in STATUS_COLORS for value in category_values):
        color_encoding = alt.Color(
            f"{category_column}:N",
            title=category_label,
            scale=alt.Scale(
                domain=category_values,
                range=[STATUS_COLORS[value] for value in category_values],
            ),
            legend=alt.Legend(symbolType="circle", orient="bottom", columns=3, labelLimit=120),
        )
    else:
        color_encoding = category_color(f"{category_column}:N", title=category_label)

    # Keep the complete donut and its labels inside narrow Streamlit columns.
    # The previous fixed radii (122px ring, 145px labels) overflowed the
    # two-column disability cards. These values scale with the available chart
    # height and place labels safely inside the ring.
    chart_height = max(240, int(height))
    outer_radius = max(72, min(106, int((chart_height - 90) / 2)))
    inner_radius = int(outer_radius * 0.60)
    label_radius = int((inner_radius + outer_radius) / 2)

    donut = (
        alt.Chart(summary)
        .mark_arc(innerRadius=inner_radius, outerRadius=outer_radius, cornerRadius=3, stroke="#FFFFFF", strokeWidth=2)
        .encode(
            theta=alt.Theta("Records:Q", stack=True),
            color=color_encoding,
            order=alt.Order("Slice order:Q", sort="ascending"),
            tooltip=[alt.Tooltip(f"{category_column}:N", title=category_label), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Share:Q", title="Share", format=".1%")],
        )
    )
    labels = (
        # Retain every slice so the text layer uses exactly the same angular
        # scale as the arcs. Small slices carry a blank label rather than being
        # removed, which prevents remaining labels from shifting segments.
        alt.Chart(summary)
        .mark_text(
            radius=label_radius,
            fontSize=11,
            fontWeight=800,
            color="#FFFFFF",
            stroke="#334155",
            strokeWidth=1.2,
        )
        .encode(
            theta=alt.Theta("Records:Q", stack=True),
            order=alt.Order("Slice order:Q", sort="ascending"),
            text=alt.Text("Share label:N"),
        )
    )
    st.altair_chart(
        polish_chart(
            (donut + labels).properties(
                height=chart_height,
                padding={"top": 10, "right": 10, "bottom": 10, "left": 10},
            )
        ),
        use_container_width=True,
    )


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
    x_upper = chart_headroom(summary["Records"], fraction=0.35)

    base = alt.Chart(summary).encode(
        y=alt.Y(
            "Request type:N",
            sort=type_order,
            title=None,
            axis=alt.Axis(labelLimit=360, labelFontSize=12, labelPadding=8),
        ),
        x=alt.X("Records:Q", title="Records", scale=alt.Scale(domain=[0, x_upper], nice=False)),
    )

    bars = base.mark_bar(cornerRadiusEnd=6, opacity=0.94, stroke="#FFFFFF", strokeWidth=0.7).encode(
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
    status_data = frame[[status_column, "information_seeker_gender"]].copy()
    status_data[status_column] = status_data[status_column].fillna("[Missing]").astype(str)
    status_data["Gender"] = status_data["information_seeker_gender"].fillna("[Missing]").astype(str)
    status_data = status_data[status_data[status_column].isin(["No Disability", "Has Disability"])]
    if status_data.empty:
        st.info("No disability status data for the selected filters.")
        return
    grouped = status_data.groupby(["Gender", status_column], dropna=False).size().reset_index(name="Records")
    overall = status_data.groupby(status_column, dropna=False).size().reset_index(name="Records")
    overall["Gender"] = "Overall"
    grouped = pd.concat([overall, grouped], ignore_index=True)
    grouped["Gender total"] = grouped.groupby("Gender")["Records"].transform("sum")
    grouped["Share"] = grouped["Records"] / grouped["Gender total"]
    grouped["Label"] = grouped.apply(lambda row: f"{row['Share']:.1%}" if row["Share"] >= 0.07 else "", axis=1)
    gender_order = ["Overall"] + [gender for gender in GENDER_ORDER if gender in set(grouped["Gender"])]
    status_order = ["No Disability", "Has Disability"]
    grouped["Status order"] = grouped[status_column].map({status: index for index, status in enumerate(status_order)})
    grouped = grouped.sort_values(["Gender", "Status order"])
    grouped["Cumulative share"] = grouped.groupby("Gender")["Share"].cumsum()
    grouped["Label position"] = grouped["Cumulative share"] - (grouped["Share"] / 2)
    status_chart = (
        alt.Chart(grouped)
        .mark_bar(cornerRadiusEnd=5, stroke="#FFFFFF", strokeWidth=0.8)
        .encode(
            y=alt.Y("Gender:N", sort=gender_order, title=None),
            x=alt.X("Share:Q", stack="zero", title="Share within gender", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1])),
            color=alt.Color(f"{status_column}:N", title="Disability status", scale=alt.Scale(domain=status_order, range=[STATUS_COLORS[value] for value in status_order]), legend=alt.Legend(orient="bottom")),
            order=alt.Order("Status order:Q", sort="ascending"),
            tooltip=[alt.Tooltip("Gender:N", title="Gender"), alt.Tooltip(f"{status_column}:N", title="Status"), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Share:Q", title="Share within gender", format=".1%")],
        )
        .properties(height=max(height, 38 * len(gender_order) + 70))
    )
    status_labels = (
        alt.Chart(grouped)
        .mark_text(fontSize=11, fontWeight=800, color="#FFFFFF")
        .encode(
            y=alt.Y("Gender:N", sort=gender_order, title=None),
            x=alt.X("Label position:Q", scale=alt.Scale(domain=[0, 1])),
            text=alt.Text("Label:N"),
            tooltip=[alt.Tooltip("Gender:N", title="Gender"), alt.Tooltip(f"{status_column}:N", title="Status"), alt.Tooltip("Records:Q", title="Records", format=","), alt.Tooltip("Share:Q", title="Share within gender", format=".1%")],
        )
    )
    st.altair_chart(polish_chart(status_chart + status_labels), use_container_width=True)


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
        .mark_line(
            point=alt.OverlayMarkDef(filled=True, size=70, stroke="#FFFFFF", strokeWidth=1),
            strokeWidth=3.2,
            interpolate="monotone",
        )
        .encode(
            x=alt.X(
                "year_month:N",
                sort=month_order,
                title=None,
                axis=alt.Axis(
                    labelAngle=-20,
                    labelLimit=85,
                    labelFontSize=11,
                    labelBound=True,
                    labelOverlap="parity",
                ),
            ),
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
    y_upper = chart_headroom(chart_data["Records"], fraction=0.14)
    base = alt.Chart(chart_data).encode(x=alt.X("axis_label:N", sort=axis_order, title=None, axis=alt.Axis(labelAngle=-20, labelLimit=120, labelFontSize=11, labelBound=True, labelOverlap="parity")), y=alt.Y("Records:Q", title="Records", scale=alt.Scale(domain=[0, y_upper], nice=False)))
    bars = base.mark_bar(cornerRadiusEnd=6, color="#2F7D69", opacity=0.94, stroke="#FFFFFF", strokeWidth=0.7).encode(tooltip=[alt.Tooltip(f"{category_label}:N", title=category_label), alt.Tooltip("Records:Q", title="Records", format=",")])
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


def filter_section_badge(number, title, detail, tone):
    st.markdown(
        f"""
        <div class="filter-section-badge filter-section-badge-{escape_text(tone)}">
            <div class="filter-section-number">{escape_text(number)}</div>
            <div class="filter-section-copy">
                <div class="filter-section-title">{escape_text(title)}</div>
                <div class="filter-section-detail">{escape_text(detail)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def filter_selection_feedback(label, values, max_items=4):
    if not values:
        return

    values = list(values)
    shown_values = values[:max_items]
    extra_count = len(values) - len(shown_values)
    chips = "".join(
        f'<span class="filter-selected-chip">{escape_text(value)}</span>'
        for value in shown_values
    )

    if extra_count > 0:
        chips += f'<span class="filter-selected-chip filter-selected-more">+{extra_count} more</span>'

    st.markdown(
        f"""
        <div class="filter-selected-summary">
            <span class="filter-selected-label">Selected {escape_text(label)}</span>
            <div class="filter-selected-chips">{chips}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title, note=None):
    st.markdown(f"""<div class="section-header"><span class="section-accent"></span><span class="section-title">{escape_text(title)}</span></div>""", unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="section-note">{escape_text(note)}</div>', unsafe_allow_html=True)


HELPDESK_SECTION_META = {
    "Overview": ("🏠", "Overview", "Review overall volume, request mix, demographics and location coverage."),
    "CPV Work": ("👥", "Staff / CPV Performance", "Compare staff workload, requests, referrals, follow-up and operating coverage."),
    "Disability": ("♿", "Disability Inclusion", "Review disability prevalence, impairment types and single versus multiple impairments."),
    "Concerns": ("🛡️", "Protection Concerns", "Explore reported protection concerns, rankings and age/gender patterns."),
    "Information": ("ℹ️", "Information Requests", "Understand the protection information requested by helpdesk users."),
    "Referrals": ("🔁", "Referrals", "Review referral partners, destinations and demographic patterns."),
    "Map": ("🗺️", "Service Map", "Locate mapped helpdesk records and assess geographic coverage."),
    "DQA": ("✅", "Data Quality", "Review completeness, corrections and protected follow-up records."),
    "Records": ("📄", "Records & Export", "Inspect filtered records and prepare privacy-safe downloads."),
}
HELPDESK_SECTION_GROUPS = {
    "Summary": ["Overview"],
    "CPVs Submissions": ["CPV Work"],
    "Service Requests": ["Disability", "Concerns", "Information", "Referrals"],
    "Operations & Data": ["Map", "DQA", "Records"],
}
HELPDESK_CATEGORY_LABELS = {
    "Summary": "📊 Summary", "CPVs Submissions": "👥 CPVs Submissions",
    "Service Requests": "🛡️ Service Requests", "Operations & Data": "✅ Operations & Data",
}


def helpdesk_section_navigation():
    """Render one compact navigation control for all dashboard views."""
    section_key = "helpdesk_section"
    category_key = "helpdesk_section_category"
    if section_key not in st.session_state or st.session_state[section_key] not in HELPDESK_SECTION_META:
        st.session_state[section_key] = "Overview"

    selected = st.selectbox(
        "**Explore dashboard**",
        list(HELPDESK_SECTION_META),
        key=section_key,
        format_func=lambda value: (
            f"{HELPDESK_SECTION_META[value][0]} {HELPDESK_SECTION_META[value][1]}"
        ),
        help="Choose any dashboard view. Type while the list is open to find a view quickly.",
    )
    category = next(
        category
        for category, views in HELPDESK_SECTION_GROUPS.items()
        if selected in views
    )
    # Keep the legacy category state synchronized for saved sessions and reset
    # behaviour, although navigation now uses one user-facing control.
    st.session_state[category_key] = category
    description = HELPDESK_SECTION_META[selected][2]
    st.markdown(
        f'<div class="sidebar-view-context">'
        f'<div class="sidebar-view-group">{escape_text(category)}</div>'
        f'<div class="sidebar-view-description">{escape_text(description)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    return selected


def helpdesk_section_intro(section, filtered_count):
    icon, label, description = HELPDESK_SECTION_META[section]
    category = next(category for category, views in HELPDESK_SECTION_GROUPS.items() if section in views)
    st.caption(f"Dashboard › {category} › {label} · {filtered_count:,} records in view")
    st.markdown(
        f'<div class="section-intro-card"><div class="section-intro-icon">{icon}</div>'
        f'<div><div class="section-intro-title">{escape_text(label)}</div>'
        f'<div class="section-intro-desc">{escape_text(description)}</div></div></div>',
        unsafe_allow_html=True,
    )


def helpdesk_go_to_overview():
    st.session_state["helpdesk_section_category"] = "Summary"
    st.session_state["helpdesk_section"] = "Overview"


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
    footer_html = (
        '<div class="developer-footer">'
        '<div class="developer-brand">'
        f'{developer_logo_html()}'
        '<div><div class="developer-brand-name">ImpactLens Africa</div>'
        '<div class="developer-brand-tagline">Turning Data Into Human Impact</div></div>'
        '</div>'
        '<div class="developer-credit">'
        '<div>Developed by <strong>John Kul</strong>, MEAL Officer-Tdh</div>'
        f'<div class="developer-version">{APP_VERSION} &middot; {APP_VERSION_DATE}</div>'
        '</div></div>'
    )
    if hasattr(st, "html"):
        st.html(footer_html)
    else:
        st.markdown(footer_html, unsafe_allow_html=True)


def search_records(frame, query):
    if not query:
        return frame
    searchable = frame.copy()
    mask = pd.Series(False, index=searchable.index)
    for column in searchable.columns:
        mask = mask | searchable[column].astype(str).str.contains(query, case=False, regex=False, na=False)
    return searchable[mask]


def configured_pii_password():
    """Read the password used to unlock PII tables.

    Configure either Streamlit secrets or an environment variable:
    - .streamlit/secrets.toml: DQA_PII_PASSWORD = "your-password"
    - environment variable: DQA_PII_PASSWORD
    """
    try:
        password = st.secrets.get("DQA_PII_PASSWORD", None)
        if password:
            return str(password)
    except Exception:
        pass
    return os.environ.get("DQA_PII_PASSWORD")


def pii_access_granted(key="pii_access_password"):
    """Password gate for PII-sensitive DQA tables."""
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
    """Build a password-protected DQA follow-up table for education concerns."""
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

def build_helpdesk_findings(section, frame, protection_frame, information_frame, referral_frame):
    """Build auditable findings from the filtered sources used by each section."""
    total = len(frame)
    if total == 0:
        return "No records match the current filters, so the section tables do not support a finding."

    excluded = {"[Missing]", "[Not recorded]", "Missing / unspecified", "Needs review", "None"}

    def value_counts(data, column):
        if data.empty or column not in data.columns:
            return pd.Series(dtype="int64")
        values = data[column].dropna().astype(str)
        return values[~values.isin(excluded)].value_counts()

    def leading(data, column):
        result = value_counts(data, column)
        return (str(result.index[0]), int(result.iloc[0])) if not result.empty else ("", 0)

    def gender_distribution(data=frame):
        result = value_counts(data, "information_seeker_gender")
        denominator = int(result.sum())
        if not denominator:
            return "Gender disaggregation is unavailable for the current filters."
        details = "; ".join(f"{label}: {int(count):,} ({int(count) / denominator:.1%})" for label, count in result.items())
        return f"Among {denominator:,} records with a usable gender response, {details}."

    def positive_gender_rates(column, positive, description):
        if column not in frame.columns:
            return ""
        parts = []
        for gender in GENDER_ORDER:
            scoped = frame[frame["information_seeker_gender"].astype(str).eq(gender) & frame[column].notna()]
            if len(scoped) < 5:
                continue
            positive_count = int(scoped[column].astype(str).eq(positive).sum())
            parts.append(f"{gender}: {positive_count:,} of {len(scoped):,} ({positive_count / len(scoped):.1%})")
        return f"By gender, {description} was recorded for " + "; ".join(parts) + "." if parts else ""

    def leaders_by_gender(data, column, unit="records"):
        if data.empty or column not in data.columns or "information_seeker_gender" not in data.columns:
            return ""
        parts = []
        for gender in GENDER_ORDER:
            scoped = data[data["information_seeker_gender"].astype(str).eq(gender)]
            label, count = leading(scoped, column)
            if label:
                parts.append(f"for {gender}, {label} is highest at {count:,} {unit}")
        return "; ".join(parts) + "." if parts else ""

    blocks = []
    if section == "Overview":
        location, location_n = leading(frame, "helpdesk_location")
        request, request_n = leading(frame, "request_category")
        age, age_n = leading(frame, "age_group")
        coverage = f"The view contains {total:,} records"
        if location:
            coverage += f"; {location} is the busiest helpdesk with {location_n:,} records ({location_n / total:.1%})"
        blocks.append(("Coverage", coverage + "."))
        profile = f"{request} is the largest request category at {request_n:,} ({request_n / total:.1%})" if request else "No usable request category remains"
        if age:
            profile += f", while {age} is the largest age group at {age_n:,} ({age_n / total:.1%})"
        blocks.append(("Request and demographic profile", profile + ". " + gender_distribution()))
        visit_counts = value_counts(frame, "helpdesk_visit_history")
        known_visits = int(visit_counts.sum())
        first_time = int(visit_counts.get("First-time visitor", 0))
        repeat = int(visit_counts.get("Repeat visitor", 0))
        if known_visits:
            repeat_timing = value_counts(frame, "repeat_visit_timing")
            within_month = int(repeat_timing.get("Repeat — within current month", 0))
            timed_repeats = int(
                repeat_timing.get("Repeat — within current month", 0)
                + repeat_timing.get("Repeat — before current month", 0)
            )
            timing_sentence = (
                f" Of {timed_repeats:,} repeat visits with recorded timing, "
                f"{within_month:,} occurred within the current month "
                f"({within_month / timed_repeats:.1%})."
                if timed_repeats else ""
            )
            blocks.append((
                "Helpdesk entry point",
                f"Among {known_visits:,} records with known prior-visit status, "
                f"{first_time:,} were first-time visitors ({first_time / known_visits:.1%}) "
                f"and {repeat:,} were repeat visitors ({repeat / known_visits:.1%})."
                f"{timing_sentence}",
            ))
    elif section == "CPV Work":
        summary = cpv_work_summary(frame)
        if not summary.empty:
            top = summary.iloc[0]
            blocks.append(("Workload", f"{len(summary):,} CPVs are represented; {top['CPV']} has the largest workload with {int(top['Records']):,} records."))
        blocks.append(("Gender reach", gender_distribution()))
        blocks.append(("Case outcomes", " ".join(filter(None, [positive_gender_rates("follow_up_required_clean", "Yes", "follow-up required"), positive_gender_rates("referral_status", "Referred to partner agency", "a partner referral")]))))
    elif section == "Disability":
        disability = frame[frame["disability_status"].astype(str).eq("Has Disability")]
        dtype, dtype_n = leading(disability, "disability_type")
        blocks.append(("Prevalence", f"Disability is recorded in {len(disability):,} of {total:,} records ({len(disability) / total:.1%}). {positive_gender_rates('disability_status', 'Has Disability', 'a disability')}"))
        if dtype:
            blocks.append(("Impairment profile", f"{dtype} is the most frequently recorded disability type ({dtype_n:,} records). {leaders_by_gender(disability, 'disability_type')}"))
        if not disability.empty:
            adult_disability = disability[disability["derived_life_stage"].astype(str).eq("Adult")]
            adult_people = adult_person_impairment_frame(adult_disability)
            if not adult_people.empty:
                multiplicity = value_counts(adult_people, "adult_impairment_multiplicity")
                single_n = int(multiplicity.get("Single Impairment", 0))
                multiple_n = int(multiplicity.get("Multiple Impairments", 0))
                blocks.append((
                    "Adult impairment multiplicity",
                    f"Among {len(adult_people):,} adults with disability, {single_n:,} have one impairment and {multiple_n:,} have two or more impairments.",
                ))
    elif section == "Concerns":
        concern, concern_n = leading(protection_frame, "protection_concern")
        record_n = protection_frame["record_id"].nunique() if "record_id" in protection_frame.columns else 0
        blocks.append(("Concern profile", f"The tables contain {len(protection_frame):,} concern mentions across {record_n:,} records. {concern} is highest at {concern_n:,} mentions." if concern else "No usable protection-concern mentions remain."))
        if concern:
            blocks.append(("Gender pattern", leaders_by_gender(protection_frame, "protection_concern", "mentions")))
        children = frame[frame["derived_life_stage"].astype(str).eq("Child")]
        accompaniment = value_counts(children, "child_accompaniment_status")
        known_children = int(accompaniment.sum())
        unaccompanied = int(accompaniment.get("Unaccompanied", 0))
        if known_children:
            blocks.append((
                "Child accompaniment",
                f"Among {known_children:,} child records with a determinable accompaniment status, "
                f"{unaccompanied:,} were unaccompanied ({unaccompanied / known_children:.1%}).",
            ))
    elif section == "Information":
        need, need_n = leading(information_frame, "general_information_need")
        record_n = information_frame["record_id"].nunique() if "record_id" in information_frame.columns else 0
        blocks.append(("Information profile", f"The tables contain {len(information_frame):,} information-need mentions across {record_n:,} records. {need} is highest at {need_n:,} mentions." if need else "No usable information-request mentions remain."))
        if need:
            blocks.append(("Gender pattern", leaders_by_gender(information_frame, "general_information_need", "mentions")))
    elif section == "Referrals":
        partner, partner_n = leading(referral_frame, "referral_partner")
        referred = int(frame["referral_status"].astype(str).eq("Referred to partner agency").sum())
        blocks.append(("Referral rate", f"{referred:,} of {total:,} records were referred to a partner agency ({referred / total:.1%}). {positive_gender_rates('referral_status', 'Referred to partner agency', 'a partner referral')}"))
        if partner:
            blocks.append(("Partner profile", f"{partner} is the leading recorded referral partner with {partner_n:,} mentions. {leaders_by_gender(referral_frame, 'referral_partner', 'mentions')}"))
    elif section == "Map":
        mapped = frame[["gps_latitude", "gps_longitude"]].notna().all(axis=1) if {"gps_latitude", "gps_longitude"}.issubset(frame.columns) else pd.Series(False, index=frame.index)
        camp, camp_n = leading(frame[mapped], "camp_location")
        blocks.append(("Geographic coverage", f"{int(mapped.sum()):,} of {total:,} records have usable coordinates ({mapped.mean():.1%})."))
        if camp:
            blocks.append(("Mapped distribution", f"{camp} contributes the largest mapped volume with {camp_n:,} records. {gender_distribution(frame[mapped])}"))
    elif section == "DQA":
        checks = {"interview date": frame["interview_date"].notna(), "gender": ~frame["information_seeker_gender"].astype(str).isin(excluded), "age group": ~frame["age_group"].astype(str).isin(excluded), "helpdesk location": ~frame["helpdesk_location"].astype(str).isin(excluded)}
        ordered = sorted(((label, int(mask.sum()) / total) for label, mask in checks.items()), key=lambda item: item[1])
        blocks.append(("Completeness", f"Headline completeness ranges from {ordered[0][1]:.1%} for {ordered[0][0]} to {ordered[-1][1]:.1%} for {ordered[-1][0]}."))
        blocks.append(("Corrections", f"Gender/age corrections affect {int(frame['gender_age_correction_flag'].sum()):,} records, while seeker-type/age corrections affect {int(frame['type_age_correction_flag'].sum()):,} records."))
    else:
        blocks.append(("Records", f"The table contains {total:,} filtered, non-PII dashboard records. {gender_distribution()}"))
        blocks.append(("Export", "The standard download excludes configured direct identifiers; protected education follow-up data remain password-gated."))

    blocks = [(heading, text.strip()) for heading, text in blocks if text and text.strip()]
    return "\n\n".join(f"**{heading}.** {text}" for heading, text in blocks) if blocks else "The filtered tables do not support a sufficiently clear descriptive finding."


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
load_css()
file_signature = data_file_signature(DATA_FILE_PATH)
st.session_state.setdefault("helpdesk_kobo_refresh_nonce", 0)
source_mode = "KoboToolbox API" if kobo_configured() else "Local Excel fallback"

try:
    if kobo_configured():
        kobo_base_url = normalize_kobo_base_url(setting("KOBO_BASE_URL", "https://eu.kobotoolbox.org"))
        kobo_asset_uid = normalize_kobo_asset_uid(setting("KOBO_ASSET_UID"))
        source_signature = (
            "kobo",
            kobo_base_url,
            kobo_asset_uid,
            st.session_state.helpdesk_kobo_refresh_nonce,
        )
    else:
        source_signature = ("local", *file_signature)
    load_started_at = time.perf_counter()
    records, secure_records, protection, information, referrals, kpis = load_data(source_signature)
    load_elapsed_seconds = time.perf_counter() - load_started_at
except requests.RequestException as error:
    st.error(f"Kobo could not be reached: {error}")
    st.info("Check the Kobo server URL, network access, asset UID, and token permissions.")
    st.stop()
except Exception as error:
    st.error(f"The Helpdesk dashboard data could not be loaded: {error}")
    if not kobo_configured():
        st.info("Configure KOBO_TOKEN and KOBO_ASSET_UID in .streamlit/secrets.toml, or add the fallback workbook under data/.")
    st.stop()

source_metadata = records.attrs.get("source_metadata", {})
if records.empty:
    st.error("No valid dashboard records were found in the configured source.")
    st.stop()

min_date = records["interview_date"].min().date()
max_date = records["interview_date"].max().date()
default_from_date = min_date
calendar_min_date = pd.Timestamp(year=min_date.year, month=1, day=1).date()
calendar_max_date = pd.Timestamp(year=max_date.year, month=12, day=31).date()

if "from_date_filter" not in st.session_state or "to_date_filter" not in st.session_state:
    legacy_date_range = st.session_state.pop("date_range_filter", None)
    if isinstance(legacy_date_range, (tuple, list)) and len(legacy_date_range) == 2:
        legacy_from_date, legacy_to_date = legacy_date_range
    else:
        legacy_from_date, legacy_to_date = default_from_date, max_date
    st.session_state.setdefault("from_date_filter", legacy_from_date)
    st.session_state.setdefault("to_date_filter", legacy_to_date)

with st.sidebar:
    st.header("Dashboard Controls")

    st.markdown(
        """
        <div class="sidebar-filter-guide">
            <div class="sidebar-filter-guide-title">Control the dashboard view</div>
            <div class="sidebar-filter-guide-body">
                Start with the date range, then choose camp location before selecting helpdesk location.
                Other filters update based on the selections above them.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.button(
        "↺ Reset view", use_container_width=True,
        on_click=reset_filters, args=(default_from_date, max_date),
        help="Clear filters and return to the Overview section.",
    )

    selected_tab = helpdesk_section_navigation()

    if kobo_configured():
        fetched_at = pd.to_datetime(
            source_metadata.get("fetched_at"), utc=True, errors="coerce"
        )
        fetched_label = (
            fetched_at.tz_convert("Africa/Nairobi").strftime("%d %b %Y %H:%M:%S EAT")
            if pd.notna(fetched_at)
            else "Not recorded"
        )
        st.markdown(
            f'<div class="live-sync-card">'
            f'<div class="live-sync-heading"><span class="live-sync-dot"></span>Live Kobo data</div>'
            f'<div class="live-sync-time">Last synced: {escape_text(fetched_label)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if st.button(
            "↻ Sync latest Kobo data",
            key="primary_kobo_sync",
            type="primary",
            use_container_width=True,
            help="Bypass the cache and retrieve all current Kobo submissions now.",
        ):
            st.session_state.helpdesk_kobo_refresh_nonce += 1
            fetch_kobo_submissions.clear()
            fetch_kobo_form_contract.clear()
            load_data.clear()
            st.rerun()
        # Monitor silently; the full page reruns only after an actual Kobo
        # submission addition, edit, or deletion.
        live_change_monitor(
            kobo_base_url,
            kobo_asset_uid,
            source_metadata.get("data_fingerprint"),
        )
    else:
        st.caption("Using the local file fallback; live Kobo synchronization is unavailable.")

    with st.expander("How to use this dashboard", expanded=False):
        st.markdown(
            "1. Choose a view from **Explore dashboard**.\n"
            "2. Apply filters below; they remain active across views.\n"
            "3. Open **Findings from the current tables** for interpretation.\n\n"
            "**CPV:** Community-based protection volunteer  \n"
            "**Mention:** A selected response; one record may contain several mentions"
        )
    with st.expander("Live data & schema status", expanded=False):
        st.caption(f"Source: {source_mode}")
        if kobo_configured():
            st.caption(f"Kobo form: {source_metadata.get('asset_name', kobo_asset_uid)}")
            st.caption(f"Asset UID: {kobo_asset_uid}")
            fetched = pd.to_datetime(source_metadata.get("fetched_at"), utc=True, errors="coerce")
            if pd.notna(fetched):
                st.caption(f"Last fetched: {fetched.tz_convert('Africa/Nairobi').strftime('%d %b %Y %H:%M EAT')}")
            st.caption(f"API pages: {source_metadata.get('api_pages', 0):,}")
            st.caption(
                f"Background change check: every {KOBO_CHANGE_CHECK_SECONDS} seconds; "
                "the page updates only when Kobo data changes"
            )
        else:
            st.caption(f"Workbook: {DATA_FILE_PATH.name}")
            st.caption(f"Last modified: {file_signature[3] if file_signature[3] else 'Unknown'}")
        st.caption(f"Transformation rules: {PROCESSED_CACHE_VERSION}")
        st.caption(f"Source records: {source_metadata.get('raw_records', len(records)):,}")
        st.caption(f"Analysable records: {len(records):,}")
        st.caption(f"Load/cache lookup: {load_elapsed_seconds:.3f} seconds")
        unmapped = source_metadata.get("unmapped_source_columns", [])
        missing = source_metadata.get("missing_contract_columns", [])
        st.caption(f"Unmapped new/source attributes: {len(unmapped):,}")
        st.caption(f"Contract fields absent from source: {len(missing):,}")
        if unmapped:
            st.write("Unmapped attributes (do not shift existing fields):", unmapped)
        if missing:
            st.write("Absent contract fields:", missing)
        st.caption("Use the prominent synchronization controls above to refresh data.")

    filter_section_badge(
        "01",
        "Display",
        "Choose what support panels appear above the dashboard.",
        "slate",
    )
    with st.expander("Display options", expanded=False):
        show_current_selection_summary = st.checkbox(
            "Show current selection summary",
            value=True,
            key="show_current_selection_summary",
            help="Show or hide the record count, date range, update time, and selected filter chips above the KPI cards.",
        )

    st.markdown('<div class="filter-divider"></div>', unsafe_allow_html=True)

    filter_section_badge(
        "02",
        "Date range",
        "Set the reporting period before applying other filters.",
        "gold",
    )
    with st.expander("Date range", expanded=True):
        st.caption("Click each date field to open its calendar and select the reporting period.")
        selected_from_date = st.date_input(
            "From",
            min_value=calendar_min_date,
            max_value=calendar_max_date,
            format="DD/MM/YYYY",
            key="from_date_filter",
            help="Select the first date included in the reporting period.",
        )
        selected_to_date = st.date_input(
            "To",
            min_value=calendar_min_date,
            max_value=calendar_max_date,
            format="DD/MM/YYYY",
            key="to_date_filter",
            help="Select the last date included in the reporting period.",
        )

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

    filter_section_badge(
        "03",
        "Location",
        "Select camp first, then unlock helpdesk locations.",
        "green",
    )
    with st.expander("Location", expanded=True):
        camp_options = [v for v, _ in filter_options_with_counts(date_filtered_records["camp_location"])]
        st.markdown('<div class="filter-label">Camp location</div>', unsafe_allow_html=True)
        selected_camp_locations = multi_choice_selector("Camp", camp_options, key="camp_location_filter", help_text="Select one or more camps")
        filter_selection_feedback("camp", selected_camp_locations)

        if selected_camp_locations:
            camp_filtered_records = date_filtered_records[
                date_filtered_records["camp_location"].astype(str).isin(selected_camp_locations)
            ].copy()
        else:
            camp_filtered_records = date_filtered_records.copy()
            st.session_state["helpdesk_location_filter"] = []

        st.markdown('<div class="filter-label">Helpdesk location</div>', unsafe_allow_html=True)
        if selected_camp_locations:
            helpdesk_options = [v for v, _ in filter_options_with_counts(camp_filtered_records["helpdesk_location"])]
            selected_helpdesk_locations = multi_choice_selector(
                "Helpdesk location",
                helpdesk_options,
                key="helpdesk_location_filter",
                help_text="Select helpdesk locations after choosing camp location",
            )
            filter_selection_feedback("helpdesk", selected_helpdesk_locations)
        else:
            selected_helpdesk_locations = []
            st.markdown(
                '<div class="filter-step-note">Select a camp location first to unlock helpdesk locations.</div>',
                unsafe_allow_html=True,
            )

    helpdesk_filtered_records = camp_filtered_records[camp_filtered_records["helpdesk_location"].astype(str).isin(selected_helpdesk_locations)].copy() if selected_helpdesk_locations else camp_filtered_records.copy()

    # Demographic and request breakdowns remain available in the dashboard
    # views; they are intentionally not duplicated as sidebar filters.
    selected_information_seeker_types = []
    selected_genders = []
    selected_age_groups = []
    selected_request_categories = []

    selected_filter_groups = [
        selected_camp_locations,
        selected_helpdesk_locations,
    ]
    active_filter_count = sum(1 for selected in selected_filter_groups if selected)
    if from_date != min_date or to_date != max_date:
        active_filter_count += 1

    sidebar_preview_records = helpdesk_filtered_records.copy()
    filter_status_class = "filter-status active" if active_filter_count else "filter-status"
    filter_status_text = (
        f"{active_filter_count} filter group{'s' if active_filter_count != 1 else ''} active"
        if active_filter_count
        else "No filters active"
    )
    st.markdown(
        f"""
        <div class="filter-status-panel">
            <div class="{filter_status_class}">
                <span class="filter-icon">Status</span>
                <span>{escape_text(filter_status_text)}</span>
            </div>
            <div class="filter-status-hint">Estimated records after filters: {format_number(len(sidebar_preview_records))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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
# secure_records contains PII, so it is filtered lazily only after the protected
# table is unlocked instead of during every app startup/rerun.
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
known_visit_records = filtered_records[
    filtered_records["helpdesk_visit_history"].isin(["First-time visitor", "Repeat visitor"])
]
first_time_visitors = known_visit_records["helpdesk_visit_history"].eq("First-time visitor").sum()
repeat_visitors = known_visit_records["helpdesk_visit_history"].eq("Repeat visitor").sum()
if "staff_name" in filtered_records.columns:
    harmonized_staff = filtered_records["staff_name"].map(normalize_staff_name)
    staff_no = int(harmonized_staff[harmonized_staff.ne("[Not recorded]")].nunique())
else:
    staff_no = 0
last_updated = file_signature[3] if file_signature[3] else "Unknown"

header_html = (
    '<div class="app-header">'
    f'{tdh_logo_html()}'
    '<div class="app-header-text">'
    '<div class="app-header-title">Tdh Kenya Helpdesk Data Dashboard</div>'
    '<div class="app-header-subtitle">Protection helpdesk monitoring &middot; Turkana West &amp; Dadaab</div>'
    '</div></div>'
)
if hasattr(st, "html"):
    st.html(header_html)
else:
    st.markdown(header_html, unsafe_allow_html=True)

selection_pills_html = "".join([
    selection_pill("Camp", selected_camp_locations),
    selection_pill("Helpdesk", selected_helpdesk_locations),
    selection_pill("Gender", selected_genders),
    selection_pill("Age", selected_age_groups),
])
if selected_tab == "Overview" and st.session_state.get("show_current_selection_summary", True):
    with st.expander("Current selection summary", expanded=False):
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

if filtered_records.empty:
    st.info("No records match the selected filters.")
    show_footer()
    st.stop()

# Keep the overview as a true landing page. Global KPIs and quick insights are
# deliberately omitted from analytical sections so users reach their data
# immediately without repeatedly scrolling past the same summary cards.
if selected_tab == "Overview":
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

    kpi_group_caption("Helpdesk entry point — prior visit history")
    entry_cols = st.columns(2)
    show_kpi_card(entry_cols[0], "First-time visitors", format_number(first_time_visitors), f"{format_rate(first_time_visitors, len(known_visit_records))} of records with known visit history", share=safe_share(first_time_visitors, len(known_visit_records)), accent="#1F6FB2")
    show_kpi_card(entry_cols[1], "Repeat visitors", format_number(repeat_visitors), f"{format_rate(repeat_visitors, len(known_visit_records))} of records with known visit history", share=safe_share(repeat_visitors, len(known_visit_records)), accent="#D9A441")

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
else:
    st.markdown(
        f"""
        <div class="section-context-strip" aria-label="Current analytical context">
            <span><strong>{format_number(total_records)}</strong> records in view</span>
            <span>{escape_text(from_date.strftime('%d %b %Y'))} &ndash; {escape_text(to_date.strftime('%d %b %Y'))}</span>
            <span>{active_filter_count} filter group{'s' if active_filter_count != 1 else ''} active</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

helpdesk_section_intro(selected_tab, total_records)
if selected_tab != "Overview":
    st.button("← Back to Overview", key="helpdesk_back_to_overview", on_click=helpdesk_go_to_overview)
section_findings = build_helpdesk_findings(
    selected_tab, filtered_records, filtered_protection, filtered_information, filtered_referrals
)
with st.expander("Findings from the current tables", expanded=(selected_tab == "Overview")):
    st.caption("Automatically generated, filter-aware descriptive findings. They summarize observed patterns and do not establish causes.")
    st.markdown(section_findings)

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
    st.subheader("First-time and Repeat Helpdesk Visits")
    st.caption(
        '"visited_tdh_helpdesk_before" establishes first-time versus repeat status. '
        '"last_visit_within_current_month" is then applied only to repeat visitors.'
    )
    if known_visit_records.empty:
        st.info("No usable prior-visit responses match the selected filters.")
    else:
        draw_gender_column_bar(known_visit_records, "helpdesk_visit_history", height=300)
        show_gender_table(known_visit_records, "helpdesk_visit_history", "Visit history")

        repeat_visit_records = known_visit_records[
            known_visit_records["helpdesk_visit_history"].eq("Repeat visitor")
        ].copy()
        st.markdown("#### Repeat Visit Timing")
        if repeat_visit_records.empty:
            st.info("No repeat visitors match the selected filters.")
        else:
            draw_gender_column_bar(
                repeat_visit_records,
                "repeat_visit_timing",
                height=300,
            )
            show_gender_table(
                repeat_visit_records,
                "repeat_visit_timing",
                "Repeat visit timing",
            )

    st.divider()
    st.subheader("Age Group by Gender")
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

    st.divider()

    # Strict disability-only slice for the entire tab.
    # This is the controlling filter for every chart/table in this menu.
    disability_only = filtered_records[
        filtered_records["disability_status"].astype(str).eq("Has Disability")
    ].copy()

    # Extra safety: remove any accidental non-disability type labels from the
    # combined impairment analysis. This protects the tab even if derivation
    # logic upstream returns a non-disability label for a record.
    non_disability_labels = ["No Disability", "None", "", "[Missing]"]
    if "disability_type" in disability_only.columns:
        disability_only = disability_only[
            ~disability_only["disability_type"].astype(str).isin(non_disability_labels)
        ].copy()

    if disability_only.empty:
        st.info("No disability records match the current filters.")
        # Footer is still shown by the global show_footer() call later.

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

        # Double safety filter: keep only adult rows confirmed as disability.
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

            st.caption("Single impairment vs multiple impairments (two or more)")

            draw_total_donut(
                adult_person,
                "adult_impairment_multiplicity",
                "Impairment multiplicity",
                height=280,
            )

            show_gender_table(
                adult_person,
                "adult_impairment_multiplicity",
                "Impairment multiplicity",
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

        # Double safety filter: keep only child rows confirmed as disability.
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
# Other tabs
# -----------------------------------------------------------------------------
if selected_tab == "Concerns":
    st.subheader("Top Protection Concerns by gender")
    concern_rank = st.radio("Rank", ["Highest values", "Lowest values"], horizontal=True, index=0, key="concern_rank")
    concern_top_n = st.radio("Number of categories", [5, 10, 15, 20, 25], horizontal=True, index=2, key="concern_top_n")
    draw_gender_bar(filtered_protection, "protection_concern", top_n=concern_top_n, height=640, ascending=concern_rank == "Lowest values")
    st.caption("Full table (all categories, unaffected by chart slicing)")
    show_gender_table(filtered_protection, "protection_concern", "Protection concern", top_n=None)
    st.markdown("#### Protection Concern by Age Group")
    st.caption("Select one or more protection concerns to view the age group and gender breakdown.")
    concern_age_options = age_breakdown_options(filtered_protection, "protection_concern")

    if not concern_age_options:
        st.info("No protection concern records match the selected filters.")
    else:
        selected_concerns_for_age = st.multiselect(
            "Protection concerns",
            concern_age_options,
            default=concern_age_options[: min(3, len(concern_age_options))],
            key="selected_concerns_for_age",
        )

        if not selected_concerns_for_age:
            st.info("Select at least one protection concern to view the age and gender breakdown.")
        else:
            draw_age_gender_breakdown_bar(
                filtered_protection,
                "protection_concern",
                selected_concerns_for_age,
                "Protection concern",
                height=320,
            )
            show_age_gender_breakdown_table(
                filtered_protection,
                "protection_concern",
                selected_concerns_for_age,
                "Protection concern",
            )

            st.markdown("#### Disability Distribution by Age Group")
            st.caption(
                "Uses the same selected protection-concern rows as the table above, "
                "then retains only mentions linked to records with disability."
            )
            selected_protection_rows = filtered_protection[
                filtered_protection["protection_concern"]
                .astype(str)
                .isin(selected_concerns_for_age)
            ].copy()
            protection_disability_by_age = selected_protection_rows[
                selected_protection_rows["disability_status"]
                .astype(str)
                .eq("Has Disability")
            ].copy()

            if protection_disability_by_age.empty:
                st.info(
                    "None of the selected protection-concern mentions are linked "
                    "to records with disability."
                )
            else:
                show_gender_table(
                    protection_disability_by_age,
                    "age_group",
                    "Age group",
                    top_n=None,
                )

    st.divider()
    st.markdown("#### Child Accompaniment Status")
    st.caption(
        'Prioritizes "child_unaccompanied_minor". Where that field is blank, '
        "the respondent relationship fields are used only when they clearly "
        "identify an unaccompanied child or a caregiver."
    )
    child_accompaniment = filtered_records[
        filtered_records["derived_life_stage"].astype(str).eq("Child")
        & filtered_records["child_accompaniment_status"].isin(
            ["Unaccompanied", "Not unaccompanied"]
        )
    ].copy()
    if child_accompaniment.empty:
        st.info("No determinable child accompaniment records match the selected filters.")
    else:
        draw_gender_column_bar(
            child_accompaniment,
            "child_accompaniment_status",
            height=300,
        )
        show_gender_table(
            child_accompaniment,
            "child_accompaniment_status",
            "Accompaniment status",
        )

        unaccompanied_children = child_accompaniment[
            child_accompaniment["child_accompaniment_status"].eq("Unaccompanied")
        ]
        st.markdown("##### Unaccompanied Children by Age Group")
        if unaccompanied_children.empty:
            st.info("No unaccompanied children match the selected filters.")
        else:
            show_gender_table(
                unaccompanied_children,
                "age_group",
                "Age group",
                top_n=None,
            )

if selected_tab == "Information":
    st.subheader("Top General Information Needs by Gender")
    information_rank = st.radio("Rank", ["Highest values", "Lowest values"], horizontal=True, index=0, key="information_rank")
    information_top_n = st.radio("Number of categories", [5, 10, 15, 20, 25], horizontal=True, index=2, key="information_top_n")
    draw_gender_bar(filtered_information, "general_information_need", top_n=information_top_n, height=640, ascending=information_rank == "Lowest values")
    st.caption("Full table (all categories, unaffected by chart slicing)")
    show_gender_table(filtered_information, "general_information_need", "General information need", top_n=None)

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
    referred_case_count = int(
        filtered_records["referral_status"].astype(str).eq("Referred to partner agency").sum()
    )
    partner_record_count = int(filtered_referrals["record_id"].nunique()) if "record_id" in filtered_referrals.columns else 0
    partner_assignment_count = len(filtered_referrals)
    st.caption(
        f"Reconciliation: {referred_case_count:,} referred cases; "
        f"{partner_record_count:,} cases with a recorded partner; "
        f"{partner_assignment_count:,} partner assignments."
    )
    if partner_record_count < referred_case_count:
        st.warning(
            f"{referred_case_count - partner_record_count:,} referred case(s) do not have a partner recorded."
        )
    if partner_assignment_count > partner_record_count:
        st.info(
            f"{partner_assignment_count - partner_record_count:,} additional assignment(s) arise because some cases were referred to more than one partner."
        )
    referral_rank = st.radio("Rank", ["Highest values", "Lowest values"], horizontal=True, index=0, key="referral_rank")
    referral_top_n = st.radio("Number of categories", [10, 15, 25], horizontal=True, index=1, key="referral_top_n")
    draw_gender_bar(filtered_referrals, "referral_partner", top_n=referral_top_n, height=560, ascending=referral_rank == "Lowest values")
    st.caption("Full partner-assignment table (all categories, unaffected by chart slicing)")
    show_gender_table(filtered_referrals, "referral_partner", "Referral partner", top_n=None)
    st.markdown('<div class="dashboard-subsection-break"></div>', unsafe_allow_html=True)
    st.markdown("#### Referral Partner by Age Group")
    st.caption("Select one or more referral partners to view the age group and gender breakdown.")
    referral_age_options = age_breakdown_options(filtered_referrals, "referral_partner")

    if not referral_age_options:
        st.info("No referral partner records match the selected filters.")
    else:
        selected_referral_partners_for_age = st.multiselect(
            "Referral partners",
            referral_age_options,
            default=referral_age_options[: min(3, len(referral_age_options))],
            key="selected_referral_partners_for_age",
        )

        if not selected_referral_partners_for_age:
            st.info("Select at least one referral partner to view the age and gender breakdown.")
        else:
            draw_age_gender_breakdown_bar(
                filtered_referrals,
                "referral_partner",
                selected_referral_partners_for_age,
                "Referral partner",
                height=320,
            )
            show_age_gender_breakdown_table(
                filtered_referrals,
                "referral_partner",
                selected_referral_partners_for_age,
                "Referral partner",
            )

            st.markdown("#### Disability Distribution by Age Group")
            st.caption(
                "Uses the same selected referral-partner assignments as the table "
                "above, then retains only assignments linked to records with disability."
            )
            selected_referral_rows = filtered_referrals[
                filtered_referrals["referral_partner"]
                .astype(str)
                .isin(selected_referral_partners_for_age)
            ].copy()
            referral_disability_by_age = selected_referral_rows[
                selected_referral_rows["disability_status"]
                .astype(str)
                .eq("Has Disability")
            ].copy()

            if referral_disability_by_age.empty:
                st.info(
                    "None of the selected referral-partner assignments are linked "
                    "to records with disability."
                )
            else:
                show_gender_table(
                    referral_disability_by_age,
                    "age_group",
                    "Age group",
                    top_n=None,
                )

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
        cpv_chart_color = CPV_METRIC_COLORS.get(cpv_chart_metric, "#2F7D69")
        cpv_x_upper = chart_headroom(cpv_chart_data[cpv_chart_metric])

        cpv_chart = (
            alt.Chart(cpv_chart_data)
            .mark_bar(
                cornerRadiusEnd=6,
                color=cpv_chart_color,
                opacity=0.94,
                stroke="#FFFFFF",
                strokeWidth=0.7,
            )
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
                    scale=alt.Scale(domain=[0, cpv_x_upper], nice=False),
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
                color="#12312F",
            )
            .encode(
                y=alt.Y("CPV:N", sort=cpv_order, title=None),
                x=alt.X(f"{cpv_chart_metric}:Q", scale=alt.Scale(domain=[0, cpv_x_upper], nice=False)),
                text=alt.Text(f"{cpv_chart_metric}:Q", format=","),
            )
        )

        st.altair_chart(
            polish_chart(cpv_chart + cpv_labels),
            use_container_width=True,
        )

        st.markdown(
            '<div class="cpv-table-title">Full CPV Work Summary — all CPVs, unaffected by chart slicers</div>',
            unsafe_allow_html=True,
        )
        render_dashboard_table(cpv_summary, label_column="CPV", max_height=620)

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
    st.markdown("### Helpdesk visit-history consistency")
    st.caption(
        'Checks the dependency between "visited_tdh_helpdesk_before" and '
        '"last_visit_within_current_month". The timing question should only be '
        "answered for repeat visitors."
    )
    visit_consistency_table = basic_count_table(
        filtered_records,
        "visit_history_consistency",
        "Consistency result",
    )
    render_dashboard_table(
        visit_consistency_table,
        label_column="Consistency result",
        max_height=360,
    )

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
    if st.checkbox("Prepare filtered CSV download", value=False, help="CSV bytes are generated only when requested to keep ordinary page opening fast."):
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


