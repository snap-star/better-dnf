#!/bin/bash
# Complete Setup Script for Better DNF
# This script guides you through COPR and GitHub Actions setup

set -e

echo "🚀 Better DNF - Complete Setup Script"
echo "====================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print section headers
print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to check command existence
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✅ $1 is installed${NC}"
        return 0
    else
        echo -e "${RED}❌ $1 is not installed${NC}"
        return 1
    fi
}

# Function to prompt for yes/no
prompt_yes_no() {
    while true; do
        read -p "$1 (y/n): " answer
        case $answer in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer y or n.";;
        esac
    done
}

# ============================================
# PART 1: Check Prerequisites
# ============================================
print_section "PART 1: Checking Prerequisites"

echo "Checking required tools..."
echo ""

MISSING_TOOLS=()

if check_command "python3"; then
    PYTHON_VERSION=$(python3 --version)
    echo "   Version: $PYTHON_VERSION"
else
    MISSING_TOOLS+=("python3")
fi

if check_command "pip3"; then
    echo "   pip3 is available"
else
    MISSING_TOOLS+=("pip3")
fi

if check_command "git"; then
    GIT_VERSION=$(git --version)
    echo "   Version: $GIT_VERSION"
else
    MISSING_TOOLS+=("git")
fi

if check_command "rpmbuild"; then
    RPM_VERSION=$(rpmbuild --version | head -1)
    echo "   Version: $RPM_VERSION"
else
    echo -e "${YELLOW}⚠️  rpmbuild not found (optional for local builds)${NC}"
fi

if check_command "copr-cli"; then
    echo "   copr-cli is available"
else
    echo -e "${YELLOW}⚠️  copr-cli not found${NC}"
    if prompt_yes_no "Install copr-cli now?"; then
        echo "Installing copr-cli..."
        sudo dnf install -y copr-cli
    fi
fi

