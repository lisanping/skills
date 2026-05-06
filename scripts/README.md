# Repository-level scripts

仓库级工具，**不属于任何 pack**。仅用于 lint / 校验，不做生成。

| 脚本                               | 用途                                                                     |
| ---------------------------------- | ------------------------------------------------------------------------ |
| [lint_skill.py](lint_skill.py)     | 校验 SKILL.md frontmatter（name / description / kebab-case / USE WHEN…） |
| [check_naming.py](check_naming.py) | 检查 pack / SKILL / references / scripts 目录与文件命名                  |

## 运行

只依赖 `pyyaml`。任何 pack 的 conda 环境激活后都可运行；也可单独装：

```bash
pip install pyyaml
python scripts/lint_skill.py
python scripts/check_naming.py
```

## 在 CI 中

见 [.github/workflows/lint.yml](../.github/workflows/lint.yml)。
