# PR0M3N4DE

**[English](README.md)**

> **一场穿行于建筑推理过程的漫游。**

建筑并非在一瞬间被完整地体验；它通过运动、序列、阈限、回返与修订而逐渐显现。PR0M3N4DE 将这一思想用于建筑被有把握地绘制之前所发生的工作：设计推理本身应当在可见处逐步展开。

**设计不是一个答案。设计是一连串决策。**

**机器负责秩序。人负责意义。**

**先有可追溯性，才值得信任。**

PR0M3N4DE 不试图替代建筑师的决策；它试图保留使决策能够被理解的路径。

**最终方案不是设计的全部。演化过程也是设计的一部分。**

> **命名说明。** 本源代码树中已实现的 Skill 仍名为 `architectural-concept-design`。PR0M3N4DE 是面向未来发行的公开产品身份；本 README 不会暗中重命名既有合同、包标识符或发布清单。

## 为什么叫这个名字

`PR0M3N4DE` 借用建筑学中的 *promenade architecturale*（建筑漫游）概念：建筑通过运动、序列、变化的视点、阈限与时间被理解，而不是作为一张静止图像被一次看完。名称中的 `0`、`3`、`4` 分别代替 `O`、`E`、`A`，使其具有数字化辨识度，而不沦为泛化的 AI 品牌。

同一隐喻也指引产品：设计不应从提示直接跳到形式，而应通过状态、理由、操作、决策与修订的序列逐步展开。

```text
状态 → 操作 → 状态 → 操作 → 状态
```

PR0M3N4DE 是独立开源项目，与勒·柯布西耶、Fondation Le Corbusier 或任何建筑软件供应商均无关联。

## 这场漫游：当前核心与未来方向

### 已实现的推理核心

```text
任务书 → 证据 → 约束 → 假设 → 选项 → 比较
       → 人类决策 → 交付物
```

每一步都被刻意设计为可检查的。缺失的测绘资料不会被变成事实；看似有前景的选项不会被当作决策；决策不会抹去其所依据的证据、依赖项或不确定性。

### 目标演化方向——尚未实现

目标产品方向是 **建筑推理 + 设计演化 + 设计操作**：

```text
任务书 → 证据 → 约束 → 假设 → 设计操作 → 选项
       → 比较 → 人类决策 → 交付物
```

未来的“设计操作”层将把一次变换描述得足够具体、可供检查：改变了什么、为何改变、由哪些证据与约束触发、背后的假设、受影响的系统、权衡、已过期的下游对象，以及建筑师是接受、拒绝还是修订该操作。

例如，一次操作可说明其意图、一次 `Carve` 或 `Terrace` 动作、理由，以及对体量、流线、功能、立面、结构或景观的影响。这**不**表示当前仓库已经具有状态到状态的操作历史、几何引擎或 CAD/BIM 集成。当前的选项合同记录的是 `spatial_operation` 描述；通用的操作／演化模型仍属于愿景。

这是一个可安装、local-first（本地优先）的建筑**前期设计 Skill**，服务具有设计素养的建筑使用者：具备设计判断的学生、高年级及 AI-native 建筑学生、年轻建筑师、独立设计师、小型工作室与早期设计团队。它将显式输入、证据标签、约束、空间假设、选项、比较和人类决策组织为可追溯的前期设计记录。它不是 Web 应用、施工图系统、自动审批引擎，也不替代专业判断。

## 当前已经实现的内容

下列能力已存在于当前仓库中，并由合同、确定性脚本或固定评测支持。

