# BuyOpsAudit

An automated, end-to-end audit and data reconciliation engine built for the Merchandising and Buying Operations teams. 

## Overview
`BuyOpsAudit` is a Python-based data verification pipeline designed to eliminate manual compliance checks. The tool bridges operational workflows in **Freshservice** and financial/transactional records in **Snowflake**, executing 50+ rigorous validation checkpoints (matching items, dates, amounts, and metadata) to ensure absolute data integrity.

## Key Features
* **Freshservice ETL Pipeline:** Connects via REST API to systematically download targeted tickets, extract core metrics, isolate attachments, and clean the data into structured Pandas DataFrames.
* **Snowflake Data Warehousing:** Query and pull vendor and product purchase records matching the active ticket backlog.
* **50+ Check Audit Engine:** Executes a massive suite of automated validation tests across matching item IDs, transaction timelines, financial amounts, and contract specifics.
* **Comprehensive Multi-Sheet Reporting:** 
  * Generates a primary **Summary Sheet** featuring high-level compliance metrics and an overall data health score.
  * Exports **5 Raw Data Sheets** containing granular breakdown records.
  * Outputs a specialized **Exception Report** detailing specific formatting and document failures for attachments that failed validation.

## Architecture & Data Flow
1. **Ingest:** Extract ticket payload and files from Freshservice API.
2. **Transform:** Clean, parse, and normalize data payloads into DataFrames.
3. **Fetch:** Retrieve source-of-truth transactional data from Snowflake.
4. **Reconcile:** Run the 50-point matrix audit engine.
5. **Output:** Generate detailed Excel workbooks for the end-user.

## Tech Stack
* **Language:** Python 3.x
* **Data Libraries:** Pandas, NumPy
* **Integrations:** Freshservice REST API, Snowflake Connector for Python
* **Reporting:** OpenPyXL / XlsxWriter

## Getting Started

### Prerequisites
Ensure you have a `.env` file in the root directory containing your secure credentials (never commit this file to GitHub):
```env
FRESHSERVICE_API_KEY=your_key_here
FRESHSERVICE_DOMAIN=your_domain.freshservice.com
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=your_account
