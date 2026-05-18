from requests.auth import HTTPBasicAuth
import os
import requests


# --- API & AUTH ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
FRESHSERVICE_DOMAIN = "saks.freshservice.com"
API_KEY = "Fresh Service API Key"
fresh_headers = {"Content-Type": "application/json"}
BASE_URL = f"https://{FRESHSERVICE_DOMAIN}/api/v2"
auth = HTTPBasicAuth(API_KEY, "X")
API_CALL_COUNT = 0
API_CALL_LIMIT = 120
worksheet_anchor = 70000

# --- PATHS ---
down_path = r'Down_Folder'
attachment_path = r"Fixed_attachments"
sql_path = r"SQL_Files"

# --- DATA MAPPING & VALIDATION ---
COL_MAP = {
  "GROUP_NUMBER": ["group","groupid", "grp","grpid", "groupnumber", "group#","grp#","group_number","grpnumber","groupno", "grpno"],
  "DIVISION_NUMBER": ["division","divisionid", "div","divid", "divisionnumber", "division#","div#","division_number","divnumber","divisionno", "divno"],
  "BUYER_NUMBER": ["buyer", "byr", "buyernumber", "buyer#","byr#","BUYER_NUMBER","buyerid", "byrid"],
  "DEPARTMENT_NUMBER": ["dept", "department", "departmentnumber", "dept#","department#","DEPARTMENT_NUMBER","deptnumber","deptno", "deptnum", "departmentno","deptid"],
  "MANUFACTURER_NUMBER": ["mfg", "mfgid","manufacturer","manufacturerid", "manufacturernumber", "mfg#", "vendor","vendorid","manufacturer#","mfgnumber","mfgno", "mfgnum", "vendorno", "vendornumber"],
  "MANUFACTURER_NAME": ["mfgname","manufacturername","vendorname"],
  "CLASS_NUMBER": ["class","classid","classnumber", "class#","cls#","cls","CLASS_NUMBER","clsnumber","classno", "classnum"],
  "STATIC_SKN": ["staticskn", "skn","staticskn#","STATIC_SKN","staticsknno","staticsknnum"],
  "FASHION_STYLE_NUMBER": ["fashionstyle", "fashionstylenumber","fashionstylenumber","fashionstyle#","fashionid","fstyle","fstyleid","fstyleno","fstylenumber","fashionstyleid","fashionstylecode","fstylecode"],
  "NEW_RETAIL_PRICE": ["retailprice", "newretailprice","newretailprice$","retailprice$","retial$"],
  "NEW_COST_PRICE": ["newcostprice", "costprice","costprice$","newcostprice$","cost$"],
  "UPC": ["upcid", "upc","upcno","upcnumber","upc#","upcid","upccode","upc(optional)","upc(optional)","upcoptional"],
  "CHANGE_PERC": ["change%", "change", "chg","chg%", "changepct","changepct%","changeperc","changeperc%","mu%","muperc","mupct","mdperc","md%","mdpct","markdownperc","markdown%"]
}
ANCHOR_COLS = {'MFG NAME', 'FASHION STYLE', 'STATIC SKN'}
REQUIRED_SETS = [
    {"DEPARTMENT_NUMBER","MANUFACTURER_NUMBER","FASHION_STYLE_NUMBER","STATIC_SKN","UPC","CHANGE_PERC","NEW_RETAIL_PRICE","NEW_COST_PRICE"},
    {"DEPARTMENT_NUMBER","MANUFACTURER_NUMBER","FASHION_STYLE_NUMBER","STATIC_SKN","UPC","NEW_RETAIL_PRICE","NEW_COST_PRICE","CHANGE_PERC"}
]
req_cols = ["DEPARTMENT_NUMBER","MANUFACTURER_NUMBER","FASHION_STYLE_NUMBER","STATIC_SKN","UPC","CHANGE_PERC","NEW_RETAIL_PRICE","NEW_COST_PRICE"]
ct_cols = ['DEPARTMENT_NUMBER','CLASS_NUMBER','FASHION_STYLE_NUMBER']
SKU_COL_SETS = [
    ["DEPARTMENT_NUMBER","MANUFACTURER_NUMBER","FASHION_STYLE_NUMBER"],
    ["DEPARTMENT_NUMBER","MANUFACTURER_NUMBER","STATIC_SKN"],
    ["DEPARTMENT_NUMBER","MANUFACTURER_NUMBER","UPC"],
]

