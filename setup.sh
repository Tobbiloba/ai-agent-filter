#!/bin/bash
# AI Agent Safety Filter - One-Line Setup Script
# Usage: ./setup.sh or curl -sSL <url>/setup.sh | bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo -e "${GREEN}🚀 Setting up AI Agent Safety Filter...${NC}"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required but not installed.${NC}"
    echo "   Please install Python 3.9+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "   Found Python ${PYTHON_VERSION}"

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}❌ requirements.txt not found.${NC}"
    echo "   Please run this script from the project root directory."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
else
    echo -e "   Virtual environment already exists"
fi

# Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${YELLOW}📥 Upgrading pip...${NC}"
pip install --upgrade pip --quiet

# Install dependencies
echo -e "${YELLOW}📥 Installing dependencies...${NC}"
pip install -r requirements.txt --quiet

# Install SDK in development mode
if [ -d "sdk/python" ]; then
    echo -e "${YELLOW}📥 Installing SDK...${NC}"
    pip install -e sdk/python --quiet
fi

# Success message
echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo -e "To start the server:"
echo -e "  ${YELLOW}source venv/bin/activate${NC}"
echo -e "  ${YELLOW}uvicorn server.app:app --reload${NC}"
echo ""
echo -e "Then visit: ${GREEN}http://localhost:8000/docs${NC}"
echo ""