if [ ${#MISSING_TOOLS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Missing required tools: ${MISSING_TOOLS[*]}${NC}"
    echo "Please install them before continuing."
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All prerequisites checked${NC}"

# ============================================
# PART 2: COPR Setup
# ============================================
print_section "PART 2: Fedora COPR Setup"

echo "Fedora COPR (Cool Other Package Repo) is Fedora's official"
echo "third-party repository system."
echo ""

if prompt_yes_no "Do you have a Fedora Account (FAS)?"; then
    echo -e "${GREEN}Great! Let's proceed with COPR setup.${NC}"
else
    echo ""
    echo "Please create a Fedora account first:"
    echo -e "${BLUE}  https://accounts.fedoraproject.org/${NC}"
    echo ""
    echo "Use username: snap-star"
    echo ""
    read -p "Press Enter after creating your account..."
fi

# Check COPR login
echo ""
echo "Checking COPR login status..."

if command -v copr-cli &> /dev/null; then
    if copr-cli whoami &> /dev/null; then
        COPR_USER=$(copr-cli whoami 2>/dev/null | grep -oP '"name":\s*"\K[^"]+' || echo "unknown")
        echo -e "${GREEN}✅ Logged in as: $COPR_USER${NC}"
    else
        echo -e "${YELLOW}⚠️  Not logged in to COPR${NC}"
        echo ""
        echo "To login, run:"
        echo -e "${BLUE}  copr-cli login snap-star${NC}"
        echo ""
        echo "You'll need your Fedora account credentials."
        echo ""
        read -p "Press Enter after logging in..."
    fi
fi

# Create COPR project
echo ""
echo "Creating COPR project..."

if prompt_yes_no "Create COPR project 'better-dnf'?"; then
    echo ""
    echo "Creating project for Fedora 41, 42, and Rawhide..."
    
    if copr-cli get-project "snap-star/better-dnf" &> /dev/null; then
        echo -e "${GREEN}✅ Project already exists${NC}"
    else
        copr-cli create better-dnf \
            --chroot fedora-41-x86_64 \
            --chroot fedora-42-x86_64 \
            --chroot fedora-rawhide-x86_64 \
            --description "A smarter DNF update tool for Fedora" \
            --instructions "https://github.com/snap-star/better-dnf"
        
        echo -e "${GREEN}✅ Project created successfully!${NC}"
    fi
fi

# ============================================
# PART 3: GitHub Repository Setup
# ============================================
print_section "PART 3: GitHub Repository Setup"

echo "You'll need to create a GitHub repository for better-dnf."
echo ""

if prompt_yes_no "Do you have a GitHub account?"; then
    echo -e "${GREEN}Great!${NC}"
else
    echo "Please create a GitHub account at: https://github.com"
    read -p "Press Enter after creating your account..."
fi

echo ""
echo "Steps to create the repository:"
echo ""
echo "1. Go to: ${BLUE}https://github.com/new${NC}"
echo "2. Repository name: ${YELLOW}better-dnf${NC}"
echo "3. Owner: ${YELLOW}snap-star${NC}"
echo "4. Description: ${YELLOW}A smarter DNF update tool for Fedora${NC}"
echo "5. Make it ${GREEN}Public${NC}"
echo "6. Don't initialize with README (we have one)"
echo "7. Click 'Create repository'"
echo ""

read -p "Press Enter after creating the repository..."

# ============================================
# PART 4: Push Code to GitHub
# ============================================
print_section "PART 4: Push Code to GitHub"

cd "$(dirname "$0")/.."

echo "Current directory: $(pwd)"
echo ""

if [ -d ".git" ]; then
    echo "Git repository already initialized."
else
    echo "Initializing git repository..."
    git init
    git branch -M main
fi

echo ""
echo "Files to be committed:"
git status --short

echo ""
if prompt_yes_no "Add and commit all files?"; then
    git add .
    git commit -m "Initial release: Better DNF v1.0.0

Features:
- Smart categorization of updates
- Importance analysis using changelogs and CVEs
- Interactive selection with navigation
- Btrfs snapshot protection
- Package preview before confirmation
- Security updates detection
- User apps categorization
- Updated help documentation"
    
    echo -e "${GREEN}✅ Files committed${NC}"
fi

echo ""
echo "To push to GitHub, run:"
echo -e "${BLUE}  git remote add origin https://github.com/snap-star/better-dnf.git${NC}"
echo -e "${BLUE}  git push -u origin main${NC}"
echo ""

if prompt_yes_no "Add remote and push now?"; then
    git remote add origin https://github.com/snap-star/better-dnf.git 2>/dev/null || true
    git push -u origin main
    echo -e "${GREEN}✅ Code pushed to GitHub${NC}"
fi

# ============================================
# PART 5: Configure GitHub Secrets
# ============================================
print_section "PART 5: Configure GitHub Secrets"

echo "GitHub Actions requires secrets for COPR and PyPI publishing."
echo ""

# COPR Secret
echo -e "${YELLOW}Setting up COPR secret...${NC}"
echo ""
echo "Steps:"
echo "1. Go to: ${BLUE}https://copr.fedorainfracloud.org/api/${NC}"
echo "2. Copy the contents of your COPR config"
echo "3. Go to: ${BLUE}https://github.com/snap-star/better-dnf/settings/secrets/actions${NC}"
echo "4. Click 'New repository secret'"
echo "5. Name: ${YELLOW}COPR_CONFIG${NC}"
echo "6. Value: Paste your COPR config"
echo ""

read -p "Press Enter after adding COPR_CONFIG secret..."

# PyPI Secret
echo ""
echo -e "${YELLOW}Setting up PyPI secret (optional)...${NC}"
echo ""
echo "Steps:"
echo "1. Go to: ${BLUE}https://pypi.org/manage/account/token/${NC}"
echo "2. Create a new API token"
echo "3. Go to: ${BLUE}https://github.com/snap-star/better-dnf/settings/secrets/actions${NC}"
echo "4. Click 'New repository secret'"
echo "5. Name: ${YELLOW}PYPI_API_TOKEN${NC}"
echo "6. Value: Paste your PyPI token"
echo ""

if prompt_yes_no "Do you want to add PyPI secret now?"; then
    read -p "Press Enter after adding PYPI_API_TOKEN secret..."
fi

# ============================================
# PART 6: Create First Release
# ============================================
print_section "PART 6: Create First Release"

echo "Creating a release will trigger automatic COPR build."
echo ""

if prompt_yes_no "Create release v1.0.0 now?"; then
    echo ""
    echo "Creating git tag..."
    git tag -a v1.0.0 -m "Release v1.0.0 - First stable release"
    
    echo "Pushing tag..."
    git push origin v1.0.0
    
    echo ""
    echo -e "${GREEN}✅ Release created!${NC}"
    echo ""
    echo "GitHub Actions will now:"
    echo "  1. Run CI tests"
    echo "  2. Build the package"
    echo "  3. Create GitHub release"
    echo "  4. Trigger COPR build"
    echo ""
    echo "Monitor at: ${BLUE}https://github.com/snap-star/better-dnf/actions${NC}"
fi

# ============================================
# PART 7: Summary
# ============================================
print_section "SETUP COMPLETE! 🎉"

echo "Next steps:"
echo ""
echo "1. ${GREEN}Monitor COPR build:${NC}"
echo "   https://copr.fedorainfracloud.org/coprs/snap-star/better-dnf/builds/"
echo ""
echo "2. ${GREEN}Users can install with:${NC}"
echo "   sudo dnf copr enable snap-star/better-dnf"
echo "   sudo dnf install better-dnf"
echo ""
echo "3. ${GREEN}For future releases:${NC}"
echo "   - Update version in pyproject.toml and __init__.py"
echo "   - Commit changes"
echo "   - Create tag: git tag v1.1.0"
echo "   - Push tag: git push origin v1.1.0"
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
