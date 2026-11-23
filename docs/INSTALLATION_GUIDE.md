# Installation Guide
**Basista Oil Traders - Petrol Station Management System (Nepal)**

---

## 1. System Requirements

### Hardware Requirements
- **Architecture**: x86_64 or ARM64 Linux
- **Processor**: Minimum 2 CPU cores (4 cores recommended for production concurrency)
- **RAM**: Minimum 2 GB (4 GB recommended for concurrent PDF rendering with WeasyPrint)
- **Disk Storage**: 20 GB SSD storage minimum

### Software Prerequisites
- **Operating System**: Ubuntu 22.04 LTS / 24.04 LTS or Debian 12
- **Python**: Version 3.11, 3.12, or 3.13+
- **Database**: PostgreSQL 15, 16, or 17
- **Web Server**: Nginx (1.18+)
- **Application Server**: Gunicorn (22+)
- **Fonts**: `fonts-noto-core` (Required for Nepali Devanagari typography)

---

## 2. Operating System Dependencies

Run the following commands to install required system packages, compilers, and WeasyPrint rendering libraries:

```bash
sudo apt update && sudo apt upgrade -y

# Core tools and Python development headers
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    git \
    curl \
    gettext

# PostgreSQL server and client libraries
sudo apt install -y \
    postgresql \
    postgresql-contrib \
    libpq-dev

# WeasyPrint PDF graphics and typography dependencies
sudo apt install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libjpeg-dev \
    libopenjp2-7-dev \
    libffi-dev \
    fonts-noto-core \
    fonts-noto-cjk

# Nginx web server and Certbot for SSL
sudo apt install -y \
    nginx \
    certbot \
    python3-certbot-nginx
```

---

## 3. Clone Repository & Setup Virtual Environment

```bash
# Clone the application repository
git clone https://github.com/basista-oil/petrol-station-system.git /var/www/basista_oil
cd /var/www/basista_oil

# Create dedicated Python virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip, wheel, and setuptools
pip install --upgrade pip setuptools wheel

# Install all Python dependencies
pip install -r requirements.txt
```

---

## 4. PostgreSQL Database Initialization

1. Switch to the `postgres` system user:
   ```bash
   sudo -u postgres psql
   ```
2. Execute the initialization SQL:
   ```sql
   CREATE USER petrol_admin WITH LOGIN PASSWORD 'YourSecurePasswordHere123!';
   CREATE DATABASE petrol_station_db OWNER petrol_admin ENCODING 'UTF8';
   ALTER ROLE petrol_admin SET client_encoding TO 'utf8';
   ALTER ROLE petrol_admin SET default_transaction_isolation TO 'read committed';
   ALTER ROLE petrol_admin SET timezone TO 'Asia/Kathmandu';
   GRANT ALL PRIVILEGES ON DATABASE petrol_station_db TO petrol_admin;
   \c petrol_station_db
   GRANT ALL ON SCHEMA public TO petrol_admin;
   \q
   ```

---

## 5. Application Environment Configuration

Copy the example environment file:
```bash
cp .env.example .env
```
Edit `.env` and set your actual values:
```env
SECRET_KEY=generate-a-strong-random-key-with-secrets-module
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,petrol.basistaoil.com.np
CSRF_TRUSTED_ORIGINS=https://petrol.basistaoil.com.np

DB_ENGINE=django.db.backends.postgresql
DB_NAME=petrol_station_db
DB_USER=petrol_admin
DB_PASSWORD=YourSecurePasswordHere123!
DB_HOST=127.0.0.1
DB_PORT=5432

STATION_NAME_EN=Basista Oil Traders
STATION_NAME_NE=बसिस्ट आयल ट्रेडर्स
TIME_ZONE=Asia/Kathmandu
DEFAULT_LANGUAGE=ne
```

Protect file permissions:
```bash
chmod 600 .env
```

---

## 6. Database Migrations, Translations & Static Files

```bash
# Apply all database migrations
python manage.py migrate

# Seed initial station configuration and demo accounts
python manage.py seed_station_data

# Compile bilingual gettext translations
python manage.py compilemessages

# Collect all static files for Nginx
python manage.py collectstatic --noinput
```

---

## 7. Verify Installation

Run the automated production verification suite:
```bash
python deploy/scripts/verify_production.py
```

Expected output:
```
==================================================================
 Verification Complete: 10/10 Passed, 0 Failed.
==================================================================
 SYSTEM PRODUCTION READY: All critical checks passed successfully!
```
