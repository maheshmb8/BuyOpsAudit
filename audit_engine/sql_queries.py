pcdf_q = """
select 
unique_key as fs_uk, 
Ticket_Id as fs_ticketid,
Po_Agent as fs_po_agent,
Audit_Status as fs_audit_status,
Cost_Updates as fs_Cost_Updates,
Markdown_Code as fs_markdown_code,
Price_Change_Type as fs_Price_Change_Type,
Effective_Date_fixed as fs_Effective_Date_fixed,
Ticket_Creation_Datetime as fs_Ticket_Creation_Datetime,
fs_Effective_Date_fixed::date as fs_effective_date,
Ticket_Creation_Datetime::date as fs_ticket_date,
Ticket_Creation_Datetime::datetime as fs_ticket_ts,
Cost_Updates_req_flag as fs_Cost_Updates_req_flag,
Worksheet_Details,
Worksheet_Details_Cleaned,
Worksheet_Details_Cleaned_PCW,
Worksheet_Details_Cleaned_CS,
list_aggregate(list_transform(Worksheet_Details, x -> '''' || x::VARCHAR || ''''), 'string_agg', ', ') AS fs_wk_string,
Percent_Off2 as fs_Percent_Off2

from price_change_df_send
"""

fs_attach_merge_q = """
select 
p.*, 
a.* EXCLUDE (source_file, ticket_id),
case when 
trim(lower(fs_Price_Change_Type)) in ('perm markdown') then 
count(distinct FASHION_STYLE_NUMBER||'_'||DEPARTMENT_NUMBER||'_'||MANUFACTURER_NUMBER) over (partition by fs_ticketid)
when 
trim(lower(fs_Price_Change_Type)) in ('regular / regular','markdown cancel') then
count(distinct SELF_PROD_ID2||'_'||DEPARTMENT_NUMBER||'_'||MANUFACTURER_NUMBER) over (partition by fs_ticketid)
else 0 end as fs_count,

case when 
trim(lower(fs_Price_Change_Type)) in ('perm markdown') then 
count(distinct FASHION_STYLE_NUMBER) over (partition by fs_ticketid,DEPARTMENT_NUMBER,MANUFACTURER_NUMBER)
when 
trim(lower(fs_Price_Change_Type)) in ('regular / regular','markdown cancel') then
count(distinct SELF_PROD_ID2) over (partition by fs_ticketid,DEPARTMENT_NUMBER,MANUFACTURER_NUMBER)
else 0 end as fs_count_ws,

ifnull(round(CHANGE_PERC,2),round(fs_Percent_Off2,2)) as CHANGE_PERC2,
lower(trim(fs_Price_Change_Type)) as fs_Price_Change_Type_cleaned
from price_change_df_send2 p
left join attach_full a
on p.fs_ticketid = a.ticket_id
and 'fixed_'||fs_uk||'.xlsx'==source_file
"""

sql_query_1 = """
select BUYER_NO,EFFECTIVE_DATE,REQ_REASON_NO,PRICE_TYPE_CODE,SPECIAL_INSTRUCTIONS,
STATUS,CHANGE_PCT,CLASS_NO,CURRENT_TICKET_DOL,DEPT_NO as DEPARTMENT_NUMBER,FASHION_STYLE_NO as FASHION_STYLE_NUMBER,MFG_NO as MANUFACTURER_NUMBER,
NEW_TICKET_DOL,ORIGINAL_TKT_DOL,SKN_NO,a.WORKSHEET_NO,current_date()-60 as run_range
from reporting.pcw.wp_worksheet a 
join reporting.pcw.wp_worksheet_detail b 
on a.worksheet_no=b.worksheet_no
where 1=1
and a.insert_timestamp::date >= current_date()-60
and a.worksheet_no in ({wd_string})
order by a.insert_timestamp;
"""

