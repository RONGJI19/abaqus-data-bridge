# Abaqus Data Bridge (ADB)

> 🔗 从 Abaqus `.inp` / `.dat` 文件中一键提取有限元结果到 CSV — **无需 Abaqus 许可证**
> 
> One-click extraction of FEA results from Abaqus .inp/.dat files to CSV — **no Abaqus license needed**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-orange)]()
[![Tests](https://img.shields.io/badge/tests-66%20passed-brightgreen)]()

## ✨ 为什么选择 ADB？ / Why ADB?

| 痛点 / Pain Point | ADB 的解决方案 / Solution |
|------|---------------|
| 需要 Abaqus 许可证 | **纯文本解析** `.inp` + `.dat`，Python 标准库即可 |
| 手工从 DAT 文件复制粘贴 | **一键提取**，CLI 驱动 |
| 接触力/弹簧力无工具支持 | 内置 CNORMF/CPRESS/COPEN/弹簧 S11 **专用解析器** |
| 按 Set 批量导出困难 | **自动识别 NSET/ELSET**，按 Set 分别导出 CSV |

## 🚀 快速开始 / Quick Start

### 安装 / Install

```bash
pip install abaqus-data-bridge

# 带全部可选依赖 / with all optional deps
pip install abaqus-data-bridge[all]
```

### 基础用法 / Basic Usage

```bash
# 一键提取全部结果 / Extract all results
adb extract -i model.inp -d results.dat -o ./output

# 按变量类型筛选 / Filter by variable type
adb extract -i model.inp -d results.dat --variables "U,RF,S"

# 按 Set 筛选 / Filter by sets
adb extract -i model.inp -d results.dat --nsets "TOP,BOTTOM"

# 提取接触结果 / Extract contact results
adb extract -i model.inp -d results.dat --variables "CNORMF,CPRESS,COPEN"

# 查看 DAT 内容 / Inspect DAT file
adb inspect results.dat

# 列出 INP 中的 Set / List sets in INP
adb list-sets model.inp

# 统计结果 / Statistics
adb stats results.dat

# 批量处理 / Batch processing
adb batch jobs.txt -o ./batch_output

# 交互式向导 / Interactive wizard
adb wizard

# 配置文件模式 / Config file mode
adb extract -c config.yaml
```

## 📊 支持的结果类型 / Supported Result Types

| 类别 | 变量 | 说明 |
|------|------|------|
| 节点位移 / Displacement | U1, U2, U3, UR1, UR2, UR3 | 平动 + 转动 / Translation + Rotation |
| 支反力 / Reaction Force | RF1, RF2, RF3 | 节点约束反力 / Nodal reaction |
| 单元应力 / Stress | S11~S33, S12~S23, Mises | 应力分量 + Mises / Stress components |
| 单元应变 / Strain | E11~E33, E12~E23 | 应变分量 / Strain components |
| 接触面力 / Contact Force | CNORMF, CSHEARF1, CSHEARF2 | 法向 + 切向 / Normal + Shear |
| 接触压力 / Contact Stress | CPRESS, CSHEAR1, CSHEAR2 | 接触应力 / Contact stress |
| 接触位移 / Contact Disp | COPEN, CSLIP1, CSLIP2 | 张开 + 滑移 / Opening + Slip |
| 弹簧内力 / Spring Force | S11, E11 | 弹簧力 + 相对位移 / Force + Relative disp |
| 截面力 / Section Force | SF1~SF3, SM1~SM3 | 截面力 + 弯矩 / Section force + moment |

## 📁 输出格式 / Output Format

每个 Set × 变量类型 → 一个 CSV 文件：
Each Set × variable type → one CSV file:

```
output/
├── Step-1_incr1_ALL_NODES_U.csv
├── Step-1_incr1_ALL_ELEMENTS_S.csv
├── Step-1_incr1_CONTACT_PAIR_MASTER_CNORMF.csv
├── Step-1_incr1_CONTACT_PAIR_SLAVE_CPRESS.csv
└── ...
```

CSV 格式 / Format:

```csv
# Abaqus Data Bridge v0.1.0
# Job: simple_truss
# Rows: 5
# Extracted: 2026-06-25 14:30:00
ENTITY_ID,X,Y,Z,U1,U2,U3,RF1,RF2
1,0.0,0.0,0.0,0.000000,0.000000,0.000000,-500.0,-288.68
```

## 🐍 Python API

```python
from adb.core.engine import ExtractionEngine
from adb.models.extraction_config import ExtractionConfig

config = ExtractionConfig()
config.inp_file = "model.inp"
config.dat_file = "results.dat"
config.output_dir = "./output"
config.variables.contact = ["CNORMF", "CPRESS"]
config.filters.node_sets = ["TOP_NODES"]

engine = ExtractionEngine(config)
stats = engine.run()
print(f"Exported {stats['exported_files']} files, {stats['total_rows']} rows")
```

详见 / See `examples/` 目录。

## 🖥️ GUI 桌面应用 / Desktop GUI

```bash
pip install abaqus-data-bridge[gui]
adb-gui
```

GUI 面向非脚本用户优化为单屏左右分栏，尽量利用宽屏空间：

- **左侧**：文件选择、预分析入口、变量预设、Step/NSET/ELSET/Increment 筛选
- **右侧**：预分析结果、输出选项、开始提取、进度日志、打开输出目录

![GUI](docs/gui_screenshot.png)

或命令行版本 / Or CLI: `adb extract -i model.inp -d results.dat -o ./output`

## 📦 打包为独立 EXE（无需 Python） / Standalone EXE

把 ADB 打包成单个 .exe，拷贝到其他电脑直接运行：

```bash
# 1. 安装打包工具
pip install pyinstaller pyside6

# 2. 执行打包（Windows）
build_exe.bat
# 或
python build_exe.py          # 同时构建 GUI + CLI
python build_exe.py --gui    # 只构建 GUI
python build_exe.py --cli    # 只构建 CLI

# 3. 输出在 dist/ 目录
#    dist/ADB_GUI.exe  — 双击运行，无需 Python
#    dist/ADB_CLI.exe  — 命令行版本

# 跨平台打包 (macOS / Linux)
pyinstaller adb_gui.spec
```

打包后的 `dist/` 文件夹可以直接拷贝给同事，无需安装 Python 或任何依赖。GUI 和 CLI 使用独立 PyInstaller 入口构建，避免命令行版误加载 GUI 依赖。

## 🔧 依赖 / Dependencies

- **必需 / Required**: Python 3.10+, click, pyyaml
- **GUI**: pyside6
- **可选 / Optional**: tqdm (进度条), chardet (编码检测), openpyxl (Excel)

## 📖 文档 / Documentation

- [中文用户指南 / Chinese User Guide](docs/user_guide_zh.md)
- [需求说明书 / Requirements Spec](REQUIREMENTS_SPECIFICATION.md)

## 🗺️ 路线图 / Roadmap

- [x] v0.1.0 — INP/DAT 基础解析 + 位移/应力/支反力 + CLI
- [x] v0.2.0 — 接触力/弹簧力/截面力 + 批量处理 + 统计
- [x] v0.3.0 — 大模型流式处理 + 多版本兼容 + CI/CD
- [x] v0.4.0 — PySide6 GUI 桌面应用 + PyInstaller 独立打包

## 📄 License

MIT