| 能力 | 当前实现 | 仓库证据 |
| --- | --- | --- |
| 任务书规范化 | 宽松的人类任务书会转化为十三个显式标注的字段。`PROVIDED`、`UNKNOWN` 与 `MISSING` 保持区分；规范化器既不生成设计内容，也不生成新证据。 | [规范化任务书台账](skills/architectural-concept-design/references/normalized-brief-ledger.md) · [输入 Schema](skills/architectural-concept-design/references/normalized-brief-ledger.input.schema.json) · [规范化器](skills/architectural-concept-design/scripts/normalize_project_brief.py) |
| 证据纪律 | 记录带有 `PROVIDED`、`VERIFIED`、`INFERRED`、`ASSUMED` 或 `PROPOSED` 标签。合同防止假设或推断被悄然表述为已验证事实。 | [证据 Schema](skills/architectural-concept-design/references/evidence.schema.json) · [任务书／证据协议](skills/architectural-concept-design/references/brief-and-evidence.md) |
| 场地、功能与流线推理 | 参考资料组织场地观察、功能、面积、邻接、分区、流线、网格／核心筒／高度假设与缺失信息。面积算术由确定性的本地脚本处理。 | [场地／语境](skills/architectural-concept-design/references/site-context-analysis.md) · [功能／面积／流线](skills/architectural-concept-design/references/program-area-and-circulation.md) · [面积表检查器](skills/architectural-concept-design/scripts/check_area_schedule.py) |
| 实质不同的选项 | 输出合同记录假设、选项、标准、比较、依赖项与交付物。选项必须在空间操作上不同，而非仅仅风格不同。现有 `spatial_operation` 字段是选项描述，而不是通用演化历史引擎。 | [概念选项与决策](skills/architectural-concept-design/references/concept-options-and-decisions.md) · [比较／决策交接](skills/architectural-concept-design/references/option-comparison-decision-handoff.md) · [状态包 Schema](skills/architectural-concept-design/references/output.schema.json) |
| 人类决策门与状态包 | 确定性装配器接收 Schema 有效的任务书与**已经由人撰写**的假设、选项和标准；它使状态包等待明确的人类决策。验证器追踪依赖项和过期的下游状态。 | [项目状态装配](skills/architectural-concept-design/references/project-state-assembly.md) · [装配器](skills/architectural-concept-design/scripts/assemble_project_state.py) · [状态验证器](skills/architectural-concept-design/scripts/validate_state.py) |
| 仅状态的演示交接 | 当有效的真实项目状态具有一项明确的人类选择、且没有已审查的运行时候选集时，Skill 可以只用团队原创图示创建一份有边界的十页状态交接。它不渲染 PPTX，也不转移外部先例。 | [仅状态交接](skills/architectural-concept-design/references/state-only-presentation-handoff.md) · [构建器](skills/architectural-concept-design/scripts/build_state_only_presentation_handoff.py) |
| 受控来源访问边界 | 本地注册表、请求计划检查、合成回放、运行时 dry-run 与明确门控的 canary 合同，约束精确来源、预算与遇拒即停行为。它们不是通用网页搜索或抓取设施。 | [来源注册表](skills/architectural-concept-design/references/source-access-registry.json) · [来源访问门](skills/architectural-concept-design/references/runtime-source-access-gate.md) · [受控计划](skills/architectural-concept-design/references/controlled-crawl-plan.md) |
| 发布完整性 | 仓库包含确定性的 Skill 归档构建／验证／干净安装逻辑，以及独立的门：验证已提供的 PPTX 视觉 QA 证据，并在不覆盖受保护输入的前提下发布已验证候选稿。 | [发布安装](skills/architectural-concept-design/references/release-installation.md) · [发布打包器](skills/architectural-concept-design/scripts/release_skill_package.py) |
| 回归与治理来源 | 源开发工作流使用 Python 评测、Node 治理测试、严格 preflight、仓库检查和 GitHub Actions。这些仅供开发的测试与治理源文件刻意未随本公开发行包提供。 | [公开发行清单](PUBLIC-DISTRIBUTION-MANIFEST.json) |

## 本地、可追溯的工作路径

源开发工作流使用匿名合成 fixture 测试这一链条；它们是结构示例，**不是**可以复用的建筑结论，并且刻意未随本公开发行包提供。真实项目从人类提供的材料开始，并保留其未知项。

```text
1. 规范化人类任务书。
2. 登记来源并标注证据。
3. 记录场地、功能、关系与约束。
4. 撰写可比较的假设和真正不同的选项。
5. 依照明确标准进行比较。
6. 请求人类选择、拒绝或修订。
7. 装配并验证状态包。
8. 仅创建现有证据所授权的交接或交付物。
```

用于本地开发时，核心确定性检查使用锁定的 Python 环境：

```bash
uv sync --project skills/architectural-concept-design --frozen --group test

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/normalize_project_brief.py \
  <human-brief.json> --output <normalized-brief-ledger.json>

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/check_area_schedule.py \
  <area-schedule.json>

```