sql_query_2 = """
select ccd.DEPT_NO as cs_DEPT_NO,ccd.MFG_NO as cs_MFG_NO,ccd.CLASS_NO as cs_CLASS_NO,ccd.FASHION_STYLE_NO as cs_FASHION_STYLE_NO,
ic.STATIC_SKN as cs_STATIC_SKN,ic.ITEM_ID as cs_ITEM_ID,ic.UPC as cs_UPC,ic.vendor_product_id as cs_vendor_product_id,ic.PRODUCT_ID as cs_PRODUCT_ID,ccd.COST_AT_REQ as cs_COST_AT_REQ,
ccd.COST_AMOUNT_DOL2 as cs_COST_AMOUNT_DOL2,ic.cost_amount_dollars as cs_cost_amount_dollars,ccd.COST_CHANGE as cs_COST_CHANGE,cch.CREATE_DATE as cs_CREATE_DATE,
cch.LAST_MOD_DATE as cs_LAST_MOD_DATE,cch.ACTIVE_DATE as cs_ACTIVE_DATE,cch.REASON as cs_REASON,cch.COST_CHANGE_DESC as cs_COST_CHANGE_DESC,cch.CREATE_ID as cs_CREATE_ID,
cch.LAST_MOD_ID as cs_LAST_MOD_ID,cch.STATUS as cs_STATUS,cch._FIVETRAN_SYNCED::TIMESTAMP_NTZ as cs__FIVETRAN_SYNCED,ccd.PO_UPDATE_IND as cs_PO_UPDATE_IND,ccd._FIVETRAN_ID as cs__FIVETRAN_ID
from reporting.cms_rfs.rf_cost_chg_detail ccd
left join reporting.cms_rfs.rf_cost_chg_header cch
on ccd.cost_change = cch.cost_change
left join
(select fashion_style_number,department_number,manufacturer_number,static_skn,
upc,item_id,product_id,vendor_product_id,cost_amount_dollars
from marts.items.items_current)ic
on ic.fashion_style_number = ccd.fashion_style_no
and ic.department_number = ccd.dept_no
and ic.manufacturer_number = ccd.mfg_no
where 1=1
and cch.create_date >= current_date()-60
and ccd.cost_change in ({wd_string})
order by cch.create_date;
"""

sql_merge = """
select a.*,s.CHANGE_PCT,s.WORKSHEET_NO,s.CURRENT_TICKET_DOL,s.NEW_TICKET_DOL,s.ORIGINAL_TKT_DOL,s.STATUS,
s.REQ_REASON_NO,s.PRICE_TYPE_CODE,s.EFFECTIVE_DATE,
trim(concat('_', s.FASHION_STYLE_NUMBER::VARCHAR, '_', s.SKN_NO::VARCHAR, '_')) as SQL_CC,
coalesce(a.NEW_RETAIL_PRICE::float=s.NEW_TICKET_DOL::float,False) as PRICE_MATCH
from attach a
left join sql_df s
on (
    a.DEPARTMENT_NUMBER = s.DEPARTMENT_NUMBER
    and a.MANUFACTURER_NUMBER = s.MANUFACTURER_NUMBER
    and contains(trim(concat('_', s.FASHION_STYLE_NUMBER::VARCHAR, '_', s.SKN_NO::VARCHAR, '_')),trim(a.SELF_PROD_ID2::VARCHAR))
)
"""


