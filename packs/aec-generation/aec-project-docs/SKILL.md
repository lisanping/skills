---
name: aec-project-docs
description: "Use this skill whenever the user needs to draft, review, or standardize AEC project communication documents — including RFI (信息请求 / 工程询问), design change orders (设计变更单), engineering correspondence (工程联系单 / 工作联系单), submittal logs, meeting minutes (设计例会 / 工地例会纪要), and daily / weekly construction reports (施工日报 / 周报 / 监理日志). Trigger this skill on phrases like '写一份变更单', '帮我整理今天的工地例会纪要', 'draft an RFI about ...', '生成施工日报', or whenever the user references one of these document types by name, even casually. Also trigger when the user asks to standardize, review, or extract information from an existing document of these types. Do NOT use this skill for technical specifications (use a separate spec-writing skill) or for tender documents (招投标文件)."
---

# AEC 项目通信文档生成

## 目的

这个 SKILL 用来生成 AEC 工程项目中"项目通信类"文档。这一族文档有共同特征：表头字段固定、需要追溯编号、有明确的分发对象、内容字段高度结构化。LLM 自由生成时容易遗漏关键字段（比如"提资单位"、"答复期限"、"分发列表"），SKILL 的价值是把这些必填项作为硬约束。

支持的文档类型：

| 类型 | 中文名 | 主要场景 |
|------|--------|----------|
| RFI | 信息请求单 / 工程询问单 | 施工方/总包向设计方或业主询问图纸或技术信息 |
| 设计变更单 | Design Change Order | 设计方发起的图纸或方案变更 |
| 工程联系单 | Engineering Correspondence | 参建各方之间的非正式工作沟通 |
| 会议纪要 | Meeting Minutes | 设计例会、工地例会、协调会 |
| 施工日报 | Daily Report | 现场每日施工进展、人材机投入、天气、问题 |
| 周报 / 监理日志 | Weekly / Supervision Log | 周度汇总、监理巡视记录 |

## 工作流

### 第 1 步：确定文档类型

如果用户的请求里类型明确（"写一份 RFI"、"会议纪要"），直接进入第 2 步。

如果不明确，**先问一句**而不是猜。例如用户说"帮我把今天和甲方沟通的内容整理一下"，可能是工程联系单也可能是会议纪要——先确认。

### 第 2 步：收集必要信息

每种文档都有"必填字段"和"可选字段"。**必填字段缺一不可**——如果用户没提供，主动询问；若用户明确表示"先用占位符，后面再填"，用 `[待填]` 占位并在结尾汇总提醒。

各类型的必填字段见下方"模板"部分。共有的必填字段：

- 项目名称 / 项目编号
- 文档编号（按编号规则生成，见"编号约定"）
- 日期
- 发出方 / 接收方
- 分发列表（cc）

**跨 SKILL 上下文复用**（来自 `aec-compliance-checklist` 等上游 SKILL）：

如果用户的请求中包含来自 `aec-compliance-checklist` SKILL 的"上下文移交"段落（含项目名称 / 编号、审查依据、不合规条款清单等结构化字段），**直接复用其中字段**，不要再向用户重复询问。具体处理：

- **项目名称 / 项目编号** → 直接填入 RFI / 变更单 / 联系单的表头
- **审查依据**（规范号 + 版本）→ 写入"问题描述"或"变更原因"段落
- **不合规条款清单** → 逐条写入"问题描述"或"变更原因"，保留**条款编号 + 限值 + 设计值 + 超 / 缺数据**的精确表述（不要改写、不要四舍五入）
- **附件**栏增列"合规审查清单（来源：aec-compliance-checklist 第 X 轮输出）"
- 仅在提资人 / 答复人 / 签字栏 / 图纸编号 / 估算造价等**审查清单未覆盖**的字段上向用户追问

**反向移交**：如本 SKILL 输出的变更单 / RFI 触发了"变更后须复审"需求（典型场景：变更单的"变更内容"涉及防火 / 无障碍 / 人防 / 绿建合规条款），**在文档末尾追加一句**：

> **下一步建议**：本变更涉及合规条款（[列出条款]），变更后须重新提交合规审查。请切换到 `aec-compliance-checklist` SKILL 进行复审，并以本变更单为输入。

### 第 3 步：按模板生成

读取 `references/` 下对应的模板文件，按结构填入。**不要重排字段顺序**——表头顺序是行业共识，重排会被甲方/监理打回。

### 第 4 步：输出格式选择

默认产出：

- **简单场景**（用户在聊天里要一份草稿）：直接输出 Markdown，方便复制到邮件或公司系统。
- **正式交付**（用户提到"生成 Word"、"出一份正式文件"、".docx"）：**委托给 `docx` skill 生成 .docx**（详见下方"Word 输出（委托给 docx skill）"）。

