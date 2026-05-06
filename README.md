# Skills Monorepo

跨领域的 **Agent SKILL 分享仓库**。每个领域作为独立的 *skill pack* 存放在 [packs/](packs/) 下，自带 Conda 环境、SKILL 集合与测试基线。

> 仓库本身**不是 Python 包**，不发布到 PyPI——它只是文档、SKILL 文件与脚手架的集合。

---

## 包含的 Skill Packs

| Pack                                           | 领域                                                                            | 状态   |
| ---------------------------------------------- | ------------------------------------------------------------------------------- | ------ |
| [packs/aec-generation/](packs/aec-generation/) | AEC（建筑/工程/施工）—— BREP 建模、IFC/DWG 解析、合规审查、规格书、项目通信文档 | active |

新增 pack 请见 [CONTRIBUTING.md](CONTRIBUTING.md)。

---

## 快速导航

| 我想……                       | 看这里                                                                              |
| ---------------------------- | ----------------------------------------------------------------------------------- |
| 让 AI agent 找到正确的 SKILL | [AGENTS.md](AGENTS.md)                                                              |
| 写一个新 SKILL               | [SKILL-SPEC.md](SKILL-SPEC.md) + [templates/skill/](templates/skill/)               |
| 新建一个领域 pack            | [CONTRIBUTING.md](CONTRIBUTING.md) + [templates/skill-pack/](templates/skill-pack/) |
| 了解整体架构                 | [docs/architecture.md](docs/architecture.md)                                        |
| 了解评测/基线方法论          | [docs/evaluation.md](docs/evaluation.md)                                            |

---

## 仓库结构

```text
skills/
├── README.md                       # 你正在看的文件
├── AGENTS.md                       # 顶层 agent 路由
├── CONTRIBUTING.md                 # 贡献指南（新 pack / 新 SKILL 流程）
├── SKILL-SPEC.md                   # SKILL 写作规范（frontmatter 字段、命名）
├── LICENSE                         # MIT
├── .editorconfig
├── .gitignore
│
├── packs/                          # 所有 skill packs
│   └── <pack-name>/
│       ├── README.md
│       ├── AGENTS.md (or CLAUDE.md)
│       ├── environment.yml         # 每个 pack 自己的 Conda 环境
│       ├── pyproject.toml          # 可选：pack 自己的 Python 项目
│       └── .claude/skills/
│           └── <skill-name>/
│               ├── SKILL.md
│               ├── references/
│               └── scripts/
│
├── templates/                      # 复制即可开新 pack/SKILL
│   ├── skill-pack/                 # 整个 pack 的最小骨架
│   └── skill/                      # 单个 SKILL.md 模板
│
├── docs/                           # 框架级长文档
│   ├── architecture.md             # 多 pack 协同 / SKILL 加载机制
│   ├── writing-skills.md           # 触发条件、references 拆分原则
│   └── evaluation.md               # prompt-eval 与 pytest 双轨
│
├── scripts/                        # 仓库级工具
│   ├── lint_skill.py               # 校验所有 SKILL.md 的 frontmatter
│   └── check_naming.py             # 检查 pack/SKILL 命名是否 kebab-case
│
└── .github/
    ├── workflows/                  # CI: lint + naming check
    ├── ISSUE_TEMPLATE/
    └── PULL_REQUEST_TEMPLATE.md
```

---

## 设计约定

1. **Monorepo**：所有 pack 在同一仓库，便于横向参考与统一 CI。
2. **每 pack 独立环境**：每个 pack 自带 `environment.yml`，互不污染（如 OCCT 这种重依赖只装在 AEC pack 里）。
3. **SKILL 加载路径**：每个 pack 内部以 `.claude/skills/<skill-name>/SKILL.md` 组织，与 Claude Code / Anthropic Skills 约定一致。
4. **kebab-case 命名**：pack 名、SKILL 名、文件夹名均使用小写 + 连字符，禁止 `.` 与下划线。

---

## 许可

[MIT](LICENSE)
