# User Acceptance Testing (UAT) Scenarios & Test Scripts

**Petrol Station Management System (Basista Oil Traders, Nepal)**  
**Version:** 1.0 (Phase 6 Final Verification)  
**Timezone:** Asia/Kathmandu (NPT) | **Calendar:** Dual Bikram Sambat (BS) & Gregorian (AD)  

---

## 1. Role-Based User Profiles

| Role | Test Username | Primary Responsibilities & Permitted Scope | Restricted Boundaries |
|---|---|---|---|
| **Station Owner** | `owner_test` | Executive oversight, user management, station legal config, price approval, full financial P&L, system audit trail, database backup/restore. | None (Supreme station authority). |
| **Station Manager** | `manager_test` | Shift opening/closing, fuel deliveries receipt, tank dip reconciliation, employee duty assignments, manual sales entry, voucher approvals. | Cannot deactivate users, change PAN/VAT or view system audit logs. |
| **Accountant** | `accountant_test` | Double-entry journals, chart of accounts, P&L, balance sheet, trial balance, customer credit statements, supplier payments, tax reconciliation. | Cannot modify pumps, nozzles, storage tanks, or alter operational shifts. |
| **Cashier** | `cashier_test` | Shift cash float counting, cash fuel receipts, customer credit collection, daily expenses entry, bank slip recording. | Cannot void sales without manager authorization, cannot view accounting journals. |
| **Pump Operator** | `operator_test` | Mechanical & electronic nozzle meter logging, direct fuel dispensing (MS & HSD), shift cash handover. | Strictly blocked from all accounting, financial reports, user management, and price changes. |

---

## 2. Test Scenarios by Role

### Scenario A: Station Owner
- **UAT-A1: Executive Dashboard & Live Financial Metrics**
  - *Steps*: Sign in as `owner_test`. Navigate to `/dashboard/`.
  - *Expected Result*: View real-time sales strips (MS vs HSD), cash drawer balance, customer credit balance, underground tank fill gauges with visual low-stock alerts, and 7 Chart.js analytics charts.
- **UAT-A2: Staff Management & Account Status**
  - *Steps*: Navigate to `/auth/users/`. Deactivate a resigned employee.
  - *Expected Result*: Account is immediately marked inactive; user is blocked from logging in. Action is recorded in audit ledger.
- **UAT-A3: Security Audit Trail Inspection**
  - *Steps*: Navigate to `/audit/`.
  - *Expected Result*: View tamper-evident log of all price changes, sales voids, meter rollovers, stock adjustments, and failed login attempts. Attempting to edit or delete any audit entry via admin or shell raises `ValidationError`.

---

### Scenario B: Station Manager
- **UAT-B1: Shift Opening & Float Allocation**
  - *Steps*: Navigate to `/operations/shifts/open/`. Enter opening cash float (NPR 10,000.00), select morning shift schedule, and assign operators.
  - *Expected Result*: Shift session activates (`OPEN`); date is converted to current Bikram Sambat automatically; Cash Book logs opening float.
- **UAT-B2: Tanker Delivery Receipt & Fuel Inward**
  - *Steps*: Navigate to `/purchases/orders/new/`. Enter NOC challan details, select Petrol (MS) and receiving tank T-1 (capacity check). Submit and approve.
  - *Expected Result*: Tank capacity validation prevents overflow; physical stock is atomically increased with `select_for_update()` row locking; double-entry journal (Dr Inventory, Cr Accounts Payable) posts automatically.
- **UAT-B3: Audited Sales Cancellation (Void)**
  - *Steps*: Navigate to a disputed sales invoice. Select Void Transaction. Enter mandatory justification note.
  - *Expected Result*: Invoice is marked voided; fuel quantity is restored to the underground tank via `SALE_REVERSAL`; audit event is logged.

---

### Scenario C: Station Accountant
- **UAT-C1: Double-Entry Balancing & Chart of Accounts**
  - *Steps*: Navigate to `/accounting/coa/` and `/accounting/journal/`.
  - *Expected Result*: All 5 account classifications (Asset, Liability, Equity, Revenue, Expense) are categorized. Every journal entry has balanced Debits and Credits ($\sum \text{Dr} = \sum \text{Cr}$).
- **UAT-C2: Profit & Loss Statement (Income Statement)**
  - *Steps*: Navigate to `/reports/financial/?tab=pnl`.
  - *Expected Result*: Fuel sales revenue minus Cost of Goods Sold (COGS derived from purchases and inventory movements) yields Gross Operating Profit. Less operating expenses yields Net Operating Profit.
- **UAT-C3: Customer Credit Account Reconciliation**
  - *Steps*: Navigate to `/customers/`. Inspect credit customer statement. Record payment.
  - *Expected Result*: Outstanding credit balance updates immediately; Cash Book or Bank ledger debited, Accounts Receivable credited.

---

### Scenario D: Cashier
- **UAT-D1: Shift Handover & Cash Reconciliation**
  - *Steps*: Navigate to `/operations/shifts/<id>/close/`. Input physical cash counted in drawer at shift end.
  - *Expected Result*: System calculates Expected Cash = (Opening Cash + Cash Sales). Discrepancy is calculated automatically (`cash_difference`).
- **UAT-D2: Operating Expense Voucher Registration**
  - *Steps*: Navigate to `/expenses/new/`. Record tea/stationery expense of NPR 450.00.
  - *Expected Result*: Generates sequential expense voucher `EXP-YYYY-XXXXX`, records Cash Book outflow, and posts operating expense journal.

---

### Scenario E: Pump Operator
- **UAT-E1: Dispenser Nozzle Closing Meter Entry**
  - *Steps*: Sign in as `operator_test`. Navigate to `/operations/meter-readings/new/`. Input closing reading.
  - *Expected Result*: Dispensed litres = (Closing - Opening). Closing reading less than opening is rejected unless authorized as rollover.
- **UAT-E2: RBAC Server-Side Restriction Enforcement**
  - *Steps*: Attempt to access `/reports/financial/`, `/accounting/coa/`, or `/purchases/suppliers/new/`.
  - *Expected Result*: Server rejects request with redirect and error message: *"You do not have permission to access this resource."* Access is strictly blocked on the backend.
