# 🤝 Contributing to Abaqus Data Bridge

Thank you for your interest in contributing to ADB! This document outlines the process and guidelines.

## Code of Conduct

- Be respectful and inclusive
- Focus on the technical merits of contributions
- Help others learn and grow

## How to Contribute

### 🐛 Reporting Bugs

1. Search [existing issues](https://github.com/RONGJI19/abaqus-data-bridge/issues) first
2. Include:
   - ADB version (`adb --version`)
   - Python version (`python --version`)
   - Operating system
   - Abaqus version that generated the files
   - Minimal `.inp`/`.dat` files to reproduce (if possible)
   - Full error message with `--debug` flag

### 💡 Feature Requests

1. Check the [Roadmap](README.md#-路线图--roadmap) for planned features
2. Describe the use case and why it matters
3. If possible, attach example INP/DAT snippets showing the desired output

### 🔧 Pull Requests

#### Setup

```bash
# Fork and clone
git clone https://github.com/YOUR_USER/abaqus-data-bridge.git
cd abaqus-data-bridge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install in dev mode
pip install -e ".[all,dev]"

# Run tests to verify setup
pytest tests/ -v
```

#### Development Workflow

1. **Create a branch**: `git checkout -b feature/your-feature`
2. **Make changes**: Follow the [Architecture Guide](ARCHITECTURE.md)
3. **Write tests**: Every new feature needs test coverage
4. **Run tests**: `pytest tests/ -v` — all tests must pass
5. **Run lint**: `ruff check adb/ tests/`
6. **Commit**: Use clear, descriptive commit messages
7. **Push**: Open a PR against the `main` branch

#### Code Style

- Follow PEP 8
- Use type hints for all function signatures
- Use `dataclasses` for data structures
- Use `logging` instead of `print()`
- Keep functions focused and under 50 lines
- Write docstrings in Google style

#### Commit Messages

```
type(scope): Brief description

- Detailed bullet points if needed
- Reference issue numbers (#123)
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

### 📚 Documentation

- User-facing docs: `docs/` directory (Chinese + English)
- Code docs: docstrings within Python files
- Architecture docs: `ARCHITECTURE.md`
- README: Keep the quick-start section concise

### 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=adb --cov-report=term-missing

# Run specific test file
pytest tests/test_inp_parser.py -v

# Run tests matching a pattern
pytest tests/ -v -k "contact"
```

### 📦 Adding New Parsers

If you're adding support for a new INP keyword or DAT output type:

1. **INP Keywords**: Add a handler to `_DISPATCH` dict in `inp_parser.py`
2. **DAT Tables**: Add detection logic to the state machine in `dat_parser.py`
3. **Classification**: Update `_classify_table_variables()` in `matcher.py`
4. **Config**: Update `VariableConfig` in `extraction_config.py`
5. **CLI**: Add variable mapping in `cli.py`
6. **GUI**: Add checkbox in `gui.py` `VARIABLE_GROUPS`
7. **Tests**: Add test fixture files and test case

### 🏷️ Adding Abaqus Version Patterns

1. Add new patterns to `version_patterns.py`
2. The pattern format is: `(compiled_regex, version_label)`
3. Patterns are tried in order — put more specific patterns first
4. Add a test fixture from the target Abaqus version

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture and module guide.

## Questions?

- Open a [GitHub Discussion](https://github.com/RONGJI19/abaqus-data-bridge/discussions)
- Check the [User Guide (中文)](docs/user_guide_zh.md)
- Read the [Requirements Specification](REQUIREMENTS_SPECIFICATION.md)

Thank you for contributing! 🎉
