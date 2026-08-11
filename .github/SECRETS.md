# 🔐 GitHub Actions Secrets Setup

This document explains how to configure the required secrets for GitHub Actions workflows.

## Required Secrets

| Secret | Purpose | Where to get it |
|--------|---------|-----------------|
| `COPR_CONFIG` | COPR CLI authentication | Fedora COPR API page |

> 💡 No PyPI token is needed: the COPR workflow builds from the GitHub release tag (SCM build), so `COPR_CONFIG` is the only required secret.

---

## 🔧 Setting up COPR_CONFIG

### Step 1: Create Fedora Account

1. Go to [accounts.fedoraproject.org](https://accounts.fedoraproject.org/)
2. Create an account with username: `snap-star`

### Step 2: Get COPR API Token

1. Go to [copr.fedorainfracloud.org](https://copr.fedorainfracloud.org/)
2. Login with your Fedora account
3. Go to your [API settings page](https://copr.fedorainfracloud.org/api/)
4. Copy the contents of your `~/.config/copr` file

The file should look like this:
```ini
[copr]
username = snap-star
token = your-api-token-here
login = snap-star
```

### Step 3: Add to GitHub Secrets

1. Go to your GitHub repository: `https://github.com/snap-star/better-dnf`
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `COPR_CONFIG`
5. Value: Paste the contents of your `~/.config/copr` file
6. Click **Add secret**

⚠️ **Note:** COPR API tokens expire after 180 days. You'll need to regenerate and update the secret periodically.

---

## 🚀 Creating a Release

Once secrets are configured, creating a release is simple:

```bash
# Update version in files
sed -i 's/version = "1.0.0"/version = "1.1.0"/' pyproject.toml
sed -i 's/__version__ = "1.0.0"/__version__ = "1.1.0"/' src/better_dnf/__init__.py

# Commit changes
git add .
git commit -m "Bump version to 1.1.0"

# Create and push tag
git tag v1.1.0
git push origin main --tags
```

This will automatically:
1. ✅ Run CI tests
2. ✅ Build the package
3. ✅ Create GitHub release
4. ✅ Trigger the COPR build — built straight from the GitHub tag, so no PyPI upload is needed

---

## 🔍 Verifying the Setup

### Check COPR Build

1. Go to [COPR builds](https://copr.fedorainfracloud.org/coprs/snap-star/better-dnf/builds/)
2. You should see a new build triggered by the release

### Check GitHub Release

1. Go to [GitHub Releases](https://github.com/snap-star/better-dnf/releases)
2. You should see the new release with attached artifacts

---

## 🛠️ Troubleshooting

### Build Failed

1. Check the [COPR build logs](https://copr.fedorainfracloud.org/coprs/snap-star/better-dnf/builds/)
2. Common issues:
   - Missing dependencies
   - Spec file errors
   - Version mismatches

### Authentication Errors

1. Verify the secret is correctly formatted
2. Check if the COPR token has expired (180 days)
3. Regenerate the token if needed

### Version Mismatch

Ensure version is updated in all these files:
- `pyproject.toml`
- `src/better_dnf/__init__.py`
- `better-dnf.spec`

---

## 📚 Resources

- [Fedora COPR Documentation](https://docs.copr.fedorainfracloud.org/)
- [PyPI Publishing Guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [GitHub Actions Secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
