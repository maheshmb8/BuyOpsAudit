import requests
import json
import mimetypes
import os
import time
from jsonpath_ng.ext import parse
from . import config
from .config import BASE_URL, auth, fresh_headers, down_path, API_CALL_LIMIT
from .utils import normalize_date
import concurrent.futures
from tqdm.auto import tqdm
import threading

download_lock = threading.Lock()
request_counter = 0

def get_tickets_created_after(date_str, per_page=100):
    date_str = normalize_date(date_str)

    all_tickets = []
    page = 1

    # ⚠️ IMPORTANT: wrap query in DOUBLE QUOTES
    query = f"\"created_at:>'{date_str}'\""

    while True:
        params = {
            "query": query,
            "page": page,
            "per_page": per_page
        }

        r = requests.get(
            f"{BASE_URL}/tickets/filter",
            auth=auth,
            headers=fresh_headers,
            params=params
        )
        r.raise_for_status()

        tickets = r.json().get("tickets", [])
        if not tickets:
            break

        all_tickets.extend(tickets)
        page += 1

    return all_tickets

def get_tickets_between_dates(start_date, end_date, per_page=100):
    """
    Fetch Freshservice tickets created between two dates (exclusive).

    Parameters
    ----------
    start_date : str
        Start date/time. Accepted formats:
        - YYYY-MM-DD
        - YYYY-MM-DDTHH:MM:SSZ   (UTC only)

    end_date : str
        End date/time (same accepted formats as start_date).

    per_page : int, optional
        Number of tickets fetched per API call (max 100).
        Default is 100.

    limit : int or None, optional
        Maximum number of tickets to return.
        - None (default): return all matching tickets
        - N: stop after N tickets

    Returns
    -------
    list[dict]
        List of Freshservice ticket objects.
        Each ticket is a dict as returned by the Freshservice API.
    """
    start = normalize_date(start_date)
    end = normalize_date(end_date)

    all_tickets = []
    page = 1

    # ⚠️ Entire query must be inside DOUBLE QUOTES
    query = f"\"created_at:>'{start}' AND created_at:<'{end}'\""

    while True:
        params = {
            "query": query,
            "page": page,
            "per_page": per_page
        }

        r = requests.get(
            f"{BASE_URL}/tickets/filter",
            auth=auth,
            headers=fresh_headers,
            params=params
        )
        r.raise_for_status()

        tickets = r.json().get("tickets", [])
        if not tickets:
            break

        all_tickets.extend(tickets)
        page += 1

    return all_tickets

def save_or_load_tickets(tickets=None, ts_prefix=None, filename=None, mode="save"):
    """
    Save tickets to JSON (auto filename) or load tickets from JSON (explicit filename).

    SAVE mode:
        filename = f"tickets_{ts_prefix}.json"

    LOAD mode:
        filename must be provided

    Parameters
    ----------
    tickets : list[dict] or None
        Tickets list to save (required for save).

    ts_prefix : str or None
        Timestamp prefix (required for save).

    filename : str or None
        JSON filename (required for load).

    mode : str
        "save" or "load"

    Returns
    -------
    list[dict] or None
    """

    if mode == "save":
        if tickets is None or ts_prefix is None:
            raise ValueError("tickets and ts_prefix are required in save mode")
        if filename is None:
            filename = f"tickets_{ts_prefix}.json"
            print(filename)
        if filename is not None and not filename.endswith('.json'):
            filename += '.json'

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(tickets, f, indent=2, default=str)

        return None

    elif mode == "load":
        if filename is None:
            raise ValueError("filename is required in load mode")

        if not os.path.exists(filename):
            raise FileNotFoundError(f"{filename} not found")

        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    else:
        raise ValueError("mode must be 'save' or 'load'")

def get_tickets(page=1, per_page=30):
    url = f"{BASE_URL}/tickets"
    params = {"page": page, "per_page": per_page}

    r = requests.get(url, auth=auth, headers=fresh_headers, params=params)
    r.raise_for_status()
    return r.json()


