# Abaqus 结果一键提取工具 — 开发与需求说明书

> **文档版本**: v1.1  
> **日期**: 2026-06-28  
> **状态**: 已按 GUI 优化版更新  

---

## 目录

1. [项目概述](#1-项目概述)
2. [市场调研与竞品分析](#2-市场调研与竞品分析)
3. [用户场景与痛点](#3-用户场景与痛点)
4. [功能需求](#4-功能需求)
5. [技术架构](#5-技术架构)
6. [模块详细设计](#6-模块详细设计)
7. [CSV 输出格式规范](#7-csv-输出格式规范)
8. [开发路线图](#8-开发路线图)
9. [风险与对策](#9-风险与对策)
10. [附录](#10-附录)

---

## 1. 项目概述

### 1.1 项目名称 (暂定)

**Abaqus Data Bridge (ADB)** — Abaqus 有限元结果一键导出工具

### 1.2 一句话描述

读取 Abaqus 的 `.inp` 输入文件和 `.dat` 结果文件，**无需 Abaqus 许可证**，一键提取节点坐标、位移、应力、接触面力、面位移、弹簧内力等计算结果，导出为标准 CSV 格式。

### 1.3 项目目标

| 目标 | 描述 |
|------|------|
| **零依赖运行** | 纯 Python 实现，不依赖 Abaqus 安装或许可证，仅解析文本文件 |
| **全覆盖提取** | 支持节点坐标、点位移、单元应力、接触面力(CNORMF/CSHEARF)、接触压力(CPRESS)、面位移(COPEN/CSLIP)、弹簧内力(S11)、支反力(RF) 等 |
| **一键操作** | CLI + GUI + 配置文件驱动，一条命令或一个向导式界面完成提取 |
| **结构化输出** | CSV 格式，清晰表头，支持中文/英文双语列名 |
| **健壮容错** | 处理不完整的 DAT 文件、大模型 (>100万节点)、多种 Abaqus 版本 |
| **易分发部署** | PyInstaller 独立打包，GUI/CLI 分入口生成 EXE，便于拷贝到无 Python 环境的电脑 |

### 1.4 核心理念

```
.inp 文件  ──→  提取模型拓扑（节点坐标、单元连接、Set 定义）
.dat 文件  ──→  提取计算结果（位移、应力、接触力、弹簧力等）

                    ↓ 交叉匹配 ↓

               CSV 输出（按 Set 筛选、按 Step/Frame 组织）
```

**不需要 Abaqus 许可证！** `.inp` 和 `.dat` 都是纯文本文件，Python 标准库即可处理。这与现有大多数工具（依赖 ODB API → 需要 Abaqus 安装）形成差异化。

---

## 2. 市场调研与竞品分析

### 2.1 现有工具全景

#### A 类：基于 ODB API（需要Abaqus许可证）

| 项目 | 语言 | ⭐ | 能力 | 局限 |
|------|------|-----|------|------|
| [abqpy](https://github.com/haiiliin/abqpy) | Python | 234 | Abaqus 脚本类型提示 + IDE 支持；可调用 ODB API 提取任意场量 | **必须安装 Abaqus**；本质是 API wrapper |
| [AbaPy](https://github.com/lcharleux/abapy) | Python | ~50 | ODB 后处理专用库：fieldOutputs/historyOutputs 封装 | **必须安装 Abaqus**；文档不全 |
| [abaqus_python_batch](https://github.com/NM0ser/abaqus_python_batch) | Python | ~30 | 批量 ODB→CSV：节点场量、积分点应力、历史输出 | **必须安装 Abaqus**；仅支持 ODB |
| [abaqus_python_batch (kkxuxu fork)](https://github.com/kkxuxu/abaqus_python_batch) | Python | - | 中文注释增强版，5 个 Demo | 同上 |
| [SPADE (LANL)](https://github.com/lanl-aea/spade) | Python/C++ | ~40 | ODB→开放格式(CSV/HDF5)；CLI工具 | **必须安装 Abaqus** (需要 C++ API)；Windows only |
| [Abaqus-Sensor-Data-Extractor](https://github.com/tufailmab/Abaqus-Sensor-Data-Extractor) | Python | - | 指定节点位移 U1/U2/U3 → TXT/XLSX | **必须安装 Abaqus**；功能单一 |
| [Abaqus_Python_Plotting](https://github.com/Guillaume-Lostec/Abaqus_Python_Plotting) | Python | ~20 | 生成 .rpt 报告 → 正则解析 → CSV → 绑图 | **必须安装 Abaqus**；通过 .rpt 中间格式 |
| [abq-scripting](https://github.com/johann-cardenas/abq-scripting) | Python | - | INP 创建 + ODB 提取 + 可视化脚本集合 | **必须安装 Abaqus**；零散脚本 |

#### B 类：纯文本解析（无需 Abaqus 许可证）⭐ 我们属于这类

| 项目 | 语言 | ⭐ | 能力 | 局限 |
|------|------|-----|------|------|
| [parser_for_abaqus_input_files](https://github.com/mrettl/parser_for_abaqus_input_files) | Python | ~30 | **仅 .inp 文件**解析：关键字/参数/数据行 → Python 结构 | **不处理 .dat 结果**；仅模型拓扑 |
| [abqInputParser](https://github.com/yeguang-xue/abqInputParser) | Python | ~5 | .inp 解析，计划支持 JSON/XML/VTK 导出 | **不处理 .dat**；开发中 |
| [abaqus-parse](https://pypi.org/project/abaqus-parse/) | Python | 9 | .inp + 部分输出读取/写入 | **已停维 4 年**；功能不完整 |
| [pybaqus](https://pypi.org/project/pybaqus/) | Python | - | .fil 结果文件解析（需 ASCII 格式） | 不支持 .dat；需额外设置 FILE FORMAT, ASCII |

#### C 类：商业/企业工具

| 工具 | 类型 | 描述 |
|------|------|------|
| SIMULIA fe-safe | 商业 | 疲劳分析，可读取 ODB |
| Altair HyperView | 商业 | 通用 CAE 后处理，支持 Abaqus 格式 |
| MATLAB Abaqus Toolbox | 学术 | 通过 Python 桥接调用 ODB API |
| Tecplot | 商业 | 支持 Abaqus 导出的数据格式 |

### 2.2 竞品能力矩阵

| 能力 | abqpy | AbaPy | abaqus_python_batch | SPADE | parser_for_inp | **ADB (我们)** |
|------|-------|-------|---------------------|-------|---------------|---------------|
| 解析 .inp (节点坐标) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 解析 .inp (Set 定义) | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 解析 .dat 结果 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| 不需要 Abaqus 许可证 | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| 节点位移 U1/U2/U3 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 单元应力 S11~S33 | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| 接触面力 CNORMF | ✅ | ✅ | ❌ | - | ❌ | ✅ |
| 接触压力 CPRESS | ✅ | ✅ | ❌ | - | ❌ | ✅ |
| 面位移 COPEN/CSLIP | ✅ | ✅ | ❌ | - | ❌ | ✅ |
| 弹簧内力 S11 | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| 支反力 RF | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| 按 Set 筛选输出 | ⚠️ | ⚠️ | ✅ | ⚠️ | ❌ | ✅ |
| CLI 命令行界面 | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| CSV 输出 | ⚠️ | ⚠️ | ✅ | ✅ | ❌ | ✅ |
| 跨平台 (Win/Mac/Linux) | ⚠️ | ⚠️ | ⚠️ | ❌ | ✅ | ✅ |
| 中文文档/社区 | ❌ | ❌ | ⚠️ | ❌ | ❌ | ✅ |

> **核心差异**: 我们是唯一 **纯文本解析 + 全面结果提取 + CSV 输出 + 免许可证** 的工具。

### 2.3 现有工具的共性缺陷 (我们应避免的)

1. **依赖 Abaqus 安装**: 90% 的工具都通过 `from odbAccess import *` 工作 → 没装 Abaqus 的机器完全不能用
2. **功能单一**: 多数工具只做一件事（如只提位移、只提应力），缺乏"一键全提取"能力
3. **无 Set 感知**: 不能按 INP 中定义的 *NSET/*ELSET 筛选输出
4. **脆弱的输出格式**: 多数直接 dump 原始数据，缺少结构化表头和可追溯的元数据
5. **不支持接触面结果**: CNORMF、CPRESS、COPEN 等接触相关变量几乎无工具覆盖
6. **不支持弹簧内力**: SPRINGA/SPRING1/SPRING2 等弹簧单元的 S11 力提取无人问津
7. **缺乏中文本地化**: 国内大量 Abaqus 用户，但几乎没有中文文档或中文社区支持的工具

### 2.4 值得借鉴的设计

| 来源 | 优点 | 我们的借鉴 |
|------|------|-----------|
| `parser_for_abaqus_input_files` | INP 解析架构清晰：Keyword → Parameter → Data 三层模型 | 采用相同的分层解析模型 |
| `abaqus_python_batch` | 批量处理模式 + 结构化的 CSV 输出函数 | 参考其 CSV 写入模式和函数签名 |
| `SPADE` | CLI 接口 (`spade extract`) + 模块化设计 | 采用 CLI (click/argparse) + 插件式提取器 |
| `abqpy` | 类型提示 + 良好的包结构 | 使用 Python dataclasses 定义数据结构 |
| ODB/后处理工具常见工作流 | 先选择 Step/Frame/Region，再导出结果 | GUI 采用“文件 → 选择 → 预览 → 输出与运行”的 4 步工作流，并在预分析中勾选 Step/NSET/ELSET |

---

## 3. 用户场景与痛点

### 3.1 典型用户画像

| 角色 | 场景 | 痛点 |
|------|------|------|
| **CAE 工程师** | 完成 Abaqus 计算后，需要在 Excel/Origin 中做后处理和报告 | 手动从 .dat 复制粘贴数据；ODB API 脚本编写门槛高 |
| **仿真团队负责人** | 需要批量处理多个 Job 的结果，汇总对比 | 逐个打开 CAE/Viewer 导出，效率极低 |
| **二次开发工程师** | 需要将 Abaqus 结果接入 Python/ML 分析流程 | 现有工具要么要许可证，要么功能残缺 |
| **学术研究人员** | 在无 Abaqus 许可证的服务器/笔记本上分析结果 | 无法使用 ODB API；只能手动处理文本 |

### 3.2 核心痛点

1. **"我有 .inp 和 .dat 文件，但没装 Abaqus，怎么把结果导出到 Excel？"**
   - → ADB 解决：pip install 即用，零依赖

2. **"我需要接触面上的法向力 CNORMF，但找不到工具提取"**
   - → ADB 解决：内置接触面结果解析器

3. **"我定义了 50 个 NSET，我需要每个 Set 的节点位移单独导出一个 CSV"**
   - → ADB 解决：批量按 Set 筛选 + 分别导出

4. **"我只需要 Step-3 最后一帧的应力结果"**
   - → ADB 解决：支持按 Step/Increment 过滤

5. **"我的模型有 200 万节点，脚本内存不够用"**
   - → ADB 解决：流式解析 + 分块写入

---

## 4. 功能需求

### 4.1 功能总览

```
ADB (Abaqus Data Bridge)
│
├── 4.2 INP 解析器
│   ├── 节点坐标 (*NODE)
│   ├── 单元连接 (*ELEMENT)
│   ├── 节点集 (*NSET / *ELSET)
│   ├── 材料属性 (*MATERIAL)
│   └── 截面属性 (*SOLID SECTION / *SHELL SECTION 等)
│
├── 4.3 DAT 结果解析器
│   ├── 节点位移 (U1, U2, U3, UR1, UR2, UR3, Magnitude)
│   ├── 节点支反力 (RF1, RF2, RF3)
│   ├── 单元应力 (S11, S22, S33, S12, S13, S23, Mises, MaxPrincipal, ...)
│   ├── 单元应变 (E11, E22, E33, E12, E13, E23)
│   ├── 接触面力 (CNORMF, CSHEARF)
│   ├── 接触压力 (CPRESS)
│   ├── 接触面位移 (COPEN, CSLIP1, CSLIP2)
│   ├── 弹簧内力 (S11 → 实际是力)
│   ├── 弹簧位移 (E11 → 相对位移)
│   ├── 截面力/弯矩 (SF1, SF2, SF3, SM1, SM2, SM3)
│   └── 节点温度 (NT11, ...)
│
├── 4.4 数据匹配与筛选
│   ├── 按 Set 名称筛选节点/单元
│   ├── 按 Step 名称筛选
│   ├── 按 Increment/Frame 编号筛选
│   ├── 按位置范围筛选 (X/Y/Z bounding box)
│   └── 正则匹配 Set 名称
│
├── 4.5 CSV 输出引擎
│   ├── 自定义表头 (中/英文)
│   ├── 自定义分隔符 (逗号/制表符/分号)
│   ├── 批量导出 (一个 Set 一个文件 / 全部合并)
│   ├── 元数据行 (Job名, Step, Increment, 日期, 提取参数)
│   └── 编码选择 (UTF-8 / GBK / UTF-8-BOM)
│
├── 4.6 CLI 命令行界面
│   ├── 主命令: adb extract
│   ├── 配置文件驱动 (YAML/TOML)
│   ├── 交互式向导模式 (adb wizard)
│   └── 进度条与日志
│
├── 4.7 GUI 桌面界面
│   ├── 文件页：拖放/选择 INP、DAT，自动生成输出目录
│   ├── 选择页：变量预设、Step/NSET/ELSET/Increment 筛选
│   ├── 预览页：预分析模型，勾选 Step、节点集、单元集并应用到筛选
│   ├── 输出页：CSV/TSV、编码、小数位、元数据、坐标列、合并输出
│   └── 运行反馈：后台线程、进度条、日志、打开输出目录
│
├── 4.8 独立 EXE 打包
│   ├── ADB_GUI.exe：窗口版，面向工程师直接操作
│   ├── ADB_CLI.exe：命令行版，面向批处理和自动化
│   ├── python build_exe.py：同时构建 GUI + CLI
│   ├── python build_exe.py --gui：只构建 GUI
│   └── python build_exe.py --cli：只构建 CLI
│
└── 4.9 辅助功能
    ├── DAT 文件完整性检查
    ├── 多 Job 批量处理
    ├── 结果统计摘要
    └── 简单的文本报告生成
```

### 4.2 INP 解析 — 详细规格

#### 4.2.1 节点坐标提取

**输入**: `.inp` 文件中的 `*NODE` 关键字块  
**输出格式**:

```csv
NODE_ID, X, Y, Z
1, 0.000, 0.000, 0.000
2, 10.000, 0.000, 0.000
...
```

**支持的 INP 语法**:
```abaqus
*NODE, NSET=ALL_NODES
1, 0.0, 0.0, 0.0
2, 10.0, 0.0, 0.0

*NODE, INPUT=submesh.inp   (外部文件引用)
```

#### 4.2.2 Set 定义提取

**输入**: `*NSET`, `*ELSET` 关键字  
**输出**: `{set_name: [node_ids/elem_ids]}` 映射字典

**支持的语法**:
```abaqus
*NSET, NSET=BOTTOM, GENERATE
1, 100, 1

*NSET, NSET=TOP
101, 102, 103, 104, 105, 106, 107, 108, 109, 110

*ELSET, ELSET=CONTACT_SURFACE, INTERNAL
1, 2, 3, ... (自动检测 continuation lines)
```

#### 4.2.3 单元类型识别

解析 `*ELEMENT, TYPE=...` 以确定后续应力输出的分量数：
- C3D8R → 8节点六面体 → 应力有 6 分量
- S4R → 4节点壳 → 应力有 5 分量 (平面应力假设)
- SPRINGA → 2节点弹簧 → 只有 S11 (力)

### 4.3 DAT 结果解析 — 详细规格

#### 4.3.1 DAT 文件结构理解

Abaqus/Standard 的 `.dat` 文件是带格式的文本输出，关键特征：

```
S T E P   1    S T A T I C   A N A L Y S I S

INCREMENT     1  SUMMARY
TIME       0.10000E-01
STEP TIME  0.10000E-01
...

N O D E   O U T P U T

THE FOLLOWING TABLE IS PRINTED FOR NODES BELONGING TO NODE SET ALL_NODES

NODE FOOT-   U1           U2           U3          UR1          UR2          UR3
     NOTE

   1         0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00
   2        -2.3456E-03   1.2345E-03   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00
...

E L E M E N T   O U T P U T

THE FOLLOWING TABLE IS PRINTED FOR ELEMENTS BELONGING TO ELEMENT SET SPRING_SET

ELEMENT  FOOT-  S11      
                NOTE      
SPRINGA  ...    ...
...
```

**关键解析挑战**:
1. 表格头部跨多行（`FOOT-NOTE` 占位行）
2. 数值使用 Fortran 科学记数法 (`0.1234E-02`, `-1.234E+03`)
3. 多列折叠 (9列/表，超出则分多个表)
4. SET 名称嵌入在表头描述文字中
5. 不同 Abaqus 版本输出格式有细微差异

#### 4.3.2 节点位移

**触发关键字**: `N O D E   O U T P U T` + `U1` / `U2` / `U3`  
**变量**: U1, U2, U3, UR1, UR2, UR3, U_Magnitude  
**INP 对应**: `*NODE PRINT, U`  

**CSV 输出**:
```csv
NODE_ID, U1, U2, U3, UR1, UR2, UR3, U_MAGNITUDE
1, 0.000000, 0.000000, 0.000000, 0.0, 0.0, 0.0, 0.000000
2, -0.002346, 0.001235, 0.000000, 0.0, 0.0, 0.0, 0.002651
```

#### 4.3.3 节点支反力

**触发关键字**: `N O D E   O U T P U T` + `RF1` / `RF2` / `RF3`  
**变量**: RF1, RF2, RF3, RF_Magnitude  
**INP 对应**: `*NODE PRINT, RF`  

#### 4.3.4 单元应力

**触发关键字**: `E L E M E N T   O U T P U T` + `S11` / `S22` / etc.  
**变量** (按单元类型):
- 实体单元: S11, S22, S33, S12, S13, S23, Mises, MaxPrincipal, MidPrincipal, MinPrincipal
- 壳单元: S11, S22, S12 (膜应力) + 弯矩分量
- 梁/桁架: S11, S12 (轴向力/剪力)

**CSV 输出**:
```csv
ELEMENT_ID, S11, S22, S33, S12, S13, S23, MISES, MAX_PRINCIPAL
1, 123.45, -67.89, 12.34, -45.67, 8.90, -1.23, 156.78, 180.23
```

#### 4.3.5 接触面结果

**触发关键字**: `C O N T A C T   O U T P U T`  
**变量**:
- CNORMF: 接触面法向力 (Contact Normal Force)
- CSHEARF: 接触面切向力 (Contact Shear Force)
- CPRESS: 接触压力 (Contact Pressure)
- COPEN: 接触面开度 (Contact Opening)
- CSLIP1, CSLIP2: 接触面滑移量 (Contact Slip)

**特殊处理**:
- 接触输出按主面(MASTER) / 从面(SLAVE) 组织
- 需要关联接触对名称到节点集
- COPEN 符号约定在不同版本中可能反转

**CSV 输出** (按接触对):
```csv
NODE_ID, CNORMF, CSHEARF1, CSHEARF2, CPRESS, COPEN, CSLIP1, CSLIP2
101, 12.345, 0.123, -0.456, 1.234, -0.001, 0.000, 0.000
102, 23.456, 0.234, -0.567, 2.345, -0.002, 0.001, 0.000
```

#### 4.3.6 弹簧内力 ⭐ 差异化功能

**触发关键字**: `E L E M E N T   O U T P U T` + `S11` + `SPRINGA`/`SPRING1`/`SPRING2`  
**变量**: S11 (力), E11 (相对位移)  

> **关键理解**: 对于弹簧单元，S11 **不是应力而是力(N)**。我们需要根据单元类型自动标注正确的物理量单位。

**CSV 输出**:
```csv
ELEMENT_ID, ELEMENT_TYPE, NODE_I, NODE_J, FORCE_S11, DISP_E11
201, SPRINGA, 10, 11, 150.23, 0.015
202, SPRINGA, 12, 13, 98.45, 0.010
```

#### 4.3.7 截面力/弯矩

**变量**: SF1, SF2, SF3 (截面力), SM1, SM2, SM3 (截面弯矩)  
**INP 对应**: `*SECTION PRINT`  
**按截面名称组织输出**

### 4.4 筛选与匹配功能

| 筛选条件 | 示例 | 说明 |
|---------|------|------|
| 按 Set 名称 | `--nsets "TOP,BOTTOM"` | 只提取指定 NSET 的节点结果 |
| 按 Step 名称 | `--steps "Step-2,Step-3"` | 只提取指定 Step |
| 按 Increment | `--increments "last"` 或 `--increments "1,5,10"` | last=最后一帧 |
| 按坐标范围 | `--bbox "0,0,0,100,100,50"` | X/Y/Z 包围盒过滤 |
| 正则匹配 | `--set-pattern "CONTACT.*"` | 匹配所有接触相关 Set |
| 按单元类型 | `--elem-types "C3D8R,SPRINGA"` | 按单元类型筛选输出 |

### 4.5 CLI 设计

```bash
# 一键提取（使用配置文件）
adb extract -c config.yaml

# 快速命令行提取
adb extract \
    -i model.inp \
    -d results.dat \
    -o ./output/ \
    --nsets "TOP_NODES,BOTTOM_NODES" \
    --elsets "SPRING_SET,CONTACT_SET" \
    --variables "U,S,RF,CNORMF,CPRESS,S11" \
    --step "Step-2" \
    --increment "last" \
    --format csv \
    --encoding utf-8

# 查看 DAT 文件包含哪些结果
adb inspect results.dat

# 列出 INP 中所有 Set
adb list-sets model.inp

# 交互式向导
adb wizard

# 批量处理
adb batch jobs.txt -o ./all_results/
```

### 4.6 配置文件格式 (YAML)

```yaml
# config.yaml — ADB 配置文件
job:
  name: "my_analysis"
  inp_file: "model.inp"
  dat_file: "results.dat"
  output_dir: "./output"

extraction:
  # 提取的变量类型
  variables:
    nodal: ["U", "RF"]           # 节点位移、支反力
    element: ["S", "E"]          # 单元应力、应变
    contact: ["CNORMF", "CPRESS", "COPEN", "CSLIP"]
    spring: ["S11", "E11"]       # 弹簧力、位移
    section: ["SF"]              # 截面力

  # 筛选条件
  filters:
    node_sets: ["TOP_NODES", "BOTTOM_NODES"]
    element_sets: ["SPRING_ELEMENTS", "CONTACT_ELEMENTS"]
    steps: ["Step-2"]
    increments: "last"           # "last" | "all" | [1, 3, 5]
    bbox: null                   # [xmin, ymin, zmin, xmax, ymax, zmax]

  # 输出设置
  output:
    format: "csv"                # csv | tsv | xlsx
    encoding: "utf-8-sig"        # utf-8 | utf-8-sig | gbk
    delimiter: ","
    include_metadata: true       # 是否在 CSV 头部写入元数据
    merge_sets: false            # true = 所有 Set 合并到一个文件
    decimal_places: 6            # 小数位数

  # 高级选项
  advanced:
    coordinate_system: "global"  # global | local
    include_node_coords: true    # 在结果 CSV 中附带坐标列
    detect_incomplete: true      # 检测未完成的分析
    memory_limit_mb: 2048        # 内存限制，超出则流式处理
```

---

## 5. 技术架构

### 5.1 技术栈

| 层次 | 技术选择 | 理由 |
|------|---------|------|
| 语言 | **Python 3.10+** | CAE 领域最通用；丰富的文本处理能力 |
| CLI 框架 | **Click** | 成熟、装饰器式、自动生成 help |
| YAML 解析 | **PyYAML** | 配置文件标准 |
| CSV 处理 | **标准库 csv** | 零依赖 |
| 正则引擎 | **标准库 re** | DAT 解析的核心 |
| 数据模型 | **dataclasses** | 轻量数据结构 |
| 测试 | **pytest** | Python 标准测试框架 |
| 打包 | **pip / setuptools** | 标准分发 |
| 可选 XLSX | **openpyxl** | 可选 Excel 输出 |
| 进度条 | **tqdm** | 大文件处理进度显示 |

### 5.2 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Layer (click)                       │
│  adb extract | adb inspect | adb list-sets | adb wizard     │
├─────────────────────────────────────────────────────────────┤
│                    Configuration Layer                        │
│  ConfigParser (YAML) → ExtractionConfig dataclass            │
├─────────────────────────────────────────────────────────────┤
│                      Core Engine                             │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ INP Parser  │  │ DAT Parser   │  │  Data Matcher     │  │
│  │             │  │              │  │  (Set × Step ×    │  │
│  │ - NODE      │  │ - Header     │  │   Increment →     │  │
│  │ - ELEMENT   │  │   Detector   │  │   filtered data)  │  │
│  │ - NSET      │  │ - Table      │  │                   │  │
│  │ - ELSET     │  │   Extractor  │  │                   │  │
│  │ - MATERIAL  │  │ - Fortran    │  │                   │  │
│  │ - SECTION   │  │   Number     │  │                   │  │
│  │             │  │   Parser     │  │                   │  │
│  └─────────────┘  └──────────────┘  └───────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              CSV Output Engine                         │  │
│  │  - TableBuilder (per result type)                      │  │
│  │  - MetadataWriter                                      │  │
│  │  - BatchExporter                                       │  │
│  │  - EncodingHandler                                     │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                     Utilities Layer                          │
│  FortranNumberParser | ProgressBar | FileUtils | Logger     │
└─────────────────────────────────────────────────────────────┘
```

### 5.3 数据流

```
                        ┌──────────────┐
                        │  config.yaml │
                        └──────┬───────┘
                               │
            ┌──────────────────┼──────────────────┐
            ▼                                     ▼
   ┌────────────────┐                    ┌────────────────┐
   │  INP Parser    │                    │  DAT Parser    │
   │                │                    │                │
   │ 1. 分段扫描    │                    │ 1. 检测Step边界│
   │ 2. 关键字匹配  │                    │ 2. 识别表格类型 │
   │ 3. 数据行解析  │                    │ 3. 解析表头     │
   │ 4. Set展开     │                    │ 4. 解析数据行   │
   └───────┬────────┘                    └───────┬────────┘
           │                                     │
           ▼                                     ▼
   ┌────────────────┐                    ┌────────────────┐
   │  InpModel      │                    │  DatResults    │
   │                │                    │                │
   │ .nodes: dict   │                    │ .steps: dict   │
   │ .elements:dict │                    │  └─ increments │
   │ .nsets: dict   │                    │     └─ tables  │
   │ .elsets: dict  │                    │        └─ data │
   └───────┬────────┘                    └───────┬────────┘
           │                                     │
           └──────────────┬──────────────────────┘
                          │
                          ▼
                ┌──────────────────┐
                │  Data Matcher    │
                │                  │
                │ • Set ID → 查表  │
                │ • 结果关联节点/  │
                │   单元坐标       │
                │ • 变量名标准化   │
                └────────┬─────────┘
                         │
                         ▼
                ┌──────────────────┐
                │  CSV Exporter    │
                │                  │
                │ • 按 Set 分文件  │
                │ • 写入元数据头   │
                │ • 格式化数值     │
                │ • 编码处理       │
                └────────┬─────────┘
                         │
                         ▼
                  ┌──────────────┐
                  │  output/     │
                  │  ├─ TOP_NODES_U.csv
                  │  ├─ TOP_NODES_S.csv
                  │  ├─ CONTACT_CNORMF.csv
                  │  ├─ SPRING_S11.csv
                  │  └─ summary.txt
                  └──────────────┘
```

---

## 6. 模块详细设计

### 6.1 INP Parser (`adb/parsers/inp_parser.py`)

```python
# 核心数据结构
@dataclass
class InpModel:
    """INP 文件解析结果"""
    nodes: Dict[int, Node]           # node_id → Node(x,y,z)
    elements: Dict[int, Element]     # elem_id → Element(type, node_ids[])
    nsets: Dict[str, List[int]]     # nset_name → [node_ids]
    elsets: Dict[str, List[int]]    # elset_name → [elem_ids]
    materials: Dict[str, Material]   # material_name → Material
    sections: Dict[str, Section]     # section_name → Section
    job_name: str
    metadata: Dict[str, Any]

@dataclass
class Node:
    id: int
    x: float
    y: float
    z: float
    coordinate_system: str = "global"

@dataclass  
class Element:
    id: int
    type: str           # "C3D8R", "S4R", "SPRINGA", etc.
    connectivity: List[int]  # node IDs
```

**解析策略**:

采用**状态机 + 行级正则匹配**：
1. 逐行读取 (支持大文件流式)
2. 遇到 `*KEYWORD` → 切换解析状态
3. 参数行 (`,`) 和数据行分行处理
4. 自动处理 continuation lines (`,\n` 结尾)
5. 支持 `*INCLUDE` 和 `*NODE, INPUT=` 外部引用

### 6.2 DAT Parser (`adb/parsers/dat_parser.py`)

```python
@dataclass
class DatResults:
    """DAT 文件解析结果"""
    job_name: str
    analysis_type: str       # "STANDARD" | "EXPLICIT"
    completion_status: str   # "COMPLETED" | "INCOMPLETE" | "ERROR"
    steps: Dict[str, StepResult]
    warnings: List[str]
    errors: List[str]

@dataclass
class StepResult:
    step_name: str
    step_type: str          # "STATIC" | "FREQUENCY" | "MODAL_DYNAMIC" | ...
    increments: Dict[int, IncrementResult]

@dataclass
class IncrementResult:
    increment_num: int
    time: float
    step_time: float
    tables: List[ResultTable]  # 一个 Increment 可能有多张表(位移表+应力表+...)

@dataclass
class ResultTable:
    table_type: str          # "NODE_OUTPUT" | "ELEMENT_OUTPUT" | "CONTACT_OUTPUT"
    set_name: str            # 所属的 SET 名称
    variable_names: List[str] # ["U1", "U2", "U3", ...]
    data: List[ResultRow]    # 数据行

@dataclass
class ResultRow:
    entity_id: int           # Node ID / Element ID
    values: Dict[str, float] # {"U1": 0.00123, "U2": -0.00456, ...}
    foot_note: Optional[str] # 脚注标记（如有）
```

**DAT 解析的核心挑战与对策**:

| 挑战 | 对策 |
|------|------|
| 跨行表头 | 状态机累积表头行直到检测到数据行 |
| Fortran 科学记数法 | 自定义 `parse_fortran_float()` 支持 `D`, `E`, `+`, `-` 变体 |
| 多列折叠(>9列分表) | 检测分表标记，合并同名表 |
| SET 名称嵌入描述文本 | 正则提取 `BELONGING TO NODE SET XXX` / `ELEMENT SET XXX` |
| 不同版本格式差异 | 多版本 header pattern 匹配库 |
| GBK/UTF-8 编码混合 | `chardet` 自动检测 + 回退策略 |
| 空行/分页符 | 预过滤噪音行 |

### 6.3 Fortran 数值解析 (`adb/utils/fortran.py`)

```python
def parse_fortran_float(s: str) -> float:
    """
    解析 Fortran 格式的浮点数
    
    支持格式:
    - 0.1234E+02  (标准)
    - 0.1234D+02  (双精度)
    - 1234.5678    (普通小数)
    - -.1234E-02   (前导负号省略零)
    - 0.1234+02    (省略 E)
    - 12.34E-2     (负指数)
    
    也处理 Abaqus 特殊格式:
    - 1.234E+003   (3位指数)
    - **********   (溢出/未定义 → NaN)
    """
```

### 6.4 数据匹配器 (`adb/core/matcher.py`)

核心逻辑：将 DAT 中提取的结果表与 INP 中定义的 Set 进行交叉匹配。

```python
def match_results_to_sets(
    model: InpModel,
    results: DatResults,
    config: ExtractionConfig
) -> Dict[str, pd.DataFrame]:
    """
    返回: {
        "TOP_NODES_U": DataFrame(node_id, x, y, z, U1, U2, U3, ...),
        "SPRING_S11": DataFrame(elem_id, node_i, node_j, S11, E11, ...),
        ...
    }
    """
```

### 6.5 CSV 输出引擎 (`adb/exporters/csv_exporter.py`)

```python
class CsvExporter:
    """CSV 导出器"""
    
    def __init__(self, config: OutputConfig):
        self.config = config
    
    def export(self, tables: Dict[str, pd.DataFrame], output_dir: Path):
        """批量导出所有结果表"""
        
    def _write_metadata(self, writer, table_name: str):
        """写入元数据头部"""
        # # Job: my_analysis
        # # Step: Step-2, Increment: 5
        # # Set: TOP_NODES
        # # Extracted: 2026-06-25 14:30:00
        # # Tool: ADB v1.0.0
        # NODE_ID, X, Y, Z, U1, U2, U3
```

### 6.6 项目目录结构

```
abaqus-data-bridge/
│
├── adb/                           # 主包
│   ├── __init__.py
│   ├── cli.py                     # Click CLI 入口
│   │
│   ├── parsers/                   # 文件解析器
│   │   ├── __init__.py
│   │   ├── inp_parser.py          # INP 文件解析
│   │   ├── dat_parser.py          # DAT 文件解析
│   │   ├── header_detector.py     # DAT 表格头部检测
│   │   └── table_extractor.py     # DAT 表格数据提取
│   │
│   ├── models/                    # 数据模型
│   │   ├── __init__.py
│   │   ├── inp_model.py           # INP 数据类
│   │   ├── dat_model.py           # DAT 数据类
│   │   └── extraction_config.py   # 配置数据类
│   │
│   ├── core/                      # 核心引擎
│   │   ├── __init__.py
│   │   ├── matcher.py             # 数据匹配器
│   │   ├── filter.py              # 筛选器
│   │   └── engine.py              # 主提取引擎
│   │
│   ├── exporters/                 # 输出导出器
│   │   ├── __init__.py
│   │   ├── csv_exporter.py        # CSV 导出
│   │   ├── metadata_writer.py     # 元数据写入
│   │   └── summary_report.py      # 摘要报告
│   │
│   ├── utils/                     # 工具函数
│   │   ├── __init__.py
│   │   ├── fortran.py             # Fortran 数值解析
│   │   ├── encoding.py            # 编码检测与转换
│   │   └── progress.py            # 进度条
│   │
│   └── templates/                 # 输出模板
│       ├── config_template.yaml   # 配置模板
│       └── header_templates.json  # 表头模式库
│
├── tests/                         # 测试
│   ├── test_inp_parser.py
│   ├── test_dat_parser.py
│   ├── test_matcher.py
│   ├── test_exporters.py
│   └── fixtures/                  # 测试用的 .inp/.dat 文件
│       ├── simple_truss.inp
│       ├── simple_truss.dat
│       ├── contact_model.inp
│       ├── contact_model.dat
│       ├── spring_model.inp
│       └── spring_model.dat
│
├── docs/                          # 文档
│   ├── user_guide_zh.md           # 中文用户指南
│   ├── api_reference.md           # API 参考
│   └── examples/                  # 示例
│
├── examples/                      # 使用示例
│   ├── example_config.yaml
│   └── example_script.py
│
├── setup.py                       # 打包配置
├── pyproject.toml
├── requirements.txt
├── README.md
├── README_zh.md                   # 中文 README
├── LICENSE                        # MIT License
└── CHANGELOG.md
```

---

## 7. CSV 输出格式规范

### 7.1 通用元数据头部

每个 CSV 文件开头包含可选的元数据行（以 `#` 前缀）：

```csv
# ============================================================
# Abaqus Data Bridge (ADB) v1.0.0
# Job: my_analysis
# INP File: model.inp
# DAT File: results.dat
# Step: Step-2 (STATIC)
# Increment: 5, Step Time: 1.0000E+00
# Extraction Date: 2026-06-25 14:30:00
# ============================================================
NODE_ID, X, Y, Z, U1, U2, U3, U_MAGNITUDE
```

### 7.2 节点位移输出

**文件名**: `{SetName}_U.csv` 或 `{SetName}_Step-{N}_Incr-{M}_U.csv`

```csv
NODE_ID, X, Y, Z, U1, U2, U3, UR1, UR2, UR3, U_MAGNITUDE
1, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000, 0.000000
2, 10.000000, 0.000000, 0.000000, -0.002346, 0.001235, 0.000000, 0.000000, 0.000000, 0.000000, 0.002651
```

### 7.3 单元应力输出

**文件名**: `{ElsetName}_S.csv`

```csv
ELEMENT_ID, ELEMENT_TYPE, CENTROID_X, CENTROID_Y, CENTROID_Z, S11, S22, S33, S12, S13, S23, MISES, MAX_PRINCIPAL
1, C3D8R, 5.000000, 10.000000, 2.500000, 123.450000, -67.890000, 12.340000, -45.670000, 8.900000, -1.230000, 156.780000, 180.230000
```

### 7.4 接触面结果输出

**文件名**: `{ContactPairName}_Contact.csv`

```csv
NODE_ID, X, Y, Z, SURFACE_ROLE, CNORMF, CSHEARF1, CSHEARF2, CPRESS, COPEN, CSLIP1, CSLIP2
101, 50.000, 12.000, 0.500, SLAVE, 12.345000, 0.123000, -0.456000, 1.234000, -0.001000, 0.000000, 0.000000
```

### 7.5 弹簧内力输出

**文件名**: `{ElsetName}_Spring.csv`

```csv
ELEMENT_ID, ELEMENT_TYPE, NODE_I, NODE_J, DIRECTION, FORCE_S11, DISP_E11
201, SPRINGA, 10, 11, (10→11), 150.230000, 0.015000
202, SPRINGA, 12, 13, (12→13), -98.450000, -0.010000
```

### 7.6 命名规则

| 条件 | 文件命名 |
|------|---------|
| 单 Step, 单 Increment | `{SetName}_{Variable}.csv` |
| 多 Step, 单 Increment | `{SetName}_Step-{N}_{Variable}.csv` |
| 单 Step, 多 Increment | `{SetName}_Incr-{M}_{Variable}.csv` |
| 多 Step, 多 Increment | `{SetName}_Step-{N}_Incr-{M}_{Variable}.csv` |

---

## 8. 开发路线图

### Phase 0: 原型验证 (1-2 周)

```
目标: 验证技术可行性，完成最小可运行原型
```

- [x] ~~市场调研与竞品分析~~
- [x] ~~需求说明书编写~~
- [ ] 搭建 Python 项目骨架 (poetry/setuptools + pytest)
- [ ] INP 解析器原型：`*NODE`, `*NSET`, `*ELSET` 基础支持
- [ ] DAT 解析器原型：简单的节点位移表解析
- [ ] Fortran 数值解析器
- [ ] 最小 CLI: `adb extract -i model.inp -d results.dat -o ./out`
- [ ] 5 个测试用例 (简单桁架模型)

### Phase 1: MVP — 核心功能 (3-4 周)

```
目标: 覆盖最常用的提取场景，发布 v0.1.0
```

- [ ] 完整的 INP 解析器
  - `*NODE` (含 `INPUT=` 外部引用)
  - `*ELEMENT` (含 `TYPE=`, `ELSET=`)
  - `*NSET` / `*ELSET` (含 `GENERATE`, `INTERNAL`)
  - 大文件流式处理
- [ ] DAT 解析器 — 节点结果
  - 位移 (U1~U3, UR1~UR3)
  - 支反力 (RF1~RF3)
  - 多 Step / 多 Increment 支持
- [ ] DAT 解析器 — 单元结果
  - 应力 (S11~S33, S12~S23, Mises)
  - 应变 (E11~E33, E12~E23)
- [ ] CSV 导出引擎
  - 元数据头部
  - 按 Set 分文件
  - UTF-8/GBK 编码
- [ ] CLI 完善: `adb extract`, `adb inspect`, `adb list-sets`
- [ ] YAML 配置文件支持
- [ ] 用户文档 (中文)
- [ ] 打包发布到 PyPI

### Phase 2: 进阶功能 (2-3 周)

```
目标: 覆盖接触、弹簧等差异化场景，发布 v0.2.0
```

- [ ] 接触面结果提取
  - CNORMF / CSHEARF 解析
  - CPRESS 解析
  - COPEN / CSLIP 解析
  - 接触对名称识别与关联
- [ ] 弹簧内力提取
  - SPRINGA / SPRING1 / SPRING2 识别
  - S11 → Force 语义转换
  - E11 → 相对位移提取
- [ ] 截面力提取 (SF1~SF3, SM1~SM3)
- [ ] 增强筛选: Bounding Box, 正则 Set 匹配, 单元类型过滤
- [ ] 批量多 Job 处理 (`adb batch`)
- [ ] 进度条 (tqdm)
- [ ] 基础结果统计 (min, max, mean, std per variable)

### Phase 3: 完善与优化 (2-3 周)

```
目标: 健壮性、性能、生态完善，发布 v1.0.0
```

- [ ] Abaqus/Explicit DAT 格式支持
- [ ] 多版本 Abaqus 格式兼容性 (2016~2025)
- [ ] 大模型优化 (>100万节点流式处理)
- [ ] 可选 XLSX 输出 (openpyxl)
- [ ] 交互式向导 (`adb wizard`)
- [ ] DAT 文件完整性检查与错误诊断
- [ ] 完整的 API 文档
- [ ] CI/CD (GitHub Actions)
- [ ] 中文 + 英文双语文档
- [ ] 示例库 (10+ 代表性案例)

### Phase 4: 生态扩展 (未来)

```
目标: 扩展工具链，形成 Abaqus 后处理生态
```

- [ ] 支持 `.fil` 文件格式 (ASCII 模式)
- [ ] 支持 `.sta` 状态文件解析
- [ ] 结果可视化 (matplotlib 快速绑图)
- [ ] GUI 桌面应用 (PySide6 + pandastable)
- [ ] Excel 加载项 (xlwings)
- [ ] VS Code 插件
- [ ] 与 ParaView / VTK 集成导出
- [ ] HDF5 输出格式 (大规模数据)
- [ ] Web 报告生成

---

## 9. 风险与对策

| 风险 | 等级 | 对策 |
|------|------|------|
| DAT 格式因版本差异大 | 🔴 高 | 建立多版本 pattern 库；收集 Abaqus 2016~2025 各版本测试文件；社区贡献格式样本 |
| 大文件内存溢出 | 🟡 中 | 流式解析 + 分段写入；惰性加载；设置内存上限自动降级 |
| INP 语法多变（include/参数/续行） | 🟡 中 | 参考 `parser_for_abaqus_input_files` 的成熟方案；优先覆盖常用语法 |
| 接触输出格式复杂（主/从面分离） | 🟡 中 | 仔细研读 Abaqus 文档中的 CONTACT OUTPUT 章节；多场景测试 |
| 用户基础差异大（Abaqus 版本、编码、OS） | 🟡 中 | 广泛测试；提供 Docker 环境；尽可能减少依赖 |
| 中文编码问题（GBK vs UTF-8） | 🟢 低 | 自动编码检测 (chardet)；默认 UTF-8-BOM (Excel 友好) |
| 社区接受度低 | 🟢 低 | MIT 开源；双语文档；CSDN/知乎宣传；响应 issue |

---

## 10. 附录

### A. Abaqus 输出变量速查表

#### 节点变量 (*NODE PRINT)

| INP 关键字 | DAT 列名 | 物理意义 | 分量数 |
|-----------|---------|---------|--------|
| U | U1, U2, U3 | 平动位移 | 3 |
| U | UR1, UR2, UR3 | 转动位移 | 3 |
| V | V1, V2, V3 | 速度 | 3 |
| A | A1, A2, A3 | 加速度 | 3 |
| RF | RF1, RF2, RF3 | 支反力 | 3 |
| RM | RM1, RM2, RM3 | 支反力矩 | 3 |
| NT | NT11, NT22, ... | 节点温度 | 可多分量 |

#### 单元变量 (*EL PRINT)

| INP 关键字 | DAT 列名 | 适用单元 | 物理意义 |
|-----------|---------|---------|---------|
| S | S11~S33, S12~S23 | 实体/壳/梁 | 应力分量 |
| E | E11~E33, E12~E23 | 实体/壳/梁 | 应变分量 |
| S | S11 (仅) | SPRINGA/SPRING1/2 | **力** (不是应力!) |
| E | E11 (仅) | SPRINGA/SPRING1/2 | 相对位移 |
| SF | SF1, SF2, SF3 | 梁/壳 | 截面力 |
| SM | SM1, SM2, SM3 | 梁/壳 | 截面弯矩 |

#### 接触变量 (*CONTACT PRINT)

| INP 关键字 | DAT 列名 | 物理意义 |
|-----------|---------|---------|
| CFORCE | CNORMF | 法向接触力 |
| CFORCE | CSHEARF1, CSHEARF2 | 切向接触力 |
| CSTRESS | CPRESS | 接触压力 |
| CSTRESS | CSHEAR1, CSHEAR2 | 接触剪应力 |
| CDISP | COPEN | 接触面张开距离 |
| CDISP | CSLIP1, CSLIP2 | 接触面滑移量 |

### B. 关键参考资源

| 资源 | URL |
|------|-----|
| Abaqus Output Reference | https://docs.software.vt.edu/abaqusv2025/English/SIMACAEOUTRefMap/ |
| parser_for_abaqus_input_files | https://github.com/mrettl/parser_for_abaqus_input_files |
| abqpy (类型提示) | https://github.com/haiiliin/abqpy |
| abaqus_python_batch | https://github.com/NM0ser/abaqus_python_batch |
| SPADE (LANL) | https://github.com/lanl-aea/spade |
| AbaPy (后处理) | https://github.com/lcharleux/abapy |
| pybaqus (.fil 解析) | https://pypi.org/project/pybaqus/ |

### C. 术语表

| 缩写 | 全称 | 说明 |
|------|------|------|
| INP | Input File | Abaqus 输入文件，定义模型拓扑、载荷、边界条件 |
| DAT | Data File | Abaqus 打印输出文件，包含 `*PRINT` 请求的表格结果 |
| ODB | Output Database | Abaqus 二进制输出数据库，需 Abaqus API 读取 |
| FIL | Results File | Abaqus 结果文件，二进制或 ASCII 格式 |
| NSET | Node Set | 节点集 |
| ELSET | Element Set | 单元集 |
| CNORMF | Contact Normal Force | 接触面法向力 |
| CPRESS | Contact Pressure | 接触压力 |
| COPEN | Contact Opening | 接触面张开距离 |
| CSLIP | Contact Slip | 接触面滑移量 |
| SPRINGA | Spring (axial) | 轴向弹簧单元 (两点间) |

---

> **文档状态**: 🔴 待审核  
> **下一步**: 请审核此文档，确认需求范围和技术路线。审核通过后进入 Phase 0 原型开发。
