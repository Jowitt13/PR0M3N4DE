# PR0M3N4DE

**[English](README.md)**

> **一场穿行于建筑推理之中的漫游。**

建筑不是一眼望尽的。它在移动中展开，在序列中显现，在门槛、回返与修订之间，慢慢说出自己。PR0M3N4DE 把这份体悟带回落笔之前：设计的推理，也应当沿着一条可见的路径徐徐展开。

**设计不是一个答案，而是一连串决策。**

**机器负责秩序，人负责意义。**

**先可追溯，才谈得上信任。**

PR0M3N4DE 不试图替代建筑师的决策，它要保存的，是让决策得以被理解的那条路径。

**最终方案不等于整个设计，演化过程本身就是设计的一部分。**

> **命名说明。** 本源码树中已实现的 Skill 仍命名为 `architectural-concept-design`。PR0M3N4DE 是面向未来公开发行的产品身份；本 README 不会悄悄改动既有的契约、包标识符或发布清单。

## 为什么叫这个名字

`PR0M3N4DE` 之名，取自建筑学中的 *promenade architecturale*（建筑漫步）：建筑是在移动、序列、视点的变换、门槛与时间之中被理解的，而非一张静止的图像。名称中以 `0`、`3`、`4` 分别替代 `O`、`E`、`A`，为的是让它在数字世界里一眼可辨，又不至于淹没在泛泛的 AI 品牌之中。

同一个隐喻也指引着产品本身：设计不应从提示词直接跳向形式，而应沿着状态、理由、操作、决策与修订的序列，徐徐展开。

```text
状态 → 操作 → 状态 → 操作 → 状态
```

PR0M3N4DE 是一个独立的开源项目，与勒·柯布西耶、Fondation Le Corbusier 以及任何建筑软件厂商均无关联。

## 这场漫步：当前核心与未来方向

### 已实现的推理核心

```text
任务书 → 证据 → 约束 → 假设 → 选项 → 比较
       → 人类决策 → 交付物
```

每一步都被刻意留成可供检视的样子。缺失的勘测资料不会被当作事实，有前景的选项不会被当作定论，任何一个决策，也不会抹去让它得以成立的证据、依赖与不确定性。

### 目标演化方向——尚未实现

目标产品方向是 **建筑推理 + 设计演化 + 设计操作**：

```text
任务书 → 证据 → 约束 → 假设 → 设计操作 → 选项
       → 比较 → 人类决策 → 交付物
```

未来的"设计操作"层，会把每一次变换描述得足够具体、经得起审视：改变了什么、为何而改、由哪条证据与哪项约束触发、背后押上了什么假设、牵动了哪些系统、取舍何在、哪些下游对象因此过期，以及建筑师最终接纳、驳回还是修订了它。

举例来说，一次操作可以说清自己的意图（如一次 `Carve` 或 `Terrace` 动作）、理由，以及它落在体量、流线、功能、立面、结构或景观上的痕迹。**这并不意味着**当前仓库已具备状态之间的操作历史、几何引擎或 CAD/BIM 集成——目前的选项契约只记录了 `spatial_operation` 描述，通用的操作／演化模型仍属于愿景。

它是一个可安装、本地优先（local-first）的建筑**前期设计 Skill**，面向具备设计素养的使用者：有一定功力的学生、高年级及 AI 原生（AI-native）的建筑系学生、青年建筑师、独立设计师、小型工作室与早期设计团队。它把显式的输入、证据标签、约束、空间假设、选项、比较与决策，整理成一份份可追溯的前期设计记录。它不是 Web 应用，不是施工图系统，不是自动审批引擎，更不取代专业判断。

## 当前已实现的能力

以下能力已在当前仓库落地，各自有契约、确定性脚本或固化评测作为支撑。