fs_attach_sql_merge_q = """
select 
--- fs cols
fa.fs_uk,fa.fs_ticketid::bigint as fs_ticketid,fs_po_agent,fs_audit_status,fs_Cost_Updates,fs_markdown_code, fs_Price_Change_Type, fs_Effective_Date_fixed, 
fs_Ticket_Creation_Datetime, fs_effective_date, fs_ticket_date, fs_ticket_ts, fa.Worksheet_Details_Cleaned_PCW as fs_Worksheet_Details,fa.Worksheet_Details_Cleaned_CS as fs_worksheet_details_cs, fs_wk_string, 
fs_Percent_Off2,fs_Price_Change_Type_cleaned,fs_cost_updates_req_flag,

--- attach_cols
fa.DEPARTMENT_NUMBER as attach_DEPARTMENT_NUMBER, fa.MANUFACTURER_NUMBER as attach_MANUFACTURER_NUMBER, 
fa.FASHION_STYLE_NUMBER as attach_FASHION_STYLE_NUMBER, fa.STATIC_SKN as attach_STATIC_SKN, fa.UPC as attach_upc,
fa.CHANGE_PERC as attach_change_perc, fa.NEW_RETAIL_PRICE as attach_NEW_RETAIL_PRICE, fa.NEW_COST_PRICE as attach_NEW_COST_PRICE, 
fa.filled_cols as attach_filled_cols, fa.SELF_PROD_ID2 as attach_SELF_PROD_ID2, attach_shape, attach_perc_list, fs_count as attach_fhs_count,
fs_count_ws as attach_fhs_ws_count, 
fa.CHANGE_PERC2 as attach_CHANGE_PERC2, 

--- sql_cols
s.BUYER_NO as sql_BUYER_NO, s.EFFECTIVE_DATE as sql_EFFECTIVE_DATE, s.REQ_REASON_NO as sql_REQ_REASON_NO, s.PRICE_TYPE_CODE as sql_PRICE_TYPE_CODE, 
s.SPECIAL_INSTRUCTIONS as sql_SPECIAL_INSTRUCTIONS, s.STATUS as sql_STATUS, s.CHANGE_PCT as sql_CHANGE_PCT, s.CLASS_NO as sql_CLASS_NO, 
s.CURRENT_TICKET_DOL as sql_CURRENT_TICKET_DOL, s.DEPARTMENT_NUMBER as sql_DEPARTMENT_NUMBER, s.FASHION_STYLE_NUMBER as sql_FASHION_STYLE_NUMBER, 
s.MANUFACTURER_NUMBER as sql_MANUFACTURER_NUMBER, s.NEW_TICKET_DOL as sql_NEW_TICKET_DOL, s.ORIGINAL_TKT_DOL as sql_ORIGINAL_TKT_DOL, 
s.SKN_NO as sql_SKN_NO, s.WORKSHEET_NO as sql_WORKSHEET_NO, s.RUN_RANGE as sql_RUN_RANGE,
s.CHANGE_PCT2 as sql_CHANGE_PCT2, sql_ticketid::bigint as sql_ticketid, sql_unique_status_list, sql_unique_price_type_code_list, sql_unique_special_ins_list, 
sql_unique_req_reason_no_list, sql_shape,sql_fhs_count,sql_fhs_ws_count,sql_SELF_PROD_ID2, sql_unique_change_pct_list,

---- basic_checks
case when trim(upper(s.STATUS)) in ('PROC','INC', 'VOID', 'FAIL') then FALSE else TRUE end as sql_ws_status_match,
CASE WHEN s.WORKSHEET_NO IS NOT NULL THEN TRUE ELSE FALSE END AS sql_not_missing,
max(coalesce(sql_shape,0)) over (partition by fa.fs_ticketid) as sql_shape_orig,
case when sql_shape_orig > 0 then TRUE else FALSE end as sql_exists

FROM fs_attach_df fa

LEFT JOIN sql_full s
  ON fa.fs_ticketid = s.sql_ticketid   
  AND fa.fs_uk = s.fs_uk             
  AND fa.DEPARTMENT_NUMBER = s.DEPARTMENT_NUMBER
  AND fa.MANUFACTURER_NUMBER = s.MANUFACTURER_NUMBER
  AND (
    (
      fa.fs_Price_Change_Type_cleaned = 'perm markdown' 
      AND fa.FASHION_STYLE_NUMBER = s.FASHION_STYLE_NUMBER
    )
    OR 
    (
      fa.fs_Price_Change_Type_cleaned IN ('regular / regular', 'markdown cancel') 
      AND contains(s.sql_SELF_PROD_ID2, fa.SELF_PROD_ID2)
    )
  )

  ;
"""

