# audit_engine/__init__.py

# 1. Database functions (ae.get_sf_connection)
from .db_logic import get_sf_connection, run_query 

# 2. API functions (ae.get_tickets_between_dates)
from .fs_api import get_tickets_between_dates, view_ticket,bulk_download_attachments_v2,save_or_load_tickets

# 3. Core Brain functions (ae.extract_pricechange_vars)
from .core import extract_pricechange_vars, build_price_change_df,process_tickets_parallel, API_CALL_COUNT,summary_txt_builder_v2

from .sql_queries import pcdf_q,fs_attach_merge_q,sql_query_1,sql_merge,fs_attach_sql_merge_q,audit_sql_1,audit_sql_2,audit_sql_3,audit_sql_4,fs_attach_sql_pcw_cs_merge_q

# from .config import attachment_path,sql_path,price_change_df_col_order,price_change_df_rename_dict,mkdown_dict,down_path,COL_MAP,REQUIRED_SETS,SKU_COL_SETS,sql_query_1,markdown_list12,regular_pcw
# from .config import *

from . import core  # <--- Add this line to expose the live module
from . import utils
from . import config
from . import fs_api
from . import sql_queries
from . import config
from . import db_logic