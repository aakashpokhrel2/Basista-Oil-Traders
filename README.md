# Bilingual Petrol Station Management System (Nepal)
## Phase 1 & 2: Station Configuration, Tanks, Pumps, Nozzles & Fuel Pricing

A production-ready Petrol Station Management System designed for petroleum dealership operations in Nepal (Basista Oil Traders).

---

### Features Implemented

#### Phase 1: Setup, Database, Authentication & RBAC
1. **Modular Architecture**:
   - `config/`: Project configuration, environment-driven database & i18n settings.
   - `apps/authentication/`: Custom `User` model, role-based access control (RBAC), login/logout, password change/reset, staff management.
   - `apps/dashboard/`: Station operations dashboard with dual calendar metrics and phase roadmap.
   - `common/`: Verified Gregorian (AD) to Bikram Sambat (BS) date conversion, Devanagari numerals, NPR currency formatting, decorators, mixins.
   - `templates/`: Clean, accessible Tailwind CSS templates with green-and-white petrol station theme.
   - `locale/`: Bilingual translation catalog (`en` and `ne` - Nepali Devanagari) with 199 pre-compiled `.mo` entries.

2. **5 Operational Roles (RBAC)**:
   - **Owner / Administrator** (`OWNER`): Full access to users, settings, fuel pricing, and audits.
   - **Manager** (`MANAGER`): Operational oversight, fuel prices, inventory, and staff administration.
   - **Accountant** (`ACCOUNTANT`): Financial transactions, credit ledger, and expenses.
   - **Cashier** (`CASHIER`): Daily sales entry and cash collection.
   - **Pump Operator** (`PUMP_OPERATOR`): Meter reading entries and shift duties.

#### Phase 2: Bilingual Interface & Station Configuration
1. **Station Settings (Singleton `StationConfiguration`)**:
   - Station name & address (bilingual EN/NE).
   - Phone, official email, IRD PAN/VAT registration (`601234567`).
   - Currency (`NPR`), Timezone (`Asia/Kathmandu`), Fiscal Year (`2083/84`).
   - Station logo upload.

2. **Fuel Configuration (`FuelType`)**:
   - Pre-configured Petrol (`MS`) and Diesel (`HSD`).
   - Units, color indicators, badge styles, and active status toggle.

3. **Storage Tanks (`StorageTank`)**:
   - Underground tanks (`T-1` Petrol 15,000 L, `T-2` Diesel 20,000 L).
   - Real-time stock fill level percentage gauges.
   - Strict validation: opening stock and current stock cannot exceed maximum tank capacity.
   - Low-stock safety alerts when level drops below re-order threshold.

4. **Dispensing Pumps & Nozzles (`Pump` & `Nozzle`)**:
   - Dispensing Pump 1 and Pump 2 (Dual electronic dispensers).
   - Multiple nozzles per pump (`P1-N1`, `P1-N2`, `P2-N1`, `P2-N2`).
   - Enforced fuel compatibility rule: prevents linking a Petrol nozzle to a Diesel tank.
   - Electronic totalizer cumulative meter readings.

5. **Fuel Price Management (`FuelPrice`)**:
   - Complete audit trail of NOC price circular revisions.
   - Purchase rate, retail selling rate, dealer gross margin.
   - Effective date & time with approval workflow (`APPROVED`, `PENDING`, `REJECTED`).
   - `FuelPrice.get_effective_price(fuel, as_of_datetime)`: guaranteed immutable historical pricing for previous sales.

6. **Enhanced Date Utilities**:
   - `get_bs_month_date_range(year, month)`: converts BS month to Gregorian AD range for ORM filtering.
   - `get_current_fiscal_year_bs()` & `get_fiscal_year_date_range()`: Nepal fiscal year calculations (Shrawan 1 to Ashadh end).


#### Phase 3: Operations, Shifts, Meter Readings & Sales
- Shift management with cash handover and managerial approval.
- Nozzle opening and closing meter tracking with monotonic check and rollover support.
- Cash, credit, and manual fuel sales entries with instant stock depletion.
- Concurrency-safe atomic transactions (`select_for_update()`).
- Sales cancellation with mandatory justification and audit logging.

#### Phase 4: Purchases, Suppliers, Expenses & Double-Entry Accounting
- NOC supplier registration and fuel purchase receipt linked to tanks.
- Comprehensive expense management with categorised operational costs.
- Customer credit ledger with credit limit enforcement and payment collection.
- Multi-account cash & bank ledger with transfer capability.
- Automated double-entry balanced journal vouchers ($\sum \text{Dr} = \sum \text{Cr}$).

#### Phase 5: Reporting, Analytics & Exports
- Real-time station operational dashboard with Tank level gauges, sales figures, and BS calendar cards.
- Shift reconciliation summaries and daily sales reports.
- Tank dipping calibration and physical-vs-system variance calculations.
- Comprehensive Profit & Loss financial statements.
- Export to Excel (`openpyxl`) and PDF (`WeasyPrint`).

#### Phase 6: Security, Testing, Audit & Disaster Recovery
- Brute-force rate limiting and 15-minute account lockout on consecutive failed logins.
- Strict server-side RBAC across all 5 operational roles (`@owner_required`, `@role_required`).
- Tamper-evident, append-only `AuditLog` model (modifications and deletions blocked).
- Automated backup command (`backup_database`) with SHA-256 manifests, retention pruning, and offsite replication.
- Verified restore command (`restore_database`) with checksum verification.
- 69/69 automated test suite passing across all modules.
- Disaster recovery manual (`docs/BACKUP_AND_RECOVERY.md`), UAT test scripts (`docs/UAT_SCENARIOS.md`), and comprehensive audit report (`docs/SECURITY_AND_QA_AUDIT.md`).


#### 1. Activate Environment
```bash
source venv/bin/activate
pip install -r requirements.txt
```

#### 2. Configure Database
Copy `.env.example` to `.env` and configure your credentials:
```bash
cp .env.example .env
```
For production PostgreSQL:
```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=petrol_station_db
DB_USER=petrol_admin
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
```

#### 3. Run Migrations & Seed Demo Accounts
```bash
python manage.py migrate
python manage.py seed_station_data
```

#### 4. Pre-configured Demo Accounts
| Role | Username | Password |
|---|---|---|
| **Owner** | `owner` | `OwnerPassword123!` |
| **Manager** | `manager` | `ManagerPassword123!` |
| **Accountant** | `accountant` | `AccountantPassword123!` |
| **Cashier** | `cashier` | `CashierPassword123!` |
| **Pump Operator**| `operator1` | `OperatorPassword123!` |

#### 5. Run Automated Tests
```bash
python manage.py test tests
```

#### 6. Start Development Server
```bash
python manage.py runserver 0.0.0.0:8000
```
Visit `http://localhost:8000` to log in.
