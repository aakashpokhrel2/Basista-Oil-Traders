# Administrator Manual
**Petrol Station Management System: Administrative Governance & Management Operations**
**Station Dealer: Basista Oil Traders (बसिस्ट आयल ट्रेडर्स)**

---

## 1. System Roles and Access Governance

The system enforces a 5-tier role-based access control (RBAC) model:

| Role | Intended User | Permissions & Scope |
| :--- | :--- | :--- |
| **OWNER** | Station Owner / Proprietor | Sole authority to modify legal settings, PAN/VAT, view immutable Audit Logs, perform database backups/restores, and create/promote Owner accounts. |
| **MANAGER** | Station Manager | Operational management, shift schedule approval, fuel purchase registration, price revisions, sales voiding with documented reason, and stock adjustments. |
| **ACCOUNTANT**| Chief Accountant | Double-entry journal vouchers, supplier payment processing, expense recording, bank account transfers, and financial statements (P&L, Balance Sheet). |
| **CASHIER** | Front-desk Cashier | Customer billing, cash/credit fuel sales recording, and customer credit collections. Blocked from altering approved entries. |
| **PUMP OPERATOR** | Dispenser Operator | Shift opening and closing meter reading submissions, physical cash handover. Blocked from all financial back-office functions. |

---

## 2. Station Profile & Legal Settings

1. Navigate to **Station Settings** (Only accessible by `ROLE_OWNER`).
2. Manage official legal records:
   - Station Name in English and Nepali Devanagari.
   - Physical Address & Municipality ward.
   - Contact numbers and official email.
   - Inland Revenue Department (IRD) PAN/VAT registration number (`601234567`).
   - Fiscal Year calendar mapping.

---

## 3. Storage Tanks & Dispenser Equipment Management

### Storage Tanks
- Navigate to **Tanks & Fuel Configuration**.
- Underground tanks (`T-1` Petrol 15,000 L, `T-2` Diesel 20,000 L).
- Live stock gauge displays fill percentage, available capacity, and minimum reorder alert levels.
- System strictly prevents assigning a fuel type incompatible with the tank's certified designation.

### Dispensing Pumps and Nozzles
- Supports multi-nozzle electronic dispensers.
- Each nozzle is bound to a specific underground tank and fuel product.
- Maintains electronic cumulative totalizer counter to ensure total sales match nozzle meter movements.

---

## 4. Fuel Price Management (NOC Price Circulars)

1. Navigate to **Fuel Pricing**.
2. Click **New Price Revision**:
   - Select Fuel Type (Petrol or Diesel).
   - Enter NOC Purchase Rate per Liter (NPR).
   - Enter Retail Selling Rate per Liter (NPR).
   - The system automatically calculates the dealer gross margin.
   - Set Effective Date & Time.
3. Review and click **Approve Revision**.
4. Effective price is immediately active for all subsequent sales while preserving historical price records for previous transactions.

---

## 5. Shift Approval & Reconciliation

1. Operators submit opening and closing meter readings and cash collection upon shift completion.
2. Manager reviews the **Shift Summary**:
   - Total liters dispensed per nozzle ($Q = \text{Closing} - \text{Opening}$).
   - System sales amount vs Physical cash handed over.
   - Cash discrepancy variance (Over / Short).
3. Manager clicks **Approve Shift**.
   - Generates automated double-entry accounting vouchers.
   - Finalizes stock movement ledger.

---

## 6. Audit Trail Monitoring

1. Navigate to **Audit Trail** in the sidebar (Owner-only).
2. Review append-only audit events:
   - User identity, IP address, and timestamp.
   - Action type (`CREATE`, `UPDATE`, `APPROVE`, `CANCEL`, `PRICE_CHANGE`, `ADJUSTMENT`).
   - Target model and record ID.
   - Pre-mutation vs post-mutation JSON state diff.
   - Mandatory reason provided by the staff member.
3. Audit log entries are strictly immutable and cannot be edited or deleted by any user or administrator.