| 能力 | 当前实现 | 仓库证据 |
| --- | --- | --- |
| 任务书规范化 | 一份松散的任务书，会被整理为十三个标注清晰的字段。`PROVIDED`、`UNKNOWN` 与 `MISSING` 各归其位；规范化器既不生成设计内容，也不制造新的证据。 | [规范化任务书台账](skills/architectural-concept-design/references/normalized-brief-ledger.md) · [输入 Schema](skills/architectural-concept-design/references/normalized-brief-ledger.input.schema.json) · [规范化器](skills/architectural-concept-design/scripts/normalize_project_brief.py) |
| 证据纪律 | 每条记录都带着 `PROVIDED`、`VERIFIED`、`INFERRED`、`ASSUMED` 或 `PROPOSED` 标签；契约确保假设与推断，不会被悄悄当作已验证的事实呈现。 | [证据 Schema](skills/architectural-concept-design/references/evidence.schema.json) · [任务书／证据协议](skills/architectural-concept-design/references/brief-and-evidence.md) |
| 场地、功能与流线推理 | 参考资料覆盖场地观察、功能、面积、邻接关系、分区、流线、网格／核心筒／高度假设，以及尚缺的信息；面积的核算交给确定性的本地脚本。 | [场地／语境](skills/architectural-concept-design/references/site-context-analysis.md) · [功能／面积／流线](skills/architectural-concept-design/references/program-area-and-circulation.md) · [面积表检查器](skills/architectural-concept-design/scripts/check_area_schedule.py) |
| 实质差异化的选项 | 输出契约记录假设、选项、评判标准、比较、依赖与交付物。选项必须在空间操作上真正不同，而不只是风格上的差异。现有的 `spatial_operation` 字段是选项描述，并非通用的演化历史引擎。 | [概念选项与决策](skills/architectural-concept-design/references/concept-options-and-decisions.md) · [比较／决策交接](skills/architectural-concept-design/references/option-comparison-decision-handoff.md) · [状态包 Schema](skills/architectural-concept-design/references/output.schema.json) |
| 决策关卡与状态包 | 确定性装配器收下符合 Schema 的任务书，以及**已由人撰写**的假设、选项与标准，随后让状态包停在等待明确决策的位置。验证器追踪依赖关系与已经过期的下游状态。 | [项目状态装配](skills/architectural-concept-design/references/project-state-assembly.md) · [装配器](skills/architectural-concept-design/scripts/assemble_project_state.py) · [状态验证器](skills/architectural-concept-design/scripts/validate_state.py) |
| 纯状态演示交接 | 当一个真实项目状态通过验证、含一项明确的选择、且没有待审的运行时候选集时，Skill 可以生成一份十页为限、只呈现状态、只用团队原创图示的交接文档。它不渲染 PPTX，也不引入外部先例。 | [纯状态交接](skills/architectural-concept-design/references/state-only-presentation-handoff.md) · [构建器](skills/architectural-concept-design/scripts/build_state_only_presentation_handoff.py) |
| 受控的来源访问边界 | 本地注册表、请求计划检查、合成回放、运行时试运行（dry-run）与显式门控的金丝雀（canary）契约，共同限定可用的来源、预算与"遭拒即停"的纪律。它们不是通用的网页搜索或抓取工具。 | [来源注册表](skills/architectural-concept-design/references/source-access-registry.json) · [来源访问关卡](skills/architectural-concept-design/references/runtime-source-access-gate.md) · [受控计划](skills/architectural-concept-design/references/controlled-crawl-plan.md) |
| 发布完整性 | 仓库包含确定性的 Skill 归档构建／验证／纯净安装逻辑，以及一道独立关卡：核验所提交的 PPTX 视觉质检（QA）证据，并在不覆盖受保护输入的前提下发布已验证的候选版本。 | [发布安装](skills/architectural-concept-design/references/release-installation.md) · [发布打包器](skills/architectural-concept-design/scripts/release_skill_package.py) |
| 回归与治理溯源 | 源码开发工作流以 Python 评测、Node 治理测试、严格的预检（preflight）、仓库检查与 GitHub Actions 把关。这些仅供开发使用的测试与治理源文件，刻意不包含在本公开发行版中。 | [公开发行清单](PUBLIC-DISTRIBUTION-MANIFEST.json) |

## 本地、可追溯的工作流程

源码开发工作流使用匿名的合成测试夹具（fixture）来检验整条链路；它们只是结构的示范，**不是**可供复用的建筑结论，也刻意不包含在本公开发行版中。真实项目从人提供的材料开始，并把自己的未知项留在原地。

```text
1. 规范化人类任务书。
2. 登记来源并标注证据。
3. 记录场地、功能、关系与约束。
4. 撰写可比较的假设和真正不同的选项。
5. 依照明确的标准进行比较。
6. 交由人类选择、驳回或修订。
7. 装配并验证状态包。
8. 只创建现有证据所允许的交接文档或交付物。
```

本地开发时，核心的确定性检查在锁定版本的 Python 环境中运行：