fs_attach_sql_pcw_cs_merge_q = """
select 
--- fs cols
fa.fs_uk,fa.fs_ticketid::bigint as fs_ticketid,fs_po_agent,fs_audit_status,fs_Cost_Updates,fs_markdown_code, fs_Price_Change_Type, fs_Effective_Date_fixed, 
fs_Ticket_Creation_Datetime, fs_effective_date, fs_ticket_date, fs_ticket_ts, fa.Worksheet_Details_Cleaned_PCW as fs_Worksheet_Details,fa.Worksheet_Details_Cleaned_CS as fs_worksheet_details_cs, fs_wk_string, 
fs_Percent_Off2,fs_Price_Change_Type_cleaned,fs_cost_updates_req_flag,

--- attach_cols
fa.DEPARTMENT_NUMBER as attach_DEPARTMENT_NUMBER, fa.MANUFACTURER_NUMBER as attach_MANUFACTURER_NUMBER, 
fa.FASHION_STYLE_NUMBER as attach_FASHION_STYLE_NUMBER, fa.STATIC_SKN as attach_STATIC_SKN, fa.UPC as attach_upc,
fa.CHANGE_PERC as attach_change_perc, fa.NEW_RETAIL_PRICE as attach_NEW_RETAIL_PRICE, fa.NEW_COST_PRICE as attach_NEW_COST_PRICE, 
fa.filled_cols as attach_filled_cols, fa.SELF_PROD_ID2 as attach_SELF_PROD_ID2, attach_shape, attach_perc_list, fs_count as attach_fhs_count,
fs_count_ws as attach_fhs_ws_count, 
fa.CHANGE_PERC2 as attach_CHANGE_PERC2, 

--- sql_cols
s.BUYER_NO as sql_BUYER_NO, s.EFFECTIVE_DATE as sql_EFFECTIVE_DATE, s.REQ_REASON_NO as sql_REQ_REASON_NO, s.PRICE_TYPE_CODE as sql_PRICE_TYPE_CODE, 
s.SPECIAL_INSTRUCTIONS as sql_SPECIAL_INSTRUCTIONS, s.STATUS as sql_STATUS, s.CHANGE_PCT as sql_CHANGE_PCT, s.CLASS_NO as sql_CLASS_NO, 
s.CURRENT_TICKET_DOL as sql_CURRENT_TICKET_DOL, s.DEPARTMENT_NUMBER as sql_DEPARTMENT_NUMBER, s.FASHION_STYLE_NUMBER as sql_FASHION_STYLE_NUMBER, 
s.MANUFACTURER_NUMBER as sql_MANUFACTURER_NUMBER, s.NEW_TICKET_DOL as sql_NEW_TICKET_DOL, s.ORIGINAL_TKT_DOL as sql_ORIGINAL_TKT_DOL, 
s.SKN_NO as sql_SKN_NO, s.WORKSHEET_NO as sql_WORKSHEET_NO, s.RUN_RANGE as sql_RUN_RANGE,sql_SELF_PROD_ID2,
s.CHANGE_PCT2 as sql_CHANGE_PCT2, sql_ticketid::bigint as sql_ticketid, sql_unique_status_list, sql_unique_price_type_code_list, sql_unique_special_ins_list, 
sql_unique_req_reason_no_list, sql_shape,sql_fhs_count,sql_fhs_ws_count, sql_unique_change_pct_list,

--- cs_sql_cols
cs.CS_COST_AT_REQ,CS_COST_AMOUNT_DOL2,CS_cost_amount_dollars,cs.CS_COST_CHANGE as sql_cs_WORKSHEET_NO,cs_CREATE_DATE,cs_ACTIVE_DATE,cs_status,cs_sql_shape,cs_sql_fhs_count,cs_sql_fhs_ws_count,sql_SELF_PROD_ID2,
cs.CS_DEPT_NO as sql_cs_DEPARTMENT_NUMBER,CS_FASHION_STYLE_NO as sql_cs_FASHION_STYLE_NUMBER,CS_MFG_NO as sql_cs_MANUFACTURER_NUMBER,

---- basic_checks
case when trim(upper(s.STATUS)) in ('PROC','INC', 'VOID', 'FAIL') then FALSE else TRUE end as sql_ws_status_match,
CASE WHEN s.WORKSHEET_NO IS NOT NULL THEN TRUE ELSE FALSE END AS sql_not_missing,
max(coalesce(sql_shape,0)) over (partition by fa.fs_ticketid) as sql_shape_orig,
case when sql_shape_orig > 0 then TRUE else FALSE end as sql_exists,

CASE WHEN cs.cs_COST_CHANGE IS NOT NULL THEN TRUE ELSE FALSE END AS cs_sql_not_missing,
max(coalesce(cs_sql_shape,0)) over (partition by fa.fs_ticketid) as cs_sql_shape_orig,
case when cs_sql_shape_orig > 0 then TRUE else FALSE end as cs_sql_exists


FROM fs_attach_df fa

LEFT JOIN sql_full s
  ON fa.fs_ticketid = s.sql_ticketid   
  AND fa.fs_uk = s.fs_uk             
  AND fa.DEPARTMENT_NUMBER = s.DEPARTMENT_NUMBER
  AND fa.MANUFACTURER_NUMBER = s.MANUFACTURER_NUMBER
  AND (
    (
      fa.fs_Price_Change_Type_cleaned = 'perm markdown' 
      AND fa.FASHION_STYLE_NUMBER = s.FASHION_STYLE_NUMBER
    )
    OR 
    (
      fa.fs_Price_Change_Type_cleaned IN ('regular / regular', 'markdown cancel') 
      AND contains(s.sql_SELF_PROD_ID2, fa.SELF_PROD_ID2)
    )
  )

LEFT JOIN sql_full_cs cs
  ON fa.fs_ticketid = cs.cs_sql_ticketid   
  AND fa.fs_uk = cs.fs_uk             
  AND fa.DEPARTMENT_NUMBER = cs.CS_DEPT_NO
  AND fa.MANUFACTURER_NUMBER = cs.CS_MFG_NO
  AND fa.fs_Cost_Updates_req_flag = TRUE
  AND (
    (
      fa.fs_Price_Change_Type_cleaned = 'perm markdown' 
      AND fa.fs_Cost_Updates_req_flag = TRUE
      AND fa.FASHION_STYLE_NUMBER = cs.CS_FASHION_STYLE_NO
    )
    OR 
    (
      fa.fs_Price_Change_Type_cleaned IN ('regular / regular', 'markdown cancel') 
      AND fa.fs_Cost_Updates_req_flag = TRUE
      AND contains(cs.cs_sql_SELF_PROD_ID2, fa.SELF_PROD_ID2)
    )
  )

  ;
"""

