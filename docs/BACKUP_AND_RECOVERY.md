# Database Backup, Disaster Recovery & Retention Policy

**Petrol Station Management System (Basista Oil Traders, Nepal)**  
**Version:** 1.0 (Phase 6 Production Release)  
**Security Classification:** Confidential / Financial Ledger  

---

## 1. Overview & Objectives

The petroleum station operates 7 days a week, processing high-volume retail transactions (Petrol MS & Diesel HSD), tank dip measurements, credit invoicing, and double-entry accounting journals. Data loss or corruption risks fuel theft, tax penalties with the Inland Revenue Department (IRD), and reconciliation failures with the Nepal Oil Corporation (NOC).

This backup and disaster recovery framework guarantees:
- **Zero Financial Transaction Loss**: Continuous ledger immutability and atomic row locking.
- **RPO (Recovery Point Objective)**: < 12 hours (automated twice-daily snapshots) or real-time WAL shipping in full PostgreSQL production.
- **RTO (Recovery Time Objective)**: < 15 minutes to fully restore station operations from cold storage.
- **Cryptographic Integrity**: SHA-256 manifest verification on every backup snapshot before and after transmission.

---

## 2. Backup Architecture

```
                          ┌────────────────────────────────┐
                          │   PostgreSQL / Station DB      │
                          └──────────────┬─────────────────┘
                                         │
                             [python manage.py backup_database]
                                         │
                 ┌───────────────────────┴────────────────────────┐
                 ▼                                                ▼
     ┌───────────────────────┐                        ┌───────────────────────┐
     │  Local On-Site Backup │                        │   Off-Site Secondary   │
     │  (backups/local/)     │                        │   (backups/offsite/)  │
     │  - Compressed archive │                        │   - Replicated copy   │
     │  - SHA-256 Manifest   │                        │   - Isolated partition│
     └───────────────────────┘                        └───────────────────────┘
```

### Supported Formats
1. **PostgreSQL Native Archive (`sql_gz`)**: Generates compressed SQL dumps using `pg_dump --clean --if-exists` for high-speed restoration.
2. **Portable Django Fixture (`json_gz`)**: Generates compressed, database-agnostic JSON representations with natural foreign keys, enabling seamless cross-engine migration and offline disaster recovery.

---

## 3. Automated Backup Command

To generate an immediate verified backup snapshot:

```bash
# Standard backup with default offsite replication and SHA-256 verification
./venv/bin/python manage.py backup_database

# Custom directories and retention period
./venv/bin/python manage.py backup_database \
    --output-dir=/var/backups/petrol_station/local \
    --offsite-dir=/mnt/nas_storage/petrol_station/offsite \
    --keep-days=14 \
    --format=auto
```

### What Happens During Backup Execution:
1. Database engine is detected (`postgresql` or development `sqlite3`).
2. An atomic snapshot is taken and compressed using Gzip.
3. Cryptographic SHA-256 checksum is computed.
4. JSON metadata manifest is created alongside the archive (`.manifest.json`).
5. Replicated to the secondary off-site directory.
6. Retention policy pruning purges expired backups beyond `--keep-days`.
7. An immutable security audit log entry (`BACKUP`) is logged to the system audit trail.

---

## 4. Production Cron Automation (`crontab`)

On Linux production hosts (Nginx + Gunicorn), configure automated twice-daily snapshots at the end of each shift (e.g. 14:00 and 22:00 NPT):

```cron
# Edit crontab
crontab -e

# Run automated backup at 14:15 and 22:15 daily
15 14,22 * * * /home/aakash/Documents/Basista\ Oil\ Traders/venv/bin/python /home/aakash/Documents/Basista\ Oil\ Traders/manage.py backup_database >> /var/log/petrol_backup.log 2>&1
```

---

## 5. Restoration & Disaster Recovery Procedure

### Step 1: Identify Backup & Verify Checksum
Every backup archive possesses a corresponding `.manifest.json` file containing:
- ISO-8601 generation timestamp
- SHA-256 hash
- Size in bytes
- Target database engine and station details

### Step 2: Execute Restore Command
```bash
./venv/bin/python manage.py restore_database \
    --backup-file=backups/local/db_backup_YYYYMMDD_HHMMSS.json.gz \
    --confirm
```

> [!CAUTION]
> The `--confirm` flag is mandatory. Restoration will overwrite existing tables with data from the backup archive.

### Verification Steps Post-Restore:
1. Verify station login with Owner credentials.
2. Check Storage Tank physical stock against dip records on the dashboard.
3. Verify that Trial Balance debits equal credits (`/reports/financial/?tab=trial_balance`).
4. Inspect the Audit Trail (`/audit/`) to confirm the `RESTORE` audit event.

---

## 6. Retention Policy

| Archive Tier | Frequency | Retention Window | Storage Location |
|---|---|---|---|
| **Shift / Daily** | 2x Daily | 7 Days | Local SSD + Offsite mount |
| **Weekly Snapshot** | Sundays | 4 Weeks | Offsite NAS / Cloud Object Storage |
| **Monthly Financial Close** | Month End | 12 Months (Fiscal Year) | Offsite Archive & Cold Storage |
