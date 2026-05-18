import pandas as pd
import time
from jsonpath_ng.ext import parse
import threading
count_lock = threading.Lock()
import os
import concurrent.futures
from tqdm.auto import tqdm


# --- TEMPORARY TEST IMPORTS ---
from .utils import *
from .fs_api import *
from .config import *

API_CALL_COUNT = 0


def build_price_change_df(df_rows, ts_prefix, output_dir=".", save_excel=True):
    """
    Builds and processes price_change_df from raw rows.

    Parameters
    ----------
    df_rows : list[dict] or compatible
        Input rows to construct DataFrame
    ts_prefix : str
        Timestamp prefix used in unique_key and filename
    output_dir : str, optional
        Directory to save the Excel file
    save_excel : bool, optional
        Whether to save the DataFrame to Excel

    Returns
    -------
    pd.DataFrame
        Processed price_change_df
    """

    price_change_df = pd.DataFrame(df_rows)

    # count URLs per row (before explode)
    # price_change_df["canonical_url_ct"] = price_change_df["tickt_canonical_url"].apply(len)
    price_change_df["canonical_url_ct"] = price_change_df["tickt_canonical_url"].apply(lambda x: len(x) if x is not None else 0)

    # flag rows that will explode into multiple rows
    price_change_df["exploded_flag"] = price_change_df["tickt_canonical_url"].apply(
        lambda x: int(isinstance(x, list) and len(x) > 1)
    )

    # explode URLs
    price_change_df = price_change_df.explode("tickt_canonical_url").reset_index(drop=True)

    # extract last part of URL
    price_change_df["canonical_last_part"] = (
        price_change_df["tickt_canonical_url"].str.split("/").str[-1]
    )

    # generate unique key
    price_change_df["unique_key"] = [
        f"{ts_prefix}_{ticko}_{canon}_{i:08d}"
        for i, (ticko, canon) in enumerate(
            zip(
                price_change_df["ticko_id"],
                price_change_df["canonical_last_part"]
            ),
            start=1
        )
    ]

    # save to Excel if needed
    if save_excel:
        output_path = f"{output_dir}/price_change_df_{ts_prefix}.xlsx"
        price_change_df.to_excel(output_path, index=False)

    return price_change_df

def read_price_change_sheet_v4(file_name, col_map, required_sets, max_header_row=20):
    xl = pd.ExcelFile(file_name)
    best_missing_count = float('inf')
    best_missing_report = []

    for sheet in xl.sheet_names:
        for h in range(max_header_row + 1):
            try:
                # 1️⃣ Probe (Same as v2)
                probe = pd.read_excel(xl, sheet_name=sheet, header=h, nrows=5)
                probe = probe.dropna(how="all")
                if probe.empty: continue
                
                # IMPORTANT: Use the col_map passed into the function
                probe = rename_with_map(probe, col_map)

                # 2️⃣ Validate Schema 
                # Use the REQUIRED_SETS (global) or required_sets (local) consistently
                # Let's use the local one to be safe
                current_missing = [req - set(probe.columns) for req in required_sets]
                current_min_count = min(len(m) for m in current_missing)

                # 3️⃣ Success Case (Exact same as v2)
                if current_min_count == 0:
                    df = pd.read_excel(xl, sheet_name=sheet, header=h)
                    df = df.dropna(thresh=3)
                    df = df.dropna(how="all")
                    # Ensure the full DF gets renamed and returned
                    df = rename_with_map(df, col_map)
                    return df, None

                # 4️⃣ Update Best Failure (The v3 addition)
                if current_min_count < best_missing_count:
                    best_missing_count = current_min_count
                    best_missing_report = current_missing

            except Exception as e:
                # If you want to see why a specific row crashed:
                # print(f"Error on {sheet} row {h}: {e}")
                continue 

    # Return None + the best report found if no perfect match was hit
    return None, best_missing_report