如果用户没说，默认 Markdown，并在末尾问一句"是否需要导出 Word 版本？"

#### Word 输出（委托给 `docx` skill）

本 SKILL **不自行实现** .docx 文件的字节级生成。落地路径：

1. **本 SKILL 负责**：内容结构、字段填充、AEC 文档特有的样式约定（页眉=项目名+文档编号、签字栏空白单元格、表头字段表 30/70 列宽等，见 `references/docx-styling.md`）
2. **`docx` skill 负责**：基于 docx-js 的实际文件生成、中文字体设置、表格/页眉页脚渲染、`validate.py` 验证

执行步骤：

1. 读取 `references/docx-styling.md` 取得 AEC 文档特有约定
2. 按 `docx` skill 的 "Creating New Documents" 章节编写 Node.js 脚本（推荐保存到 `output/<doc_id>.js`）
3. 运行 `node output/<doc_id>.js` 生成 .docx
4. 运行 `python .claude/skills/docx/scripts/office/validate.py output/<doc_id>.docx` 验证
5. 验证失败时，按 `docx` skill 的 "unpack → 修 XML → repack" 流程修正

前置依赖：`npm install -g docx`（一次性）。

如运行环境无 Node.js 或 `docx` 包，**明确告知用户**而不是声称已生成；可降级为 Markdown 输出 + 提供脚本由用户本地执行。

---

## 编号约定

项目文档编号是高频出错点。规则如下，按优先级匹配：

1. **如果用户提供了编号规则**，严格使用用户的规则。
2. **如果项目模板里有规则**（用户上传的样例文件），从样例中推断并复用。
3. **否则使用通用回退规则**：

```
{项目代号}-{文档类型代号}-{年}{月}-{流水号}
```

文档类型代号：RFI = `RFI`，变更单 = `DC`（Design Change），联系单 = `EC`（Engineering Correspondence），会议纪要 = `MM`（Meeting Minutes），日报 = `DR`，周报 = `WR`。

例：`SHTX-RFI-202510-005` 表示"上海塔项目第 5 份 RFI，2025 年 10 月发起"。

**绝不要**自己编造一个"看起来合理"的编号格式而不告知用户——明确说"我用了这套回退规则，如果项目有自己的规则请告诉我"。

---

## 模板

以下是核心模板的精简版。完整模板（含示例填写）在 `references/` 下。

### RFI（信息请求单）

必填字段：
- 项目信息（名称、编号、合同段）
- RFI 编号、签发日期
- 提资单位（通常是施工方/总包）
- 答复单位（通常是设计方或业主代表）
- **答复期限**（重要！缺失会导致甲方/设计方无限期拖延）
- 涉及图纸 / 规范条文 / 部位
- 问题描述（用陈述句，避免歧义）
- 提资单位建议方案（可选但推荐）
- 分发列表

详见 `references/rfi-template.md`。

### 设计变更单

必填字段：
- 项目信息、变更单编号、签发日期
- 变更原因（设计优化 / 业主要求 / 现场实际 / 规范更新——必须分类）
- 变更前 / 变更后的描述（图文对照）
- **影响评估**：对工期、造价、其他专业的影响（必填，不能空着）
- 涉及图纸编号、版次
- 设计、审核、审定签字栏
- 分发列表

详见 `references/change-order-template.md`。

### 工程联系单

必填字段：
- 项目信息、联系单编号、日期
- 发出方 / 接收方
- 联系事项（一事一单，不要混合）
- 需对方处理的事项 + 期限
- 附件清单

### 会议纪要

必填字段：
- 会议名称（"第 X 次设计例会"等带流水的命名）
- 时间、地点、主持人
- 参会人员（按单位分组，列名字+职务）
- **议题列表**
- 每个议题下：讨论要点、**决议事项**、责任人、完成时限
- **遗留问题**（明确指出本次未决议的事项）
- 下次会议时间（如已定）
- 分发列表

会议纪要最容易出错的地方是把"讨论"和"决议"混在一起。**SKILL 必须强制把每个议题拆成"讨论要点"和"决议事项"两栏**——前者是过程，后者是结论。如果原始材料没有明确决议，标注"未达成决议，待[X]进一步沟通"，而不是把讨论内容包装成决议。

详见 `references/meeting-minutes-template.md`。

### 施工日报

必填字段：
- 日期、天气（含温度、风力、有无降水——影响混凝土施工等）
- 项目部位 / 当日工作面
- 投入人材机（按工种、班组列）
- 当日完成工作量
- **当日发生的问题与处理**
- 次日计划
- 安全 / 质量事项（即使无事也写"无"，不能空缺）
- 监理 / 甲方现场指令（如有）

详见 `references/daily-report-template.md`。

---

## 输出约定

### Markdown 输出

- 用二级标题区分文档头和正文
- 字段名加粗，值不加粗
- 表格用于"参会人员"、"人材机投入"等结构化内容
- 末尾用 `---` 分隔分发列表

