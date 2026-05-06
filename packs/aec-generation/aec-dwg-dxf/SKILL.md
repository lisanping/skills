---
name: aec-dwg-dxf
description: "Use this skill whenever the user needs to read, parse, validate, batch-process, or generate DWG / DXF CAD files for AEC projects — including 图层规范检查 (layer compliance), 图签信息提取 (titleblock metadata extraction), 图纸目录生成 (drawing index / sheet list), 批量重命名 (batch rename by titleblock), 块属性查询 (block attribute query), and DXF 几何后处理 (geometry post-processing of BREP-engine outputs). Trigger on phrases like '检查这个 DWG 的图层是否符合制图标准', '从这批图纸里提取图号和版次', '生成图纸目录', '批量重命名 DWG 文件', 'parse DXF titleblock', 'extract attributes from blocks'. Also trigger when the user uploads .dwg / .dxf files and asks to inspect, validate, or summarize them. Built on top of ezdxf. Do NOT use this skill for IFC parsing (use aec-ifc-parser), PDF drawings (use a PDF skill), or for generating new architectural geometry (use aec-building)."
---

# AEC DWG / DXF 文件处理

## 目的

DWG / DXF 是 AEC 行业最流通的图纸交换格式。痛点:

1. **图层规范 (制图标准 / GB/T 18112)** 不统一,跨单位协作时图层混乱
2. **图签 (titleblock)** 信息散落在块属性里,人工抽取耗时易错
3. **图纸目录** 通常人工维护,与实际图纸不一致
4. **批量操作** (重命名、版本归档、属性查询) 缺少标准脚本

本 SKILL 沉淀**怎么用对 ezdxf 库**的工程经验,把常见操作固化为可复用脚本,避免重复踩坑。

## 技术栈