仅供开发的 fixture 与评测刻意未随本公开发行包提供；公开包保留的是上面展示的确定性本地操作。

## 建筑学的具体性

PR0M3N4DE 应避免没有建筑后果的建筑套话。“回应场地”“创造丰富的空间层次”“顺应等高线”或“强化与自然的关系”是意图，而不是足以检验设计动作的信息。

只要证据允许，每次操作描述都应与下列具体链条相连：

```text
证据 → 约束 → 操作 → 后果
```

例如，一个场地观察可以导向一项到达约束，再导向一个被提出的分置、台地或切开的通道，并明确其流线、结构、景观、功能和权衡影响。仓库不声称今天能自动化这类几何工作；这是未来产品应保留的建筑学精确度标准。

## PR0M3N4DE 刻意不作的声明

- 它不会因为人类提供了一份文件就验证其内容。
- 它不会将 `ASSUMED`、`INFERRED` 或 `PROPOSED` 记录变成 `VERIFIED` 事实。
- 它不作规范符合性、规划许可、可建性、成本、工期、结构、消防安全或专业审批声明。
- 它不自由抓取网页、不绕过访问控制、不保留原始页面内容、不下载媒体，也不使用反机器人规避。
- 它不会代替人类选择设计选项。
- 它不会将可编辑 PPTX、视觉 QA receipt 或已发布文件当作设计质量、作者身份、权利清除、法律合规或人类审批的证明。

## 实验性／部分能力

下列部分仅在以下限制内存在，不应被表述为完整的自主设计流水线。

| 领域 | 当前限制 |
| --- | --- |
| 设计操作与演化 | 仓库记录推理状态、依赖项、过期状态和选项级 `spatial_operation` 描述；尚未提供通用的状态到状态操作台账、操作语义或几何执行层。 |
| 运行时来源观察 | 访问受注册表、计划、运行时和人类确认约束；它仍是来源特定且 fail-closed 的，仓库不提供不受限制的发现、搜索或爬取。 |
| 外部演示渲染 | 演示交接指定了一个独立锁定的外部渲染器边界；该渲染器不随包提供，也不会由仅状态交接本身调用。 |
| PPTX 发布门 | 这些门验证已经生成的候选稿及其提供的渲染证据；它们不生成建筑内容、不评判视觉质量，也不替代人类逐页审阅。 |
| 公开发行 | 该候选 PR0M3N4DE 公开导出包带有自己的 `LICENSE`、`NOTICE` 和确定性导出清单；它本身不是 GitHub Release、仓库可见性变更或最终公开发行授权。 |
| 案例与媒体材料 | 本地研究与媒体政策受其 ADR 约束。该候选导出包执行**排除所有第三方媒体**的政策；它不为任何被省略内容推断权利。 |

## 未来方向——尚未实现

公开愿景是一种更易理解的设计工作空间，而不是对下列系统已经存在的宣称：

- 一个可将每项决策追溯至其证据、假设、依赖项和替代方案的可视化工作空间；
- 一套用于描述和比较空间操作、而不将其压缩为风格标签的 **Design Grammar**；
- 选项演化：明确的分叉、修订、被拒绝路径与决策历史，而非一个不透明的“最终答案”；
- 连接证据、约束、假设、空间变换、后果与权衡的 Design Operations 词汇与记录；
- 面向特定建筑类型的 Domain Packs，每一类都拥有自己的功能语法、流线语法、空间关系、服务逻辑、场地逻辑与评估标准；
- 将人类撰写的空间命题转化为可检查图示与可测试关系的几何操作；
- 保持同样证据与人类决策边界的、严格受控的 SketchUp MCP、Rhino、CAD 与 BIM 集成；
- 用于比较、不确定性与交接的更丰富人类审阅界面。

策略是**先做领域深度，再扩展领域广度**：先深化一个滩头建筑类型，再扩大范围。这不是为每种建筑类型训练独立模型的承诺。预期顺序是共享基础模型 API、结构化输出、确定性工具、Schema 验证、检索、领域规则、Domain Packs、评测、真实用户修正、重复失败数据，并仅在有理由时微调。过早训练只会让尚未定义的工作流错误更稳定。