# --- RENAME & ORDER LOGIC ---
price_change_df_col_order = ['ticko_id','ticko_created_at','ticko_audit_agent','ticko_audit_status','ticko_po_agent_details','ticko_subject','tickt_service_item_name',
'tickt_division','tickt_buyer','tickt_department','tickt_mfg','tickt_price_change_type','tickt_percent_off','tickt_price_change_description',
'tickt_price_status','tickt_markdown','tickt_cost_updates','ticko_effective_date_reporting_mmddyyyy','ticko_effective_due_date_mmddyyyy','tickt_additional_notes','ticko_pos_expected_due_date','tickt_expected_due_date',
'ticko_total_no_of_worksheets','ticko_pcw_worksheet_details','worksheet_checks','REQUESTED_ITEMS_CHECK','tickt_canonical_url','canonical_url_ct',
'canonical_last_part','unique_key','ticko_pcw_worksheet_details_ct']

price_change_df_rename_dict = {"ticko_id": "Ticket_Id","ticko_created_at": "Ticket_Creation_Datetime","ticko_audit_agent": "Audit_Agent","ticko_audit_status": "Audit_Status",
"ticko_po_agent_details": "Po_Agent","ticko_subject": "Subject","tickt_service_item_name": "Ticket_Service_Item_Name","tickt_division": "Division",
"tickt_buyer": "Buyer","tickt_department": "Department","tickt_mfg": "Mfg","tickt_price_change_type": "Price_Change_Type","tickt_percent_off": "Percent_Off",
"tickt_price_change_description": "Price_Change_Description","tickt_price_status": "Price_Status","tickt_markdown": "Markdown",
"tickt_cost_updates": "Cost_Updates","ticko_effective_date_reporting_mmddyyyy": "Effective_Date","ticko_effective_due_date_mmddyyyy": "Effective_Date2",
"ticko_pos_expected_due_date":"pos_expected_due_date",
"tickt_additional_notes": "Additional_Notes",
"tickt_expected_due_date": "expected_due_date",
"ticko_total_no_of_worksheets": "Total_No_Of_Worksheets","ticko_pcw_worksheet_details": "Worksheet_Details","REQUESTED_ITEMS_CHECK": "REQUESTED_ITEMS_CHECK",
"tickt_ff_single_line_tf": "tickt_ff_single_line_tf","tickt_canonical_url": "tickt_canonical_url","canonical_url_ct": "canonical_url_ct",
"exploded_flag": "exploded_flag","canonical_last_part": "canonical_last_part","unique_key": "unique_key",
"ticko_pcw_worksheet_details_ct": "ticko_pcw_worksheet_details_ct","worksheet_checks": "worksheet_checks"}



# --- BUSINESS LOGIC CONSTANTS ---
mkdown_dict = {'1st Markdown':22,
               '2nd Markdown':23,
               'Final (Used for Penny Markdowns)':24,
               'Regular':21
              }
markdown_list12 = [22, 23,24]
regular_pcw = [21]

sql_cs_req_cols = ['cs_sql_ticketid','CS_DEPT_NO', 'CS_MFG_NO', 'CS_CLASS_NO', 'CS_FASHION_STYLE_NO', 'CS_STATIC_SKN',
       'CS_ITEM_ID','cs_sql_SELF_PROD_ID2', 'CS_UPC', 'CS_COST_AT_REQ',
       'CS_COST_AMOUNT_DOL2', 'CS_COST_AMOUNT_DOLLARS', 'CS_COST_CHANGE', 'CS_CREATE_DATE',
        'CS_ACTIVE_DATE','CS_STATUS','cs_sql_shape','cs_sql_fhs_count','cs_sql_fhs_ws_count', 'fs_uk',
       'Worksheet_Details']

