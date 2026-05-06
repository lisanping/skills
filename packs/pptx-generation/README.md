# PPTX Generation Skills

模板感知的 PowerPoint 生成与分析 SKILL 集合。覆盖**模板剖析 → 内容编排 → 品牌合规生成 → 图像填充 → 底层 .pptx 操作**的完整链路。

| SKILL                         | 用途                                   | 触发场景                                                                                                            |
| ----------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| **`pptx-profiler`**           | 模板结构 + 视觉语义剖析                | "分析这个模板"、"这套 .potx 有哪些版式"、"提取品牌画像"，或下游 SKILL 需要 `template-profile.json`                  |
| **`branded-pptx-generator`**  | 基于企业模板的品牌合规演示文稿生成     | "按这套模板出片"、"匹配我们的品牌风格"、"corporate deck"；strict / balanced / creative 三档姿态                     |
| **`narrative-pptx-composer`** | 内容驱动的叙事型演示文稿生成           | "把这份报告做成 PPT"、"做一份说服董事会的汇报"、"把这张草图变成 PPT"、"美化这份 PPT"                                |
| **`image-generator`**         | 批量 AI 配图（Azure gpt-image / FLUX） | 任何 SKILL 需要按 prompt 批量生成图片；接受 JSON 请求清单，输出 `images/*.png` + 清单                               |
| **`pptx`**（基础设施）        | `.pptx` 解包/打包/加片/校验/渲染       | 被 `branded-pptx-generator` / `narrative-pptx-composer` 委托使用；本身也直接面向"读 / 编辑 / 创建"任意 .pptx 的任务 |

详细路由见 [AGENTS.md](AGENTS.md)。

---

## 项目结构

```text
pptx-generation/
├── README.md                         # 本文件
├── AGENTS.md                         # SKILL 路由（含变量约定）
├── environment.yml                   # Conda 环境（name: pptx-generation）
├── .env.example                      # image-generator 后端凭据模板（复制到项目根使用）
├── .gitignore                        # 忽略 output / 中间 .pptx / 图片 / .env
│
├── pptx-profiler/                    # 模板剖析
│   ├── SKILL.md
│   ├── prompts/                      # VLM 分析提示词
│   ├── schemas/                      # template-profile / composer-digest JSON schema
│   └── scripts/                      # extract_template / render_layouts / render_samples / …
│
├── branded-pptx-generator/           # 品牌合规生成
│   ├── SKILL.md
│   ├── prompts/                      # 模式宣言、生成策略提示词
│   ├── references/                   # mode-philosophy / 各模式的姿态说明
│   ├── schemas/                      # plan / style policy JSON schema
│   └── scripts/                      # validate_plan / compliance_checker / extract_slide_elements
│
├── narrative-pptx-composer/          # 叙事型生成（9 步工作流）
│   ├── SKILL.md
│   ├── references/                   # design-principles / batching-strategy / python-pptx-guide …
│   ├── schemas/                      # 各步骤 s01 ~ s09 的 JSON schema
│   └── scripts/                      # s01_validate_inputs … s08_precompute_metrics
│
├── image-generator/                  # 批量配图
│   ├── SKILL.md
│   ├── .env.example                  # 后端凭据模板（pack 级 .env.example 是其升级版）
│   ├── schemas/                      # image_requests / output 清单 schema
│   └── scripts/generate_images.py    # 异步并发，支持 gpt-image-1.5 / FLUX
│
└── pptx/                             # 底层 .pptx 操作（被上面三个 SKILL 委托）
    ├── SKILL.md
    ├── LICENSE.txt                   # 该 SKILL 自带许可证（来自上游）
    ├── references/                   # editing.md 等
    └── scripts/                      # add_slide / clean / thumbnail / office/{pack,unpack,validate,soffice,potx2pptx}
```

> 与 `aec-generation` 不同，本 pack **不发布 Python 包**——所有逻辑都在各 SKILL 的 `scripts/` 中以独立 CLI 形式存在。无 `src/`，无 `pyproject.toml`，运行时依赖完全由 [environment.yml](environment.yml) 管理。

