---
name: hgyjy-user-story
description: 通过对话构建用户故事地图，管理原始需求与功能特性。一张地图对应一个原始需求（七要素：需求来源/业务场景/现状痛点/期望目标/方案/价值/DoD），方案分解为用户旅程步骤（骨干），旅程下可按用户行为细分，功能特性挂在用户行为下或直接挂旅程（Who/What/When/Why/DoD，可带优先级与版本）。当用户说"梳理原始需求""做用户故事地图""把方案拆成旅程""这个功能特性归到哪个版本"或要求对需求进行可视化、迭代、导出时使用。对话过程中状态实时落盘为 story_map.json，随时渲染为自包含 HTML 地图。支持从 hgyjy-user-journey 的旅程图输出（journey_map.json）一键导入草稿：角色/场景/预期/痛点/机会点自动映射为原始需求字段与功能特性。当用户说"从旅程图导入""把旅程图的机会点转成需求"时触发。
---

# hgyjy-user-story：对话式用户故事地图

## 数据模型（必须严格遵守）

- **一张地图 = 一个原始需求**。原始需求七要素：`name`（需求名称）、`source`（需求来源）、`scenario`（业务场景）、`pain_points`（现状痛点）、`goals`（期望目标）、`solution`（方案）、`value`（价值）、`dod`（DoD）。
- **用户旅程 = 方案的分解**。把 `solution` 拆成 3-7 个旅程步骤（用户视角的动词短语，如"上料""定位""加工""质检"），横向构成地图骨干。
- **用户行为是旅程下的可选细分层级**。一个旅程步骤可拆成若干用户行为（用户在该阶段的具体动作，动词短语，如"上传文档""审核条目"），功能特性挂在行为之下；简单旅程也可不建行为、直接挂特性。功能特性名称在同一旅程内必须唯一（不论挂在行为下还是直接挂旅程）。
- **功能特性字段**：`name`（特性名称，必填）、`who`、`what`、`when`、`why`、`dod`（对应 Who/What/When/Why/DoD），以及可选的 `priority`（must/should/could/wont）和 `release`（归属版本，须先在 releases 中定义）。其中 `why` 体现该特性的价值——为什么要做它。
- **功能特性与原始需求的关联是隐式的**：一张地图只有一个原始需求，地图内所有功能特性自动属于它，无需逐条填写。

## 铁律：状态走脚本，不走手改

1. `story_map.json` 是单一事实源，工作目录下始终维护这份文件。
2. **禁止直接编辑 JSON**——一切增删改通过 `scripts/update_map.py` 的结构化变更指令完成（脚本负责校验：重名、非法优先级、引用未定义版本等，非法则整体拒绝）。
3. 渲染只通过 `scripts/render_map.py`，同一 JSON 永远得到同一张图。
4. 每轮变更后，把脚本的输出摘要转述给用户确认（一行一条，如"已添加功能特性「X」（旅程: 上料, must, R1）"）。

## 工作流

### 阶段 0（可选）：从用户旅程图导入草稿

当工作目录（或用户指定路径）存在 hgyjy-user-journey 产出的 `journey_map.json`，且用户要求"从旅程图导入/把旅程图结论转成需求"时，用导入脚本生成草稿，替代阶段 1-3 的手工采集：

```bash
python3 scripts/import_journey.py --journey journey_map.json --story story_map.json --output draft_ops.json
python3 scripts/update_map.py --file story_map.json --changes "$(cat draft_ops.json)"
```

映射规则（脚本输出的 stderr 摘要含全部审阅提示，必须转述给用户）：

| 旅程图字段 | → 故事地图 |
|---|---|
| persona + scenario | requirement.scenario（带【源自旅程图】出处标注） |
| 各阶段 pain_points 汇总 | requirement.pain_points（按阶段分组） |
| expectations | requirement.goals |
| 需求来源 | 自动标 "hgyjy-user-journey 用户旅程图分析输出" |
| 阶段名序列 | add_journey 骨干草稿——**注意是名词短语，须与用户确认改为动词短语** |
| 阶段 opportunities[] | add_feature 草稿（what=机会点原文，why=同阶段痛点） |
| 阶段 emotion ≤ -1 | 对应特性预填 priority=must（建议，可推翻） |
| 阶段 evidence==hypothesis | 特性 description 标「源自假设阶段·待验证」 |

导入纪律：
1. **草稿必审**——脚本只生成指令不直接落盘；先转述摘要（尤其"待验证"清单和 must 建议），用户确认或修订后再执行。
2. 幂等——重复导入已存在的旅程/特性会自动跳过，已填的原始需求字段不覆盖（只补空）。
3. 导入后 `solution`/`value`/`dod` 通常仍为空，进入阶段 1 补齐剩余要素；旅程步骤改名用 `rename`。
4. 目标 story_map.json 不存在时脚本会自动调 update_map.py init（仍走脚本，不手写 JSON）。