def view_ticket(ticket_id, requested_items=True):
    """
    Fetch a Freshservice ticket by ID.

    Parameters
    ----------
    ticket_id : int or str
        Freshservice ticket ID.

    requested_items : bool, optional
        - False (default): fetch ticket details
          GET /api/v2/tickets/{id}
        - True: fetch requested items for the ticket
          GET /api/v2/tickets/{id}/requested_items

    Returns
    -------
    dict
        API response payload.
        - If requested_items=False → ticket object
        - If requested_items=True  → requested items data
    """
    suffix = "/requested_items" if requested_items else ""
    url = f"{BASE_URL}/tickets/{ticket_id}{suffix}"

    r = requests.get(
        url,
        auth=auth,
        headers=fresh_headers
    )
    r.raise_for_status()

    data = r.json()

    # Normalize return for convenience
    if requested_items:
        return data.get("requested_items", data)
    return data.get("ticket", data)


def view_ticket2(ticket_id, requested_items=True, include_conversations=False):
    """
    Fetch a Freshservice ticket by ID with optional extras.

    Parameters
    ----------
    ticket_id : int or str
        Freshservice ticket ID.
    requested_items : bool, optional
        If True, fetches the requested items endpoint.
    include_conversations : bool, optional
        If True, appends the include=conversations query param (costs 2 API calls).
    """
    # 1. Determine the base path
    suffix = "/requested_items" if requested_items else ""
    url = f"{BASE_URL}/tickets/{ticket_id}{suffix}"

    # 2. Handle query parameters (only valid for the main ticket endpoint)
    params = {}
    if include_conversations and not requested_items:
        params["include"] = "conversations"

    r = requests.get(
        url,
        auth=auth,
        headers=fresh_headers,
        params=params
    )
    r.raise_for_status()
    data = r.json()

    # 3. Normalize return
    if requested_items:
        return data.get("requested_items", data)
    
    return data.get("ticket", data)


def download_attachment_by_id(attachment_id, filename):
    """
    Download a Freshservice attachment by ID and save it locally.

    Parameters
    ----------
    attachment_id : int or str
        Freshservice attachment ID

    filename : str
        Filename to save as (include extension, e.g. 'file.xlsx')

    Returns
    -------
    str
        Full path of the saved file
    """
    url = f"{BASE_URL}/attachments/{attachment_id}"
    save_path = os.path.join(config.down_path, filename)

    r = requests.get(url, auth=auth, stream=True)
    r.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return save_path

def download_attachment_by_id_v2(attachment_id, filename_base,allowed_exts=None):
    """
    Download a Freshservice attachment by ID and save it locally.
    File extension is inferred automatically from Content-Type.
    """
    if allowed_exts is None:
        allowed_exts = ['.xlsx', '.csv', '.xls']
    allowed_exts = {f".{e.lower().lstrip('.')}" for e in allowed_exts}
    url = f"{BASE_URL}/attachments/{attachment_id}"

    r = requests.get(url, auth=auth, stream=True)
    r.raise_for_status()

    # Infer extension from Content-Type
    content_type = r.headers.get("Content-Type", "").split(";")[0]
    ext = mimetypes.guess_extension(content_type) or ""

    if ext.lower() not in allowed_exts:
        return None

    filename = f"{filename_base}{ext}"
    save_path = os.path.join(config.down_path, filename)

    with open(save_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return save_path

def bulk_download_attachments(tasks, max_workers=5):
    """
    Downloads multiple attachments in parallel with a progress bar.
    """
    def _worker(task):
        can_id, uk = task
        try:
            download_attachment_by_id_v2(can_id, uk)
            return True
        except Exception:
            return False

    print(f"Initiating parallel download with {max_workers} workers...")
    
    # Use tqdm to track the completion of tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # We use list() around tqdm to force the generator to execute
        results = list(tqdm(executor.map(_worker, tasks), total=len(tasks), desc="Downloading"))
    
    success_count = results.count(True)
    print(f"\nBulk download complete. Success: {success_count}/{len(tasks)}")
    return results

def bulk_download_attachments_v2(tasks, max_workers=5):
    global request_counter
    request_counter = 0 # Reset for new bulk job

    def _worker(task):
        global request_counter
        can_id, uk = task
        
        # --- Rate Limiting Logic ---
        with download_lock:
            request_counter += 1
            if request_counter % 105 == 0:
                print(f"\n[Rate Limit] Reached {request_counter} requests. Sleeping for 65s...",end="\r")
                time.sleep(65)
        # ---------------------------

        try:
            download_attachment_by_id_v2(can_id, uk)
            return True
        except Exception:
            return False

    print(f"Initiating parallel download with {max_workers} workers...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(tqdm(executor.map(_worker, tasks), total=len(tasks), desc="Downloading"))
    
    return results