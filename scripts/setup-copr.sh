#!/bin/bash
# COPR Setup Script for Better DNF
# This script helps set up COPR and build the package

set -e

echo "🚀 Better DNF - COPR Setup Script"
echo "=================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if copr-cli is installed
if ! command -v copr-cli &> /dev/null; then
    echo -e "${YELLOW}⚠️  copr-cli not found. Installing...${NC}"
    sudo dnf install -y copr-cli
fi

# Check if logged in
echo "📋 Checking COPR login status..."
if copr-cli whoami &> /dev/null; then
    echo -e "${GREEN}✅ Already logged in to COPR${NC}"
    COPR_USER=$(copr-cli whoami 2>/dev/null | grep -oP '"name":\s*"\K[^"]+' || echo "unknown")
    echo "   Username: $COPR_USER"
else
    echo -e "${YELLOW}⚠️  Not logged in to COPR${NC}"
    echo ""
    echo "Please follow these steps:"
    echo ""
    echo "1. Go to: https://copr.fedorainfracloud.org/"
    echo "2. Login with your Fedora account"
    echo "3. Go to: https://copr.fedorainfracloud.org/api/"
    echo "4. Copy your API token"
    echo ""
    echo "Then run: copr-cli login snap-star"
    echo ""
    exit 1
fi

echo ""
echo "=================================="
echo ""

# Check if project exists
PROJECT_NAME="better-dnf"
echo "🔍 Checking if project '$PROJECT_NAME' exists..."

if copr-cli get-project "$COPR_USER/$PROJECT_NAME" &> /dev/null; then
    echo -e "${GREEN}✅ Project '$PROJECT_NAME' already exists${NC}"
else
    echo -e "${YELLOW}⚠️  Project '$PROJECT_NAME' not found. Creating...${NC}"
    
    copr-cli create "$PROJECT_NAME" \
        --chroot fedora-41-x86_64 \
        --chroot fedora-42-x86_64 \
        --chroot fedora-rawhide-x86_64 \
        --description "A smarter DNF update tool for Fedora" \
        --instructions "https://github.com/snap-star/better-dnf"
    
    echo -e "${GREEN}✅ Project created successfully!${NC}"
fi

echo ""
echo "=================================="
echo ""

# Get version
VERSION=$(cd "$(dirname "$0")/.." && grep -oP 'version = "\K[^"]+' pyproject.toml)
echo "📦 Package version: $VERSION"

# Build option
echo ""
echo "🔧 Build options:"
echo "1. Build from PyPI (recommended)"
echo "2. Build from local SRPM"
echo "3. Build from GitHub tag"
echo ""
read -p "Select build method (1-3): " BUILD_METHOD

case $BUILD_METHOD in
    1)
        echo ""
        echo "🔨 Building from PyPI..."
        copr-cli build "$COPR_USER/$PROJECT_NAME" "pypi:better-dnf==${VERSION}"
        ;;
    2)
        echo ""
        echo "🔨 Building SRPM first..."
        bash "$(dirname "$0")/build-srpm.sh"
        
        SRPM_FILE=$(ls rpmbuild/SRPMS/better-dnf-*.src.rpm 2>/dev/null | head -1)
        if [ -z "$SRPM_FILE" ]; then
            echo -e "${RED}❌ SRPM not found${NC}"
            exit 1
        fi
        
        echo "📦 SRPM: $SRPM_FILE"
        copr-cli build "$COPR_USER/$PROJECT_NAME" "$SRPM_FILE"
        ;;
    3)
        echo ""
        echo "🔨 Building from GitHub tag..."
        read -p "Enter tag (e.g., v1.0.0): " TAG
        copr-cli build "$COPR_USER/$PROJECT_NAME" \
            scm \
            --clone-url "https://github.com/snap-star/better-dnf" \
            --committish "$TAG"
        ;;
    *)
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

echo ""
echo "=================================="
echo ""
echo -e "${GREEN}✅ Build submitted successfully!${NC}"
echo ""
echo "📊 Monitor your build at:"
echo "   https://copr.fedorainfracloud.org/coprs/$COPR_USER/$PROJECT_NAME/builds/"
echo ""
echo "📦 Users can install with:"
echo "   sudo dnf copr enable $COPR_USER/$PROJECT_NAME"
echo "   sudo dnf install better-dnf"
echo ""
