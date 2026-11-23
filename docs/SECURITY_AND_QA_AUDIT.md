# Comprehensive Security & QA Audit Report: Basista Oil Traders
**Petrol Station Management System (Phase 6 Deliverable)**
**Date:** November 2026  
**Auditor / Engineer:** Senior Software Security Engineer & Django QA Architect  
**Status:** **PASSED / PRODUCTION-READY**

---

## Executive Summary

A comprehensive, end-to-end security review, data integrity audit, server-side authorization enforcement, and automated quality assurance inspection was conducted on the **Basista Oil Traders Petrol Station Management System**.

The audit verified all modules across Phases 1 through 6, identifying potential vulnerabilities, race conditions, authorization gaps, and edge cases. All issues were remediated with defense-in-depth architectural patterns. The test suite now comprises **69 automated test cases**, achieving **100% pass rate** in under 4 seconds.

---

## 1. Authentication Security

### 1.1 Password Hashing & Security Policies
- **Algorithm**: Standard Django PBKDF2 with SHA-256 (600,000 iterations default) and upgrade path to Argon2id.
- **Complexity Validators**: Configured in `config/settings.py`:
  - `UserAttributeSimilarityValidator`
  - `MinimumLengthValidator` (min 8 characters)
  - `CommonPasswordValidator`
  - `NumericPasswordValidator`
- **Session Security**:
  - `SESSION_COOKIE_HTTPONLY = True`: Blocks XSS access to session tokens.
  - `CSRF_COOKIE_HTTPONLY = True`: Protects anti-CSRF tokens.
  - `SESSION_COOKIE_SAMESITE = 'Lax'`: Mitigates Cross-Site Request Forgery.
  - Automatic session flushing on password change via `update_session_auth_hash`.

### 1.2 Brute-Force Rate Limiting & Account Lockout
- **Engine**: Dedicated `LoginAttempt` model in `apps/authentication/security.py`.
- **Thresholds**:
  - **Account Lockout**: 5 consecutive failed login attempts within 15 minutes locks out the target username for 15 minutes.
  - **IP Rate Limit**: 10 failed login attempts within 15 minutes locks out the offending client IP address.
- **Form Integration**: Enforced in `UserLoginForm.clean()` before credential evaluation to prevent password guessing and timing side-channels.
- **Test Coverage**: Tested in `tests/test_phase6_security.py::SecurityAndQATestCase.test_login_rate_limiting_and_lockout`.

### 1.3 Account Deactivation
- Inactive users (`is_active = False`) are blocked at both authentication (`authenticate()`) and session middleware layers.
- Deactivating an employee immediately suspends active sessions and prevents shift assignments.

---

## 2. Server-Side Role-Based Access Control (RBAC)

Authorization is strictly enforced on the server via view decorators and model service methods, completely independent of UI visibility.

### 2.1 Role Matrix & Permissions Enforcement

| Feature / Action | Owner | Manager | Accountant | Cashier | Pump Operator | Enforced By |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Station Legal Info & PAN/VAT** | **YES** | NO | NO | NO | NO | `@owner_required` in `apps/station/views.py` |
| **Audit Trail Logs** | **YES** | NO | NO | NO | NO | `@owner_required` in `apps/audit/views.py` |
| **DB Backup & Restore** | **YES** | NO | NO | NO | NO | CLI command restricted; Superuser/Owner |
| **Create/Promote to Owner** | **YES** | NO | NO | NO | NO | `forms.py` clean check prevents non-owner |
| **Hardware & Tank Setup** | **YES** | **YES** | NO | NO | NO | `@role_required([OWNER, MANAGER])` |
| **Fuel Price Approval** | **YES** | **YES** | NO | NO | NO | `@role_required([OWNER, MANAGER])` |
| **Sales Invoicing (Cash/Credit)** | **YES** | **YES** | **YES** | **YES** | NO | `@role_required([OWNER, MGR, ACCT, CASHIER])` |
| **Customer Credit Collection** | **YES** | **YES** | **YES** | **YES** | NO | `@role_required([OWNER, MGR, ACCT, CASHIER])` |
| **Supplier Payments** | **YES** | **YES** | **YES** | NO | NO | `@role_required([OWNER, MANAGER, ACCOUNTANT])` |
| **Financial Statements / P&L** | **YES** | **YES** | **YES** | NO | NO | `@role_required([OWNER, MANAGER, ACCOUNTANT])` |
| **Cash Transfer between Accounts**| **YES** | **YES** | **YES** | NO | NO | `@role_required([OWNER, MANAGER, ACCOUNTANT])` |
| **Void / Cancel Sales Invoice** | **YES** | **YES** | NO | NO | NO | `@role_required([OWNER, MANAGER])` + Reason |
| **Shift Meter Reading Entry** | **YES** | **YES** | NO | NO | **YES** | Shift assignment authorization |

### 2.2 Privilege Escalation Defense
- Tested that Cashiers and Pump Operators attempting direct HTTP GET/POST to `/reports/financial-statements/` or `/purchases/suppliers/payments/new/` receive `403 Forbidden`.
- Tested that Managers attempting to modify Station Settings (`/station/settings/`) receive `403 Forbidden`.
- Form validation guarantees that non-owners cannot elevate any user to `ROLE_OWNER`.

---

## 3. Transaction Integrity & Concurrency

### 3.1 Meter Reading Consistency
- Monotonic constraint: Closing reading cannot be less than opening reading ($Q = \text{Closing} - \text{Opening} \ge 0$).
- Prevent duplicate nozzle readings per shift using database unique constraint:
  `UniqueConstraint(fields=['shift', 'nozzle'], name='unique_nozzle_reading_per_shift')`.