def extract_pricechange_vars(ticko):
    """
    Extract variables for Price Change tickets (Thread-Safe).
    """
    from . import core   # To access live API_CALL_COUNT
    from . import config # To access API_CALL_LIMIT
    
    row = {}

    # --- ticko level ---
    row["ticko_id"] = ticko.get("id")
    row["ticko_subject"] = ticko.get("subject")
    row["ticko_created_at"] = ticko.get("created_at")

    cf_o = ticko.get("custom_fields", {})
    row["ticko_audit_agent"] = cf_o.get("audit_agent")
    row["ticko_audit_status"] = cf_o.get("audit_status_1")
    row["ticko_po_agent_details"] = cf_o.get("po_agent_details")
    row["ticko_effective_date_reporting_mmddyyyy"] = cf_o.get("effective_date_reporting_mmddyyyy")
    row['ticko_effective_due_date_mmddyyyy'] = cf_o.get('effective_due_date_mmddyyyy')
    row['ticko_pos_expected_due_date'] = cf_o.get('pos_expected_due_date')
    row["ticko_total_no_of_worksheets"] = cf_o.get("total_no_of_worksheets")

    pcw = cf_o.get("pcw_worksheet_details")
    row["ticko_pcw_worksheet_details"] = pcw.split("\n") if pcw else None

    row["REQUESTED_ITEMS_CHECK"] = "OK"

    # --- detailed ticket (The API Call) ---
    try:
        # Fetch detailed data
        tickt_res = view_ticket(ticko["id"])
        tickt = tickt_res[0]

        # Thread-safe counter update and rate-limit check
        with count_lock:
            core.API_CALL_COUNT += 1
            if core.API_CALL_COUNT % config.API_CALL_LIMIT == 0:
                print(f"\n[Rate Limit] {core.API_CALL_COUNT} calls reached. Sleeping 65s...",end="\r")
                time.sleep(65)

    except Exception as e:
        row["REQUESTED_ITEMS_CHECK"] = "ERROR"
        # Null all tickt fields exactly as in your original code
        detailed_fields = [
            "tickt_service_item_name", "tickt_markdown", "tickt_percent_off",
            "tickt_price_change_description", "tickt_price_change_type",
            "tickt_price_status", "tickt_expected_due_date", "tickt_additional_notes",
            "tickt_cost_updates", "tickt_buyer", "tickt_department",
            "tickt_mfg", "tickt_division", "tickt_ff_single_line_tf", "tickt_canonical_url"
        ]
        for f in detailed_fields:
            row[f] = None
        return row

    # --- detailed ticket extraction (Matching your keys exactly) ---
    cf_t = tickt.get("custom_fields", {})

    row["tickt_service_item_name"] = tickt.get("service_item_name")
    row["tickt_markdown"] = cf_t.get("reasons_this_represents_what_the_status_will_be_after_price_change")
    row["tickt_percent_off"] = cf_t.get("percent_off_off_example_30_remember_to_enter")
    row["tickt_price_change_description"] = cf_t.get("price_change_description_special_instructions_this_is_the_price_change_description_entered_in_the")
    row["tickt_price_change_type"] = cf_t.get("price_change_type")
    row["tickt_price_status"] = cf_t.get("untitledcurrent_status_this_represents_what_the_current_price_status_is_for_the_items_included_in")
    row['tickt_expected_due_date'] = cf_t.get("due_date_mm_dd_yy___double_click_to_enter_when_the_price_change_is_due_to_be_entered_in_pcw_reque")
    row["tickt_additional_notes"] = clean_html(cf_t.get("additional_request_notes"))
    row["tickt_cost_updates"] = cf_t.get("are_cost_updates_required_to_refrain_from_having_to_enter_a_separate_mass_item_change_for_identic")
    
    row["tickt_buyer"] = find_first_non_null_by_prefix(ticket=tickt, prefix="buyer_", top_n_keys=30, max_key_len=50)
    row["tickt_department"] = find_first_non_null_by_prefix(ticket=tickt, prefix="department_", top_n_keys=30, max_key_len=50)
    
    row["tickt_mfg"] = cf_t.get("mfg")
    row["tickt_division"] = cf_t.get("division")
    row["tickt_ff_single_line_tf"] = tickt.get("ff_single_line_tf")
    row["tickt_canonical_url"] = [m.value for m in parse("$.attachments[*].canonical_url").find(tickt)]
    if not row["tickt_canonical_url"]:
        try:
            tickt_conv = view_ticket2(ticko["id"], requested_items=False, include_conversations=True)
            conv_attachments_expr = parse("$.conversations[*].attachments[*].id")
            can_burl = "https://saks.freshservice.com/helpdesk/attachments/"
            row["tickt_canonical_url"] = [f"{can_burl}{m.value}" for m in conv_attachments_expr.find(tickt_conv)]
            # row["tickt_canonical_url"] = [m.value for m in conv_attachments_expr.find(tickt_conv)]
            with count_lock:
                core.API_CALL_COUNT += 1

        except:
            row["tickt_canonical_url"] = []
    return row