- **核心库**:[`ezdxf`](https://ezdxf.readthedocs.io/) ≥ 1.1
- **DWG 支持**:ezdxf 仅原生支持 DXF;DWG 需先用 ODA File Converter 或 LibreDWG 转 DXF
- **不依赖** AutoCAD / ARX / .NET API

## 工作流

### 第 1 步:确认输入格式

| 输入 | 处理 |
|------|------|
| `.dxf` (任何版本) | 直接 `ezdxf.readfile()` |
| `.dwg` | 提示用户先转换为 DXF (ODA File Converter / LibreDWG),或调用 `scripts/dwg2dxf.py` |
| 多个文件 / 文件夹 | 批量遍历模式 |

### 第 2 步:识别任务类型

按用户意图分发到 `scripts/` 下对应脚本:

| 任务 | 脚本 | 说明 |
|------|------|------|
| 图层合规性检查 | `scripts/check_layers.py` | 对照图层标准 YAML,输出违规清单 |
| 图签信息提取 | `scripts/extract_titleblock.py` | 从 INSERT 块属性抽取图号/版次/比例/图名 |
| 图纸目录生成 | `scripts/generate_index.py` | 批量提图签 → 生成 sheet list (Markdown / CSV / Excel) |
| 批量重命名 | `scripts/batch_rename.py` | 按图签内容重命名文件 (含 dry-run 模式) |
| 块属性查询 | `scripts/query_blocks.py` | 按块名 / 属性过滤,导出 CSV |
| 几何统计 | `scripts/geom_summary.py` | 统计实体数、范围框、图层分布 |

### 第 3 步:输出与产物

- **报告**:Markdown 或 JSON,默认写到 `output/dwg-dxf/<job_id>/`
- **修改后的 DXF**:**绝不覆盖原文件**,统一写到 `output/dwg-dxf/<job_id>/processed/`
- **批量重命名**:默认 `--dry-run`,用户确认后再 `--apply`

### 第 4 步:跨 SKILL 联动

- 来自 `aec-building` 的 `model.dxf` 输出 → 可直接走"图层合规性检查"流程
- 提取出的图签 (项目名 / 图号) → 可作为 `aec-project-docs` 生成提交物清单的输入
- 图纸目录 → 可作为 `aec-compliance-checklist` "施工图自审清单"的来源

## 关键脚本骨架

### `scripts/extract_titleblock.py` (核心)

```python
"""从 DXF 中提取图签 (titleblock) 信息。

约定:图签为 INSERT 实体,块名匹配 BLOCK_NAME_PATTERNS,
属性 (ATTRIB) 的 tag 在 ATTRIB_FIELD_MAP 中映射到标准字段。
"""
import ezdxf
from pathlib import Path
import json
import re

# 常见图签块名 (可被项目级配置覆盖)
BLOCK_NAME_PATTERNS = [
    r"^TITLEBLOCK.*",
    r"^TITLE.*",
    r"^图签.*",
    r"^A[0-4]_?标题栏.*",
]

# ATTRIB tag → 标准字段
ATTRIB_FIELD_MAP = {
    "DWG_NO":       "drawing_number",
    "图号":         "drawing_number",
    "DWG_NAME":     "drawing_title",
    "图名":         "drawing_title",
    "REV":          "revision",
    "版次":         "revision",
    "SCALE":        "scale",
    "比例":         "scale",
    "DATE":         "date",
    "日期":         "date",
    "PROJECT":      "project_name",
    "项目":         "project_name",
}


def extract(dxf_path: Path) -> dict:
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    patterns = [re.compile(p, re.IGNORECASE) for p in BLOCK_NAME_PATTERNS]

    for insert in msp.query("INSERT"):
        if not any(p.match(insert.dxf.name) for p in patterns):
            continue
        record = {"block_name": insert.dxf.name, "source": str(dxf_path)}
        for attrib in insert.attribs:
            field = ATTRIB_FIELD_MAP.get(attrib.dxf.tag.upper())
            if field:
                record[field] = attrib.dxf.text
        return record
    return {"source": str(dxf_path), "error": "no titleblock found"}


if __name__ == "__main__":
    import sys
    result = extract(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
```

### `scripts/check_layers.py` (核心)

依据 `references/layer-standards.yaml` 中的图层白名单 / 命名正则,
扫描 DXF 中所有图层,输出:
- 缺失的强制图层
- 命名不规范的图层
- 颜色 / 线型与标准不符的图层

### `scripts/generate_index.py`

遍历目录下所有 DXF → 调 `extract_titleblock.extract()` → 汇总为 sheet list。

输出格式:
```markdown
| 图号 | 图名 | 版次 | 比例 | 日期 | 文件 |
|------|------|------|------|------|------|
| A-101 | 一层平面图 | C | 1:100 | 2026-04-15 | A-101_一层平面图_RC.dxf |
```

### `scripts/batch_rename.py`

按规则 `{drawing_number}_{drawing_title}_R{revision}.dxf` 批量重命名。

**安全约束**:
- 默认 `--dry-run`,只打印计划,不实际重命名
- `--apply` 才执行
- 重命名前在 `output/.../rename-log.json` 记录映射关系,便于回滚

## 边界

- ❌ 不解析 DWG 二进制 (转 DXF 后处理)
- ❌ 不渲染 / 不出图 (PDF 出图属于另一个 SKILL)
- ❌ 不做几何修复 / 闭合检查 (属于 BIM 模型审查 SKILL)
- ❌ 不做参数化建模 (使用 `aec-building`)
- ✅ 只做 **元数据 + 图层 + 块属性** 的读取、校验、批量操作

## 依赖检查

```bash
python -c "import ezdxf; print(ezdxf.__version__)"   # 需要 ≥ 1.1
```

如未安装:`pip install ezdxf`

## 参考文件

- `references/layer-standards.yaml` —— GB/T 18112 + 常见公司图层标准
- `references/titleblock-conventions.md` —— 常见图签块名与属性约定
- `references/ezdxf-cookbook.md` —— ezdxf 常见操作速查 (实体查询、块解包、几何边界)

## 免责声明

输出仅为**自动化读取结果**。涉及合规性结论 (是否满足公司制图标准、是否可归档),需由 BIM / CAD 管理员复核。
