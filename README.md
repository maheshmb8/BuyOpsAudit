# 🚀 BuyOpsAudit

> **Automated End-to-End Audit & Data Reconciliation Engine** Built Exclusively for Merchandising & Buying Operations Teams.

---

## 📋 Overview
`BuyOpsAudit` is an enterprise-grade Python data verification pipeline engineered to eliminate manual compliance overhead. The system serves as an automated, high-speed bridge between operational ticketing workflows in **Freshservice** and financial/transactional truth records in **Snowflake**. 

By executing an exhaustive **50+ matrix validation checkpoint suite**, it programmatically cross-checks items, timelines, amounts, and attachment metadata to guarantee absolute data integrity.

---

## ✨ Key Features

* 📥 **Freshservice ETL Pipeline:** Seamlessly connects via REST API to download targeted backlogs, extract core metadata, isolate multi-format attachments, and normalize data streams into high-performance Pandas DataFrames.
* ❄️ **Snowflake Data Infrastructure:** Runs dynamic relational query wrappers to automatically fetch corresponding live vendor, product, and purchase records matching the in-flight ticket backlog.
* 🛡️ **50+ Check Deep Audit Engine:** Operates a massive validation matrix testing against item IDs, complex transaction timelines, financial amounts, and distinct contract parameters.
* 📊 **Executive Multi-Sheet Reporting:** * 👑 **Summary Scorecard:** A color-coded dashboard outlining critical compliance tracking metrics and an overall operational data health score.
  * 🗄️ **5 Raw Data Sheets:** Granular, deep-dive data dumps partitioned for advanced troubleshooting.
  * ⚠️ **Exception Tracking Log:** A dedicated fallout report mapping out exact document layout and structural formatting failures within failed attachments.

---

## 📐 Architecture & Data Flow

```text
  [Freshservice API] ──► Ingestion Module ──► Dynamic Schema Mapping (COL_MAP)
                                                   │
  [Snowflake DW]     ──► DB Query Engine  ──► Pandas & DuckDB Core Analytics
                                                   │
  [Automated Audit]  ◄── Multi-Layer Matrix Matrix Verification (50+ Rules)
         │
         └───► Excel Engine (Summary Scorecard, Exception Log, 5 Raw Data Dumps)
