# 写作 SKILL 的实操指南

> 本文件是 [SKILL-SPEC.md](../SKILL-SPEC.md) 的**操作手册**。规范说"必须怎样"，本文件说"为什么 + 怎么做好"。

---

## 1. 起步：复制模板

```bash
cp -r templates/skill packs/<pack>/.claude/skills/<new-skill>
```

然后做 4 件事：

1. 改 `SKILL.md` frontmatter 的 `name`（必须等于目录名）
2. 写 `description`（决定 agent 何时触发，最关键）
3. 写 workflow 步骤
4. 删模板里的 TODO 占位

---

## 2. 写 description 的方法论

`description` 是 agent 路由的**唯一线索**——它不读你的 workflow 来判断要不要激活。

### 公式

```
<动词短语描述能力>。
USE WHEN <用户语义 1> / <用户语义 2> / <用户语义 3>。
DO NOT USE for <反例 1> / <反例 2>。
```

### 检查清单

- [ ] 第一句**用动词开头**说能力，不要写"This is a skill that..."
- [ ] **USE WHEN** 列举至少 2 个具体场景，避免"general purpose"
- [ ] **DO NOT USE** 列举常被混淆的相邻领域（防误触发）
- [ ] 全文 ≤ 200 字
- [ ] 关键词与你期望用户输入的措辞一致（如用户会说"防火"，就写"防火"而不是"消防"）

---

## 3. references/ 的拆分原则

把内容放进 `references/` 而不是 `SKILL.md` 的判据：

| 场景                                 | 放哪里                                       |
| ------------------------------------ | -------------------------------------------- |
| 每次任务都要读                       | `SKILL.md`                                   |
| 仅特定子任务才用（如某条规范的细则） | `references/<topic>.md`                      |
| 长篇模板 / 表格 / YAML 配置          | `references/`                                |
| 易过时的版本号、规范条文             | `references/` 且首行声明"使用前核查现行版本" |

### 阈值

- `SKILL.md` 控制在 ≤ 200 行
- 单个 reference 文件 ≤ 500 行；超出考虑再拆

---

## 4. scripts/ 的写法

### 原则

- **CLI parameterized**：路径与参数走 argparse / click，不硬编码
- **Help-able**：`--help` 必须可运行，且说明每个参数
- **Idempotent**：同输入跑两次结果一致
- **No hidden side effects**：未传 `--write` 就只读
- **Diagnosable failures**：异常含 `fix_action: ...` 提示

### 反例

```python
# ❌ 硬编码路径
def main():
    df = pd.read_csv("/Users/me/data.csv")
```

```python
# ✅ CLI
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    df = pd.read_csv(args.input)
```

---

## 5. 触发场景的"误触发"测试

写完 SKILL 后，构造 5–10 条用户提问，自检：

| 提问                  | 期望                                       | 实际 |
| --------------------- | ------------------------------------------ | ---- |
| "帮我画个 L 形办公楼" | aec-building 触发                          | ?    |
| "RFI 怎么写"          | aec-project-docs 触发，aec-building 不触发 | ?    |
| "Photoshop 怎么用"    | 全部不触发                                 | ?    |

如果误触发 / 漏触发，调整 `description` 的 USE WHEN / DO NOT USE。

---

## 6. 文档类 vs 代码类 SKILL

| 维度       | 文档类（如合规审查）                    | 代码类（如 BREP 引擎）               |
| ---------- | --------------------------------------- | ------------------------------------ |
| 主要资产   | `references/` 模板与清单                | `scripts/` 与 `src/`                 |
| 测试方式   | prompt-eval（手工执行 + JSON 二元判定） | `pytest` 单元测试                    |
| 触发关键词 | 用户业务语言（"出 RFI"、"消防自审"）    | 用户技术语言（"导出 IFC"、"画楼梯"） |

---

## 7. 完成后的 5 步检查

```bash
# 1. frontmatter 校验
python scripts/lint_skill.py packs/<pack>/.claude/skills/<skill>

# 2. 命名校验
python scripts/check_naming.py

# 3. SKILL.md 行数（建议 ≤ 200）
wc -l packs/<pack>/.claude/skills/<skill>/SKILL.md

# 4. 误触发自测（手工）

# 5. 把 SKILL 加进 pack 的 README.md / AGENTS.md 路由表
```