- Meter rollover / calibration reset requires explicit managerial authorization and records an audit log entry.

### 3.2 Inventory Ledger Movements
- Every stock change is backed by an atomic `StockMovement` entry:
  - `PURCHASE`: Tank capacity validation prevents overflow.
  - `SALE`: Depletes tank inventory atomically.
  - `ADJUSTMENT`: Requires managerial reason and audit event.
  - `REVERSAL`: Reverse movement on sales cancellation.
- All inventory updates utilize Django's `transaction.atomic()` combined with `select_for_update()` to prevent race conditions during high-concurrency pump dispensing.

### 3.3 Duplicate Sales & Purchase Prevention
- Fuel Purchases: Unique constraint `UniqueConstraint(fields=['supplier', 'invoice_number'], name='unique_supplier_invoice')` prevents duplicate supplier billing.
- Sales Invoices: Consecutive, auto-generated sequence numbers per financial year.

### 3.4 Double-Entry Balanced Ledger Guarantee
- Every financial transaction automatically posts balancing journal vouchers via `create_journal_voucher()`:
  $$\sum \text{Debit} \equiv \sum \text{Credit}$$
- Model validation raises `ValidationError` if total debits do not equal total credits.

---

## 4. Immutable Audit System (`apps/audit`)

### 4.1 Architecture
- **Model**: `AuditLog`
  - `user`: User responsible (or NULL for system background tasks).
  - `action`: `CREATE`, `UPDATE`, `DELETE`, `APPROVE`, `CANCEL`, `PRICE_CHANGE`, `ADJUSTMENT`, `BACKUP`, `RESTORE`.
  - `timestamp`: UTC creation timestamp (`auto_now_add=True`).
  - `model_name` & `object_id`: Target entity identifier.
  - `previous_values` & `new_values`: JSON snapshots of mutated data.
  - `reason`: Mandatory justification for adjustments or cancellations.
  - `ip_address`: Captured client IP.

### 4.2 Tamper Evident & Append-Only Enforcement
- **Save Override**: `AuditLog.save()` rejects any update to an existing record with `ValidationError("AuditLog records are append-only and cannot be modified.")`.
- **Delete Override**: `AuditLog.delete()` blocks record removal with `ValidationError("AuditLog records cannot be deleted.")`.
- **Admin & UI Access**: Only users with `ROLE_OWNER` can view audit trails; the Django admin marks all fields as `readonly` and disables delete permissions.

---

## 5. Automated Backup & Disaster Recovery

### 5.1 Command Specifications
1. **Backup Command**: `python manage.py backup_database`
   - Supports native PostgreSQL `pg_dump` format and portable compressed JSON format (`.json.gz`).
   - Computes SHA-256 checksum and writes atomic `.manifest.json`.
   - Supports `--offsite-dir` replication.
   - Enforces backup retention policies via `--keep-days` (default 30 days).
   - Records an immutable `BACKUP` event in `AuditLog`.
2. **Restore Command**: `python manage.py restore_database --backup-file <path> --confirm`
   - Verifies SHA-256 integrity against `.manifest.json` before restoring.
   - Requires explicit `--confirm` flag to prevent accidental execution.
   - Records an immutable `RESTORE` event in `AuditLog`.

### 5.2 Verification
- Successfully tested backup generation, SHA-256 hashing, manifest verification, and automated restoration within the test suite (`test_backup_and_restore_cycle`).
- Complete disaster recovery runbook available at `docs/BACKUP_AND_RECOVERY.md`.

---

## 6. Automated Test Suite Results

The comprehensive test suite covers all application domains:

```
Ran 69 tests in 3.578s
OK
```

### Breakdown of Passing Tests:
- `tests/test_phase1_models.py` (10 tests): User roles, fuel types, tanks, pumps, nozzles, shifts, sales, double-entry vouchers.
- `tests/test_phase2_bilingual.py` (9 tests): Nepali date conversions, BS month filtering, translations, station settings, price revisions.
- `tests/test_phase3_operations.py` (11 tests): Shift opening/closing, meter calculations, stock ledgers, manual sales, sales cancellation.
- `tests/test_phase4_accounts.py` (10 tests): Suppliers, purchases, expenses, customer credit limits, cash ledger, double-entry equality.
- `tests/test_phase5_reporting.py` (19 tests): Dashboard KPIs, shift summaries, stock reconciliations, P&L generation, Excel/PDF exports.
- `tests/test_phase6_security.py` (10 tests): Brute force lockout, RBAC server enforcement, audit log immutability, backup & restore integrity, duplicate invoice protection.

---

## 7. UX & Interface Verification

- **Sidebar Scrolling Bug Fixed**: Restructured `templates/components/sidebar.html` and `templates/base.html` using flexbox containers (`flex-1 min-h-0 overflow-y-auto custom-scrollbar`) with pinned header and user profile footer. Tested scrolling with multi-item menus.
- **Bilingual Coverage**: 667 translated entries compiled into `locale/ne/LC_MESSAGES/django.mo`. Devanagari typography rendered with Noto Sans Devanagari.
- **Dual Calendar**: Gregorian (AD) and Bikram Sambat (BS) displayed across all screens and report exports.

---

## 8. Conclusion & Sign-Off

The **Basista Oil Traders Petrol Station Management System** complies with all security, authorization, data integrity, and operational requirements. All business controls and audit trails are verified and ready for production deployment.
