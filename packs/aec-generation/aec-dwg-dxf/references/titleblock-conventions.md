# 图签 (Titleblock) 约定速查

## 概念

DXF 中图签通常表现为 **INSERT (块引用)** 实体,块名约定俗成,内部含若干 **ATTRIB (属性)** 实体存放图号、图名、版次等信息。

## 常见块名模式

| 来源         | 块名示例                             |
| ------------ | ------------------------------------ |
| AutoCAD 模板 | `TITLEBLOCK`, `TITLE_A1`, `A1_TITLE` |
| Revit 导出   | `M_TitleBlock_A1`, `TitleBlock`      |
| 国内设计院   | `图签`, `A1标题栏`, `A2_标题栏`      |
| 第三方模板   | `BORDER`, `SHEET_BORDER`             |

## 常见 ATTRIB tag → 标准字段映射

| Tag (英文)                | Tag (中文)          | 标准字段                          | 示例值     |
| ------------------------- | ------------------- | --------------------------------- | ---------- |
| `DWG_NO` / `SHEET_NO`     | `图号`              | `drawing_number`                  | A-101      |
| `DWG_NAME` / `SHEET_NAME` | `图名`              | `drawing_title`                   | 一层平面图 |
| `REV` / `REVISION`        | `版次`              | `revision`                        | C          |
| `SCALE`                   | `比例`              | `scale`                           | 1:100      |
| `DATE` / `ISSUE_DATE`     | `日期` / `出图日期` | `date`                            | 2026-04-15 |
| `PROJECT` / `PROJ_NO`     | `项目` / `项目编号` | `project_name` / `project_number` | SHTX-001   |
| `DESIGNER`                | `设计`              | `designer`                        |            |
| `CHECKER`                 | `校对`              | `checker`                         |            |
| `APPROVER`                | `审核` / `审定`     | `approver`                        |            |
| `PHASE`                   | `设计阶段`          | `phase`                           | 施工图     |

## 取值时的注意

1. **大小写不敏感匹配** —— `DWG_NO` / `dwg_no` / `Dwg_No` 都视为同一字段
2. **空属性** 不要忽略 —— 记录为 `null` 而非跳过 (便于检查"图签未填"的图)
3. **多图签** —— 一张 DXF 可能有多个图签 (套图、明细),应返回列表而非单条
4. **嵌套块** —— 图签块内可能嵌套子块,`ezdxf` 的 `attribs` 只取顶层 ATTRIB

## 项目级覆盖

如项目使用非标准图签,在项目根目录放置 `titleblock-config.yaml`,格式:

```yaml
block_name_patterns:
  - "^MyCompany_TB.*"
attrib_field_map:
  TBL_DWG_NO: drawing_number
  TBL_NAME: drawing_title
```

脚本启动时优先加载项目级配置,叠加在内置默认之上。
