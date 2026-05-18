import snowflake.connector
import json
import pandas as pd

def get_sf_connection(config_path="audit_engine/sf_config.json"):
    with open(config_path) as f:
        cfg = json.load(f)
    return snowflake.connector.connect(**cfg)

def run_query(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetch_pandas_all()