def process_tickets_parallel(filtered_tickets, max_workers=8):
    """
    Takes a list of tickets ALREADY filtered by the notebook 
    and extracts their details in parallel.
    """
    import concurrent.futures
    from tqdm.auto import tqdm
    import pandas as pd

    if not filtered_tickets:
        print("No tickets provided for processing.")
        return pd.DataFrame()

    print(f"Starting parallel extraction for {len(filtered_tickets)} tickets...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Use ae.extract_pricechange_vars (which has the Lock/Rate limit logic we built)
        results = list(tqdm(
            executor.map(extract_pricechange_vars, filtered_tickets), 
            total=len(filtered_tickets), 
            desc="API Extraction"
        ))
        
    return pd.DataFrame([r for r in results if r])

def get_clean_key(df):
    return (
        df['DEPARTMENT_NUMBER'].astype(str).str.strip() + "_" +
        df['MANUFACTURER_NUMBER'].astype(str).str.strip() + "_" +
        df['FASHION_STYLE_NUMBER'].astype(str).str.strip()
    ).str.upper()

def format_summary_v2(row):
    styles_str = ", ".join(row['attach_fashion_style_number'])
    return f"WS:{row['sql_worksheet_no']}_MFG:{row['attach_manufacturer_number']}_Styles:{row['fs_ct']}({styles_str})"

def format_summary_v3(row):
    styles_str = ", ".join(row['attach_fashion_style_number'])
    # Added DEPT to the output string
    return f"WS:{row['sql_worksheet_no']}_DEPT:{row['sql_department_number']}_MFG:{row['attach_manufacturer_number']}_Styles:{row['fs_ct']}({styles_str})"


def build_conc_id(row):
    style = str(row['FASHION_STYLE_NUMBER']).strip()
    skn = str(row['STATIC_SKN']).strip()
    
    # Check if style is "empty" (NaN, 'nan', or '')
    if style == '' or style.lower() == 'nan':
        return f'_{skn}_'
    
    return f'_{style}_{skn}_'


def summary_txt_builder_v2(mask_df, mfg_ws_dict):
    """
    Builds a summary string for missing/invalid data and updates the audit dictionary.
    """
    missing_df = mask_df.copy()
    # Initialize the key in the dict
    
    if not missing_df.empty:
        # Mapping logic
        missing_df['sql_worksheet_no'] = missing_df['attach_manufacturer_number'].map(mfg_ws_dict)
        missing_df['sql_worksheet_no'] = missing_df['sql_worksheet_no'].fillna("No Worksheet Found")
        
        # Formatting IDs
        for col in ['attach_manufacturer_number', 'attach_fashion_style_number']:
            missing_df[col] = (pd.to_numeric(missing_df[col], errors='coerce')
                               .astype('Int64')
                               .astype(str)
                               .replace('<NA>', 'Unknown'))
        
        # Grouping - Note: Calling format_summary directly
        grouped = (missing_df.groupby(['sql_worksheet_no', 'attach_manufacturer_number'])['attach_fashion_style_number']
                   .unique()
                   .reset_index())
        
        grouped['fs_ct'] = grouped['attach_fashion_style_number'].str.len()
        
        # Calling the local function directly
        combined_output = grouped.apply(format_summary_v2, axis=1).tolist()
        
        return combined_output

def summary_txt_builder_v3(mask_df, mfg_dept_ws_dict):
    """
    Builds a summary string using a multi-key dictionary (Dept, Mfg).
    """
    missing_df = mask_df.copy()
    
    if not missing_df.empty:
        # 1. Clean the ID columns first so they match the dictionary keys (strings/ints)
        cols_to_fix = ['attach_manufacturer_number', 'attach_fashion_style_number', 'sql_department_number']
        for col in cols_to_fix:
            if col in missing_df.columns:
                missing_df[col] = (pd.to_numeric(missing_df[col], errors='coerce')
                                   .astype('Int64')
                                   .astype(str)
                                   .replace('<NA>', 'Unknown'))

        # 2. Map the Worksheet using the (Dept, Mfg) tuple key
        # We create a temporary Series of tuples to match your dict keys
        missing_df['sql_worksheet_no'] = (
            missing_df.set_index(['sql_department_number', 'attach_manufacturer_number'])
            .index.map(mfg_dept_ws_dict)
        )
        missing_df['sql_worksheet_no'] = missing_df['sql_worksheet_no'].fillna("No Worksheet Found")
        
        # 3. Grouping
        grouped = (missing_df.groupby(['sql_worksheet_no', 'sql_department_number', 'attach_manufacturer_number'])['attach_fashion_style_number']
                   .unique()
                   .reset_index())
        
        grouped['fs_ct'] = grouped['attach_fashion_style_number'].str.len()
        
        # 4. Generate Output
        combined_output = grouped.apply(format_summary_v3, axis=1).tolist()
        
        return combined_output

def summary_txt_builder_v4(mask_df, mfg_dept_ws_dict):
    missing_df = mask_df.copy()
    if missing_df.empty:
        return []

    # 1. Align types with the dictionary keys: ('str', int)
    # Ensure Dept is string and Mfg is integer
    missing_df['sql_department_number'] = missing_df['sql_department_number'].astype(str)
    missing_df['sql_manufacturer_number'] = pd.to_numeric(missing_df['sql_manufacturer_number'], errors='coerce').fillna(0).astype(int)

    # 2. Map using the exact type-matched tuple
    missing_df['sql_worksheet_no'] = (
        missing_df[['sql_department_number', 'sql_manufacturer_number']]
        .apply(tuple, axis=1)
        .map(mfg_dept_ws_dict)
    )
    
    # Fill the ones that truly don't exist in the dict
    missing_df['sql_worksheet_no'] = missing_df['sql_worksheet_no'].fillna("No Worksheet Found")

    # 3. Grouping (Ensuring Style numbers are strings for joining later)
    missing_df['attach_fashion_style_number'] = missing_df['attach_fashion_style_number'].astype(str)
    
    grouped = (missing_df.groupby(['sql_worksheet_no', 'sql_department_number', 'sql_manufacturer_number'])['attach_fashion_style_number']
               .unique()
               .reset_index())
    
    grouped['fs_ct'] = grouped['attach_fashion_style_number'].str.len()
    
    # 4. Generate Output
    combined_output = grouped.apply(format_summary_v3, axis=1).tolist()
    
    return combined_output

def format_summary_v3(row, prefix):
    # Dynamically grab the IDs based on the prefix used
    dept = row[f"{prefix}department_number"]
    mfg = row[f"{prefix}manufacturer_number"]
    styles_str = ", ".join(row['attach_fashion_style_number'])
    
    return f"WS:{row['sql_worksheet_no']}_DEPT:{dept}_MFG:{mfg}_Styles:{row['fs_ct']}({styles_str})"

def summary_txt_builder_v5(mask_df, mfg_dept_ws_dict, col):
    missing_df = mask_df.copy()
    if missing_df.empty:
        return []

    # 1. Determine the prefix based on the keyword "missing"
    prefix = "attach_" if 'missing' in col.lower() else "sql_"
    
    # These are the keys for mapping and grouping
    dept_key = f"{prefix}department_number"
    mfg_key = f"{prefix}manufacturer_number"

    # 2. Standardize types to match your dictionary: ('str', int)
    # Note: Using 'attach_fashion_style_number' regardless of the scenario
    missing_df[dept_key] = missing_df[dept_key].astype(str)
    missing_df[mfg_key] = (pd.to_numeric(missing_df[mfg_key], errors='coerce')
                           .fillna(0).astype(int))

    # 3. Map the Worksheet from the dictionary using the chosen columns
    missing_df['sql_worksheet_no'] = (
        missing_df[[dept_key, mfg_key]]
        .apply(tuple, axis=1)
        .map(mfg_dept_ws_dict)
        .fillna("No Worksheet Found")
    )

    # 4. Grouping & Aggregation
    missing_df['attach_fashion_style_number'] = missing_df['attach_fashion_style_number'].astype(str)
    
    grouped = (missing_df.groupby(['sql_worksheet_no', dept_key, mfg_key])['attach_fashion_style_number']
               .unique()
               .reset_index())
    
    grouped['fs_ct'] = grouped['attach_fashion_style_number'].str.len()
    
    # 5. Format the output
    # We pass the prefix into format_summary to ensure it reads the right keys
    return grouped.apply(lambda row: format_summary_v3(row, prefix), axis=1).tolist()

def format_summary_v4(row, prefix, ws_col):
    # Dynamically grab the IDs based on the prefix used
    dept = row[f"{prefix}department_number"]
    mfg = row[f"{prefix}manufacturer_number"]
    styles_str = ", ".join(row['attach_fashion_style_number'])
    
    # Use the dynamic worksheet column name
    return f"WS:{row[ws_col]}_DEPT:{dept}_MFG:{mfg}_Styles:{row['fs_ct']}({styles_str})"

def summary_txt_builder_v6(mask_df, mfg_dept_ws_dict, col):
    missing_df = mask_df.copy()
    if missing_df.empty:
        return []

    col_lower = col.lower()
    
    # 1. Determine prefix for Dept/Mfg (can be attach_)
    if 'missing' in col_lower:
        prefix = "attach_"
    elif '_cs_' in col_lower:
        prefix = "sql_cs_"
    else:
        prefix = "sql_"
    
    # 2. Determine prefix for Worksheet (Never attach_)
    ws_col = "sql_cs_worksheet_no" if '_cs_' in col_lower else "sql_worksheet_no"
    
    dept_key = f"{prefix}department_number"
    mfg_key = f"{prefix}manufacturer_number"

    # 3. Standardize types (Dept -> str, Mfg -> int)
    missing_df[dept_key] = missing_df[dept_key].astype(str)
    missing_df[mfg_key] = (pd.to_numeric(missing_df[mfg_key], errors='coerce')
                           .fillna(0).astype(int))

    # 4. Map the Worksheet from the dictionary into the dynamic ws_col
    missing_df[ws_col] = (
        missing_df[[dept_key, mfg_key]]
        .apply(tuple, axis=1)
        .map(mfg_dept_ws_dict)
        .fillna("No Worksheet Found")
    )

    # 5. Grouping & Aggregation
    missing_df['attach_fashion_style_number'] = missing_df['attach_fashion_style_number'].astype(str)
    
    grouped = (missing_df.groupby([ws_col, dept_key, mfg_key])['attach_fashion_style_number']
               .unique()
               .reset_index())
    
    grouped['fs_ct'] = grouped['attach_fashion_style_number'].str.len()
    
    # 6. Generate Output
    return grouped.apply(lambda row: format_summary_v4(row, prefix, ws_col), axis=1).tolist()

def process_all_summaries(df, columns_to_explode):
    all_results = []
    
    # Identify base columns that should repeat (Ticket ID, Agent, etc.)
    base_cols = [c for c in df.columns if c not in columns_to_explode]
    
    for col_name in columns_to_explode:
        # print(f"Processing: {col_name}")
        
        # 1. Explode the list and keep the base columns + current summary
        temp_df = df[base_cols + [col_name]].explode(col_name).dropna(subset=[col_name])
        
        if temp_df.empty:
            continue
            
        # 2. Regex Extraction
        pattern = r'WS:(?P<WS>\d+)_DEPT:(?P<DEPT>\d+)_MFG:(?P<MFG>\d+)_Styles:(?P<Count>\d+)\((?P<SKUs>.*?)\)'
        extracted = temp_df[col_name].str.extract(pattern)
        
        # 3. Combine base info with extracted parts
        combined = pd.concat([temp_df, extracted], axis=1)
        
        # --- CRITICAL CHANGE: Keep only rows where extraction was successful ---
        # If 'WS' is NaN, the regex didn't find a match, so we discard those rows
        combined = combined.dropna(subset=['WS'])
        
        if combined.empty:
            continue

        combined['summary_key'] = col_name
        combined = combined.rename(columns={col_name: 'original_summary_text'})
        
        # 4. Clean and Explode SKUs
        if 'SKUs' in combined.columns:
            combined['SKUs'] = combined['SKUs'].fillna('').astype(str).str.replace(' ', '', regex=False).str.split(',')
            combined = combined.explode('SKUs')
            
            # Final cleanup for the SKU rows
            combined = combined.dropna(subset=['SKUs'])
            combined = combined[combined['SKUs'] != '']
            
            # Convert IDs to numeric for easier analysis
            for id_col in ['WS', 'DEPT', 'MFG', 'Count']:
                combined[id_col] = pd.to_numeric(combined[id_col], errors='coerce')
            
            all_results.append(combined)
    
    if all_results:
        final_df = pd.concat(all_results, ignore_index=True)
        print(f"Success! Final row count: {len(final_df)}")
        return final_df
    else:
        print("No valid exploded rows found.")
        return pd.DataFrame()