audit_sql_1 = """
select 
    *,
    -- 1. Categorical Mapping (creates fs_price_type_code)
    CASE fs_markdown_code
        WHEN 21 THEN 'Z'
        WHEN 22 THEN 'R'
        WHEN 23 THEN 'R'
        WHEN 24 THEN 'R'
        ELSE 'Other'
    END AS fs_price_type_code,

    -- 2. Shape and Count Window Functions
    count(fs_ticketid) OVER (PARTITION BY fs_ticketid) AS ticket_shape,
    count(sql_shape)   OVER (PARTITION BY fs_ticketid) AS sql_shape_expanded,
    count(attach_shape) OVER (PARTITION BY fs_ticketid) AS attach_shape_expanded,
    
    -- Count missing rows per ticket
    SUM(CASE WHEN sql_worksheet_no IS NULL THEN 1 ELSE 0 END) OVER (PARTITION BY fs_ticketid) AS chk_sql_missing_ct,

    -- 3. Logic for full/partial missing (Boolean results)
    (chk_sql_missing_ct = attach_shape) AS full_sql_missing,
    (COALESCE(sql_shape, 0) > 0 AND chk_sql_missing_ct > 0) AS partial_sql_missing,

    -- 4. Audit Mismatch Flags (Results in TRUE, FALSE, or NULL)
    (fs_effective_date = sql_effective_date) AS chk_effective_date_match,
    (fs_markdown_code = sql_req_reason_no)   AS chk_markdown_code_match,
    (fs_price_type_code = sql_price_type_code) AS chk_price_type_code_match,
    (attach_fhs_count = sql_fhs_count) AS chk_fhs_count_match,

    case when fs_Cost_Updates_req_flag = TRUE then
    (fs_effective_date = cs_active_date) 
    else TRUE end AS chk_cs_active_date_match,

    case when fs_Cost_Updates_req_flag = TRUE then
    (attach_fhs_count = cs_sql_fhs_count)
    else TRUE end AS chk_cs_fhs_count_match,

    case when fs_Cost_Updates_req_flag = TRUE then
    CS_STATUS not in ('C','W')
    else TRUE end AS chk_cs_status_match,

    CASE 
        WHEN fs_Cost_Updates_req_flag = TRUE THEN
            ABS(
                ROUND(TRY_CAST(attach_new_cost_price AS DOUBLE), 2) - 
                ROUND(TRY_CAST(cs_cost_amount_dol2 AS DOUBLE), 2)
            ) < 0.0148
        ELSE TRUE 
    END AS chk_cs_costcng_match,

    case when fs_Price_Change_Type_cleaned = 'perm markdown' 
    then attach_fashion_style_number = sql_fashion_style_number
    when fs_Price_Change_Type_cleaned IN ('regular / regular', 'markdown cancel')
    then contains(sql_self_prod_id2, attach_self_prod_id2) end as chk_fhs_dir_match,


    -- 5. Conditional Validation based on Price Change Type
    CASE 
        WHEN fs_Price_Change_Type_cleaned IN ('perm markdown') 
        THEN (attach_change_perc = sql_change_pct2)
        ELSE TRUE 
    END AS chk_perc_match,    

    CASE 
        WHEN fs_Price_Change_Type_cleaned IN ('regular / regular') 
        THEN (attach_new_retail_price = sql_new_ticket_dol)
        ELSE TRUE 
    END AS chk_reg_price_match,

CASE 
    WHEN fs_Price_Change_Type_cleaned IN ('markdown cancel') 
    THEN (
        COALESCE(
            TRY_CAST(attach_new_retail_price AS DOUBLE), 
            TRY_CAST(sql_original_tkt_dol AS DOUBLE)
        ) = TRY_CAST(sql_new_ticket_dol AS DOUBLE)
    )
    ELSE TRUE 
END AS chk_cancel_price_match,

    CASE 
        WHEN fs_markdown_code = 24
        THEN ROUND((sql_current_ticket_dol - sql_new_ticket_dol)::FLOAT, 2) = 0.01
        ELSE TRUE 
    END AS chk_penny_price_match,


    -- 6. Requirement Validation (Completeness Checks)
    (
        fs_Price_Change_Type_cleaned IN ('markdown cancel', 'regular / regular') 
        AND sql_shape_orig > 0 
        AND sql_original_tkt_dol IS NOT NULL
    ) AS chk_reg_price_missing,

    (
        fs_Price_Change_Type_cleaned = 'perm markdown' 
        AND sql_shape_orig > 0 
        AND sql_change_pct IS NOT NULL
    ) AS chk_pct_missing,

    (
        fs_Cost_Updates_req_flag = TRUE
        AND cs_sql_shape_orig > 0 
        AND cs_cost_amount_dol2 IS NOT NULL
    ) AS chk_cs_dol_missing,

    -- 7. String Parsing (Note: DuckDB is 1-indexed)
    split(sql_special_instructions, ' ')[1]  AS sql_special_instructions_brand_name,
    split(sql_special_instructions, ' ')[-1] AS sql_special_instructions_agent_name,

    --- 8.String aggregations
    string_agg(distinct coalesce(sql_special_instructions_brand_name::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as sql_special_instructions_brand_name_list,
    string_agg(distinct coalesce(sql_special_instructions_agent_name::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as sql_special_instructions_agent_name_list,

    string_agg(distinct coalesce(attach_fhs_ws_count::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as attach_fhs_count_list,
    string_agg(distinct coalesce(sql_fhs_ws_count::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as sql_fhs_count_list,
    string_agg(distinct coalesce(cs_sql_fhs_ws_count::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as cs_sql_fhs_count_list,

    string_agg(distinct coalesce(sql_effective_date::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as sql_effective_date_list,
    string_agg(distinct coalesce(cs_active_date::varchar,''), ', ') OVER (PARTITION BY fs_ticketid) as sql_cs_active_date_list,

    string_agg(distinct coalesce(upper(sql_req_reason_no::varchar),''), ', ') OVER (PARTITION BY fs_ticketid) as sql_req_reason_no_list,
    string_agg(distinct coalesce(upper(sql_price_type_code::varchar),''), ', ') OVER (PARTITION BY fs_ticketid) as sql_price_type_code_list,
    string_agg(distinct coalesce(upper(CS_STATUS::varchar),''), ', ') OVER (PARTITION BY fs_ticketid) as sql_cs_status_list



FROM fs_attach_sql_df

"""