上述任一方向都需要独立批准的范围、合同、测试和发布审查。它们不会仅因出现在这里而被启用。

## 面向谁

PR0M3N4DE 不是为缺乏设计判断的人准备的一键式答案生成器。它应放大已有的建筑判断：

```text
学生 → 使推理显式化
年轻建筑师 → 加速分析、比较与迭代
资深建筑师 → 项目记忆、一致性检查与推理轨迹
```

产品应随着用户判断力的提升而变得更有用，而不是更无用。今天的 GitHub／Codex／Skill 形态自然服务 AI-native 建筑师、建筑学生与开发者；未来的 Web 工作空间可以面对更广泛受众，但尚未在这里实现。

## 未来架构——尚未实现

```text
Architecture State
        ↓
Design Grammar
        ↓
Hypotheses
        ↓
Design Operations
        ↓
Options
        ↓
Human Decision
        ↓
Geometry Operations
        ↓
SketchUp / Rhino / CAD / BIM
```

此图仅表示产品方向，不授予当前对 Design Grammar、Design Operations、Geometry Operations 或任何创作工具集成的支持。

## 项目地图

```text
LICENSE                           # 本公开包的 Apache-2.0 文本
NOTICE                            # 公开包 notices
PUBLIC-DISTRIBUTION-MANIFEST.json # 确定性的公开导出记录

skills/architectural-concept-design/
├── SKILL.md                 # 简洁的工作流与路由
├── references/              # 合同、Schema 与建筑指导
├── scripts/                 # 确定性的本地操作
├── assets/                  # 可打包的本地资产
├── pyproject.toml           # 锁定的 Python 运行时元数据（0.1.0）
└── uv.lock                  # 锁定的运行时依赖
```

简洁的操作入口是 [`skills/architectural-concept-design/SKILL.md`](skills/architectural-concept-design/SKILL.md)。详细规则应保留在链接的参考资料和脚本中，而非堆积在本 README 内。

## 开发与发布纪律

在源开发变更被视为完成前，开发工作流要求严格 preflight、仓库检查、治理测试、相关 Skill 评测、干净 diff，以及适用的审阅／发布证据。仅供开发的治理文档与测试源文件刻意未随本公开发行包提供；保留的发布安装边界记录在 [`skills/architectural-concept-design/references/release-installation.md`](skills/architectural-concept-design/references/release-installation.md) 中。

当前仓库包元数据版本为 `0.1.0`。归档创建、验证与干净安装均为确定性的本地操作；一个发布归档会记录其源提交、构建时间、清单与逐文件哈希。参见 [`release_skill_package.py`](skills/architectural-concept-design/scripts/release_skill_package.py)。

## 公开发行意图

计划中的公开仓库身份是 **PR0M3N4DE**。面向这一未来发行：

- **代码许可证：** 此候选导出中包含的代码带有规范的 Apache-2.0 `LICENSE`。该许可证不授予对被排除的第三方内容、项目输入或生成交付物的权利。
- **媒体政策：** 从公开包中排除所有第三方媒体。
- **隐私边界：** 不公开私有项目文件、人类提供的源材料、凭据、本地配置、运行时 receipt 或仅测试 fixture 作为生产示例。

## 留待审查的命名迁移

本 README 刻意不作机械重命名。未来另行审查的迁移至少应盘点：

1. GitHub 仓库名、公开 URL、发行名和 issue／PR 模板；
2. 根包元数据（`package.json`）及任何发布／仓库标签；
3. Skill 目录、`SKILL.md` frontmatter／名称、`pyproject.toml` 发行元数据与归档清单 `skill_id`；
4. 文档标题、交叉链接、示例和公开安装说明；
5. 发布产物、校验和、验证命令，以及对已安装 `architectural-concept-design` Skill 的兼容规则；
6. 提及旧项目名称的自动化、治理、飞书和 CI 文本。

重命名这些标识符是兼容性和发布决策，而不是一次表面的搜索替换。它应为既有安装和已记录证据保留清晰的迁移路径。

---

PR0M3N4DE 是一个让建筑推理可见的场所：不是让建筑师消失，而是让决策的工作更容易被检查、质询与延续。

**不只关注建筑成为了什么，也关注它如何、为何成为这样。**