sql_audit2_req_cols = ['fs_uk','fs_ticketid','fs_markdown_code','sql_req_reason_no','chk_markdown_code_match_flag',
'fs_effective_date','sql_effective_date','chk_effective_date_match_flag','attach_fhs_count','sql_fhs_count','chk_fhs_count_match_flag',
'sql_price_type_code','fs_price_type_code','chk_price_type_code_match_flag','sql_status','chk_sql_ws_status_match_flag','attach_change_perc',
'sql_change_pct2','chk_perc_match_flag','attach_new_retail_price','sql_new_ticket_dol','chk_reg_price_match_flag','sql_original_tkt_dol',
'chk_cancel_price_match_flag','chk_pct_missing_flag','chk_reg_price_missing_flag','sql_change_pct','sql_special_instructions_brand_name','sql_special_instructions_agent_name','attach_department_number',
'sql_department_number','attach_manufacturer_number','sql_manufacturer_number','attach_fashion_style_number','sql_fashion_style_number',
'sql_worksheet_no','fs_worksheet_details','fs_worksheet_details_cs','sql_shape_orig','attach_shape','ticket_shape',
'chk_sql_ws_status_mismatch_tkt_flag','chk_effective_date_mismatch_tkt_flag','chk_markdown_code_mismatch_tkt_flag','chk_price_type_code_mismatch_tkt_flag',
'chk_fhs_count_mismatch_tkt_flag','chk_fhs_dir_mismatch_tkt_flag', 'chk_perc_mismatch_tkt_flag','chk_reg_price_mismatch_tkt_flag', 'chk_cancel_price_mismatch_tkt_flag',
'chk_reg_price_missing_tkt_flag', 'chk_pct_missing_tkt_flag','chk_penny_price_match_flag']


audit_common_cols = ['fs_uk','fs_ticketid','fs_po_agent','fs_audit_status','fs_cost_updates','fs_cost_updates_req_flag','fs_markdown_code','fs_price_change_type_cleaned','fs_effective_date','fs_worksheet_details','fs_worksheet_details_cs',
'sql_unique_special_ins_list','sql_unique_status_list','sql_special_instructions_brand_name_list','sql_special_instructions_agent_name_list','attach_fhs_count','sql_fhs_count','attach_fhs_count_list',
'sql_fhs_count_list','cs_sql_fhs_count','cs_sql_fhs_count_list','attach_perc_list','sql_unique_change_pct_list','sql_unique_status_list','sql_effective_date_list','sql_cs_active_date_list','sql_req_reason_no_list','sql_cs_status_list','sql_price_type_code_list','chk_fhs_count_match_ct',
'chk_fhs_count_mismatch_ct','chk_cs_fhs_count_mismatch_ct','chk_cs_costcng_mismatch_ct']

audit3_full_check_cols = ['chk_sql_ws_status_mismatch_tkt_flag','chk_effective_date_mismatch_tkt_flag','chk_markdown_code_mismatch_tkt_flag',
       'chk_price_type_code_mismatch_tkt_flag', 'chk_perc_mismatch_tkt_flag',
       'chk_reg_price_mismatch_tkt_flag', 'chk_cancel_price_mismatch_tkt_flag','chk_penny_price_mismatch_tkt_flag',
       'chk_reg_price_missing_tkt_flag', 'chk_pct_missing_tkt_flag','chk_fhs_dir_mismatch_tkt_flag','chk_fhs_count_mismatch_tkt_flag','chk_cs_active_date_mismatch_tkt_flag',
'chk_cs_fhs_count_mismatch_tkt_flag','chk_cs_status_mismatch_tkt_flag','chk_cs_costcng_mismatch_tkt_flag','chk_cs_dol_missing_tkt_flag']

audit_penny_exclude = ['chk_reg_price_mismatch_tkt_flag', 'chk_cancel_price_mismatch_tkt_flag','chk_reg_price_missing_tkt_flag','chk_perc_mismatch_tkt_flag','chk_pct_missing_tkt_flag']

audit_perm_mkdn_exclude = ['chk_reg_price_mismatch_tkt_flag', 'chk_cancel_price_mismatch_tkt_flag',
                     'chk_penny_price_mismatch_tkt_flag','chk_reg_price_missing_tkt_flag']

audit_reg_exclude = ['chk_perc_mismatch_tkt_flag', 'chk_cancel_price_mismatch_tkt_flag',
                     'chk_penny_price_mismatch_tkt_flag','chk_pct_missing_tkt_flag']