### Word 输出

- A4 纸，1 英寸边距
- 表头用项目颜色（如有，问用户；否则用深蓝 #1E3A5F）
- 字段标签用粗体，值用常规体
- 编号、日期等关键字段用单元格强调
- **签字栏**（变更单、纪要等）用空白下划线，不要留"_____"这种字符占位

详见 `references/docx-styling.md`。

---

## 常见错误（必须避免）

1. **遗漏分发列表**——所有文档类型都需要明确 cc 给谁。如果用户没说，主动追问"这份文件需要发给哪些人？"
2. **答复期限模糊**——RFI 写"尽快答复"等于没写。必须给具体日期或工作日数。
3. **决议项写成动词不定式**——"考虑增加防水层" 不是决议；"由设计院于 X 月 X 日前出防水加强方案" 才是决议。
4. **变更单影响评估空缺**——哪怕填"经评估，对工期和造价无影响"也比留空好，因为留空意味着没评估。
5. **施工日报"无问题"**——现场不可能完全无问题。如果用户提供的素材里没有问题，问一句"今天确实没遇到任何问题吗？还是没记录？"
6. **编造规范条文**——若需要引用规范（如变更原因是"规范更新"），必须问用户具体是哪个规范哪一条；不要自己拼一个看起来合理的条文号。
7. **签字栏写名字**——签字栏只留位置，不要替任何人签字（哪怕用户给了名字），否则可能被误用。

---

## 示例

**用户输入**：
> 帮我写一份 RFI，关于地下二层人防口部的预埋件位置和图纸标注不一致的问题，发给中建院。

**SKILL 应该怎么做**：

1. 识别文档类型：RFI ✓
2. 检查必填字段：缺少"项目名称"、"RFI 编号"、"答复期限"、"涉及具体图纸号"——**先问用户**，不要编造。
3. 询问示例：
   > 我可以起草这份 RFI，但需要确认几个必填项：
   > 1. 项目名称和 RFI 编号（如果项目有编号规则请提供，否则我用通用规则生成一个）
   > 2. 涉及的具体图纸号和图纸版次
   > 3. 期望的答复期限（建议 5–7 个工作日）
   > 4. 这份 RFI 的分发对象（除了中建院，还需要 cc 给谁？）
4. 收齐信息后，按 `references/rfi-template.md` 填充。

---

## 与其他 SKILL 的边界

- **Word / .docx 文件落地** → **委托给 `docx` skill**（本 SKILL 提供内容与样式约定，`docx` skill 提供 docx-js 文件生成与验证）
- 招投标文件 → 用 `aec-tender-docs` SKILL（如果有）
- 技术规格书 / 施工说明书 → 用 `aec-specifications` SKILL（如果有）
- 合规审查清单 → 用 `aec-compliance-checklist` SKILL
- BIM 模型交付检查 → 用 `bim-deliverable-check` SKILL（如果有）

如果用户的请求横跨边界（比如"帮我整理这次设计审查会的纪要，并生成对应的合规审查清单"），分两步走：先用本 SKILL 生成纪要，再切换到合规审查 SKILL。

---

## 配套资源（references/）

本 SKILL 包含以下参考文件，按需读取：

- `references/rfi-template.md` — RFI 完整模板 + 填写示例 + 字段说明
- `references/change-order-template.md` — 变更单模板 + 影响评估清单 + 填写示例
- `references/meeting-minutes-template.md` — 会议纪要模板（设计例会、工地例会各一）+ 填写示例
- `references/daily-report-template.md` — 施工日报模板 + 天气描述规范 + 填写示例
- `references/numbering-conventions.md` — 文档编号规则与变体（标准格式、央企变体、外资项目变体、版次规则）
- `references/docx-styling.md` — Word 输出的样式规范（页面、字体、颜色、表格、签字栏）

### 何时读取哪个文件

| 用户请求 | 读取文件 |
|---------|---------|
| 起草 RFI | `rfi-template.md` |
| 写变更单 | `change-order-template.md` |
| 整理会议纪要 | `meeting-minutes-template.md` |
| 生成施工日报 / 周报 | `daily-report-template.md` |
| 任何文档需要生成编号 | `numbering-conventions.md` |
| 用户要求导出 Word / .docx | `docx-styling.md` |

可按需同时读取多个（如生成 .docx 版本的 RFI 时读取 `rfi-template.md` + `numbering-conventions.md` + `docx-styling.md`）。

---

## 待补充 / 后续迭代

- [ ] 增加"提取信息"模式：用户上传一份既有文档，SKILL 反向解析出结构化字段
- [ ] 增加多语言支持（中英文双语版本，外资项目常用）
- [ ] 与企业 OA 系统的编号规则对接（通过用户上传的样例文件学习）
