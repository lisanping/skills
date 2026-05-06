# Contributing

欢迎为本仓库贡献新的 *skill pack* 或在已有 pack 内新增 SKILL。本文件描述两种贡献的标准流程。

---

## 三种贡献类型

| 类型                               | 改动范围                                   | 必读                                       |
| ---------------------------------- | ------------------------------------------ | ------------------------------------------ |
| 新增**单个 SKILL**（已有 pack 内） | `packs/<pack>/.claude/skills/<new-skill>/` | [SKILL-SPEC.md](SKILL-SPEC.md)             |
| 新增**整个 pack**（新领域）        | `packs/<new-pack>/` 全部                   | 本文件 §2                                  |
| 修复 / 完善已有 SKILL              | 单个 SKILL.md 或 reference                 | [SKILL-SPEC.md](SKILL-SPEC.md) §"修改流程" |

---

## 1. 在已有 pack 内新增 SKILL

```bash
# 1. 复制单 SKILL 模板
cp -r templates/skill packs/<pack-name>/.claude/skills/<new-skill-name>

# 2. 编辑 SKILL.md 的 frontmatter 与正文
#    - name: 必须等于目录名
#    - description: 必含 USE WHEN... / DO NOT USE...
#    - 详见 SKILL-SPEC.md

# 3. 校验
python scripts/lint_skill.py packs/<pack-name>/.claude/skills/<new-skill-name>
python scripts/check_naming.py

# 4. 在该 pack 的 README.md / AGENTS.md 路由表中追加一行
```

---

## 2. 新增一个 pack

```bash
# 1. 复制 pack 模板
cp -r templates/skill-pack packs/<new-pack-name>

# 2. 编辑以下文件
#    - README.md：领域定位、SKILL 列表、安装命令
#    - AGENTS.md：内部 agent 路由
#    - environment.yml：把 name 改为 <new-pack-name>
#    - pyproject.toml：可选，如果 pack 含 Python 包

# 3. 创建至少一个 SKILL（见 §1）

# 4. 在仓库根的 README.md / AGENTS.md 路由表中追加一行

# 5. 校验
python scripts/lint_skill.py
python scripts/check_naming.py
```

### Pack 必备文件清单

- [ ] `README.md` —— 面向人类的首页
- [ ] `AGENTS.md` 或 `CLAUDE.md` —— 给 agent 的内部路由
- [ ] `environment.yml` —— Conda 环境定义，`name` 与 pack 同名
- [ ] `.claude/skills/<skill>/SKILL.md` —— 至少一个 SKILL
- [ ] `.gitignore` —— 如果 pack 产生大型输出，单独忽略

### Pack 可选文件

- `pyproject.toml` —— 如果 pack 内含 Python 源码
- `tests/` —— 单元测试或 prompt-eval 测试集
- `examples/` —— 用例脚本
- `output/`（git-ignored）—— 模型/文档输出

---

## 命名规范（强制）

| 对象           | 规则                                   | 例                                           |
| -------------- | -------------------------------------- | -------------------------------------------- |
| Pack 目录      | kebab-case                             | `aec-generation` ✓ &nbsp; `aec.generation` ✗ |
| SKILL 目录     | kebab-case，与 SKILL.md `name` 一致    | `aec-building` ✓                             |
| reference 文件 | kebab-case + `.md` / `.yaml` / `.json` | `code-versions.md` ✓                         |
| Python 文件    | snake_case + `.py`                     | `lint_skill.py` ✓                            |

[scripts/check_naming.py](scripts/check_naming.py) 会在 CI 强制执行。

---

## SKILL.md frontmatter 必填字段

```yaml
---
name: my-skill                    # 必须等于目录名
description: |                    # 必含 USE WHEN... 与 DO NOT USE...
  USE WHEN the user wants to ...
  DO NOT USE for ...
argument-hint: 'one-line input hint'   # 可选
---
```

详细字段语义见 [SKILL-SPEC.md](SKILL-SPEC.md)。

---

## 修改流程（已有 SKILL）

1. **改前先跑测试**：在该 pack 当前基线下执行 `pytest` 或人工 eval；记下当前通过率。
2. **小步改动**：一次只改 `SKILL.md` / `references/` / `scripts/` / `evals.json` 中**一处**。
3. **整轮重跑**：通过率必须 ≥ 改前；下降时先评估是 SKILL 退化还是测试用例需更新。
4. **追加报告**：在 `tests/results/` 下追加新报告，**不覆盖**原报告。
5. **更新基线**：通过率提升或测试集扩充后，更新 `tests/BASELINE-vX.Y.md` 并打 git tag。

---

## Pull Request 检查清单

- [ ] 遵循 kebab-case 命名
- [ ] `python scripts/lint_skill.py` 通过
- [ ] `python scripts/check_naming.py` 通过
- [ ] 涉及的 SKILL 测试通过率 ≥ 改前
- [ ] 更新了对应的 README.md / AGENTS.md 路由表
- [ ] 没有提交大型二进制文件（CAD / IFC / docx 等，请 git-ignore）
