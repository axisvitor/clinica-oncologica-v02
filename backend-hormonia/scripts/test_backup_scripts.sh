#!/bin/bash
# Test Backup and Restore Scripts
# Usage: bash scripts/test_backup_scripts.sh

set -e

echo "🧪 Testing Database Backup & Restore Scripts"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Check Python availability
echo -e "\n${YELLOW}Test 1: Checking Python installation${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓${NC} Python found: $PYTHON_VERSION"
else
    echo -e "${RED}✗${NC} Python 3 not found"
    exit 1
fi

# Test 2: Check required modules
echo -e "\n${YELLOW}Test 2: Checking Python dependencies${NC}"
python3 -c "import sqlalchemy" 2>/dev/null && echo -e "${GREEN}✓${NC} SQLAlchemy installed" || echo -e "${RED}✗${NC} SQLAlchemy missing (pip install sqlalchemy)"
python3 -c "import psycopg" 2>/dev/null && echo -e "${GREEN}✓${NC} psycopg3 installed" || echo -e "${RED}✗${NC} psycopg3 missing (pip install psycopg[binary])"

# Test 3: Check backup script exists
echo -e "\n${YELLOW}Test 3: Checking backup script${NC}"
if [ -f "scripts/backup_production_database.py" ]; then
    echo -e "${GREEN}✓${NC} Backup script found"
    # Check if executable
    if [ -x "scripts/backup_production_database.py" ]; then
        echo -e "${GREEN}✓${NC} Backup script is executable"
    else
        echo -e "${YELLOW}⚠${NC} Backup script not executable (chmod +x recommended)"
    fi
else
    echo -e "${RED}✗${NC} Backup script not found"
    exit 1
fi

# Test 4: Check restore script exists
echo -e "\n${YELLOW}Test 4: Checking restore script${NC}"
if [ -f "scripts/restore_database_backup.py" ]; then
    echo -e "${GREEN}✓${NC} Restore script found"
    # Check if executable
    if [ -x "scripts/restore_database_backup.py" ]; then
        echo -e "${GREEN}✓${NC} Restore script is executable"
    else
        echo -e "${YELLOW}⚠${NC} Restore script not executable (chmod +x recommended)"
    fi
else
    echo -e "${RED}✗${NC} Restore script not found"
    exit 1
fi

# Test 5: Check DATABASE_URL environment variable
echo -e "\n${YELLOW}Test 5: Checking DATABASE_URL${NC}"
if [ -n "$DATABASE_URL" ]; then
    echo -e "${GREEN}✓${NC} DATABASE_URL is set"
    # Check if it contains required components
    if [[ $DATABASE_URL == postgresql* ]]; then
        echo -e "${GREEN}✓${NC} DATABASE_URL starts with postgresql"
    else
        echo -e "${RED}✗${NC} DATABASE_URL doesn't start with postgresql"
    fi
else
    echo -e "${YELLOW}⚠${NC} DATABASE_URL not set (required for actual backup)"
fi

# Test 6: Check backups directory
echo -e "\n${YELLOW}Test 6: Checking backups directory${NC}"
if [ -d "backups" ]; then
    echo -e "${GREEN}✓${NC} Backups directory exists"
else
    echo -e "${YELLOW}⚠${NC} Backups directory doesn't exist (will be created automatically)"
fi

# Test 7: Test backup script help
echo -e "\n${YELLOW}Test 7: Testing backup script --help${NC}"
if python3 scripts/backup_production_database.py --help &> /dev/null; then
    echo -e "${GREEN}✓${NC} Backup script --help works"
else
    echo -e "${RED}✗${NC} Backup script --help failed"
fi

# Test 8: Test restore script help
echo -e "\n${YELLOW}Test 8: Testing restore script --help${NC}"
if python3 scripts/restore_database_backup.py --help &> /dev/null; then
    echo -e "${GREEN}✓${NC} Restore script --help works"
else
    echo -e "${RED}✗${NC} Restore script --help failed"
fi

# Test 9: Check script syntax
echo -e "\n${YELLOW}Test 9: Checking Python syntax${NC}"
python3 -m py_compile scripts/backup_production_database.py && echo -e "${GREEN}✓${NC} Backup script syntax OK" || echo -e "${RED}✗${NC} Backup script has syntax errors"
python3 -m py_compile scripts/restore_database_backup.py && echo -e "${GREEN}✓${NC} Restore script syntax OK" || echo -e "${RED}✗${NC} Restore script has syntax errors"

# Summary
echo -e "\n${GREEN}=============================================="
echo "✅ All tests completed!"
echo "=============================================="
echo ""
echo "Next Steps:"
echo "1. Set DATABASE_URL environment variable"
echo "2. Run: python3 scripts/backup_production_database.py --format json"
echo "3. Verify backup created in backups/ directory"
echo "4. Test restore with --dry-run flag"
echo ""