audit_sql_2 = """
select *,
sql_not_missing::int as sql_not_missing_flag,
sql_exists::int as sql_exists_flag,
full_sql_missing::int as full_sql_missing_flag,
partial_sql_missing::int as partial_sql_missing_flag,

sql_ws_status_match::int as chk_sql_ws_status_match_flag,
chk_effective_date_match::int as chk_effective_date_match_flag,
chk_markdown_code_match::int as chk_markdown_code_match_flag,
chk_price_type_code_match::int as chk_price_type_code_match_flag,
chk_fhs_count_match::int as chk_fhs_count_match_flag,
chk_fhs_dir_match::int as chk_fhs_dir_match_flag,
chk_perc_match::int as chk_perc_match_flag,
chk_reg_price_match::int as chk_reg_price_match_flag,
chk_cancel_price_match::int as chk_cancel_price_match_flag,
chk_penny_price_match::int as chk_penny_price_match_flag,
chk_cs_active_date_match::int as chk_cs_active_date_match_flag,
chk_cs_fhs_count_match::int as chk_cs_fhs_count_match_flag,
chk_cs_status_match::int as chk_cs_status_match_flag,
chk_cs_costcng_match::int as chk_cs_costcng_match_flag,

chk_reg_price_missing::int as chk_reg_price_missing_flag,
chk_pct_missing::int as chk_pct_missing_flag,
chk_cs_dol_missing::int as chk_cs_dol_missing_flag,

SUM(chk_sql_ws_status_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_sql_ws_status_match_ct,
SUM((chk_sql_ws_status_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_sql_ws_status_mismatch_ct,
MAX((chk_sql_ws_status_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_sql_ws_status_mismatch_tkt_flag,

-- 1. Effective Date Matches & Mismatches
SUM(chk_effective_date_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_effective_date_match_ct,
SUM((chk_effective_date_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_effective_date_mismatch_ct,
MAX((chk_effective_date_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_effective_date_mismatch_tkt_flag,

-- 2. Markdown Code Matches & Mismatches
SUM(chk_markdown_code_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_markdown_code_match_ct,
SUM((chk_markdown_code_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_markdown_code_mismatch_ct,
MAX((chk_markdown_code_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_markdown_code_mismatch_tkt_flag,

-- 3. Price Type Code Matches & Mismatches
SUM(chk_price_type_code_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_price_type_code_match_ct,
SUM((chk_price_type_code_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_price_type_code_mismatch_ct,
MAX((chk_price_type_code_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_price_type_code_mismatch_tkt_flag,


-- 4. FHS Count Matches & Mismatches
SUM(chk_fhs_count_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_fhs_count_match_ct,
SUM((chk_fhs_count_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_fhs_count_mismatch_ct,
MAX((chk_fhs_count_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_fhs_count_mismatch_tkt_flag,

-- 4. FHS Dir Matches & Mismatches
SUM(chk_fhs_dir_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_fhs_dir_match_ct,
SUM((chk_fhs_dir_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_fhs_dir_mismatch_ct,
MAX((chk_fhs_dir_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_fhs_dir_mismatch_tkt_flag,

-- 5. Percentage Matches & Mismatches
SUM(chk_perc_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_perc_match_ct,
SUM((chk_perc_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_perc_mismatch_ct,
MAX((chk_perc_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_perc_mismatch_tkt_flag,


-- 6. Regular Price Matches & Mismatches
SUM(chk_reg_price_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_reg_price_match_ct,
SUM((chk_reg_price_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_reg_price_mismatch_ct,
MAX((chk_reg_price_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_reg_price_mismatch_tkt_flag,

-- 7. Cancel Price Matches & Mismatches
SUM(chk_cancel_price_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_cancel_price_match_ct,
SUM((chk_cancel_price_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cancel_price_mismatch_ct,
MAX((chk_cancel_price_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cancel_price_mismatch_tkt_flag,

-- 7. penny Price Matches & Mismatches
SUM(chk_penny_price_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_penny_price_match_ct,
SUM((chk_penny_price_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_penny_price_mismatch_ct,
MAX((chk_penny_price_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_penny_price_mismatch_tkt_flag,

-- 1. Active Date Matches & Mismatches
SUM(chk_cs_active_date_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_cs_active_date_match_ct,
SUM((chk_cs_active_date_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_active_date_mismatch_ct,
MAX((chk_cs_active_date_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_active_date_mismatch_tkt_flag,

-- 2. FHS Count Matches & Mismatches
SUM(chk_cs_fhs_count_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_cs_fhs_count_match_ct,
SUM((chk_cs_fhs_count_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_fhs_count_mismatch_ct,
MAX((chk_cs_fhs_count_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_fhs_count_mismatch_tkt_flag,

-- 3. Status Matches & Mismatches
SUM(chk_cs_status_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_cs_status_match_ct,
SUM((chk_cs_status_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_status_mismatch_ct,
MAX((chk_cs_status_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_status_mismatch_tkt_flag,

-- 4. Cost Change Matches & Mismatches
SUM(chk_cs_costcng_match_flag) OVER (PARTITION BY fs_ticketid) AS chk_cs_costcng_match_ct,
SUM((chk_cs_costcng_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_costcng_mismatch_ct,
MAX((chk_cs_costcng_match_flag = 0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_costcng_mismatch_tkt_flag,

-- 8. Missing Data Flags (Count of occurrences)
SUM((chk_reg_price_missing_flag=0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_reg_price_missing_ct,
MAX((chk_reg_price_missing_flag=0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_reg_price_missing_tkt_flag,

SUM((chk_pct_missing_flag=0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_pct_missing_ct,
MAX((chk_pct_missing_flag=0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_pct_missing_tkt_flag,

SUM((chk_cs_dol_missing_flag=0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_dol_missing_ct,
MAX((chk_cs_dol_missing_flag=0)::INT) OVER (PARTITION BY fs_ticketid) AS chk_cs_dol_missing_tkt_flag


from audit_df1 """


