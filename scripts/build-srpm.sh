#!/bin/bash
# Build Script for Better DNF SRPM
# This script creates a Source RPM for COPR submission

set -e

echo "🔧 Building Better DNF SRPM..."

# Navigate to project root
cd "$(dirname "$0")/.."

# Get version from pyproject.toml
VERSION=$(grep -oP 'version = "\K[^"]+' pyproject.toml)
echo "📦 Version: $VERSION"

# Clean previous builds
rm -rf dist/ build/ *.egg-info/ rpmbuild/

# Create source tarball
echo "📦 Creating source tarball..."
python -m build --sdist

# Create RPM build directory structure
echo "📁 Setting up RPM build directory..."
mkdir -p rpmbuild/{BUILD,RPMS,SOURCES,SPECS,SRPMS}

# Copy source tarball
cp dist/better-dnf-${VERSION}.tar.gz rpmbuild/SOURCES/

# Copy spec file
cp better-dnf.spec rpmbuild/SPECS/

# Build SRPM
echo "🔨 Building SRPM..."
rpmbuild -bs rpmbuild/SPECS/better-dnf.spec \
    --define "_sourcedir $(pwd)/rpmbuild/SOURCES" \
    --define "_specdir $(pwd)/rpmbuild/SPECS" \
    --define "_srpmdir $(pwd)/rpmbuild/SRPMS"

echo ""
echo "✅ SRPM built successfully!"
echo "📁 Location: rpmbuild/SRPMS/better-dnf-${VERSION}-1.fc*.src.rpm"
echo ""
echo "📋 Next steps:"
echo "1. Upload to COPR: copr-cli build snap-star/better-dnf rpmbuild/SRPMS/better-dnf-*.src.rpm"
echo "2. Or build from PyPI: copr-cli build snap-star/better-dnf pypi:better-dnf==${VERSION}"
