# Abaqus INP/DAT 文件格式深度指南

> **Abaqus Data Bridge 学习资源** — 理解 INP 输入文件和 DAT 输出文件的完整格式，以便进行纯文本解析和结果提取。

---

## 目录

1. [INP 文件格式](#1-inp-文件格式)
2. [DAT 文件格式](#2-dat-文件格式)
3. [关键解析挑战](#3-关键解析挑战)
4. [Fortran 数值格式](#4-fortran-数值格式)
5. [接触输出格式](#5-接触输出格式)
6. [多版本兼容性](#6-多版本兼容性)
7. [完整示例](#7-完整示例)
8. [参考资源](#8-参考资源)

---

## 1. INP 文件格式

### 1.1 基本结构

Abaqus INP 文件是纯文本文件，由**关键字行**（以 `*` 开头）和**数据行**组成。

```abaqus
*HEADING
My Analysis Job
*NODE
1, 0.0, 0.0, 0.0
2, 10.0, 0.0, 0.0
*ELEMENT, TYPE=T2D2, ELSET=ALL_ELEMENTS
1, 1, 2
*END STEP
```

### 1.2 核心关键字详解

#### *NODE — 节点定义

```
格式:
  *NODE [, NSET=节点集名] [, INPUT=外部文件]
  节点编号, X坐标, Y坐标, Z坐标

GENERATE 格式:
  *NODE, NSET=SET1, GENERATE
  first_id, x1, y1, z1
  last_id,  x2, y2, z2
  increment   (可选，默认 1)
```

**关键解析注意事项**:
- 续行处理：数据行以逗号结尾时，下一行为续行
- `INPUT=` 参数可引用外部文件
- `NSET=` 参数可将节点同时加入节点集
- GENERATE 模式通过线性插值生成中间节点

**实际示例**:
```abaqus
*NODE, NSET=ALL_NODES
1, 0.0, 0.0, 0.0
2, 100.0, 0.0, 0.0
3, 50.0, 86.6025, 0.0
4, 200.0, 0.0, 0.0
5, 150.0, 86.6025, 0.0
```

#### *ELEMENT — 单元定义

```
格式:
  *ELEMENT, TYPE=单元类型 [, ELSET=单元集名]
  单元编号, 节点1, 节点2, ..., 节点N
```

**常见单元类型**:

| 类型 | 说明 | 节点数 |
|------|------|--------|
| T2D2 | 2D桁架单元 | 2 |
| B21 | 2D梁单元 | 2 |
| CPS4 | 2D平面应力四边形 | 4 |
| C3D8/C3D8R | 3D六面体 | 8 |
| S4R | 壳单元 | 4 |
| SPRINGA | 轴向弹簧 | 2 |
| SPRING1 | 接地弹簧 | 1 |
| DC2D8 | 2D热传导四边形 | 8 |

**实际示例**:
```abaqus
*ELEMENT, TYPE=T2D2, ELSET=ALL_ELEMENTS
1, 1, 2
2, 2, 3
3, 1, 3

*ELEMENT, TYPE=SPRINGA, ELSET=SPRING_SET
101, 1, 2
102, 3, 4
```

**节点顺序约定** (C3D8 六面体单元):
```
前4个节点定义底面（逆时针），后4个节点定义顶面（逆时针）:
底面: n1, n2, n3, n4
顶面: n5, n6, n7, n8
```

#### *NSET / *ELSET — Set 定义

```
直接列表:
  *NSET, NSET=集合名
  id1, id2, id3, ...

GENERATE 格式:
  *NSET, NSET=集合名, GENERATE
  start_id, end_id, increment

UNSORTED 格式:
  *NSET, NSET=集合名, UNSORTED
  id1, id2, id3
```

**实际示例**:
```abaqus
*NSET, NSET=SUPPORT
1, 4

*NSET, NSET=TOP_NODES
3, 5

*NSET, NSET=ENDS, GENERATE
1, 100, 1

*ELSET, ELSET=BOTTOM_CHORD
1, 4

*ELSET, ELSET=TOP_CHORD
6, 7

*ELSET, ELSET=DIAGONALS
2, 3, 5
```

#### *NGEN / *ELGEN — 批量生成

```
*NGEN, NSET=集合名
起始节点, 结束节点, 增量

*NGEN, LINE=C, NSET=HOLE  (圆弧生成)
119, 1919, 100, 圆心节点编号

*ELGEN, ELSET=集合名
起始单元, 重复次数, 节点增量1, 重复次数2, 节点增量2
```

**完整示例**:
```abaqus
*NODE
1, 0.0, 0.0
6, 100.0, 0.0
*NGEN, NSET=ENDS
1, 6, 1

*ELEMENT, TYPE=B21
1, 1, 2
*ELGEN, ELSET=BEAM
1, 5
```

#### *NODE PRINT / *EL PRINT — 输出请求

```abaqus
*NODE PRINT, NSET=ALL_NODES
U,      # 位移 (U1, U2, U3, UR1, UR2, UR3)
RF,     # 支反力 (RF1, RF2, RF3)

*EL PRINT, ELSET=ALL_ELEMENTS
S,      # 应力 (S11, S22, S33, S12, S13, S23, Mises)
E,      # 应变 (E11, E22, E33, E12, E13, E23)

*CONTACT PRINT
CFORCE,   # 接触力 (CNORMF, CSHEARF1, CSHEARF2)
CSTRESS,  # 接触应力 (CPRESS, CSHEAR1, CSHEAR2)
CDISP     # 接触位移 (COPEN, CSLIP1, CSLIP2)
```

### 1.3 续行和注释规则

```
续行: 行尾逗号 → 下一行为续行（包含关键字行）
注释: ** 开头的行为注释
空行: 被忽略
外部引用: *INCLUDE, INPUT=other.inp
```

**续行示例**:
```abaqus
*ELEMENT, TYPE=C3D8R, ELSET=BODY
1, 1, 2, 3, 4,
5, 6, 7, 8
; 等价于: 1, 1, 2, 3, 4, 5, 6, 7, 8
```

### 1.4 完整 INP 文件结构

```abaqus
*HEADING                          ← 作业标题
My Analysis
*NODE, NSET=ALL_NODES             ← 节点定义
...节点数据...
*ELEMENT, TYPE=T2D2               ← 单元定义
...单元数据...
*NSET / *ELSET                    ← Set 定义
...set数据...
*MATERIAL, NAME=STEEL             ← 材料定义
*ELASTIC
210000.0, 0.3
*SOLID SECTION, ELSET=..., MATERIAL=STEEL  ← 截面定义
*STEP, NAME=Step-1                ← 分析步
*STATIC                           ← 分析类型
1.0, 1.0, 0.1, 1.0
*BOUNDARY                         ← 边界条件
SUPPORT, 1, 3, 0.0
*CLOAD                            ← 载荷
TOP_NODES, 2, -1000.0
*NODE PRINT, NSET=ALL_NODES       ← 输出请求
U, RF
*EL PRINT, ELSET=ALL_ELEMENTS
S, E
*END STEP                         ← 步结束
```

---

## 2. DAT 文件格式

### 2.1 文件头

```
                                                          A B A Q U S

               S T A N D A R D   V E R S I O N   6 . 2 4 - 1

               D A T E :   2 5 - J U N - 2 0 2 6   T I M E :   1 2 : 3 0 : 0 0


                             J O B   N A M E :   simple_truss


P R O B L E M   S I Z E

 NUMBER OF ELEMENTS                         7
 NUMBER OF NODES                            5
...
```

**解析要点**:
- 文字中字母间有空格 (S T A N D A R D → STANDARD)
- 版本号可通过正则提取: `V E R S I O N\s+(\d[\d.]*)`
- 作业名在 `J O B   N A M E` 行

### 2.2 Step 和 Increment 边界

```
 S T E P   1    S T A T I C   A N A L Y S I S

 INCREMENT     1  SUMMARY
 TIME       1.0000E+00
 STEP TIME  1.0000E+00
 STEP TIME  1.0000E+00

  ...
```

**解析正则**:
```python
RE_STEP = re.compile(r'S\s+T\s+E\s+P\s+(\d+)\s+(.+)', re.IGNORECASE)
RE_INCREMENT = re.compile(r'INCREMENT\s+(\d+)\s+SUMMARY', re.IGNORECASE)
RE_TIME = re.compile(r'TIME\s+(.+)', re.IGNORECASE)
RE_STEP_TIME = re.compile(r'STEP\s+TIME\s+(.+)', re.IGNORECASE)
```

### 2.3 节点输出表格 (NODE OUTPUT)

```
 N O D E   O U T P U T

 THE FOLLOWING TABLE IS PRINTED FOR NODES BELONGING TO NODE SET ALL_NODES

 NODE FOOT-   U1           U2           U3          UR1          UR2          UR3
      NOTE

    1         0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00
    2        -2.3456E-03   1.2345E-03   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00
    3         0.0000E+00  -5.6789E-03   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00

 MAXIMUM     0.0000E+00   1.2345E-03   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00
 AT NODE          1            2            0            0            0            0
 MINIMUM    -2.3456E-03  -5.6789E-03   0.0000E+00   0.0000E+00   0.0000E+00   0.0000E+00
 AT NODE          2            3            0            0            0            0
```

**表格结构**:
1. `N O D E   O U T P U T` — 表格类型标记
2. `THE FOLLOWING TABLE IS PRINTED FOR ... NODE SET XXX` — SET 名称
3. `NODE FOOT-NOTE   U1   U2   ...` — 表头行1（变量名）
4. `     NOTE` — 表头行2（FOOT-NOTE 列头）
5. 数据行：`节点ID  val1  val2  val3 ...`
6. `MAXIMUM ... AT NODE ...` — 统计行（表格结束标记）

**SET 名称提取正则**:
```python
RE_SET_NAME = re.compile(r'(?:NODE|ELEMENT)\s+SET\s+(\S+)', re.IGNORECASE)
```

### 2.4 单元输出表格 (ELEMENT OUTPUT)

```
 E L E M E N T   O U T P U T

 THE FOLLOWING TABLE IS PRINTED FOR ELEMENTS BELONGING TO ELEMENT SET ALL_ELEMENTS

 ELEMENT  FOOT-  S11          S22          S33          S12
          NOTE

     1          1.2345E+02  -6.7890E+01   0.0000E+00   0.0000E+00
     2         -8.9012E+01   5.4321E+01   0.0000E+00   0.0000E+00

 MAXIMUM       1.2345E+02   5.4321E+01   0.0000E+00   0.0000E+00
 AT ELEMENT           1            2            0            0
 MINIMUM      -8.9012E+01  -6.7890E+01   0.0000E+00   0.0000E+00
 AT ELEMENT           2            1            0            0
```

**关键特征**:
- 表头列: `ELEMENT`, `FOOT-NOTE`, 然后是各变量名
- 数据行第一个值为单元ID
- `MAXIMUM ... AT ELEMENT ...` — 表格结束标记

### 2.5 弹簧单元输出 (特殊 S11 含义)

对于弹簧单元(SPRINGA/SPRING1/SPRING2)，S11 表示**力(N)**而非应力(Pa):

```
 E L E M E N T   O U T P U T

 THE FOLLOWING TABLE IS PRINTED FOR ELEMENTS BELONGING TO ELEMENT SET SPRING_SET

 ELEMENT  FOOT-  S11          E11
 SPRINGA  NOTE

   101         1.5023E+02   1.5023E-02
   102        -9.8456E+01  -9.8456E-03
   103         5.0012E+01   5.0012E-03
```

**解析要点**:
- 表头中包含单元类型 (`SPRINGA`)
- `S11` = 弹簧力 (N)
- `E11` = 相对位移 (m)
- 需要在导出时自动标注正确的物理量单位

### 2.6 接触输出表格 (CONTACT OUTPUT)

```
 C O N T A C T   O U T P U T

 THE FOLLOWING TABLE IS PRINTED FOR THE MASTER SURFACE TOP_SURF OF CONTACT PAIR TOP_BOTTOM

 NODE FOOT-   CNORMF       CSHEARF1     CSHEARF2     CPRESS
      NOTE

   101        1.2345E+01   1.2300E-01  -4.5600E-01   1.2340E+00
   102        2.3456E+01   2.3400E-01  -5.6700E-01   2.3450E+00
   ...

 THE FOLLOWING TABLE IS PRINTED FOR THE SLAVE SURFACE BOTTOM_SURF OF CONTACT PAIR TOP_BOTTOM

 NODE FOOT-   COPEN        CSLIP1       CSLIP2
      NOTE

   201       -1.0000E-03   0.0000E+00   0.0000E+00
   202       -2.0000E-03   1.0000E-04   0.0000E+00
   ...
```

**关键特征**:
- 按主面(MASTER)/从面(SLAVE)分组
- 每对主/从面各有一个子表
- 子表可能包含不同的变量组合（力 vs 位移）
- 接触对名称在描述行中: `OF CONTACT PAIR XXX`

**接触输出正则**:
```python
RE_CONTACT_SURFACE = re.compile(
    r'THE\s+FOLLOWING\s+TABLE\s+IS\s+PRINTED\s+FOR\s+THE\s+'
    r'(MASTER|SLAVE)\s+SURFACE\s+(\S+)\s+OF\s+CONTACT\s+PAIR\s+(\S+)',
    re.IGNORECASE
)
```

### 2.7 分析完成标记

```
 THE ANALYSIS HAS BEEN COMPLETED
```

或:

```
 JOB COMPLETED
```

或 (某些版本):

```
 ANALYSIS COMPLETE
```

### 2.8 JOB TIME SUMMARY

```
 JOB TIME SUMMARY
 USER TIME (SEC)      =    1.23
 SYSTEM TIME (SEC)    =    0.45
 TOTAL CPU TIME (SEC) =    1.68
 WALLCLOCK TIME (SEC) =    2.10
```

---

## 3. 关键解析挑战

### 3.1 DAT 文件解析状态机

正确的状态机设计是 DAT 解析的核心:

```
SCANNING ──→ Step检测 ──→ 创建 StepResult
SCANNING ──→ Increment检测 ──→ 创建 IncrementResult
SCANNING ──→ Output标记 ──→ TABLE_HEADER

TABLE_HEADER ──→ 收集表头行 ──→ 遇到数据行 ──→ TABLE_DATA
TABLE_HEADER ──→ 过长(>5行) ──→ 回退 SCANNING

TABLE_DATA ──→ 空行 ──→ commit → SCANNING
TABLE_DATA ──→ 非数据行 ──→ commit → SCANNING
TABLE_DATA ──→ Step标记 ──→ commit → SCANNING → 重新处理
TABLE_DATA ──→ Contact标记 ──→ commit → TABLE_HEADER
```

### 3.2 表格头部解析

表头跨越多行，需要累积直到检测到数据行:

```python
def _parse_variables_from_header(header_lines):
    """从多行表头中提取变量名列表"""
    known_non_vars = {
        'NODE', 'ELEMENT', 'FOOT', 'NOTE', 'SPRINGA', 'SPRING1',
        'THE', 'FOLLOWING', 'TABLE', 'IS', 'PRINTED', 'FOR',
        'NODES', 'ELEMENTS', 'BELONGING', 'TO', 'SET',
    }

    candidates = []
    for line in header_lines:
        for token in line.split():
            token_upper = token.upper()
            if token_upper in known_non_vars:
                continue
            # 变量名：字母开头，至少2个字符
            if len(token) >= 2 and token[0].isalpha():
                candidates.append(token_upper)

    # 过滤：Abaqus变量名 ≤ 12 字符
    return [v for v in candidates if len(v) <= 12]
```

### 3.3 多列折叠处理

当输出变量超过9列时，Abaqus会将表格折叠为多个子表:
- 前9列 → 第一张表
- 第10-18列 → 第二张表（重复Entity ID列）
- 需要识别并合并这些子表

### 3.4 空白行处理

DAT 文件中的空白行可能表示:
- 页面分隔符 (FORM FEED `\x0c`)
- 表格之间的分隔
- 实际的数据为空值 (较少见)

### 3.5 分页符处理

一些 Abaqus 版本会在 DAT 中插入分页符 (`\x0c` / `\f`)，需要过滤:

```python
def _is_table_end(line):
    if line.strip().startswith('\f') or line.strip() == '\x0c':
        return True
    # ... 其他检查
```

---

## 4. Fortran 数值格式

### 4.1 标准格式

Abaqus DAT 文件使用 Fortran 科学记数法:

| 格式 | 示例 | Python 等价 |
|------|------|------------|
| 标准 E | `1.234E+02` | `123.4` |
| 双精度 D | `1.234D+02` | `123.4` |
| 普通小数 | `1234.5678` | `1234.5678` |
| 省略前导零 | `-.1234E-02` | `-0.001234` |
| 省略 E | `1.234+02` | `123.4` |
| 整数省略 E | `1234+02` | `123400.0` |
| 3位指数 | `1.234E+003` | `1234.0` |
| 溢出标记 | `**********` | `NaN` |

### 4.2 解析算法

```python
def parse_fortran_float(s: str) -> float:
    s = s.strip()
    if '*' in s:
        return float('nan')

    # 1. 双精度 D → E
    s_upper = s.replace('D', 'E').replace('d', 'E')

    # 2. 尝试标准 float 解析
    try:
        return float(s_upper)
    except ValueError:
        pass

    # 3. 处理省略 E: "1.234+02" → "1.234E+02"
    #    也处理整数:"1234+02" → "1234E+02"
    match = re.match(r'^([-+]?)(\d+(?:\.\d*)?)([+-]\d{2,3})$', s)
    if match:
        base = match.group(1) + match.group(2)
        exponent = match.group(3)
        return float(base + 'E' + exponent)

    return float('nan')
```

### 4.3 测试用例覆盖

| 输入 | 期望输出 | 说明 |
|------|---------|------|
| `1.234E+02` | 123.4 | 标准格式 |
| `-1.234E-02` | -0.01234 | 负指数 |
| `1.234D+02` | 123.4 | 双精度 |
| `1234.5678` | 1234.5678 | 普通小数 |
| `-.1234E-02` | -0.001234 | 省略前导零 |
| `1.234+02` | 123.4 | 省略E+正指数 |
| `1.234-02` | 0.01234 | 省略E+负指数 |
| `1.234E+003` | 1234.0 | 3位指数 |
| `**********` | NaN | 溢出标记 |

---

## 5. 接触输出格式

### 5.1 接触变量速查

| 变量 | 物理意义 | 单位 | 输出位置 |
|------|---------|------|---------|
| CNORMF | 法向接触力 | N | MASTER/SLAVE 面 |
| CSHEARF1 | 切向接触力(分量1) | N | MASTER/SLAVE 面 |
| CSHEARF2 | 切向接触力(分量2) | N | MASTER/SLAVE 面 |
| CPRESS | 接触压力 | Pa | MASTER/SLAVE 面 |
| CSHEAR1 | 接触剪应力(分量1) | Pa | MASTER/SLAVE 面 |
| CSHEAR2 | 接触剪应力(分量2) | Pa | MASTER/SLAVE 面 |
| COPEN | 接触面张开距离 | m | SLAVE 面 |
| CSLIP1 | 接触滑移(分量1) | m | SLAVE 面 |
| CSLIP2 | 接触滑移(分量2) | m | SLAVE 面 |

### 5.2 接触结果组织方式

```
CONTACT OUTPUT
  ├── MASTER SURFACE top_surface OF CONTACT PAIR contact_pair_name
  │   ├── CNORMF, CSHEARF1, CSHEARF2  (力 → 节点)
  │   └── CPRESS, CSHEAR1, CSHEAR2   (应力 → 节点)
  │
  └── SLAVE SURFACE bottom_surface OF CONTACT PAIR contact_pair_name
      ├── CNORMF, CSHEARF1, CSHEARF2  (力 → 节点)
      ├── CPRESS, CSHEAR1, CSHEAR2   (应力 → 节点)
      └── COPEN, CSLIP1, CSLIP2      (位移 → 节点)
```

### 5.3 多接触对处理

一个模型可能有多个接触对，DAT 文件按以下顺序输出:
1. 接触对1 → MASTER 力/应力 → SLAVE 力/应力 → COPEN/CSLIP
2. 接触对2 → MASTER 力/应力 → SLAVE 力/应力 → COPEN/CSLIP

---

## 6. 多版本兼容性

### 6.1 已知版本差异

| 版本 | 差异 | 影响 |
|------|------|------|
| 6.x-2016 | `SIG11` 变量名 | 需标准化为 `S11` |
| 2017-2021 | `EP11` 变量名 | 需标准化为 `E11` |
| 2022-2025 | `MAXPRINCIPAL` 等长名 | 长变量名处理 |
| Explicit | `NODE OUTPUT` (无空格) | 模式匹配需兼容 |
| 全部 | 完成标记格式不同 | 多模式匹配 |

### 6.2 变量名别名表

```python
VARIABLE_ALIASES = {
    # 旧名 → 标准名
    "SIG11": "S11", "SIG22": "S22", "SIG33": "S33",
    "SIG12": "S12", "SIG13": "S13", "SIG23": "S23",
    "EP11": "E11", "EP22": "E22", "EP33": "E33",
    "EP12": "E12", "EP13": "E13", "EP23": "E23",
    "MAGNITUDE": "U_MAGNITUDE",
    "MAG": "U_MAGNITUDE",
}
```

### 6.3 编码兼容性

- **英文系统**: UTF-8 (最常见)
- **中文系统**: GBK/GB2312 (Windows) 或 UTF-8 (Linux)
- **日文系统**: SHIFT-JIS
- **通用回退**: Latin-1 (不会失败但可能乱码)

**推荐检测策略**:
1. 优先使用 `chardet` 自动检测
2. 回退到 UTF-8 BOM 检测
3. 依次尝试: UTF-8 → GBK → cp1252 → latin-1

---

## 7. 完整示例

### 7.1 简单桁架模型

**INP 文件** (`simple_truss.inp`):
```abaqus
*HEADING
Simple 2D Truss Model
*NODE, NSET=ALL_NODES
1, 0.0, 0.0, 0.0
2, 100.0, 0.0, 0.0
3, 50.0, 86.6025, 0.0
4, 200.0, 0.0, 0.0
5, 150.0, 86.6025, 0.0
*NSET, NSET=SUPPORT
1, 4
*NSET, NSET=TOP_NODES
3, 5
*ELEMENT, TYPE=T2D2, ELSET=ALL_ELEMENTS
1, 1, 2
2, 2, 3
3, 1, 3
4, 2, 4
5, 3, 4
6, 3, 5
7, 4, 5
*ELSET, ELSET=BOTTOM_CHORD
1, 4
*ELSET, ELSET=TOP_CHORD
6, 7
*ELSET, ELSET=DIAGONALS
2, 3, 5
*MATERIAL, NAME=STEEL
*ELASTIC
210000.0, 0.3
*SOLID SECTION, ELSET=ALL_ELEMENTS, MATERIAL=STEEL
100.0
*STEP, NAME=Step-1
*STATIC
1.0, 1.0, 0.1, 1.0
*BOUNDARY
SUPPORT, 1, 3, 0.0
*CLOAD
TOP_NODES, 2, -1000.0
*NODE PRINT, NSET=ALL_NODES
U, RF
*EL PRINT, ELSET=ALL_ELEMENTS
S, E
*END STEP
```

**DAT 文件解析结果**:
- 1 Step: `Step-1` (STATIC)
- 1 Increment
- 2 表格: NODE_OUTPUT (ALL_NODES, U+RF), ELEMENT_OUTPUT (ALL_ELEMENTS, S+E)

### 7.2 弹簧模型

```abaqus
*HEADING
Spring Element Model
*NODE, NSET=ALL_NODES
1, 0.0, 0.0, 0.0
2, 10.0, 0.0, 0.0
3, 0.0, 10.0, 0.0
4, 10.0, 10.0, 0.0
5, 0.0, 0.0, 10.0
6, 10.0, 0.0, 10.0
*NSET, NSET=FIXED
1, 3, 5
*NSET, NSET=LOADED
2, 4, 6
*ELEMENT, TYPE=SPRINGA, ELSET=SPRING_SET
101, 1, 2
102, 3, 4
103, 5, 6
*SPRING, ELSET=SPRING_SET
1000.0
*STEP, NAME=Step-1
*STATIC
1.0, 1.0, 0.1, 1.0
*BOUNDARY
FIXED, 1, 3, 0.0
*CLOAD
LOADED, 1, 100.0
*NODE PRINT, NSET=ALL_NODES
U, RF
*EL PRINT, ELSET=SPRING_SET
S, E
*END STEP
```

### 7.3 接触模型

```abaqus
*HEADING
Contact Model
*NODE, NSET=ALL_NODES
; 8个节点定义两个接触块
...节点数据...
*ELEMENT, TYPE=C3D8R, ELSET=BLOCK_A
1, 1, 2, 3, 4, 5, 6, 7, 8
*ELEMENT, TYPE=C3D8R, ELSET=BLOCK_B
2, 9, 10, 11, 12, 13, 14, 15, 16
*SURFACE, NAME=TOP_SURF
...面定义...
*SURFACE, NAME=BOTTOM_SURF
...面定义...
*CONTACT PAIR, INTERACTION=FRICTION
TOP_SURF, BOTTOM_SURF
*STEP, NAME=Step-1
*STATIC
1.0, 1.0, 0.1, 1.0
*BOUNDARY
BOTTOM, 1, 3, 0.0
*CLOAD
TOP, 2, -1000.0
*CONTACT PRINT
CFORCE, CSTRESS, CDISP
*NODE PRINT, NSET=ALL_NODES
U
*EL PRINT, ELSET=BLOCK_A, ELSET=BLOCK_B
S
*END STEP
```

---

## 8. 参考资源

### 官方文档

| 资源 | URL |
|------|-----|
| Abaqus Output Reference (2025) | https://docs.software.vt.edu/abaqusv2025/English/SIMACAEOUTRefMap/ |
| Abaqus 输入文件手册 (Harvard) | https://bertoldi.seas.harvard.edu/files/bertoldi/files/abaqusinputfilemanualv1.pdf |
| Abaqus/Standard Output Variables | https://abaqus-docs.mit.edu/2017/English/SIMACAEOUTRefMap/ |

### 开源项目参考

| 项目 | URL | 说明 |
|------|-----|------|
| parser_for_abaqus_input_files | https://github.com/mrettl/parser_for_abaqus_input_files | INP 解析参考实现 |
| abqpy | https://github.com/haiiliin/abqpy | Abaqus Python 类型提示 |
| abaqus_python_batch | https://github.com/NM0ser/abaqus_python_batch | ODB→CSV 批量处理 |
| SPADE | https://github.com/lanl-aea/spade | ODB→HDF5/CSV |
| pybaqus | https://pypi.org/project/pybaqus/ | .fil 文件解析 |

### 社区资源

| 资源 | URL |
|------|-----|
| Simwe 论坛 (中文) | https://forum.simwe.com/ |
| Fidelis FEA Blog | https://www.fidelisfea.com/post/what-does-the-dat-or-data-file-tell-me |
| 技术邻 (中文) | https://www.jishulink.com/ |
| 1CAE (中文) | http://1cae.com/ |

---

> **文档版本**: v1.0  
> **日期**: 2026-06-26  
> **基于**: Abaqus 6.x ~ 2025 各版本 DAT/INP 格式分析 + Web 研究  
> **用途**: Abaqus Data Bridge 开发参考 & 新人学习材料
