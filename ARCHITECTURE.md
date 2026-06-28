# 🏗️ Abaqus Data Bridge — Architecture & Development Guide

> Detailed architecture, data flow, design decisions, and development workflow for the ADB project.

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Philosophy](#2-architecture-philosophy)
3. [System Architecture](#3-system-architecture)
4. [Module Details](#4-module-details)
5. [Data Flow](#5-data-flow)
6. [Key Algorithms](#6-key-algorithms)
7. [Design Decisions](#7-design-decisions)
8. [Development Workflow](#8-development-workflow)
9. [Testing Strategy](#9-testing-strategy)
10. [Performance & Optimization](#10-performance--optimization)

---

## 1. Project Overview

**Abaqus Data Bridge (ADB)** is a pure-Python tool that extracts finite element analysis results from Abaqus `.inp` input files and `.dat` output files into structured CSV format — **without requiring an Abaqus license**.

### Core Value Proposition

| Traditional Approach | ADB Approach |
|---------------------|--------------|
| Requires Abaqus license + ODB API | Pure text parsing, standard library only |
| Manual copy-paste from DAT files | One-click CLI-driven extraction |
| Writing `odbAccess` scripts (high barrier) | CLI + YAML config, zero code needed |
| No tooling for contact/spring forces | Built-in CNORMF/CPRESS/Spring S11 parsers |

---

## 2. Architecture Philosophy

### Design Principles

1. **Zero Abaqus Dependency**: Parse `.inp` and `.dat` as plain text — no Abaqus installation, no license, no ODB API.
2. **Layered Separation**: Parsers → Models → Core Engine → Exporters → CLI/GUI. Each layer is independently testable.
3. **Streaming-First**: State-machine parsers process files line-by-line, supporting models with 1M+ nodes without memory issues.
4. **Graceful Degradation**: Invalid data lines are skipped with warnings, not crashes. Encoding errors trigger automatic fallback.
5. **Configurable Everything**: CLI flags override YAML config values, which override sensible defaults.

### Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Language | Python 3.10+ | Ubiquitous in CAE; excellent text processing |
| CLI | Click | Mature, decorator-based, auto help generation |
| YAML | PyYAML | Configuration file standard |
| CSV | stdlib `csv` | Zero-dependency CSV writing |
| Regex | stdlib `re` | Core of DAT parsing |
| Data Models | `dataclasses` | Lightweight, typed data structures |
| GUI | PySide6 (optional) | Cross-platform desktop GUI |
| Testing | pytest | Industry-standard Python testing |
| Packaging | setuptools + PyPI | Standard distribution |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       CLI / GUI Layer                             │
│  adb extract | inspect | list-sets | wizard | batch | stats      │
│  adb-gui (PySide6 desktop app)                                    │
├──────────────────────────────────────────────────────────────────┤
│                     Configuration Layer                            │
│  YAML → ExtractionConfig (dataclass with nested config objects)   │
├──────────────────────────────────────────────────────────────────┤
│                       Core Engine                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  INP Parser  │  │  DAT Parser  │  │    Data Matcher       │  │
│  │  (state      │  │  (state      │  │  (Set × Step ×        │  │
│  │   machine)   │  │   machine)   │  │   Increment →         │  │
│  │              │  │              │  │   filtered records)    │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                 │                      │               │
│         ▼                 ▼                      ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │  InpModel    │  │  DatResults  │  │    CSV Exporter       │  │
│  │  (nodes,     │  │  (steps,     │  │    (metadata + data   │  │
│  │   elements,  │  │   increments,│  │     + streaming)      │  │
│  │   sets)      │  │   tables)    │  │                       │  │
│  └──────────────┘  └──────────────┘  └───────────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│                       Utilities Layer                             │
│  Fortran Number Parser | Encoding Detector | Progress Bar        │
│  Crash-Proof Logger | Version Pattern Matcher                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Module Details

### 4.1 `adb/parsers/` — File Parsers

#### `inp_parser.py` — INP File Parser

**Parsing Strategy**: State machine with line-by-line streaming.

**States**:
```
SCANNING → got *KEYWORD → IN_KEYWORD → accumulate data lines
  ↑                                        ↓
  └────────── next *KEYWORD ←── flush() ──┘
```

**Supported Keywords**:
| Keyword | Handler | Output |
|---------|---------|--------|
| `*NODE` | `_process_node_data()` | `Node(id, x, y, z)` |
| `*NODE, GENERATE` | `_process_node_generate()` | Linearly interpolated nodes |
| `*ELEMENT` | `_process_element_data()` | `Element(id, type, connectivity)` |
| `*NSET` | `_process_set_data(set_type="NSET")` | Set name → node IDs |
| `*ELSET` | `_process_set_data(set_type="ELSET")` | Set name → element IDs |
| `*HEADING` | `_process_heading_data()` | Job name extraction |
| `*INCLUDE` | `_process_include()` | Warning logged |

**Key Features**:
- Continuation line handling (lines ending with `,`)
- `GENERATE` syntax support with linear interpolation
- Encoding auto-detection with fallback to `latin-1`

#### `dat_parser.py` — DAT Result Parser

**Parsing Strategy**: Multi-state state machine with table-header buffering.

**States**:
```
SCANNING (find Step/Increment/Table markers)
    ↓
TABLE_HEADER (accumulate multi-line headers until data line detected)
    ↓
TABLE_DATA (parse data rows until table-end marker or blank line)
    ↓
commit_table() → back to SCANNING
```

**Supported Output Types**:
| Type | Detection | Variables |
|------|-----------|-----------|
| `NODE_OUTPUT` | `N O D E   O U T P U T` | U1~U3, UR1~UR3, RF1~RF3 |
| `ELEMENT_OUTPUT` | `E L E M E N T   O U T P U T` | S11~S33, E11~E33, MISES |
| `CONTACT_OUTPUT` | `C O N T A C T   O U T P U T` | CNORMF, CPRESS, COPEN, CSLIP |

**Key Algorithms**:
- **Header parsing**: Accumulate header lines until a data line (starts with digit) is detected. Extract variable names from header tokens.
- **Entity type detection**: Differentiate element types (SPRINGA, C3D8R) from variables (S11, U1) by analyzing character patterns (digit-between-letters → element type).
- **Contact surface parsing**: Detect MASTER/SLAVE surface descriptions within CONTACT OUTPUT blocks.
- **Variable name remapping**: Placeholder `V0, V1, ...` keys remapped to real variable names during `commit_table()`.

#### `version_patterns.py` — Multi-Version Pattern Library

Compiles regex patterns for different Abaqus versions (2016–2025) to handle format variations in:
- Output section headers
- Completion status markers
- Table boundary indicators

### 4.2 `adb/models/` — Data Models

#### `inp_model.py`
```python
@dataclass
class InpModel:
    nodes: Dict[int, Node]          # node_id → Node(x,y,z)
    elements: Dict[int, Element]    # elem_id → Element(type, connectivity)
    nsets: Dict[str, List[int]]    # set_name → [node_ids]
    elsets: Dict[str, List[int]]   # set_name → [elem_ids]
```

#### `dat_model.py`
```python
@dataclass
class DatResults:
    steps: Dict[str, StepResult]
    # StepResult → {increment_num: IncrementResult}
    # IncrementResult → [ResultTable, ...]
    # ResultTable → {variable_names, data: [ResultRow, ...]}
    # ResultRow → {entity_id, values: {var_name: float}}
```

#### `extraction_config.py`
Hierarchical dataclass configuration:
```
ExtractionConfig
├── FilterConfig (node_sets, element_sets, steps, increments, bbox)
├── OutputConfig (format, encoding, delimiter, metadata, decimal_places)
├── VariableConfig (nodal, element, contact, spring, section)
└── AdvancedConfig (memory_limit, detect_incomplete, log_level)
```

### 4.3 `adb/core/` — Core Engine

#### `engine.py` — ExtractionEngine

Orchestrates the full pipeline:
```
1. Parse INP  →  InpModel
2. Parse DAT  →  DatResults
3. Check completion status
4. Match results to sets  →  {group_name: [records]}
5. Export CSV  →  files written to output_dir
6. Collect statistics  →  ExtractionSummary
```

#### `matcher.py` — Data Matcher

Cross-references DAT results with INP model topology:
- Resolves increment filters (`"last"`, `"all"`, `[1,3,5]`)
- Filters nodes by bounding box
- Matches result tables to user-specified sets
- Classifies table variables into types (U, RF, S, CNORMF, etc.)
- Special handling for spring elements (S11 = force, not stress)

#### `statistics.py` — Statistics Computer

Computes min, max, mean, std for each variable in result tables.

### 4.4 `adb/exporters/` — Output Exporters

#### `csv_exporter.py` — Standard CSV Exporter

- Writes metadata headers (`#`-prefixed lines)
- Auto-detects column order: `ENTITY_ID → X/Y/Z → variable columns`
- Supports configurable encoding, delimiter, decimal places
- Supports merged (single-file) or per-group export modes

#### `streaming.py` — Streaming CSV Exporter

- Chunked writing (10K rows per flush) for large models
- Iterator-based consumption — never loads all data at once
- Same output format as the standard exporter

### 4.5 `adb/utils/` — Utilities

#### `fortran.py` — Fortran Number Parser

Parses Fortran-style scientific notation used in DAT files:
- `1.234E+02` → 123.4
- `0.1234D+02` → 12.34 (double precision)
- `-1.234-02` → -0.01234 (omitted E)
- `**********` → NaN (overflow/undefined)

#### `encoding.py` — Encoding Detector

Auto-detects file encoding using `chardet` (optional) with fallback chain:
`utf-8 → gbk → cp1252 → latin-1`

#### `logging.py` — Crash-Proof Logger

Writes diagnostic logs with immediate flush to survive crashes during extraction.

#### `progress.py` — Progress Bar Wrapper

Unified progress bar interface with optional `tqdm` support.

---

## 5. Data Flow

```
                    ┌──────────────┐
                    │  config.yaml │ (or CLI args)
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                                     ▼
┌────────────────┐                    ┌────────────────┐
│  INP Parser    │                    │  DAT Parser    │
│                │                    │                │
│ 1. State       │                    │ 1. State       │
│    machine     │                    │    machine     │
│ 2. Keyword     │                    │ 2. Table       │
│    matching    │                    │    detection   │
│ 3. Data line   │                    │ 3. Header      │
│    parsing     │                    │    parsing     │
│ 4. Set         │                    │ 4. Fortran     │
│    expansion   │                    │    number      │
│                │                    │    parsing     │
└───────┬────────┘                    └───────┬────────┘
        │                                     │
        ▼                                     ▼
┌────────────────┐                    ┌────────────────┐
│  InpModel      │                    │  DatResults    │
│  .nodes        │                    │  .steps        │
│  .elements     │                    │   └─ increments│
│  .nsets        │                    │      └─ tables │
│  .elsets       │                    │         └─ data│
└───────┬────────┘                    └───────┬────────┘
        │                                     │
        └──────────────┬──────────────────────┘
                       │
                       ▼
             ┌──────────────────┐
             │  Data Matcher    │
             │  • Set ID lookup │
             │  • BBox filter   │
             │  • Variable      │
             │    classification│
             │  • Coordinate    │
             │    attachment    │
             └────────┬─────────┘
                      │
                      ▼
             ┌──────────────────┐
             │  CSV Exporter    │
             │  • Metadata write│
             │  • Column order  │
             │  • Format values │
             │  • Batch export  │
             └────────┬─────────┘
                      │
                      ▼
               ┌──────────────┐
               │  output/     │
               │  ├─ Step-1_  │
               │  │  incr1_   │
               │  │  SET_U.csv│
               │  └─ ...      │
               └──────────────┘
```

---

## 6. Key Algorithms

### 6.1 Continuation Line Joining

Abaqus INP files use trailing commas to indicate continuation:

```python
def _join_continuations(lines: List[str]) -> List[str]:
    """
    ['1, 2, 3,', '4, 5, 6']  →  ['1, 2, 3,4, 5, 6']
    """
    result = []
    current = ""
    for line in lines:
        stripped = line.strip()
        current = (current + stripped) if current else stripped
        if not current.endswith(","):
            result.append(current)
            current = ""
    return result
```

### 6.2 Variable Name Extraction from Headers

DAT headers span multiple lines. Variable extraction:
1. Collect all header lines
2. Tokenize each line
3. Filter out known non-variable words (NODE, ELEMENT, FOOT, NOTE, etc.)
4. Keep tokens matching `[A-Za-z][A-Za-z0-9_]*` pattern, ≤ 12 chars
5. Filter out pure numbers

### 6.3 Entity Type Detection

Differentiates element types (SPRINGA, C3D8R) from variable names (S11, U1):
- Variable = letter prefix + number suffix (S11, U1)
- Element type = letters and numbers interleaved (C3D8R, S4R)
- Heuristic: detect a digit between two letters → element type

### 6.4 Spring Force Semantic Override

The S11 variable has two meanings depending on context:
- **Continuum/Shell elements**: S11 = stress (MPa)
- **Spring elements (SPRINGA/SPRING1/SPRING2)**: S11 = force (N)

The matcher checks `table.entity_type` — if it contains "SPRING", S11 is classified as `SPRING_S11` (force) rather than `S` (stress).

---

## 7. Design Decisions

### 7.1 Why State Machines Instead of a Full Parser Generator?

**Decision**: Custom state machines over ANTLR/Lark/PLY.

**Rationale**:
- INP/DAT formats are semi-structured, not regular grammars
- State machines handle real-world format variations better
- Zero additional dependencies
- Easier to debug and extend for new keywords

### 7.2 Why Dataclasses Instead of Pydantic?

**Decision**: `@dataclass` over Pydantic models.

**Rationale**:
- Zero-dependency requirement
- Sufficient for internal data structures
- Faster instantiation for large models
- Serializable via `dataclasses.asdict()`

### 7.3 Why Click Instead of argparse?

**Decision**: Click over argparse.

**Rationale**:
- Decorator-based API is cleaner for nested commands
- Auto-generated `--help` is more readable
- Better support for subcommand groups (`adb extract`, `adb inspect`, etc.)
- Lazy loading of subcommands

### 7.4 Why Not Use pandas?

**Decision**: Standard library `csv` module over pandas.

**Rationale**:
- pandas is a heavy dependency (~30MB)
- Our use case is simple CSV writing, not data analysis
- Streaming export for large models is easier with raw csv
- Users who want DataFrames can `pd.read_csv()` the output

### 7.5 Multi-Version Compatibility Strategy

**Decision**: Compile multiple regex patterns per marker, try each.

**Rationale**:
- Abaqus 2016–2025 format variations are mostly whitespace/capitalization
- A pattern library is maintainable and extensible
- Users can contribute patterns for their version
- Fallback patterns catch unknown variations

---

## 8. Development Workflow

### 8.1 Project Structure

```
D:\Project5_Abaqus\
├── adb/                    # Main package
│   ├── __init__.py         # Version, package metadata
│   ├── cli.py              # Click CLI (adb command)
│   ├── gui.py              # PySide6 desktop GUI (adb-gui)
│   ├── parsers/            # File parsers
│   │   ├── inp_parser.py   # INP → InpModel
│   │   ├── dat_parser.py   # DAT → DatResults
│   │   └── version_patterns.py  # Multi-version patterns
│   ├── models/             # Data models
│   │   ├── inp_model.py    # Node, Element, InpModel
│   │   ├── dat_model.py    # ResultTable, DatResults
│   │   └── extraction_config.py  # Full config hierarchy
│   ├── core/               # Core engine
│   │   ├── engine.py       # ExtractionEngine (orchestrator)
│   │   ├── matcher.py      # Data matching & filtering
│   │   └── statistics.py   # Statistical computation
│   ├── exporters/          # Output exporters
│   │   ├── csv_exporter.py # Standard CSV export
│   │   └── streaming.py    # Streaming CSV for large models
│   ├── utils/              # Utilities
│   │   ├── fortran.py      # Fortran number parser
│   │   ├── encoding.py     # Encoding detection
│   │   ├── progress.py     # Progress bar
│   │   └── logging.py      # Crash-proof debug logger
│   └── templates/          # Templates
│       └── config_template.yaml
├── tests/                  # Test suite
│   ├── fixtures/           # Test INP/DAT files
│   │   ├── simple_truss.inp / .dat
│   │   ├── spring_model.inp / .dat
│   │   ├── contact_model.inp / .dat
│   │   └── beam_sf.inp / .dat
│   ├── test_inp_parser.py
│   ├── test_dat_parser.py
│   ├── test_integration.py
│   ├── test_contact.py
│   ├── test_utils.py
│   └── test_debug_logging.py
├── examples/               # Usage examples
│   ├── extract_truss.py
│   ├── extract_spring.py
│   ├── extract_contact.py
│   └── batch_extract.py
├── docs/                   # Documentation
│   ├── user_guide_zh.md    # Chinese user guide
│   └── abaqus_inp_dat_format_guide.md  # INP/DAT format reference
├── .github/workflows/      # CI/CD
│   ├── test.yml            # Multi-OS, multi-Python test matrix
│   └── publish.yml         # PyPI publish on release
├── pyproject.toml          # Package metadata & build config
├── build_exe.py            # PyInstaller EXE builder
├── build_exe.bat           # Windows build script
├── run_cli.py              # Dev launcher
├── README.md               # Project README
├── ARCHITECTURE.md         # This file
├── CONTRIBUTING.md         # Contribution guide
├── CHANGELOG.md            # Version history
├── LICENSE                 # MIT License
└── REQUIREMENTS_SPECIFICATION.md  # Original requirements spec
```

### 8.2 Development Setup

```bash
# Clone
git clone https://github.com/YOUR_USER/abaqus-data-bridge.git
cd abaqus-data-bridge

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in dev mode with all dependencies
pip install -e ".[all,dev]"

# Run tests
pytest tests/ -v

# Run CLI in development
python -m adb.cli --help
```

### 8.3 Adding a New Result Type

1. **DAT Parser**: Add detection logic in `dat_parser.py` state machine
2. **Model**: Add any new fields to `dat_model.py` if needed
3. **Matcher**: Add classification logic in `_classify_table_variables()`
4. **Config**: Add variable to `VariableConfig` in `extraction_config.py`
5. **CLI**: Add variable mapping in `cli.py` `extract` command
6. **GUI**: Add checkbox in `gui.py` `VARIABLE_GROUPS`
7. **Tests**: Add test fixture `.inp`/`.dat` files and test case

### 8.4 Adding Support for a New Abaqus Version

1. Run a test extraction with the new version's DAT file
2. If parsing fails, add patterns to `version_patterns.py`
3. Add a test fixture file from the new version
4. Run the full test suite to check for regressions

---

## 9. Testing Strategy

### Test Pyramid

```
        ┌─────────┐
        │   E2E   │  test_integration.py — Full pipeline tests
        ├─────────┤
        │  Module │  test_contact.py — Contact-specific parsing
        │  Tests  │  test_debug_logging.py — Crash-proof logging
        ├─────────┤
        │  Unit   │  test_inp_parser.py — INP keyword parsing
        │  Tests  │  test_dat_parser.py — DAT table extraction
        │         │  test_utils.py — Fortran number parsing
        └─────────┘
```

### Test Fixtures

| Fixture | Purpose |
|---------|---------|
| `simple_truss.inp/.dat` | Basic truss: displacement, stress, reaction force |
| `spring_model.inp/.dat` | Spring elements: S11 force, E11 displacement |
| `contact_model.inp/.dat` | Contact pairs: CNORMF, CPRESS, COPEN, CSLIP |
| `beam_sf.inp/.dat` | Beam elements: section forces SF1~SF3, moments SM1~SM3 |

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_inp_parser.py -v

# With coverage
pytest tests/ --cov=adb --cov-report=html

# Run only integration tests
pytest tests/test_integration.py -v
```

---

## 10. Performance & Optimization

### 10.1 Streaming for Large Models

The INP and DAT parsers use line-by-line file reading (`for line in fh`), meaning they never load the entire file into memory. This supports models with 1M+ nodes on machines with limited RAM.

### 10.2 CSV Export Optimization

- **Standard mode**: All records loaded, written at once (fast for <100K rows)
- **Streaming mode** (`exporters/streaming.py`): Chunked writing (10K rows/flush) for 1M+ rows

### 10.3 Memory Usage Estimates

| Model Size | INP Memory | DAT Memory | Total Peak |
|-----------|-----------|-----------|------------|
| 1K nodes | ~1 MB | ~2 MB | ~5 MB |
| 10K nodes | ~5 MB | ~15 MB | ~25 MB |
| 100K nodes | ~40 MB | ~120 MB | ~200 MB |
| 1M nodes | ~400 MB (streaming recommended) | ~1 GB (streaming recommended) | ~1.5 GB |

### 10.4 Known Bottlenecks

1. **Set lookup**: O(n) linear search in `_match_table_to_set()` — acceptable for typical set sizes
2. **Variable classification**: Called per-table — tables per model are usually < 100
3. **CSV writing**: IO-bound, not CPU-bound — `csv.writer` is efficient enough

---

> **Document version**: v0.1.0
> **Last updated**: 2026-06-28
> **Maintainer**: ADB Contributors
