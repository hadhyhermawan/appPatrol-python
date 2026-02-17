# AppPatrol Python Backend - Deployment Guide

## 📋 Overview

**Project**: AppPatrol Python Backend API  
**Framework**: FastAPI + Uvicorn  
**Domain**: https://frontend.k3guard.com/api-py/  
**Port**: 8000  
**Process Manager**: systemd (uvicorn service)  
**Database**: MySQL/MariaDB

---

## 🏗️ Architecture

```
Nginx (443) → /api-py/ → Uvicorn (8000) → FastAPI → Database
```

### Directory Structure
```
/var/www/appPatrol-python/
├── app/
│   ├── main.py           # FastAPI application entry
│   ├── routers/          # API route handlers
│   ├── models/           # Database models
│   ├── schemas/          # Pydantic schemas
│   └── core/             # Core utilities
├── .venv/                # Python virtual environment
├── requirements.txt      # Python dependencies
└── .env                  # Environment variables
```

---

## 🚀 Deployment Steps

### 1. Initial Setup

```bash
cd /var/www/appPatrol-python

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration

Edit `.env`:
```env
DATABASE_URL=mysql+pymysql://user:password@localhost/dbname
SECRET_KEY=your-secret-key-here
ENVIRONMENT=production
```

### 3. Database Setup

```bash
# Run migrations (if using Alembic)
alembic upgrade head

# Or run SQL scripts
mysql -u user -p database < schema.sql
```

### 4. Systemd Service Configuration

Create/edit service file: `/etc/systemd/system/apppatrol-python.service`

```ini
[Unit]
Description=AppPatrol Python FastAPI Backend
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/appPatrol-python
Environment="PATH=/var/www/appPatrol-python/.venv/bin"
ExecStart=/var/www/appPatrol-python/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start service:
```bash
# Reload systemd
systemctl daemon-reload

# Enable service
systemctl enable apppatrol-python

# Start service
systemctl start apppatrol-python

# Check status
systemctl status apppatrol-python
```

### 5. Nginx Configuration

Already configured in `/etc/nginx/sites-enabled/frontend.k3guard.com`:

```nginx
location /api-py/ {
    rewrite ^/api-py/(.*) /api/$1 break;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

---

## 🔧 Common Operations

### Update Code & Redeploy

```bash
cd /var/www/appPatrol-python

# Pull latest changes
git pull

# Activate virtual environment
source .venv/bin/activate

# Install new dependencies
pip install -r requirements.txt

# Restart service
systemctl restart apppatrol-python

# Check logs
journalctl -u apppatrol-python -f
```

### Check Application Status

```bash
# Service status
systemctl status apppatrol-python

# Check if running
ps aux | grep uvicorn

# Check port
netstat -tulpn | grep 8000

# View logs
journalctl -u apppatrol-python -n 100 --no-pager
```

### Test Endpoints

```bash
# Test locally
curl -I http://localhost:8000/api/

# Test through Nginx
curl -I https://frontend.k3guard.com/api-py/

# Test specific endpoint
curl https://frontend.k3guard.com/api-py/health
```

---

## 🐛 Troubleshooting

### Issue: Service Won't Start

**Diagnosis**:
```bash
# Check service status
systemctl status apppatrol-python

# View detailed logs
journalctl -u apppatrol-python -n 50 --no-pager

# Check for Python errors
journalctl -u apppatrol-python -p err
```

**Common Solutions**:

1. **Port already in use**:
   ```bash
   # Find process on port 8000
   lsof -i :8000
   
   # Kill old process
   kill <PID>
   
   # Restart service
   systemctl restart apppatrol-python
   ```

2. **Virtual environment issues**:
   ```bash
   # Recreate venv
   cd /var/www/appPatrol-python
   rm -rf .venv
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   systemctl restart apppatrol-python
   ```

3. **Permission issues**:
   ```bash
   # Fix ownership
   chown -R root:root /var/www/appPatrol-python
   
   # Fix permissions
   chmod -R 755 /var/www/appPatrol-python
   ```

### Issue: Database Connection Failed

**Symptoms**: 500 errors, connection refused

**Solutions**:

1. **Check database is running**:
   ```bash
   systemctl status mysql
   # or
   systemctl status mariadb
   ```

2. **Verify credentials**:
   ```bash
   # Test connection
   mysql -u username -p -h localhost database_name
   ```

3. **Check .env file**:
   ```bash
   cat /var/www/appPatrol-python/.env | grep DATABASE
   ```

### Issue: 502 Bad Gateway

**Diagnosis**:
```bash
# Check if service is running
systemctl status apppatrol-python

# Check if port is listening
netstat -tulpn | grep 8000

