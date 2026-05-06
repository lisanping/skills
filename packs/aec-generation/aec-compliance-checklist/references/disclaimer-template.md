# 免责声明模板

> **何时读取此文件**：当 SKILL 输出任何合规审查清单或审查结论时（**所有场景都需要免责声明，无例外**）。

---

## 一、为什么需要免责声明

合规审查清单的免责声明不是"防止 LLM 出错的免责"，而是更本质的：

**任何由非注册执业人员出具的"合规判定"，无论使用什么工具，都不能替代法定审查。**

这是中国建筑行业的法律框架：

- 施工图审查由具备资质的**审图机构**完成（《建设工程质量管理条例》）
- 消防审查由**消防主管部门**执行（《消防法》、《建设工程消防设计审查验收管理暂行规定》）
- 人防审查由**人防主管部门**执行
- 注册建筑师 / 注册结构工程师等执业人员对**自己签字的设计文件**负终身责任

SKILL 输出的清单是**自审 / 互审工具**，性质上类似于"设计师自己拿规范对一遍"，不进入法定审查程序。免责声明的作用是确保：

1. 用户不把它当作法定审查的替代
2. 后续传阅时，看到这份文件的人也明确这点
3. 涉及争议时有书面凭证证明本文件的性质

**因此，所有合规审查清单输出末尾都必须带免责声明，不可省略。**

---

## 二、标准免责声明（默认使用）

当 SKILL 输出审查清单时，末尾必须附带以下声明（中文）：

```markdown
---

## 免责声明

**本审查清单基于 [规范号 + 版本] 编制，仅作为初步审查参考，性质为设计自审 / 互审工具。**

1. **不替代法定审查程序**。本清单不构成施工图审查、消防设计审查、人防设计审查、绿建评价或任何政府主管部门审查的替代或补充。最终合规判定须由具备相应资质的审查机构或主管部门执行。

2. **不替代执业人员判断**。本清单中的"通过 / 不通过"判定，均不能替代具备执业资格的注册建筑师、注册结构工程师、注册公用设备工程师、注册电气工程师、注册消防工程师等执业人员的专业判断。最终设计文件的合规性，由执业人员对其签字盖章的成果负责。

3. **规范版本时效性**。本清单引用的规范版本可能已被修订或废止。使用前务必核查当前现行有效版本，并叠加地方标准（如适用）的相应条款。规范条款数值如发现与现行规范不一致，以现行规范为准。

4. **审查范围有限**。本清单覆盖的是常规、通用条款，不能穷尽所有可能的合规要求。具体项目可能涉及：
   - 项目所在地的地方专项规定
   - 项目特殊功能引发的专项规范（如医疗、教育、易燃易爆场所）
   - 主管部门审查意见或专家评审意见

   这些内容超出本清单范围，需另行专项审查。

5. **审查依据有限**。本清单的判定基于审查人提供的设计信息（图纸、参数、说明等）。如设计信息不准确、不完整或后续发生变更，判定结果不再适用。

6. **使用本清单的责任**。下载、参考、应用本清单的任何人，应自行承担使用结果的责任。本清单的编制者和提供者不对因使用本清单而产生的任何后果承担责任。

如有任何疑问或与现行规范、地方标准、主管部门要求冲突，**以现行规范、地方标准、主管部门书面意见为准**。

---
```

---

## 三、按场景的变体

### 3.1 模式 A（生成空白清单）

如果 SKILL 是输出**空白清单供人工填写**，附加一条说明：

```markdown
> **本清单为空白模板**。审查结果待审查人逐项填写"设计值"和"判定"列后产生。
> 空白清单本身不构成任何合规判定。
```

### 3.2 模式 B（已对照设计信息给出判定）

如果 SKILL 是已经对照用户提供的设计信息**做出了判定**，附加：

```markdown
> **本清单的判定结果基于审查人于 YYYY 年 M 月 D 日提供的下列设计信息**：
> [列出用户提供的关键参数 / 文件 / 图纸版次]
>
> 如设计信息后续发生变更，判定结果可能不再有效，需重新审查。
```

### 3.3 模式 B 中含"需进一步信息"项时

```markdown
> **本审查含 [X] 项标注为"需进一步信息"，未做出明确判定**。
> 在补充以下信息前，整体审查不构成完整结论：
> - [列出每条需进一步信息的具体内容]
```

### 3.4 项目处于早期阶段（方案 / 初设）

```markdown
> **本审查在 [方案 / 初步设计] 阶段进行**。
> 部分条款（如施工图详图相关、设备选型相关）在本阶段尚不具备审查条件，
> 已标注为"不适用"或"需进一步信息"，须在施工图阶段补充审查。
```

### 3.5 项目处于施工图阶段

```markdown
> **本审查基于施工图阶段的设计文件**。审查结果反映施工图阶段的合规情况。
> 施工过程中如发生设计变更，应针对变更内容重新审查。
```

### 3.6 涉及强制性通用规范

如审查涉及 GB 55015 / GB 55037 等强制性通用规范，附加：

