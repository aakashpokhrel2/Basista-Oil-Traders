# Production Troubleshooting Guide
**Basista Oil Traders Petrol Station System**

---

## 1. Web Server & Reverse Proxy Issues

### Problem: 502 Bad Gateway
- **Symptoms**: Browser displays "502 Bad Gateway" when opening the station URL.
- **Root Cause**: Gunicorn application server is stopped, crashed, or its UNIX socket `/run/gunicorn/basista_oil.sock` is unreachable.
- **Resolution**:
  1. Check Gunicorn systemd service status:
     ```bash
     sudo systemctl status gunicorn.service
     ```
  2. Inspect Gunicorn error logs:
     ```bash
     sudo tail -n 50 /var/log/gunicorn/error.log
     ```
  3. Verify socket file permissions:
     ```bash
     ls -la /run/gunicorn/basista_oil.sock
     # Should be owned by www-data:www-data with mode 660
     ```
  4. Restart Gunicorn:
     ```bash
     sudo systemctl restart gunicorn.socket gunicorn.service
     ```

---

### Problem: Static Files Not Loading (Unstyled Page / 404 on CSS/JS)
- **Symptoms**: Dashboard displays without Tailwind styling; browser console shows 404 for `/static/...`.
- **Root Cause**: Static files were not collected into `STATIC_ROOT` or Nginx alias path does not match.
- **Resolution**:
  1. Run Django static collection command:
     ```bash
     cd /var/www/basista_oil
     source venv/bin/activate
     python manage.py collectstatic --noinput --clear
     ```
  2. Ensure `www-data` has read permissions:
     ```bash
     sudo chown -R www-data:www-data /var/www/basista_oil/staticfiles
     sudo chmod -R 755 /var/www/basista_oil/staticfiles
     ```
  3. Reload Nginx:
     ```bash
     sudo systemctl reload nginx
     ```

---

## 2. Authentication & Security Issues

### Problem: Account Locked Out Due to Failed Attempts
- **Symptoms**: User sees "Account temporarily locked out due to multiple failed login attempts. Please try again after 15 minutes."
- **Root Cause**: Security rate limiter activated after 5 consecutive failed passwords.
- **Resolution**:
  1. To immediately unlock the user without waiting 15 minutes, access Django shell:
     ```bash
     cd /var/www/basista_oil
     source venv/bin/activate
     python manage.py shell
     ```
  2. Clear recent failed attempts for the username:
     ```python
     from apps.authentication.models import LoginAttempt
     LoginAttempt.objects.filter(username='target_username').delete()
     print("Account unlocked successfully.")
     ```

---

### Problem: CSRF Verification Failed (403 Forbidden on Forms)
- **Symptoms**: Submitting login or sales forms returns "CSRF verification failed. Request aborted."
- **Root Cause**: Accessing the server via a domain or IP not present in `CSRF_TRUSTED_ORIGINS`.
- **Resolution**:
  1. Check the domain in the browser address bar (e.g. `https://petrol.basistaoil.com.np`).
  2. Open `.env` and verify `CSRF_TRUSTED_ORIGINS` includes this exact origin:
     ```env
     CSRF_TRUSTED_ORIGINS=https://petrol.basistaoil.com.np,https://www.petrol.basistaoil.com.np
     ```
  3. Restart Gunicorn:
     ```bash
     sudo systemctl restart gunicorn
     ```

---

## 3. Typography & PDF Rendering Issues

### Problem: Nepali Devanagari Characters Display as Boxes / Question Marks in PDFs
- **Symptoms**: WeasyPrint exported PDFs show empty boxes `[ ]` instead of Nepali characters (बसिस्ट आयल ट्रेडर्स).
- **Root Cause**: Noto Sans Devanagari system font is missing from the Linux VPS.
- **Resolution**:
  1. Install Noto Sans Devanagari fonts on Ubuntu:
     ```bash
     sudo apt update && sudo apt install -y fonts-noto-core fonts-noto-cjk
     ```
  2. Refresh font cache:
     ```bash
     sudo fc-cache -f -v
     ```
  3. Test PDF generation with the verification suite:
     ```bash
     python deploy/scripts/verify_production.py
     ```

---

## 4. Database & Transaction Issues

### Problem: Duplicate Supplier Invoice Rejected
- **Symptoms**: Submitting a purchase throws database error `unique_supplier_invoice`.
- **Root Cause**: An invoice with that exact invoice number has already been recorded for this supplier.
- **Resolution**:
  - Verify the supplier invoice number on the physical tanker challan from NOC.
  - Search existing purchase records under **Purchases** to check if another staff member already logged the delivery.

---

### Problem: Database Connection Refused
- **Symptoms**: `django.db.utils.OperationalError: could not connect to server: Connection refused`.
- **Resolution**:
  1. Check PostgreSQL service status:
     ```bash
     sudo systemctl status postgresql
     ```
  2. Start service if stopped:
     ```bash
     sudo systemctl start postgresql
     ```
  3. Verify connection settings in `/var/www/basista_oil/.env`.
