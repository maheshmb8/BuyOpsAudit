import time
from datetime import datetime
import json
import html
import pandas as pd
import os
import re
import ast
import numpy as np
from datetime import datetime, timezone
from jsonpath_ng.ext import parse
from typing import List, Dict
from pathlib import Path

def datetime_to_epoch(dt_str, fmt="%Y-%m-%d %H:%M:%S"):
    """
        "YYYY-MM-DD HH:MM:SS"
    """
    return int(time.mktime(datetime.strptime(dt_str, fmt).timetuple()))

def normalize_date(d):
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    raise ValueError(f"Invalid date format: {d}")

def normalize_date(d):
    """
    Normalizes date/time for Freshservice tickets/filter API.

    Rules:
    - Date only -> YYYY-MM-DD
    - Date + time -> UTC ISO format with Z
    """
    # Already UTC ISO
    if d.endswith("Z"):
        return d

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(d, fmt)

            # date-only
            if fmt == "%Y-%m-%d":
                return dt.strftime("%Y-%m-%d")

            # convert to UTC + Z
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        except ValueError:
            pass

    raise ValueError(f"Invalid date format: {d}")


def pretty_print_ticket(ticket):
    print(json.dumps(ticket, indent=2, default=str))

def clean_html(text):
    if not isinstance(text, str):
        return text

    if "<" not in text or ">" not in text:
        return text

    # Decode entities (&nbsp;, &amp;, etc.)
    text = html.unescape(text)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def reorder_and_rename_columns(
    df: pd.DataFrame,
    ordered_cols: List[str],
    rename_map: Dict[str, str]
) -> pd.DataFrame:
    """
    Reorder columns and rename them.
    Assumes ordered_cols contains exactly the columns you want.
    """

    # Reorder
    df_out = df[ordered_cols].copy()

    # Rename
    df_out = df_out.rename(columns=rename_map)

    return df_out