# Check nginx error log
tail -50 /var/log/nginx/error.log | grep api-py
```

**Solutions**:
1. **Restart backend**: `systemctl restart apppatrol-python`
2. **Check Nginx config**: `nginx -t`
3. **Reload Nginx**: `systemctl reload nginx`

### Issue: Slow API Response

**Diagnosis**:
```bash
# Check database queries
# Enable query logging in MySQL

# Check system resources
top
htop

# Check worker count
ps aux | grep uvicorn | wc -l
```

**Solutions**:
1. **Increase workers** in systemd service:
   ```ini
   ExecStart=/var/www/appPatrol-python/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```

2. **Add database indexes**
3. **Optimize queries**
4. **Enable caching**

### Issue: Import Errors

**Symptoms**: `ModuleNotFoundError`, `ImportError`

**Solutions**:
```bash
cd /var/www/appPatrol-python
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check installed packages
pip list

# Restart service
systemctl restart apppatrol-python
```

---

## 📊 Monitoring

### Service Logs

```bash
# Follow logs in real-time
journalctl -u apppatrol-python -f

# Last 100 lines
journalctl -u apppatrol-python -n 100 --no-pager

# Errors only
journalctl -u apppatrol-python -p err

# Today's logs
journalctl -u apppatrol-python --since today

# Specific time range
journalctl -u apppatrol-python --since "2026-02-17 10:00:00" --until "2026-02-17 12:00:00"
```

### Process Monitoring

```bash
# Check process
ps aux | grep uvicorn

# Check memory usage
ps aux | grep uvicorn | awk '{print $6}'

# Check CPU usage
top -p $(pgrep -f uvicorn)
```

### API Health Check

Create a health endpoint in `app/main.py`:
```python
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }
```

Test:
```bash
curl https://frontend.k3guard.com/api-py/health
```

---

## 🔐 Security Checklist

- ✅ Virtual environment isolated
- ✅ Environment variables in `.env` (not committed)
- ✅ Database credentials secured
- ✅ CORS configured properly
- ✅ Input validation with Pydantic
- ✅ SQL injection prevention (ORM)
- ✅ Rate limiting (consider adding)
- ✅ Authentication & authorization

---

## 📝 Important Files

| File | Purpose |
|------|---------|
| `/etc/systemd/system/apppatrol-python.service` | Systemd service config |
| `/var/www/appPatrol-python/.env` | Environment variables |
| `/var/www/appPatrol-python/requirements.txt` | Python dependencies |
| `/var/www/appPatrol-python/app/main.py` | FastAPI entry point |
| `/etc/nginx/sites-enabled/frontend.k3guard.com` | Nginx proxy config |

---

## 🆘 Emergency Recovery

If backend is completely broken:

```bash
# 1. Stop service
systemctl stop apppatrol-python

# 2. Backup current code
cd /var/www
cp -r appPatrol-python appPatrol-python.backup.$(date +%Y%m%d)

# 3. Reset virtual environment
cd /var/www/appPatrol-python
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Check configuration
cat .env

# 5. Test manually
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Press Ctrl+C after verifying it starts

# 6. Restart service
systemctl start apppatrol-python

# 7. Check status
systemctl status apppatrol-python
curl -I http://localhost:8000/api/

# 8. Check through Nginx
curl -I https://frontend.k3guard.com/api-py/
```

---

## 🔄 Database Migrations

### Using Alembic (if configured)

```bash
cd /var/www/appPatrol-python
source .venv/bin/activate

# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1

# Check current version
alembic current
```

### Manual SQL Updates

```bash
# Backup database first
mysqldump -u user -p database > backup_$(date +%Y%m%d).sql

# Apply SQL file
mysql -u user -p database < migration.sql

# Restart service
systemctl restart apppatrol-python
```

---

## 📞 Quick Reference

```bash
# Service management
systemctl status apppatrol-python
systemctl restart apppatrol-python
systemctl stop apppatrol-python
systemctl start apppatrol-python

# Logs
journalctl -u apppatrol-python -f
journalctl -u apppatrol-python -n 100

# Test
curl -I http://localhost:8000/api/
curl -I https://frontend.k3guard.com/api-py/

# Process
ps aux | grep uvicorn
netstat -tulpn | grep 8000

# Update
cd /var/www/appPatrol-python
git pull
source .venv/bin/activate
pip install -r requirements.txt
systemctl restart apppatrol-python
```

---

## 🔗 Related Documentation

- Frontend Deployment: `/var/www/apppatrol-admin/DEPLOYMENT.md`
- API Documentation: https://frontend.k3guard.com/api-py/docs (if Swagger enabled)

---

**Last Updated**: 2026-02-17  
**Maintainer**: DevOps Team