```bash
uv sync --project skills/architectural-concept-design --frozen --group test

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/normalize_project_brief.py \
  <human-brief.json> --output <normalized-brief-ledger.json>

uv run --project skills/architectural-concept-design --frozen --no-sync python \
  skills/architectural-concept-design/scripts/check_area_schedule.py \
  <area-schedule.json>

```

仅供开发使用的测试夹具与评测刻意不包含在本公开发行版中；公开包里留下的，正是上文所示的确定性本地操作。

## 建筑学的具体性

PR0M3N4DE 应当避开那些不产生任何建筑后果的陈词滥调。"回应场地""营造丰富的空间层次""顺应等高线"或"加强与自然的关系"——这些都只是意愿，还不足以检验一个设计动作。

每当描述一次操作，都应在证据允许的范围内，把它接上这条具体的链条：

```text
证据 → 约束 → 操作 → 后果
```

例如，一条场地观察可以推导出一项出入口约束，进而引出一个被提议的分裂、台地或凿开的通道，并说清它对流线、结构、景观、功能的含义与取舍。仓库并不声称今天就能自动化这类几何工作；这是未来产品应当保有的建筑学精确度。

## PR0M3N4DE 刻意不作出的声明

- 它不会因为一份文件被递了过来，就默认验证其中的内容。
- 它不会把 `ASSUMED`、`INFERRED` 或 `PROPOSED` 的记录升格为 `VERIFIED` 事实。
- 它不就规范合规、规划许可、可建造性、成本、工期、结构、消防安全或专业审批作出任何声明。
- 它不随意抓取网页、不绕过访问控制、不留存原始页面内容、不下载媒体，也不采用任何反爬虫规避手段。
- 它不会代替人选定设计方案。
- 它不会把一份可编辑的 PPTX、一张视觉质检回执或一个已发布文件，当作设计质量、作者身份、权利合规、法律合规或审批通过的证明。

## 实验性／部分能力

以下部分只在所述限制的范围内存在，不应被描绘为一条完整的自主设计流水线。

| 领域 | 当前限制 |
| --- | --- |
| 设计操作与演化 | 仓库记录推理状态、依赖、过期状态与选项级的 `spatial_operation` 描述；尚未提供通用的状态间操作台账、操作语义或几何执行层。 |
| 运行时来源观察 | 访问受注册表、计划、运行时与人工确认的多重关卡约束，且始终是来源特定、失败即拒（fail-closed）的；仓库不提供不受限制的发现、搜索或爬取能力。 |
| 外部演示渲染 | 演示交接只规定了一条通往独立锁定的外部渲染器的边界；该渲染器不随包捆绑，纯状态交接本身也不会调用它。 |
| PPTX 发布关卡 | 这些关卡验证的是已产出的候选版本及其提交的渲染证据；它们不生成建筑内容、不评判视觉质量，也不替代逐页的人工审阅。 |
| 公开发行 | 这份 PR0M3N4DE 候选公开导出版附带自己的 `LICENSE`、`NOTICE` 与确定性导出清单；它本身不构成 GitHub Release、仓库可见性变更或最终发布授权。 |
| 案例与媒体素材 | 本地研究与媒体政策受各自的架构决策记录（ADR）约束。这份候选导出版执行**排除一切第三方媒体**的政策，也不为任何被排除的内容推断权利归属。 |

## 未来方向——尚未实现

公开的愿景是一个更清晰易读的设计工作空间，而不是断言以下系统已经存在：

- 一个可视化的工作空间，每一项决策都能顺着它的证据、假设、依赖与备选方案一路走回去；
- 一套 **设计语法（Design Grammar）**，用来描述和比较空间操作，而不把它们坍缩为风格标签；
- 选项的演化：显式的分叉、修订、被驳回的路径与决策历史，而非一个不透明的"最终答案"；
- 一套设计操作（Design Operations）词汇与记录，贯通证据、约束、假设、空间变换、后果与取舍；
- 面向特定建筑类型的领域包（Domain Pack），每一类都有自己的功能语法、流线语法、空间关系、服务逻辑、场地逻辑与评判标准；
- 几何操作：把人写下的空间命题，转化为可供检视的图示与可供检验的关系；
- 边界审慎的 SketchUp MCP、Rhino、CAD 与 BIM 集成，延续同样的证据与决策边界；
- 面向比较、不确定性与交接的更丰富的审阅界面。