def sanitize_for_print(obj):
    """
    Recursively walks dicts/lists and cleans HTML in strings
    """
    if isinstance(obj, dict):
        return {k: sanitize_for_print(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_print(v) for v in obj]
    elif isinstance(obj, str):
        return clean_html(obj)
    else:
        return obj

def pretty_ticket_obj(ticket):
    """
    Returns a sanitized (HTML-free) ticket dict
    """
    return sanitize_for_print(ticket)


def save_ticket(ticket, filename):
    safe_ticket = pretty_ticket_obj(ticket)

    ext = os.path.splitext(filename)[-1].lower()

    if ext == ".json":
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(safe_ticket, f, indent=2, ensure_ascii=False, default=str)

    elif ext == ".txt":
        with open(filename, "w", encoding="utf-8") as f:
            for k, v in safe_ticket.items():
                if isinstance(v, (dict, list)):
                    f.write(f"{k}: [nested]\n")
                else:
                    f.write(f"{k}: {v}\n")

    else:
        raise ValueError("Unsupported file type. Use .json or .txt")

def save_ticket_full(ticket, filename):
    safe_ticket = pretty_ticket_obj(ticket)
    ext = os.path.splitext(filename)[-1].lower()

    if ext == ".json":
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(safe_ticket, f, indent=2, ensure_ascii=False, default=str)

    elif ext == ".txt":
        with open(filename, "w", encoding="utf-8") as f:
            for k, v in safe_ticket.items():
                if isinstance(v, (dict, list)):
                    f.write(f"{k}:\n")
                    f.write(json.dumps(v, indent=2, ensure_ascii=False, default=str))
                    f.write("\n\n")
                else:
                    f.write(f"{k}: {v}\n")

    else:
        raise ValueError("Unsupported file type. Use .json or .txt")



def flatten_dict(d, parent_key="", sep="."):
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        elif isinstance(v, list):
            # skip lists here (attachments handled separately)
            continue
        else:
            items[new_key] = v

    return items

def extract_json_key(json_obj, key, return_all="Y"):
    """
    Extract value(s) for a given key from a JSON object using JSONPath deep scan.

    Parameters
    ----------
    json_obj : dict
        JSON object (e.g., Freshservice ticket).

    key : str
        Key name to search for (e.g., "canonical_url").

    return_all : str, optional
        - "Y": return all matches as a list
        - "N": return only the first match (or None)
        Default is "Y".

    Returns
    -------
    list or str or None
        - If return_all="Y" → list of values (possibly empty)
        - If return_all="N" → first value or None
    """
    expr = parse(f"$..{key}")
    matches = [match.value for match in expr.find(json_obj)]

    if return_all.upper() == "Y":
        return matches

    return matches[0] if matches else None

def find_json_paths(json_obj, key):
    """
    Find full JSONPath(s) for a given key anywhere in a JSON object.

    Parameters
    ----------
    json_obj : dict
        JSON object (e.g., Freshservice ticket)

    key : str
        Key name to search for (e.g., "canonical_url")

    Returns
    -------
    list[str]
        Full JSONPath expressions where the key exists
    """
    expr = parse(f"$..{key}")
    matches = expr.find(json_obj)

    return [str(match.full_path) for match in matches]

def find_json_paths_v2(json_obj, key):
    """
    Find Python-usable key paths for a given key anywhere in a JSON object.

    Parameters
    ----------
    json_obj : dict
        JSON object (e.g., Freshservice ticket)

    key : str
        Key name to search for (e.g., "canonical_url")

    Returns
    -------
    list[list[str]]
        Each inner list represents a Python dict access path.
        Example:
        [['custom_fields', 'po_transmit_date']]
    """
    expr = parse(f"$..{key}")
    paths = []

    for match in expr.find(json_obj):
        # match.full_path -> Fields('custom_fields','po_transmit_date')
        if hasattr(match.full_path, "fields"):
            paths.append(list(match.full_path.fields))
        else:
            # fallback (very rare)
            paths.append([key])

    return paths


def extract_custom_fields_by_prefix(ticket, prefix, max_key_len=None):
    """
    Extract non-null custom_fields whose keys start with a given prefix,
    optionally filtering by key length.

    Parameters
    ----------
    ticket : dict
        Freshservice ticket JSON.

    prefix : str
        Key prefix to match (e.g. "buyer_", "department_").

    max_key_len : int or None, optional
        Maximum allowed length of the key name.
        If None, no length filter is applied.

    Returns
    -------
    list[dict]
        DF-ready rows: key, value
    """
    rows = []

    custom_fields = ticket.get("custom_fields", {})

    for k, v in custom_fields.items():
        if not k.startswith(prefix):
            continue

        if v is None:
            continue

        if max_key_len is not None and len(k) > max_key_len:
            continue

        rows.append({
            "key": k,
            "value": v
        })

    return rows

def find_first_non_null_by_prefix(
    ticket,
    prefix,
    top_n_keys,
    max_key_len
):
    """
    Find the first non-null custom_field VALUE matching a prefix
    within the top N keys and key-length constraint.

    Returns
    -------
    value or None
    """
    custom_fields = ticket.get("custom_fields", {})

    for i, (k, v) in enumerate(custom_fields.items()):
        if i >= top_n_keys:
            break

        if not k.startswith(prefix):
            continue

        if v is None:
            continue

        if len(k) > max_key_len:
            continue

        return v   # ✅ only value

    return None


def rename_with_map(df, col_map):
    rename = {}
    for c in df.columns:
        c_str = str(c)
        norm = (c_str.lower().strip().replace(" ", "").replace("_", "").replace("#", "").replace("-", "").replace(".", "").replace("(", "").replace(")", ""))
        # print(norm)
        # print(norm)
        for canon, variants in col_map.items():
            if norm in variants:
                rename[c] = canon
                # print('--------------',norm)
                break

    return df.rename(columns=rename)

def replace_substring_in_column(df, col, old, new):
    """
    Replace a substring in a dataframe column.

    df   : pandas DataFrame
    col  : column name (string)
    old  : substring to replace
    new  : replacement substring
    """
    df[col] = df[col].astype(str).str.replace(old, new, regex=False)
    return df


def get_count(error_str):
    try:
        # Split at the colon and get the list part
        list_str = error_str.split(": ")[1]
        # Safely convert string to list of sets
        missing_list = ast.literal_eval(list_str)
        return len(missing_list[0]) if missing_list else 0
    except:
        return 0

def delete_all_files(folder_path, keep="*"):
    for f in os.listdir(folder_path):
        ext = f.split(".")[-1].lower()
        if keep != "*" and ext in keep:
            continue
        os.remove(os.path.join(folder_path, f))


def normalize_pct(val):
    if val is None or pd.isna(val):
        return np.nan
    # If it's a whole number like 50, 75, 100... scale it down
    if abs(val) >= 1.0:
        return val / 100
    return val

def normalize_pct(val):
    # 1. Handle Nulls/Nones first
    if val is None or pd.isna(val):
        return np.nan
    
    # 2. Handle Strings (Your new requirement)
    if isinstance(val, str):
        return 0
    
    # 3. Handle Numbers (scaling 50 -> 0.5)
    if abs(val) >= 1.0:
        return val / 100
        
    return val

def normalize_pct(val):
    # 1. Handle Nulls/Nones
    if val is None or pd.isna(val):
        return np.nan
    
    # 2. Handle Strings (Extract numbers like "40% OFF")
    if isinstance(val, str):
        # Find integers or decimals (e.g., "40", "40.5")
        match = re.search(r"(\d+\.?\d*)", val)
        if match:
            val = float(match.group(1))
        else:
            return 0.0 # Or np.nan, depending on your preference
    
    # 3. Handle Numbers (scaling 50 -> 0.5)
    # We use 1.0 as the threshold for 'whole' vs 'decimal'
    if abs(val) >= 1.0:
        return val / 100
        
    return float(val)

def list_to_str(items):
    # Convert each item to string and join with a comma
    return ", ".join(map(str, items))


def list_to_quoted_str(items):
    """Converts [1, 2, 3] to \"'1', '2', '3'\""""
    if not items:
        return ""
    
    # Ensure every item is treated as a string and stripped of whitespace
    return ", ".join([f"'{str(item).strip()}'" for item in items if str(item).strip()])

def list_to_quoted_str_v2(items):
    if not items:
        return ""
    
    # 1. Force to string and remove ALL brackets and existing single/double quotes
    clean_str = str(items).replace('[', '').replace(']', '').replace("'", "").replace('"', "")
    
    # 2. Split by comma
    # 3. Strip whitespace from each piece
    # 4. 'if p' ensures we ignore that annoying trailing comma
    parts = [p.strip() for p in clean_str.split(',') if p.strip()]
    
    # 5. Wrap the clean pieces in single quotes
    return ", ".join([f"'{p}'" for p in parts])

def string_to_list(val):
    if isinstance(val, str) and val.startswith('[') and val.endswith(']'):
        try:
            return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            return val # Return as is if it fails
    return val

def string_to_list_quoted(val):
    if isinstance(val, str) and val.startswith('[') and val.endswith(']'):
        try:
            # 1. Evaluate the string into a real list
            extracted_list = ast.literal_eval(val)
            
            # 2. Convert every item in that list to a string
            if isinstance(extracted_list, list):
                return [str(item).strip() for item in extracted_list]
            return extracted_list
            
        except (ValueError, SyntaxError):
            return val
    return val

def force_list_of_strings(val):
    if pd.isna(val) or val == 'nan':
        return []
    
    try:
        # If it's a string representation of a list: "[1, 2]"
        if isinstance(val, str) and val.strip().startswith('['):
            val = ast.literal_eval(val)
        
        # If it's now a list (or was already a list), convert items to strings
        if isinstance(val, list):
            return [str(item).strip() for item in val]
        
        # If it's a single item, wrap it in a list of string
        return [str(val).strip()]
        
    except (ValueError, SyntaxError):
        return [str(val).strip()]

def merge_xlsx_files(folder_path, output_filename="mega_merge.xlsx"):
    """
    Scans a folder for all .xlsx files and merges them into one.
    """
    path = Path(folder_path)
    
    # 1. Grab all .xlsx files in the directory
    files = list(path.glob("*.xlsx"))
    
    if not files:
        print(f"No Excel files found in {folder_path}")
        return None

    print(f"Found {len(files)} files. Starting merge...")

    # 2. List comprehension to read all files into DataFrames
    # We add a column to track which file the data came from (very helpful for debugging!)
    all_dfs = []
    for f in files:
        try:
            df = pd.read_excel(f)
            df['source_file'] = f.name
            all_dfs.append(df)
        except Exception as e:
            print(f"Could not read {f.name}: {e}")

    # 3. Concatenate all found DataFrames
    if all_dfs:
        mega_df = pd.concat(all_dfs, ignore_index=True, sort=False)
        cols = [c for c in mega_df.columns if c != 'source_file'] + ['source_file']
        mega_df = mega_df[cols]
        mega_df['filled_cols'] = mega_df.drop(columns=['source_file']).count(axis=1)
        # mega_df.to_excel(output_filename, index=False)
        
        # print(f"Saving file to: {os.path.abspath(output_filename)}")
        return mega_df
    
    return None

def get_similar_cols(df, col_name):
    """
    Returns a list of column names that contain the specified string.
    
    Args:
        df (pd.DataFrame): The DataFrame to search.
        col_name (str): The substring to look for in column names.
    """
    # Use list comprehension to filter columns (case-insensitive for better usability)
    return [col for col in df.columns if col_name.lower() in col.lower()]


def subtract_lists(list_1, list_2):
    """
    Returns elements in list_1 that are not present in list_2.
    """
    # Converting list_2 to a set makes the "in" check significantly faster
    items_to_remove = set(list_2)
    
    return [item for item in list_1 if item not in items_to_remove]

def union_lists(list_1, list_2):
    seen = set()
    result = []
    for item in list_1 + list_2:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result

def union_lists_multiple(nested_lists):
    """
    Takes a list of lists and returns a single list with all unique 
    elements preserved in their original order of appearance.
    """
    seen = set()
    result = []
    
    # Iterate through each list in the collection
    for current_list in nested_lists:
        # Iterate through each item in the current list
        for item in current_list:
            if item not in seen:
                result.append(item)
                seen.add(item)
                
    return result

def force_integer_format(val):
    try:
        # 1. Convert to float first (handles '123.0' strings)
        f_val = float(val)
        # 2. Check if it's a NaN or Infinite
        if np.isnan(f_val) or np.isinf(f_val):
            return np.nan
        # 3. Convert to int then string (removes the .0)
        return str(int(f_val))
    except (ValueError, TypeError):
        # 4. If it's "ABC" or None, return NaN
        return np.nan

def force_float_format(val):
    try:
        # 1. Try to convert to float directly
        f_val = float(val)
        
        # 2. Handle NaN and Infinity (return standard NaN)
        if np.isnan(f_val) or np.isinf(f_val):
            return np.nan
            
        return f_val
    except (ValueError, TypeError):
        # 3. If it's a string like "pearl blue", return NaN
        # This cleans the column so DuckDB sees only numbers or nulls
        return np.nan

def force_float_format_v2(val):
    try:
        # 1. Pre-process strings to remove currency and "sticky" spaces
        if isinstance(val, str):
            # Remove \xa0 (non-breaking space), $, commas, and regular whitespace
            # The regex [^\d.-] keeps only digits, dots, and minus signs
            val = re.sub(r'[^\d.-]', '', val.replace('\xa0', ''))
            
            # If the string becomes empty after cleaning, it's not a number
            if val == '': return np.nan

        # 2. Try to convert to float directly
        f_val = float(val)
        
        # 3. Handle NaN and Infinity
        if np.isnan(f_val) or np.isinf(f_val):
            return np.nan
            
        return f_val
        
    except (ValueError, TypeError):
        # 4. If it's "pearl blue" or anything unparseable
        return np.nan

def clean_concat_list(val):
    if pd.isna(val) or val == '':
        return val
    
    # 1. Split by comma
    parts = str(val).split(',')
    
    # 2. Clean each part (strip whitespace/newlines)
    # 3. Use 'set' to remove duplicates
    # 4. Filter out empty strings
    clean_parts = sorted(set(p.strip() for p in parts if p.strip()))
    
    # 5. Join back with a clean separator
    return ", ".join(clean_parts)

def clean_concat_logic(val):
    if pd.isna(val) or val == '' or val == 0:
        return val
    
    # Standardize: convert to string, replace newlines with commas
    val_str = str(val).replace('\n', ',').replace('\r', ',')
    
    # Split, Trim, Remove Empties, and Unique-ify
    parts = val_str.split(',')
    clean_items = sorted(set(p.strip() for p in parts if p.strip()))
    
    return ", ".join(clean_items)

def search_df(df, value, case_sensitive=False):
    """
    Searches for a value in the entire DataFrame and returns 
    the row/column locations where it was found.
    """
    if not case_sensitive and isinstance(value, str):
        # Convert search term to lower
        search_val = value.lower()
        # Create a mask by checking each cell (converted to string and lowered)
        mask = df.map(lambda x: search_val in str(x).lower())
    else:
        # Direct exact match (or sensitive substring)
        mask = df.map(lambda x: str(value) in str(x))

    # Get coordinates where the mask is True
    found = [(df.index[row], df.columns[col], df.iat[row, col]) 
             for row, col in zip(*mask.values.nonzero())]
    
    if not found:
        return "No matches found."
    
    # Return as a helpful summary DataFrame
    return pd.DataFrame(found, columns=['Index', 'Column', 'ActualValue'])

def search_df_like(df, search_term):
    """
    Returns all rows where the search_term exists as a substring 
    in ANY column of the DataFrame.
    """
    search_term = str(search_term)
    
    # Create a boolean mask: check if search_term is in the string version of each cell
    mask = df.apply(lambda row: row.astype(str).str.contains(search_term, regex=False).any(), axis=1)
    
    # Return the subset of the dataframe
    results = df[mask]
    
    if results.empty:
        print(f"No rows found containing: '{search_term}'")
    else:
        print(f"Found {len(results)} row(s) containing: '{search_term}'")
        
    return results

def deep_search_dirty_numbers(df, target):
    """
    Normalizes all cell content by removing special whitespace, 
    currency symbols, and commas, then searches.
    """
    target = str(target)
    
    # 1. Helper to clean a cell's string representation
    def clean_val(val):
        s = str(val)
        # Remove currency, commas, and all types of whitespace (including &nbsp;)
        import re
        return re.sub(r'[^\d.]', '', s)

    # 2. Apply cleaning and check for match
    # We use .map for element-wise operation
    mask = df.map(lambda x: target in clean_val(x))
    
    # 3. Get results
    found = [(df.index[row], df.columns[col], df.iat[row, col]) 
             for row, col in zip(*mask.values.nonzero())]
    
    if not found:
        return "Still nothing. The value might be in a column you don't expect."
    
    return pd.DataFrame(found, columns=['Index', 'Column', 'RawValue'])

def filter_worksheets(val_list):
    if not isinstance(val_list, list):
        return []
    
    return [
        str(x).strip() for x in val_list 
        if str(x).strip().isdigit() and len(str(x).strip()) > 3
    ]

def clean_row_ws(item):
    # Handle NaNs or non-iterable items
    if not isinstance(item, (list, np.ndarray)):
        # If it's a single string, wrap it in a list to process it
        item = [item] if pd.notnull(item) else []
    
    # Apply your logic: strip, check digits, and length
    return [
        str(i).strip() for i in item 
        if str(i).strip().isdigit() and len(str(i).strip()) > 3
    ]

def filter_df_by_col_substring(df, keyword):
    """
    Returns a DataFrame containing only the columns 
    that include the keyword (case-insensitive).
    """
    # Find the matching column names first
    matched_cols = [col for col in df.columns if keyword.lower() in col.lower()]
    
    # Return the filtered DataFrame
    return matched_cols,df[matched_cols]