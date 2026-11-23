# Server Deployment Guide
**Production Hosting Architecture: Ubuntu Linux, PostgreSQL, Gunicorn & Nginx**
**Basista Oil Traders Petrol Station System**

---

## 1. Production Architecture Overview

The system runs on a Linux VPS behind an Nginx reverse proxy terminating HTTPS via Let's Encrypt certificates, communicating with Gunicorn workers via a local UNIX socket.

```
                    Internet
                       │ (Port 80 / 443 HTTPS)
                       ▼
             ┌───────────────────┐
             │    Nginx Proxy    │
             │   (SSL & Gzip)    │
             └─────────┬─────────┘
                       │
       ┌───────────────┴───────────────┐
       ▼                               ▼
┌──────────────┐             ┌───────────────────┐
│ Static/Media │             │  Gunicorn Server  │
│ File System  │             │   (UNIX Socket)   │
└──────────────┘             └─────────┬─────────┘
                                       │
                                       ▼
                             ┌───────────────────┐
                             │  PostgreSQL 16    │
                             │ (UTF-8, Kathmandu)│
                             └───────────────────┘
```

---

## 2. Server Hardening & Security Setup

### 2.1 Firewall Configuration (UFW)
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (for SSL challenges & HTTPS redirect)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
sudo ufw status
```

### 2.2 Dedicated Web Application Directory & Permissions
```bash
sudo mkdir -p /var/www/basista_oil
sudo chown -R www-data:www-data /var/www/basista_oil
sudo chmod -R 750 /var/www/basista_oil
```

---

## 3. Gunicorn Systemd Service Configuration

1. Copy systemd unit files from the repository:
   ```bash
   sudo cp deploy/systemd/gunicorn.service /etc/systemd/system/
   sudo cp deploy/systemd/gunicorn.socket /etc/systemd/system/
   ```

2. Create required run and log directories:
   ```bash
   sudo mkdir -p /run/gunicorn /var/log/gunicorn /var/www/basista_oil/logs
   sudo chown -R www-data:www-data /run/gunicorn /var/log/gunicorn /var/www/basista_oil/logs
   ```

3. Enable and start Gunicorn socket & service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable gunicorn.socket gunicorn.service
   sudo systemctl start gunicorn.socket gunicorn.service
   ```

4. Verify service status:
   ```bash
   sudo systemctl status gunicorn.service
   ```

---

## 4. Nginx Reverse Proxy & SSL (Let's Encrypt)

1. Deploy the Nginx site configuration:
   ```bash
   sudo cp deploy/nginx/basista_oil.conf /etc/nginx/sites-available/basista_oil.conf
   sudo ln -sf /etc/nginx/sites-available/basista_oil.conf /etc/nginx/sites-enabled/
   sudo rm -f /etc/nginx/sites-enabled/default
   ```

2. Obtain Let's Encrypt SSL Certificate using Certbot:
   ```bash
   # Create webroot path for ACME challenges
   sudo mkdir -p /var/www/certbot
   sudo chown -R www-data:www-data /var/www/certbot

   # Run Certbot to issue certificates for domain
   sudo certbot certonly --webroot -w /var/www/certbot \
       -d petrol.basistaoil.com.np \
       -d www.petrol.basistaoil.com.np \
       --email info@basistaoil.com.np \
       --agree-tos --no-eff-email
   ```

3. Test Nginx syntax and reload:
   ```bash
   sudo nginx -t
   sudo systemctl reload nginx
   ```

---

## 5. Domain DNS Setup

In your domain registrar DNS management portal (e.g. Nepal Commercial Domain Registry / Cloudflare), configure:

| Type | Host | Points to | TTL |
| :--- | :--- | :--- | :--- |
| **A** | `petrol.basistaoil.com.np` | `<VPS_STATIC_PUBLIC_IP>` | 300 |
| **CNAME** | `www.petrol.basistaoil.com.np` | `petrol.basistaoil.com.np` | 300 |

---

## 6. One-Command Production Deployment Workflow

Whenever a new release or update is pushed to GitHub:

```bash
cd /var/www/basista_oil
sudo -u www-data ./deploy/scripts/deploy.sh main
```

The script automatically:
1. Pulls the latest commits.
2. Updates virtualenv dependencies.
3. Applies database migrations (`migrate --noinput`).
4. Compiles bilingual translation catalogs.
5. Collects static assets (`collectstatic --noinput`).
6. Executes Django deployment security check (`check --deploy`).
7. Restarts Gunicorn application server with zero downtime.
8. Reloads Nginx and performs local HTTP smoke check.

---

## 7. Emergency Rollback Procedure

If a deployed version has an unforeseen defect:

```bash
cd /var/www/basista_oil
sudo -u www-data ./deploy/scripts/rollback.sh
```
Or specify a specific previous commit hash / git tag:
```bash
sudo -u www-data ./deploy/scripts/rollback.sh v2.1.0
```