### 阶段 1：采集原始需求七要素
- 逐要素询问，或用户一次给全则直接采用；已填要素不要重复问。
- 询问顺序建议：需求名称 → 需求来源 → 业务场景 → 现状痛点 → 期望目标 → 方案 → 价值 → DoD。
- 首次写入用一条 `init` 指令（含 name），其余要素用 `set_requirement` 补齐。
- 七要素中 `solution` 是阶段 2 的输入，若用户方案还很粗，先记录再继续。

### 阶段 2：方案 → 用户旅程分解
- 把 `solution` 拆成 3-7 个旅程步骤：用户视角、动词开头、能一句话说完。
- 超过 7 步提示合并；步骤间是"先后顺序"而非"并列功能"。
- 每确认一步立即 `add_journey`，并回显摘要；全部确认后建议渲染一次骨架地图给用户看。

### 阶段 3：细分用户行为，挂接功能特性
- 旅程步骤较粗时（一个环节里用户有多个明显不同的动作），先 `add_behavior` 细分用户行为，再把功能特性挂到行为下；简单旅程跳过行为层直接挂特性。
- 对每个行为/旅程追问：这里**谁（Who）**在什么**情形（When）**下要完成**什么（What）**，为什么需要它（**Why**），做到什么程度算完成（**DoD**）。
- 用 `add_feature` 逐个写入（带 `behavior` 参数挂到行为下）；特性名称取 What 的简短短语。
- 引导话术与提问清单见 [references/methodology.md](references/methodology.md)，需要时再读。

### 阶段 4：版本与优先级切分（可选）
- 询问计划版本，用 `add_release` 定义后，再把功能特性归版本（`set_feature` 改 `release`）。
- 有优先级诉求时设置 `priority`；没有则留空，地图按"未规划"处理。

### 阶段 5：渲染与迭代
- 骨架确认、每轮大改后、或用户要求时执行渲染：
  ```bash
  python3 scripts/render_map.py --input story_map.json --output story_map.html
  ```
- 迭代指令（"把 X 挪到 R2""删掉 Y""Z 的 DoD 改成…"）翻译成对应 op 执行后重渲染。
- 用户要求导出 Markdown/纯文本时，直接从 story_map.json 生成，不必渲染 HTML。

## 命令参考

> 跨工具注意：Kimi / Claude Code / OpenCode 中相对路径可用；WorkBuddy 执行 shell 时工作目录不是 skill 目录，需写全路径——`python3 "${CODEBUDDY_SKILL_DIR:-<skill安装目录>}/scripts/update_map.py ...`（`${CODEBUDDY_SKILL_DIR}` 为 WorkBuddy 注入的 skill 目录绝对路径）。

```bash
# 变更（--changes 缺省从 stdin 读；init 必须单独一条）
python3 scripts/update_map.py --file story_map.json --changes '[{"op":"add_journey","name":"上料"}]'

# 渲染
python3 scripts/render_map.py --input story_map.json --output story_map.html

# 从旅程图导入草稿（见"阶段 0"）
python3 scripts/import_journey.py --journey journey_map.json --story story_map.json --output draft_ops.json
```

常用 op（完整清单与参数见 [references/schema.md](references/schema.md)）：

| op | 用途 | 必填参数 |
|----|------|---------|
| `init` | 创建状态文件 | `name` |
| `set_requirement` | 更新原始需求七要素之一或多 | 至少一个字段 |
| `add_release` | 定义版本 | `name` |
| `add_journey` | 添加旅程步骤 | `name` |
| `add_behavior` | 在旅程下添加用户行为 | `journey`、`name` |
| `add_feature` | 添加功能特性（带 `behavior` 挂到行为下） | `journey`、`name` |
| `set_feature` | 修改功能特性字段（who/what/when/why/dod/priority/release/description） | `journey`、`feature`、至少一个字段 |
| `rename` | 重命名（`type`: journey/behavior/feature） | `type`、`new_name` + 定位参数 |
| `delete` | 删除（`type`: journey/behavior/feature） | `type` + 定位参数 |

## 异常处理

- 脚本报错时原样转述错误（中文化），不猜着重试；修正指令后重发。
- 用户中途换需求、开新需求：确认后 `--force` 重新 `init`，并提醒旧文件会被覆盖（或先建议备份）。
- 大地图（功能特性 > 50）建议拆分为多个原始需求分别建图。

## 参考文件

- [references/methodology.md](references/methodology.md)：旅程分解启发式、Who/What/When/DoD 提问清单、版本切分原则、常见错误
- [references/schema.md](references/schema.md)：story_map.json 完整格式、全部 op 参数表、变更指令示例