策略上**领域深度先于领域广度**：先深耕一个突破口建筑类型，再扩大范围。这不承诺为每种建筑类型训练独立的模型。预期的推进顺序是：共享的基础模型 API、结构化输出、确定性工具、Schema 校验、检索、领域规则、领域包、评测、来自真实使用者的修正、反复积累的失败数据——只有在确有必要时才进行微调。过早训练，只会让一套尚未定义清楚的工作流把错误犯得更稳定。

上述任何一个方向，都需要各自独立的范围批准、契约、测试与发布审查；写在这里，不代表任何一项已被启用。

## 面向谁

PR0M3N4DE 不是为没有设计判断力的人准备的一键式答案生成器。它要做的，是放大已有的建筑判断力：

```text
学生 → 让推理过程显性化
青年建筑师 → 加速分析、比较与迭代
资深建筑师 → 项目记忆、一致性检查与推理轨迹
```

产品应当随着使用者判断力的增长越来越有用，而不是相反。当下以 GitHub／Codex／Skill 呈现的形态，天然贴近 AI 原生建筑师、建筑系学生与开发者；未来的 Web 工作空间或许面向更广泛的受众，但这里尚未实现。

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

此图仅表达产品方向，不意味着当前已支持设计语法、设计操作、几何操作或任何创作工具的集成。

## 项目地图

```text
LICENSE                           # 本公开包的 Apache-2.0 许可证文本
NOTICE                            # 公开包声明文件
PUBLIC-DISTRIBUTION-MANIFEST.json # 确定性的公开导出记录

skills/architectural-concept-design/
├── SKILL.md                 # 简明工作流与路由
├── references/              # 契约、Schema 与建筑学指导
├── scripts/                 # 确定性的本地操作
├── assets/                  # 可打包的本地资产
├── pyproject.toml           # 锁定版本的 Python 运行时元数据（0.2.0）
└── uv.lock                  # 锁定的运行时依赖
```

简明的操作入口是 [`skills/architectural-concept-design/SKILL.md`](skills/architectural-concept-design/SKILL.md)。详细的规则放在所链接的参考资料与脚本中，而不是堆进这份 README。

## 开发与发布纪律

在源码开发中，一项变更在视为完成之前，开发工作流要求通过严格预检、仓库检查、治理测试与相关 Skill 评测，保持 diff 干净，并附上适用的评审／发布证据。仅供开发使用的治理文档与测试源文件刻意不包含在本公开发行版中；保留下来的发布安装边界，记录在 [`skills/architectural-concept-design/references/release-installation.md`](skills/architectural-concept-design/references/release-installation.md) 中。

当前仓库的包元数据版本为 `0.2.0`。归档的创建、验证与纯净安装都是确定性的本地操作；每个发布归档都会记录自己的源提交、构建时间、清单与逐文件哈希。详见 [`release_skill_package.py`](skills/architectural-concept-design/scripts/release_skill_package.py)。

## 公开发行意图

计划中的公开仓库身份是 **PR0M3N4DE**。面向这次未来的发行：

- **代码许可证：** 候选导出版中包含的代码附带标准的 Apache-2.0 `LICENSE`。该许可证不授予对被排除的第三方内容、项目输入或所生成交付物的任何权利。
- **媒体政策：** 公开包中排除一切第三方媒体。
- **隐私边界：** 不公开私有项目文件、项目方提供的原始素材、凭据、本地配置与运行时回执，也不把仅供测试的夹具当作生产示例公开。

## 留待日后审查的命名迁移

这份 README 刻意不做任何机械式的重命名。未来经单独审查的迁移，至少要盘点：

1. GitHub 仓库名、公开 URL、发布名称以及 issue／PR 模板；
2. 根目录包元数据（`package.json`）及任何发布／仓库标签；
3. Skill 目录、`SKILL.md` frontmatter／名称、`pyproject.toml` 发行元数据与归档清单中的 `skill_id`；
4. 文档标题、交叉链接、示例与公开安装说明；
5. 发布产物、校验和、验证命令，以及与已安装的 `architectural-concept-design` Skill 的兼容规则；
6. 引用旧项目名称的自动化、治理、飞书与 CI 文本。

重命名这些标识符是一项兼容性与发布层面的决策，而不是一次表面的搜索替换。它必须为已有的安装与留存的证据保留一条清晰的迁移路径。

---

PR0M3N4DE 是一处让建筑推理显形的地方：不是让建筑师退场，而是让决策这件事更容易被检视、被追问、被接续走下去。

**不只关心建筑最终成为了什么，也关心它如何、为何成为了这样。**