---

## 环境搭建

### 前置条件

- [Miniforge](https://github.com/conda-forge/miniforge) / Mambaforge
- **LibreOffice**（可选但强烈建议）——`pptx-profiler/scripts/render_layouts.py`、`render_samples.py` 与 `pptx/scripts/office/soffice.py` 都通过 `soffice --headless` 完成 PPTX→PNG / PPTX→PDF 渲染。Windows 下走 PowerPoint COM 也可，但 CI 环境必须装 LibreOffice。
- **`.env`**（仅 `image-generator` 需要）——把 [.env.example](.env.example) 复制到**项目根目录**为 `.env`，填入 Azure OpenAI / FLUX 端点和密钥。

### 快速开始

```bash
# 1. 创建 Conda 环境
conda env create -f environment.yml

# 2. 激活
conda activate pptx-generation

# 3. 验证依赖
python -c "import pptx, lxml, defusedxml, PIL; print('PPTX stack OK')"
python -c "import httpx, dotenv; print('image-generator stack OK')"
soffice --version          # LibreOffice 渲染（可选）

# 4. 配置 image-generator（仅在用到 AI 配图时）
cp .env.example ../../.env  # 项目根
# 然后填入实际的 Azure 凭据
```

### Windows 下的 LibreOffice

```powershell
winget install TheDocumentFoundation.LibreOffice
# 安装完成后将 C:\Program Files\LibreOffice\program 加入 PATH
```

---

## 测试与基线

> ⚠️ 本 pack 当前**尚未建立 prompt-eval 基线**。新增 / 修改任何 SKILL 前，请先按 [docs/evaluation.md](../../docs/evaluation.md) 与 `aec-generation` pack 的实践模式准备一份 `tests/<skill>.evals.json`，并把首轮通过率作为基线写入 `tests/BASELINE-v0.1.md`。

短期内的最小工作流：

1. 改前手工跑一遍涉及到的 SKILL，记录可重复的输入和当前输出
2. 一次只改 `SKILL.md` / `references/` / `scripts/` / `schemas/` 之一
3. 同样输入下重跑，对照输出
4. 不退化才合入

---

## 技术栈

| 层次       | 技术                                                                         | 用途                                |
| ---------- | ---------------------------------------------------------------------------- | ----------------------------------- |
| OOXML 操作 | [python-pptx](https://python-pptx.readthedocs.io)、lxml、defusedxml          | 读 / 写 / 校验 PPTX                 |
| 文本抽取   | [markitdown](https://github.com/microsoft/markitdown)                        | `.pptx` / `.docx` / `.pdf` → 纯文本 |
| 渲染       | LibreOffice (`soffice --headless`)、PowerPoint COM（仅 Windows）             | PPTX → PNG / PDF                    |
| 图像       | Pillow、（可选）matplotlib                                                   | 缩略图、占位符、数学公式渲染        |
| 校验       | jsonschema                                                                   | plan / brief / blueprint 结构校验   |
| AI 配图    | [httpx](https://www.python-httpx.org)、python-dotenv、（可选）azure-identity | 异步并发调用 Azure 图像后端         |

---

## 相关文档

- 顶层路由：[../../AGENTS.md](../../AGENTS.md)
- SKILL 编写规范：[../../SKILL-SPEC.md](../../SKILL-SPEC.md)
- 评测方法论：[../../docs/evaluation.md](../../docs/evaluation.md)
- 多 pack 架构：[../../docs/architecture.md](../../docs/architecture.md)

---

## 编码约定

- 每个 SKILL 的 `scripts/` 必须可作为独立 CLI 调用（`python scripts/foo.py --help`）
- `narrative-pptx-composer` 脚本以 `s<step>_<purpose>.py` 命名，与 9 步工作流一一对应
- 中间产物（profile / digest / plan / build artifacts）一律落盘 JSON，不依赖内存共享
- 大型二进制（.pptx / .png / .pdf）由 [.gitignore](.gitignore) 排除，需要分享样例时走 Git LFS
