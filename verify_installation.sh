#!/bin/bash

# Verification script for M-Pesa Callback Server installation
# This script checks that all necessary files and dependencies are in place

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   M-Pesa Callback Server - Installation Verification      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check counter
PASS=0
FAIL=0

# Function to check file existence
check_file() {
    if [ -f "$1" ]; then
        echo -e "${GREEN}✓${NC} $1 ($(wc -l < "$1") lines)"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $1 - MISSING"
        ((FAIL++))
    fi
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Core Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "callback_server.py"
check_file "test_callback.py"
check_file "database_schema.sql"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Documentation Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "CALLBACK_SERVER_README.md"
check_file "IMPLEMENTATION_SUMMARY.md"
check_file "QUICKSTART.md"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Deployment Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "mpesa-callback.service"
check_file "nginx.conf"
check_file "Dockerfile"
check_file "docker-compose.yml"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Configuration Files"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
check_file "requirements.txt"
check_file ".env.example"
check_file ".gitignore"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Python Syntax Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if python3 -m py_compile callback_server.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} callback_server.py - Valid Python syntax"
    ((PASS++))
else
    echo -e "${RED}✗${NC} callback_server.py - Syntax errors"
    ((FAIL++))
fi

if python3 -m py_compile test_callback.py 2>/dev/null; then
    echo -e "${GREEN}✓${NC} test_callback.py - Valid Python syntax"
    ((PASS++))
else
    echo -e "${RED}✗${NC} test_callback.py - Syntax errors"
    ((FAIL++))
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Environment Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check Python version
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}✓${NC} Python 3 installed: $PY_VERSION"
    ((PASS++))
else
    echo -e "${RED}✗${NC} Python 3 not found"
    ((FAIL++))
fi

# Check if .env exists
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    ((PASS++))
else
    echo -e "${YELLOW}⚠${NC} .env file not found (copy from .env.example)"
fi

# Check if virtual environment exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✓${NC} Virtual environment exists"
    ((PASS++))
else
    echo -e "${YELLOW}⚠${NC} Virtual environment not found (optional)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "Checks Passed: ${GREEN}$PASS${NC}"
echo -e "Checks Failed: ${RED}$FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   ✓ Installation verified successfully!                   ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Configure .env file: cp .env.example .env && nano .env"
    echo "2. Set up database: mysql -u root -p < database_schema.sql"
    echo "3. Install dependencies: pip install -r requirements.txt"
    echo "4. Run server: python callback_server.py"
    echo "5. Test: python test_callback.py"
    exit 0
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ✗ Installation verification failed                      ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Please check the missing files above."
    exit 1
fi
