---
name: aec-spec-writer
description: "Use this skill whenever the user needs to draft, review, or standardize 施工说明书 / 技术规格书 (construction specifications / technical specifications) for AEC building projects — including 建筑施工图设计说明、结构施工图说明、装修做法说明、CSI MasterFormat / SectionFormat 三段式技术规格书. Trigger on phrases like '写一份建筑设计说明', '生成装修做法表', 'draft a Division 09 spec', '帮我整理施工说明书', '出一份技术规格书章节', or whenever the user references a specification document by name. Also trigger when the user uploads design drawings / model summary and asks to generate the corresponding 设计说明 or 做法表. Do NOT use this skill for project-communication documents (use aec-project-docs), compliance checklists (use aec-compliance-checklist), or tender documents (招投标文件)."
---

# AEC 施工说明书 / 技术规格书生成

## 目的

施工说明书 / 技术规格书是把"图纸画不出来的内容"以文字形式约束下来的法定交付物。LLM 自由生成时容易出现两类错误：

1. **章节顺序错乱** —— 不符合《建筑工程施工质量验收统一标准》或 CSI MasterFormat 编码体系
2. **引用规范号错误** —— 编造不存在的 GB / JGJ 编号,或引用已废止版本

本 SKILL 的职责是把**章节骨架、术语用法、规范引用格式**作为硬约束固化下来,避免"看着像但不规范"。

## 支持的文档类型

| 类型 | 适用阶段 | 体系 |
|------|---------|------|
| 建筑施工图设计说明 | 施工图 | 国标(GB/T 50001) |
| 结构施工图设计说明 | 施工图 | 国标 + 地标 |
| 装修做法说明 / 做法表 | 施工图 / 深化 | 国标做法表格式 |
| CSI 技术规格书 (3-Part) | 国际项目 / EPC | CSI MasterFormat 2020 |

## 工作流

### 第 1 步:确定文档类型与体系

- 国内项目默认走国标体系;
- 提到 "Division XX"、"Part 1/2/3"、"MasterFormat"、英文项目时切换到 CSI 体系;
- 不明确时**先问一句**,不要猜测。

### 第 2 步:收集项目基础信息

必填字段(缺一不可):

- 项目名称 / 项目编号 / 设计阶段
- 建设单位 / 设计单位 / 设计人 / 校对 / 审核
- 工程概况(用地面积、建筑面积、建筑高度、层数、结构形式、耐火等级、抗震设防烈度)
- 设计依据(现行规范清单 + 版本号)

**跨 SKILL 上下文复用**:
- 来自 `aec-building` 的几何 / 构造摘要 → 直接填入"工程概况"和"主要构造做法"
- 来自 `aec-compliance-checklist` 的"审查依据"清单 → 直接填入"设计依据"章节,**保留规范号 + 年份的精确表述**

### 第 3 步:按章节骨架填写

读取 `references/` 下对应模板:

- `references/architectural-spec-template.md` —— 建筑设计说明
- `references/structural-spec-template.md` —— 结构设计说明
- `references/finish-schedule-template.md` —— 装修做法表
- `references/csi-3part-template.md` —— CSI 三段式规格书

**不要重排章节顺序**。章节顺序是审图机构的检查清单,重排会被打回。

### 第 4 步:规范引用校验

每条引用必须包含:**规范号 + 年份 + 名称**,例如:

```
《建筑设计防火规范》GB 50016-2014 (2018 年版)
```

禁止形式:
- ❌ "按防火规范要求" (无编号)
- ❌ "GB 50016" (无年份)
- ❌ "GB 50016-2006" (已废止)

如不确定现行版本,**标注 `[待核实版本]`** 让用户确认,**不要猜**。

`references/code-reference-format.md` 维护当前主流规范的现行版本号清单。

### 第 5 步:输出格式

- 默认 Markdown,便于复制到设计交底文档
- 用户提到 "Word"、"出图说明"、".docx" → 委托 `docx` skill 生成
- 用户提到 "图纸说明" / "图框注释" → 输出可直接贴入 CAD 文字框的纯文本格式(无 Markdown 标记)
- **装修做法表 / 门窗表 / 房间表** → 优先调用 `scripts/finish_schedule_xlsx.py` 生成 `.xlsx`,
  比 Markdown 更便于设计院归档与施工方查阅。输入为 JSON 列表(见 `references/finish-schedule-example.json`),
  脚本会校验编号唯一性、前缀合法性、燃烧性能等级合法性。

## 章节骨架(精简版)

### 建筑施工图设计说明(国标)

完整模板见 `references/architectural-spec-template.md`,顶层章节:

1. 工程概况
2. 设计依据(规范、文件、批复)
3. 设计标高与定位
4. 墙体工程
5. 楼地面、屋面、门窗、装修工程
6. 防水、保温、防火构造
7. 无障碍设计
8. 室内外装修做法表
9. 节能设计专项说明
10. 施工注意事项

### CSI 技术规格书(三段式)

每个 Section 严格按 Part 1 / 2 / 3 组织:

- **Part 1 — General**:Summary, References, Submittals, Quality Assurance, Delivery & Storage, Warranty
- **Part 2 — Products**:Manufacturers, Materials, Accessories, Fabrication, Source Quality Control
- **Part 3 — Execution**:Examination, Preparation, Installation, Field Quality Control, Cleaning, Protection

详见 `references/csi-3part-template.md`。

## 边界

- ❌ 不做结构 / 节能 / 暖通的**计算书**(那是计算与校核类 SKILL)
- ❌ 不做图纸目录 / 图签编排(交付物标准化类 SKILL)
- ❌ 不做招投标技术标(虽然格式相近,但响应逻辑不同,需独立 SKILL)
- ✅ 只做"以文字形式补充图纸"的设计说明 / 规格书

## 免责声明

本 SKILL 输出为**初稿辅助**,所有引用规范的现行有效性、做法的工程合理性,**必须由注册建筑师 / 注册结构工程师复核盖章**后方可用于施工。
