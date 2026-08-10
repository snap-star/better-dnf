# Contributing to Better DNF

Thank you for your interest in contributing! This document provides guidelines and information for contributors.

## 🎯 How to Contribute

### Reporting Bugs

1. Check [existing issues](https://github.com/snap-star/better-dnf/issues) first
2. Create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - System information (Fedora version, Python version)
   - Screenshots if applicable

### Suggesting Features

1. Open a [new issue](https://github.com/snap-star/better-dnf/issues/new) with the `feature` label
2. Describe the problem you're trying to solve
3. Explain your proposed solution
4. Consider alternatives

### Code Contributions

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Add tests if applicable
5. Run the test suite: `pytest`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

## 🛠️ Development Setup

### Prerequisites

- Python 3.9 or higher
- pip or poetry
- Git
- Fedora Linux (for testing)

### Setting Up Development Environment

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/better-dnf.git
cd better-dnf

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Verify installation
better-dnf version
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=better_dnf

# Run specific test file
pytest tests/test_parser.py

# Run with verbose output
pytest -v
```

### Code Quality

We use several tools to maintain code quality:

```bash
# Format code
black .

# Check for issues
ruff check .

# Type checking
mypy src/

# Run all checks
pre-commit run --all-files
```

## 📝 Code Style

### Python Style Guide

- Follow [PEP 8](https://peps.python.org/pep-0008/)
- Use type hints for all function parameters and return values
- Write docstrings for all public functions and classes
- Keep functions focused and small (under 50 lines when possible)

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat: Add support for dnf5
fix: Handle empty check-update output
docs: Update installation instructions
test: Add parser unit tests
```

### Pull Request Guidelines

1. **Keep PRs focused**: One feature or fix per PR
2. **Write clear descriptions**: Explain what and why, not just how
3. **Add tests**: New features should include tests
4. **Update documentation**: If adding features, update README
5. **Follow code style**: Run linters before submitting

## 🧪 Testing

### Writing Tests

```python
# tests/test_example.py
import pytest
from better_dnf.parser import DNFParser

def test_parse_check_update():
    """Test parsing check-update output."""
    output = "package.x86_64    fedora    1.0.0-1"
    packages = DNFParser.parse_check_update(output)
    assert len(packages) == 1
    assert packages[0].name == "package"

@pytest.mark.parametrize("category,expected", [
    ("kernel", UpdateCategory.KERNEL),
    ("nvidia-driver", UpdateCategory.DRIVER),
])
def test_categorize_package(category, expected):
    """Test package categorization."""
    package = PackageUpdate(
        name=category,
        arch="x86_64",
        old_version="1.0.0",
        new_version="1.0.1",
        repository="fedora",
    )
    result = DNFParser.categorize_package(package)
    assert result == expected
```

### Running Specific Tests

```bash
# Test parser module
pytest tests/test_parser.py -v

# Test analyzer module
pytest tests/test_analyzer.py -v

# Test with coverage report
pytest --cov=better_dnf --cov-report=html
```

## 📚 Documentation

### Writing Documentation

- Use clear, concise language
- Include code examples
- Add screenshots for UI changes
- Update README for new features

### Building Documentation

```bash
# Install documentation dependencies
pip install mkdocs mkdocs-material

# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

## 🐛 Debugging

### Common Issues

1. **Permission denied errors**: The tool needs sudo for DNF commands
2. **Btrfs not detected**: Check if your root filesystem is btrfs
3. **Missing dependencies**: Run `pip install -e ".[dev]"`

### Debug Mode

```bash
# Run with debug output
better-dnf analyze --debug

# Check system information
better-dnf version
```

## 🎨 UI/UX Guidelines

### Terminal Output

- Use Rich library for formatting
- Provide clear visual hierarchy
- Use colors consistently:
  - Red: Critical/errors
  - Yellow: Warnings
  - Green: Success
  - Cyan: Information
- Include progress indicators for long operations

### Interactive Prompts

- Use Questionary for user input
- Provide sensible defaults
- Confirm destructive actions
- Show preview before applying changes

## 📋 Checklist

Before submitting a PR:

- [ ] Code follows style guidelines
- [ ] Tests pass (`pytest`)
- [ ] Linters pass (`ruff check .`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions
- [ ] PR description is clear and complete

## 🙏 Thank You!

Thank you for contributing to Better DNF! Your help makes this tool better for everyone in the Fedora community.