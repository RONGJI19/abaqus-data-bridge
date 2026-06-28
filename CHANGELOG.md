# Changelog

All notable changes to Abaqus Data Bridge (ADB) are documented in this file.

## [Unreleased] — 2026-06-28

### 🔧 GUI Workflow Improvements
- Reworked the desktop GUI into a single-screen left/right split layout that uses wide displays more effectively.
- Left side: file selection, pre-analysis entry point, variable presets, and filters.
- Right side: pre-analysis results, output options, run controls, progress, and logs.
- Added variable presets for nodal, element, contact, and spring result groups.
- Added Step filtering to the GUI.
- Enhanced pre-analysis so users can select Steps, NSETs, and ELSETs from parsed model data and apply them to extraction filters.
- Added output controls for CSV/TSV, encoding, decimal places, metadata, node coordinates, and merged output.
- Added automatic `<inp_stem>_adb_output` output directory generation.
- Added an "open output directory" action after successful extraction.

### 📦 Packaging
- Split GUI and CLI PyInstaller specs into true independent entry points.
- `python build_exe.py` now builds both `ADB_GUI.exe` and `ADB_CLI.exe`; `--gui` and `--cli` build only one target.
- Renamed the CLI executable target to `ADB_CLI.exe`.
- Disabled Windows `strip` for the CLI build to avoid noisy non-actionable packaging warnings.

### 🧪 Verification
- Full test suite: 66 passed.
- Verified CLI EXE startup and sample extraction.

## [0.1.0] — 2026-06-28

### 🎉 Initial Release

#### Parsers
- **INP Parser** (`adb/parsers/inp_parser.py`)
  - State-machine streaming parser for Abaqus `.inp` files
  - Supports `*NODE`, `*NODE GENERATE`, `*ELEMENT`, `*NSET`, `*ELSET`, `*HEADING`, `*INCLUDE`
  - Continuation line handling (trailing comma)
  - Encoding auto-detection with fallback chain
  - `GENERATE` syntax with linear coordinate interpolation

- **DAT Parser** (`adb/parsers/dat_parser.py`)
  - Multi-state state machine for Abaqus `.dat` result files
  - Supports `NODE OUTPUT`, `ELEMENT OUTPUT`, `CONTACT OUTPUT` table types
  - Multi-line header accumulation and variable name extraction
  - Entity type detection (SPRINGA, C3D8R, S4R, etc.)
  - Step/Increment boundary detection
  - Analysis completion status detection
  - Job time summary extraction
  - Sub-table boundary detection for multi-set outputs

- **Multi-Version Patterns** (`adb/parsers/version_patterns.py`)
  - Compiled regex patterns for Abaqus 2016–2025 format variations
  - Fallback pattern support for unknown versions

#### Models
- **InpModel** — Nodes, Elements, NSETs, ELSETs
- **DatResults** — Steps, Increments, ResultTables, ResultRows
- **ExtractionConfig** — Hierarchical config (filters, output, variables, advanced)

#### Core Engine
- **ExtractionEngine** — Full pipeline orchestrator (parse → match → export)
- **Data Matcher** — Set-based filtering, variable classification, coordinate attachment
- **Statistics** — Min/max/mean/std computation per variable
- Crash-proof debug logging for production diagnostics

#### Exporters
- **CSV Exporter** — Metadata headers, configurable encoding, per-set file export
- **Streaming CSV** — Chunked writing (10K rows/flush) for large models (1M+ rows)

#### CLI (Click-based)
- `adb extract` — Main extraction command (config file + CLI args)
- `adb inspect` — DAT file content inspector
- `adb list-sets` — INP set lister (NSET/ELSET)
- `adb wizard` — Interactive configuration wizard
- `adb batch` — Multi-job batch processor
- `adb stats` — Numerical statistics per variable

#### GUI (PySide6, optional)
- File drag-and-drop support for `.inp`/`.dat`
- Pre-analysis: inspect model structure before extraction
- Set checkboxes with visual selection
- Background extraction thread with progress bar
- Auto output directory from INP path
- Timestamped log panel

#### Utilities
- **Fortran Number Parser** — `parse_fortran_float()` supporting D/E/exponent variants
- **Encoding Detector** — Auto-detection with `chardet` + fallback chain
- **Progress Bar** — Unified `tqdm`-compatible progress interface
- **Crash-Proof Logger** — Immediate-flush debug logging

#### Supported Result Types
| Category | Variables |
|----------|-----------|
| Nodal Displacement | U1, U2, U3, UR1, UR2, UR3 |
| Reaction Force | RF1, RF2, RF3 |
| Element Stress | S11–S33, S12–S23, Mises, Principal |
| Element Strain | E11–E33, E12–E23 |
| Contact Force | CNORMF, CSHEARF1, CSHEARF2 |
| Contact Stress | CPRESS, CSHEAR1, CSHEAR2 |
| Contact Displacement | COPEN, CSLIP1, CSLIP2 |
| Spring Force/Displacement | S11 (force), E11 (relative displacement) |
| Section Force/Moment | SF1–SF3, SM1–SM3 |

#### Build & Packaging
- `pyproject.toml` with setuptools build
- Optional dependency groups: `gui`, `tqdm`, `chardet`, `xlsx`, `all`, `dev`
- Entry points: `adb` (CLI), `adb-gui` (GUI)
- PyInstaller support for standalone EXE generation

#### CI/CD
- GitHub Actions: Multi-OS (Windows, macOS, Linux), Multi-Python (3.10–3.13) test matrix
- Ruff linting
- PyPI publish workflow on release

#### Documentation
- Bilingual README (Chinese + English)
- Chinese user guide (`docs/user_guide_zh.md`)
- INP/DAT format reference guide (`docs/abaqus_inp_dat_format_guide.md`)
- Requirements specification (`REQUIREMENTS_SPECIFICATION.md`)
- Architecture guide (`ARCHITECTURE.md`)
- Contribution guide (`CONTRIBUTING.md`)

#### Test Suite
- 66 passing tests across 6 test files
- Test fixtures: truss, spring, contact, beam models
- Unit tests: parsers, utilities, models
- Integration tests: full pipeline
- Contact-specific tests

---

## Legend

- 🎉 New feature
- 🔧 Improvement
- 🐛 Bug fix
- 📚 Documentation
- 🧪 Testing
- ⚡ Performance