```markdown
> **本审查涉及强制性通用规范的条款**。强制性通用规范的全部条文均为强制条款，
> 不通过项必须整改，无例外。
```

### 3.7 多版本审查（同时按新旧规范审查）

```markdown
> **本审查同时参照 [旧版本] 和 [新版本] 进行**，目的是识别版本切换的合规风险。
> 如项目按 [旧版本] 立项设计，但需在 [新版本] 生效后竣工验收，
> 应特别关注两版本之间的差异条款。
```

---

## 四、特殊场景下的强化措辞

### 4.1 用户请求"出具合规结论 / 合规证明"

如果用户明确要求 SKILL 出具"合规证明"、"合规通过函"等正式结论文件，**SKILL 必须拒绝**，并使用以下措辞：

```markdown
> 我无法出具"合规证明"或类似的正式结论文件。
> 合规证明只能由具备相应资质的审图机构、政府主管部门或执业人员出具。
> 我可以提供的是**自审清单的填写结果**——这是工具性输出，不是结论性文件。
> 如您需要正式的合规证明，应当向具备资质的机构或人员申请。
```

### 4.2 用户施压"快速给我一个 OK 就行"

```markdown
> 我理解您希望快速推进，但合规审查的"OK"必须基于完整的逐项核对。
> 跳过审查直接判"OK"会带来后续的实际风险——审图驳回、消防整改、甚至运营事故。
> 我建议我们按清单逐项过一遍，对于"需进一步信息"的项可以并行收集，
> 而不是用一个未经验证的"OK"代替。
```

### 4.3 涉及生命安全的关键项目（医院、学校、超高层等）

```markdown
> **本项目属于人员密集或高风险类型**（[具体类别]）。
> 此类项目的合规审查在国家和地方层面均有专项要求，本清单仅覆盖常规通用条款。
> 强烈建议委托具备相应专项审查资质的机构进行专项审查。
```

---

## 五、英文版本（外资项目可选）

如项目是外资背景或需要英文报告，提供以下英文版免责声明：

```markdown
---

## Disclaimer

**This compliance checklist is based on [Code Reference + Version] and serves only as a preliminary review tool for design self-review or peer review.**

1. **Not a substitute for statutory review.** This checklist does not constitute or substitute construction drawing review, fire safety review, civil air defense review, green building assessment, or any review by competent governmental authorities. Final compliance determinations must be made by qualified review institutions or competent authorities.

2. **Not a substitute for licensed professional judgment.** The "Pass / Fail" determinations in this checklist do not substitute for the professional judgment of licensed architects, structural engineers, MEP engineers, fire safety engineers, or other licensed professionals. The compliance of the final design documents is the responsibility of the licensed professionals who sign and seal them.

3. **Code version validity.** The code version referenced in this checklist may have been revised or superseded. Users must verify the currently effective version before use, and apply additional local standards where applicable. In case of discrepancy with the current code, the current code shall prevail.

4. **Limited scope.** This checklist covers common and general provisions and cannot be exhaustive. Specific projects may involve local regulations, special-use codes, authority opinions, and other requirements outside this checklist's scope.

5. **Review based on provided information.** Determinations are based on the design information provided by the reviewer. If the design information is inaccurate, incomplete, or subsequently changes, the determinations may no longer be valid.

6. **User responsibility.** Anyone who downloads, references, or applies this checklist assumes responsibility for the consequences of such use. The author and provider of this checklist accept no liability for any consequences arising from its use.

In case of any conflict with the current code, local standards, or written opinions of the competent authority, **the current code, local standards, or written opinions shall prevail**.

---
```

---

## 六、SKILL 实施要点

1. **不要让用户"关闭" / "省略"免责声明**。即使用户说"这个我都知道，不用每次都加"，SKILL 仍然应当附带——因为这份文件可能会被传阅给其他人。

2. **不要把免责声明放在文档开头**。免责声明放在末尾——读者读完正文后看到声明，不会被声明阻挡阅读。

3. **不要使用过小字号或浅色字体**。免责声明应当与正文同样可见，不可以用"法律小字"的方式弱化。

4. **不要把免责声明翻译成"模糊措辞"**。比如把"不替代法定审查"改成"建议参考法定审查意见"——这是在弱化免责的法律效力。

5. **多语言场景使用对应语言**。如审查报告是英文，使用英文免责声明（见第 5 节）；中英双语报告则两种语言都附。

6. **格式上与正文有视觉分隔**。使用 `---` 分隔线、`##` 标题、加粗等手段确保读者能清楚看到这是声明部分。

---

## 七、与本 SKILL 的关系

- 本 SKILL（aec-compliance-checklist）的主 SKILL.md 已规定"输出末尾的免责声明"为硬性要求
- 任何审查清单输出（包括 Markdown、Excel、Word 格式）都必须包含适配场景的免责声明
- 如审查清单被导出为多个文件（按类别分文件），**每个文件都应附完整免责声明**——避免只看其中一份的人误以为是完整结论
