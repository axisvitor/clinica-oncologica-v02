# Database Backup & Restore - Quick Reference

**Quick access guide for emergency situations**

## 🚨 Emergency Restore

```bash
# 1. Stop application
systemctl stop backend-hormonia

# 2. Restore database
export DATABASE_URL="postgresql+psycopg://..."
python scripts/restore_database_backup.py \
  --backup backups/backup_prod_TIMESTAMP.json

# 3. Verify alembic version
psql $DATABASE_URL -c "SELECT version_num FROM alembic_version"

# 4. Restart application
systemctl start backend-hormonia
```

## 📦 Create Backup (Before Migration)

```bash
# Set environment
export DATABASE_URL="postgresql+psycopg://..."

# Create backup
python scripts/backup_production_database.py

# Verify backup
ls -lh backups/backup_prod_*.json
sha256sum -c backups/backup_prod_*.json.sha256
```

## 🔍 Test Restore (Safe)

```bash
# Dry run - no changes made
python scripts/restore_database_backup.py \
  --backup backups/backup_prod_TIMESTAMP.json \
  --dry-run
```

## 📊 Backup Statistics

**Database Size:** ~500MB
**Tables:** 47
**Estimated Rows:** ~85,000
**Backup Time:** 2-5 minutes
**Restore Time:** 5-10 minutes

## 🔐 Files Created

- `backups/backup_prod_TIMESTAMP.json` - Backup data
- `backups/backup_prod_TIMESTAMP.json.sha256` - Checksum
- `backups/BACKUP_REPORT_TIMESTAMP.md` - Summary report

## ⚙️ Command Options

### Backup Script
```bash
--format {json,sql}      # Output format (default: json)
--backup-dir DIR         # Backup directory (default: backups/)
```

### Restore Script
```bash
--backup FILE            # Backup file (required)
--dry-run               # Test restore without changes
--yes                   # Skip confirmation (DANGEROUS)
```

## 🎯 Critical Components

1. **Alembic Version** - MUST be backed up for migrations
2. **Patient Data** - PHI/PII data (HIPAA compliance)
3. **Quiz Responses** - Clinical data
4. **Messages** - Communication history
5. **Flow States** - Patient journey tracking

## ⚠️ Important Notes

- Always backup BEFORE applying migrations
- Verify checksum before restore
- Test restore on staging first
- Store backups securely (encrypted)
- Never commit backups to git

## 📞 Emergency Contacts

- DevOps Team: [contact]
- Database Admin: [contact]
- Backup Location: s3://clinic-backups/production/

## 📚 Full Documentation

See: [BACKUP_RESTORE_GUIDE.md](./BACKUP_RESTORE_GUIDE.md)