audit_sql_3 = """
select 
distinct
fs_uk, fs_ticketid,fs_po_agent, fs_audit_status, fs_cost_updates,fs_cost_updates_req_flag, fs_markdown_code, fs_price_change_type,fs_Price_Change_Type_cleaned, fs_effective_date_fixed, fs_ticket_creation_datetime, 
fs_effective_date, fs_ticket_date, fs_ticket_ts, fs_worksheet_details,fs_worksheet_details_cs, fs_wk_string, fs_percent_off2,attach_perc_list,sql_unique_change_pct_list,sql_special_instructions_brand_name_list,
sql_special_instructions_agent_name_list,sql_shape_orig,cs_sql_shape_orig,attach_fhs_count,sql_fhs_count,attach_fhs_count_list,sql_fhs_count_list,cs_sql_fhs_count,cs_sql_fhs_count_list,sql_exists,sql_unique_special_ins_list,
sql_unique_status_list,sql_effective_date_list,sql_cs_active_date_list,sql_req_reason_no_list,sql_cs_status_list,sql_price_type_code_list,
sql_shape_expanded,chk_sql_ws_status_mismatch_tkt_flag,chk_effective_date_mismatch_tkt_flag,chk_markdown_code_mismatch_tkt_flag,chk_price_type_code_mismatch_tkt_flag,
chk_fhs_count_match_ct,chk_fhs_count_mismatch_ct,chk_cs_fhs_count_mismatch_ct,chk_cs_costcng_mismatch_ct,chk_fhs_count_mismatch_tkt_flag,chk_fhs_dir_match_ct,chk_fhs_dir_mismatch_ct,chk_fhs_dir_mismatch_tkt_flag,chk_perc_mismatch_tkt_flag,
chk_reg_price_mismatch_tkt_flag,chk_cancel_price_mismatch_tkt_flag,chk_penny_price_mismatch_tkt_flag,chk_cs_active_date_mismatch_tkt_flag,chk_cs_fhs_count_mismatch_tkt_flag,
chk_cs_status_mismatch_tkt_flag,chk_cs_costcng_mismatch_tkt_flag,
chk_reg_price_missing_tkt_flag,chk_pct_missing_tkt_flag,chk_cs_dol_missing_tkt_flag,
'' as chk_sql_ws_status_mismatch_summary,
'' as chk_effective_date_mismatch_summary,
'' as chk_markdown_code_mismatch_summary,
'' as chk_price_type_code_mismatch_summary,
'' as chk_fhs_count_mismatch_summary,
'' as chk_fhs_dir_mismatch_summary,
'' as chk_perc_mismatch_summary,
'' as chk_reg_price_mismatch_summary,
'' as chk_cancel_price_mismatch_summary,
'' as chk_penny_price_mismatch_summary,
'' as chk_cs_active_date_mismatch_summary,
'' as chk_cs_fhs_count_mismatch_summary,
'' as chk_cs_status_mismatch_summary,
'' as chk_cs_costcng_mismatch_summary,
'' as chk_reg_price_missing_summary,
'' as chk_pct_missing_summary,
'' as chk_cs_dol_missing_summary
from audit_df2
where 1=1
and sql_shape_orig > 0
and not (cs_sql_shape_orig > 0 and cs_sql_fhs_count is null)
and sql_not_missing = TRUE
"""

audit_sql_4 = audit_sql_3.replace("""and sql_shape_orig > 0
and not (cs_sql_shape_orig > 0 and cs_sql_fhs_count is null)
and sql_not_missing = TRUE""","""and (sql_shape_orig = 0 or (cs_sql_shape_orig = 0 and fs_Cost_Updates_req_flag = TRUE)) """)