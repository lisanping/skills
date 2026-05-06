# AGENTS.md (pack-level)

> Agent 在执行本 pack 范围内任务前的二级路由。先读完此文件，再进入对应 SKILL.md。

## Pack 定位

一句话说明此 pack 解决的问题域、输入与输出。

## SKILL 路由

| 任务              | 先读                                   |
| ----------------- | -------------------------------------- |
| TODO 描述任务类型 | `.claude/skills/<skill-name>/SKILL.md` |

## 变量

| 变量          | 值               |
| ------------- | ---------------- |
| `SKILLS_ROOT` | `.claude/skills` |

所有 SKILL 路径相对于 `SKILLS_ROOT`。

## 关键命令

```bash
conda activate <pack-name>
pytest tests/ -v
```

## 编码约定

- 源代码：`src/<package>/`
- 示例：`examples/`
- 输出：`output/`（git-ignored）
- 测试：`tests/test_*.py`
