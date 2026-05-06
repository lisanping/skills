# 测试与评测方法论

本仓库 SKILL 分两类，各自的测试方式不同：

| 类型       | 例                                             | 测试方式                                          |
| ---------- | ---------------------------------------------- | ------------------------------------------------- |
| **代码类** | `aec-building` BREP 引擎                       | `pytest` 单元测试                                 |
| **文档类** | `aec-compliance-checklist`, `aec-project-docs` | **prompt-based eval**（手工执行 + JSON 二元判定） |

---

## 1. 代码类 SKILL（pytest）

放在 `packs/<pack>/tests/test_*.py`。约定：

```bash
cd packs/<pack>
conda activate <pack>
pytest tests/ -v
```

- 重依赖测试（如 OCCT / CadQuery）用关键词标记，可跳过：`pytest -k "not BREP"`
- fixtures 放 `tests/fixtures/`（git 跟踪小样本，大样本走 git-lfs 或脚本生成）

---

## 2. 文档类 SKILL（prompt-eval）

### 文件布局

```text
packs/<pack>/tests/
├── BASELINE-v1.0.md              # 基线清单 + 变更控制规则
├── test-design-rationale.md      # 测试集设计思路
├── <skill>.evals.json            # 用例 + expectations
├── cross-skill.evals.json        # 跨 SKILL 协同用例
└── results/                      # 每轮报告（不覆盖）
    ├── 2026-04-29-baseline.md
    └── 2026-05-03-fix-rfi-template.md
```

### evals.json 格式

```json
{
  "skill": "aec-project-docs",
  "version": "1.0",
  "cases": [
    {
      "id": "rfi-001",
      "input": "帮我写一份关于 3 层楼板厚度变更的 RFI",
      "expectations": [
        "包含 RFI 编号字段",
        "包含发起人 / 接收人字段",
        "包含技术问题描述段",
        "格式遵循 references/rfi-template.md"
      ]
    }
  ]
}
```

### 执行流程

1. 开发者按 SKILL workflow 在真实 agent 中执行 `input`
2. 对照 `expectations` **逐条** ✓/✗ 二元判定
3. 报告写入 `tests/results/<date>-<topic>.md`，记录通过率与失败原因
4. 通过率与基线对比；下降需先修复或更新测试

---

## 3. 基线（Baseline）

每个 pack 维护一份 `tests/BASELINE-vX.Y.md`，包含：

- 测试集清单（文件路径 + 用例数 + expectations 数）
- 当前通过率
- 对应 git tag（如 `aec-skills-baseline-v1.0`）
- 上次更新时间

### 升级基线的触发条件

- 新增测试集
- 通过率提升（且非测试用例放水）
- SKILL 大版本升级

升级时打新 tag：`<pack>-baseline-v<major>.<minor>`。

---

## 4. 修改 SKILL 的测试 SOP

```text
1. 改前：在当前基线下复跑对应测试集，记下通过率
2. 一次只改：SKILL.md / references / scripts / evals 中的一处
3. 整轮重跑：通过率 ≥ 改前才能合入
4. 通过率下降：评估是 SKILL 退化还是测试用例需更新
5. 任何变更：在 tests/results/ 下追加新报告（不覆盖）
```

---

## 5. CI

仓库级 CI（[.github/workflows/](../.github/workflows/)）只跑：

- `scripts/lint_skill.py`：frontmatter 校验
- `scripts/check_naming.py`：命名校验

**不在 CI 跑 pytest 与 prompt-eval**——前者每个 pack 的依赖太重（OCCT 等），后者本身就是手工执行。pack 维护者在本地跑通后提交结果到 `tests/results/`。