# audit_cancel_exclude = ['chk_reg_price_mismatch_tkt_flag','chk_penny_price_mismatch_tkt_flag','chk_perc_mismatch_tkt_flag',
#                   'chk_reg_price_missing_tkt_flag','chk_pct_missing_tkt_flag']

audit_cancel_exclude = ['chk_reg_price_mismatch_tkt_flag','chk_penny_price_mismatch_tkt_flag','chk_perc_mismatch_tkt_flag','chk_pct_missing_tkt_flag']

audit_summary_cols = ['chk_sql_ws_status_mismatch_summary','chk_effective_date_mismatch_summary',
       'chk_markdown_code_mismatch_summary','chk_price_type_code_mismatch_summary','chk_fhs_count_mismatch_summary','chk_fhs_dir_mismatch_summary', 'chk_perc_mismatch_summary',
       'chk_reg_price_mismatch_summary', 'chk_cancel_price_mismatch_summary','chk_penny_price_mismatch_summary', 'chk_reg_price_missing_summary',
       'chk_pct_missing_summary','chk_cs_active_date_mismatch_summary','chk_cs_fhs_count_mismatch_summary','chk_cs_status_mismatch_summary','chk_cs_costcng_mismatch_summary','chk_cs_dol_missing_summary']

list_clean_cols = ['sql_special_instructions_brand_name_list','sql_special_instructions_agent_name_list','attach_fhs_count_list','sql_fhs_count_list','cs_sql_fhs_count_list',
'sql_effective_date_list','sql_cs_active_date_list','sql_req_reason_no_list','sql_cs_status_list','sql_price_type_code_list']


audit_df_final_col_order = ['fs_ticketid','fs_po_agent','fs_audit_status','fs_cost_updates','fs_price_change_type_cleaned','sql_price_type_code_list','chk_price_type_code_mismatch_tkt_flag',
'fs_markdown_code','sql_req_reason_no_list','chk_markdown_code_mismatch_tkt_flag','attach_perc_list','sql_unique_change_pct_list','chk_perc_mismatch_tkt_flag','fs_effective_date',
'sql_effective_date_list','chk_effective_date_mismatch_tkt_flag','sql_unique_status_list','chk_sql_ws_status_mismatch_tkt_flag','sql_unique_special_ins_list','sql_special_instructions_brand_name_list',
'sql_special_instructions_agent_name_list','attach_fhs_count_list','sql_fhs_count_list','attach_fhs_count','sql_fhs_count','chk_fhs_count_mismatch_tkt_flag','attach_fhs_count_list','cs_sql_fhs_count_list',
'attach_fhs_count','cs_sql_fhs_count','chk_cs_fhs_count_mismatch_tkt_flag','chk_cs_costcng_mismatch_tkt_flag','chk_cs_dol_missing_tkt_flag','sql_cs_status_list','chk_cs_status_mismatch_tkt_flag',
'sql_cs_active_date_list','chk_cs_active_date_mismatch_tkt_flag','fs_worksheet_details_cs','chk_reg_price_mismatch_tkt_flag','chk_cancel_price_mismatch_tkt_flag','chk_penny_price_mismatch_tkt_flag',
'fs_worksheet_details','chk_all_flags_match','flags_count_matched','flags_count_failed','pass_reasons','failed_reasons','chk_price_type_code_mismatch_summary','chk_markdown_code_mismatch_summary',
'chk_perc_mismatch_summary','chk_effective_date_mismatch_summary','chk_sql_ws_status_mismatch_summary','chk_fhs_dir_mismatch_summary','chk_reg_price_mismatch_summary','chk_cancel_price_mismatch_summary',
'chk_penny_price_mismatch_summary','chk_pct_missing_summary','chk_cs_dol_missing_summary','chk_cs_fhs_count_mismatch_summary','chk_cs_status_mismatch_summary','chk_cs_active_date_mismatch_summary',
'chk_cs_costcng_mismatch_summary','Blank_1','Blank_2','fs_uk','chk_perc_match_flag','chk_fhs_count_match_ct','chk_fhs_count_mismatch_ct','chk_cs_fhs_count_mismatch_ct','chk_cs_costcng_mismatch_ct',
'chk_reg_price_missing_tkt_flag','chk_reg_price_missing_summary','chk_pct_missing_tkt_flag']

