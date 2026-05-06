---
name: skill-name
description: |
  One-sentence summary of what this skill does.
  USE WHEN the user wants to <action 1> / <action 2> / <action 3>.
  DO NOT USE for <out-of-scope 1> / <out-of-scope 2>.
argument-hint: 'one-line description of expected user input'
---

# skill-name SKILL

> 删除本提示后再提交。完整规范见仓库根 `SKILL-SPEC.md`。

## What this skill does

一段说明：此 SKILL 的输入、输出与边界。

## When to use

- 触发条件 1
- 触发条件 2

## When NOT to use

- 反触发 1
- 反触发 2

## Workflow

1. 读 [references/your-reference.md](references/your-reference.md)
2. 调用 `python scripts/your_script.py --input ...`
3. 验证产物，向用户报告

## Key entry points

| Entry | When to use |
|---|---|
| `scripts/your_script.py` | TODO |

## Constraints

- 不可违反的硬约束 1
- 不可违反的硬约束 2

## References

- [references/your-reference.md](references/your-reference.md) —— 何时按需读取