audit_df_final_col_order_rnm = ['fs_ticketid','fs_po_agent','fs_audit_status','fs_cost_updates','fs_price_change_type_cleaned','sql_price_type_code_list','chk_price_type_code_mismatch_tkt_flag',
'fs_markdown_code','sql_req_reason_no_list','chk_markdown_code_mismatch_tkt_flag','attach_perc_list','sql_unique_change_pct_list','chk_perc_mismatch_tkt_flag','fs_effective_date',
'sql_effective_date_list','chk_effective_date_mismatch_tkt_flag','sql_unique_status_list','chk_sql_ws_status_mismatch_tkt_flag','sql_unique_special_ins_list','sql_special_instructions_brand_name_list',
'sql_special_instructions_agent_name_list','attach_fhs_count_list','sql_fhs_count_list','attach_fhs_count','sql_fhs_count','chk_fhs_count_mismatch_tkt_flag','cs_attach_fhs_count_list',
'cs_sql_fhs_count_list','cs_attach_fhs_count','cs_sql_fhs_count','chk_cs_fhs_count_mismatch_tkt_flag','chk_cs_costcng_mismatch_tkt_flag','chk_cs_dol_missing_tkt_flag','sql_cs_status_list',
'chk_cs_status_mismatch_tkt_flag','sql_cs_active_date_list','chk_cs_active_date_mismatch_tkt_flag','fs_worksheet_details_cs','chk_reg_price_mismatch_tkt_flag','chk_cancel_price_mismatch_tkt_flag',
'chk_penny_price_mismatch_tkt_flag','fs_worksheet_details','chk_all_flags_match','flags_count_matched','flags_count_failed','pass_reasons','failed_reasons','chk_price_type_code_mismatch_summary',
'chk_markdown_code_mismatch_summary','chk_perc_mismatch_summary','chk_effective_date_mismatch_summary','chk_sql_ws_status_mismatch_summary','chk_fhs_dir_mismatch_summary','chk_reg_price_mismatch_summary',
'chk_cancel_price_mismatch_summary','chk_penny_price_mismatch_summary','chk_all_missing_summary','chk_cs_dol_missing_summary','chk_cs_fhs_count_mismatch_summary','chk_cs_status_mismatch_summary',
'chk_cs_active_date_mismatch_summary','chk_cs_costcng_mismatch_summary','Blank_1','Blank_2','fs_uk','chk_perc_match_flag','chk_fhs_count_match_ct','chk_fhs_count_mismatch_ct',
'chk_cs_fhs_count_mismatch_ct','chk_cs_costcng_mismatch_ct','chk_reg_price_missing_tkt_flag','chk_reg_price_missing_summary','chk_pct_missing_tkt_flag']

audit_df_summary_explode_all_cols = ['fs_ticketid','fs_po_agent','fs_cost_updates','fs_price_change_type_cleaned','fs_worksheet_details','chk_sql_ws_status_mismatch_summary','chk_effective_date_mismatch_summary',
       'chk_markdown_code_mismatch_summary','chk_price_type_code_mismatch_summary','chk_fhs_dir_mismatch_summary', 'chk_perc_mismatch_summary',
       'chk_reg_price_mismatch_summary', 'chk_cancel_price_mismatch_summary','chk_penny_price_mismatch_summary', 'chk_reg_price_missing_summary',
       'chk_cs_active_date_mismatch_summary','chk_cs_fhs_count_mismatch_summary','chk_cs_status_mismatch_summary','chk_cs_costcng_mismatch_summary','chk_cs_dol_missing_summary','chk_all_missing_summary']

audit_df_summary_explode_cols = ['chk_sql_ws_status_mismatch_summary','chk_effective_date_mismatch_summary',
       'chk_markdown_code_mismatch_summary','chk_price_type_code_mismatch_summary','chk_fhs_dir_mismatch_summary', 'chk_perc_mismatch_summary',
       'chk_reg_price_mismatch_summary', 'chk_cancel_price_mismatch_summary','chk_penny_price_mismatch_summary', 'chk_reg_price_missing_summary',
       'chk_cs_active_date_mismatch_summary','chk_cs_fhs_count_mismatch_summary','chk_cs_status_mismatch_summary','chk_cs_costcng_mismatch_summary','chk_cs_dol_missing_summary','chk_all_missing_summary']
