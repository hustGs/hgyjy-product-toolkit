# 数据格式与变更指令参考

## 目录

1. story_map.json 结构
2. 字段说明
3. 完整示例
4. update_map.py 操作（op）清单
5. 变更指令示例

## 1. story_map.json 结构

```json
{
  "requirement": {
    "name": "", "source": "", "scenario": "", "pain_points": "",
    "goals": "", "solution": "", "value": "", "dod": ""
  },
  "releases": [{"name": "", "description": ""}],
  "journeys": [
    {"name": "", "features": [], "behaviors": [
      {"name": "", "features": [
        {"name": "", "who": "", "what": "", "when": "", "why": "",
         "dod": "", "priority": "", "release": "", "description": ""}
      ]}
    ]}
  ]
}
```

## 2. 字段说明

### requirement（原始需求，一图一条）

| 字段 | 含义 | 必填 |
|------|------|------|
| `name` | 需求名称 | ✅ |
| `source` | 需求来源 | 阶段 1 采集 |
| `scenario` | 业务场景 | 阶段 1 采集 |
| `pain_points` | 现状痛点 | 阶段 1 采集 |
| `goals` | 期望目标 | 阶段 1 采集 |
| `solution` | 方案（阶段 2 拆成旅程） | 阶段 1 采集 |
| `value` | 价值 | 阶段 1 采集 |
| `dod` | 需求整体验收标准（DoD） | 阶段 1 采集 |

### journeys[]（旅程与用户行为）

| 字段 | 含义 | 备注 |
|------|------|------|
| `journeys[].name` | 旅程步骤名称 | 地图内唯一 |
| `journeys[].features` | 直接挂在旅程下的功能特性 | 不细分行为时使用；与 behaviors 可共存但不推荐混用 |
| `journeys[].behaviors` | 用户行为层（可选） | 每个行为含 `name`（旅程内唯一）+ `features[]` |

功能特性名称在**同一旅程内**唯一，不论挂在行为下还是直接挂旅程——定位特性时只需 `journey` + `feature`。

### journeys[].features[]（功能特性）

| 字段 | 含义 | 必填 |
|------|------|------|
| `name` | 特性名称（What 的简短动宾短语，作为卡片标题） | ✅ |
| `who` | Who：使用角色 | 建议 |
| `what` | What：能力描述（缺省时取 name） | 建议 |
| `when` | When：触发时机/条件 | 建议 |
| `why` | Why：该特性的价值，回答"为什么要做" | 建议 |
| `dod` | 该特性的完成标准，可测试可量化 | 建议 |
| `priority` | `must` / `should` / `could` / `wont` | 可选 |
| `release` | 版本名，必须已存在于 `releases` | 可选 |
| `description` | 补充说明 | 可选 |

## 3. 完整示例

```json
{
  "requirement": {
    "name": "五轴切割换型一键调试",
    "source": "华南区客户季度回访",
    "scenario": "五轴激光切割设备现场打样，频繁换型",
    "pain_points": "人工示教单件调试约 40 分钟，换型频繁时产能被吃掉一半",
    "goals": "换型调试时间降到 10 分钟以内",
    "solution": "相机拍照定位 + 自动找正 + 参数模板一键下发",
    "value": "单台设备日产能 +30%，可作为高配卖点",
    "dod": "客户现场连续试运行 2 周无人工干预，定位误差 ≤ 0.05mm"
  },
  "releases": [
    {"name": "R1", "description": "MVP：单相机定位闭环"},
    {"name": "R2", "description": "参数模板与多工位扩展"}
  ],
  "journeys": [
    {"name": "上料与拍照", "features": [
      {"name": "夹具状态自检", "who": "操作员", "when": "上料完成后",
       "what": "一键触发夹具到位与状态检测", "why": "避免夹具异常导致批量废品",
       "dod": "夹具未到位或放反时 2s 内报警并禁止下一步",
       "priority": "must", "release": "R1", "description": ""}
    ], "behaviors": []},
    {"name": "自动找正", "features": [], "behaviors": [
      {"name": "单件拍照建模", "features": [
        {"name": "视觉定位计算", "who": "系统", "when": "拍照完成后自动",
         "what": "识别工件特征并计算找正量", "why": "替代人工示教，压缩换型调试时间",
         "dod": "从拍照到输出结果 ≤ 3s，误差 ≤ 0.05mm",
         "priority": "must", "release": "R1", "description": ""}
      ]},
      {"name": "多工位批量处理", "features": [
        {"name": "多工位批量找正", "who": "系统", "when": "多工位换型时",
         "what": "一次性完成所有工位找正", "dod": "8 工位批量处理 ≤ 60s",
         "priority": "could", "release": "R2", "description": ""}
      ]}
    ]}
  ]
}
```

## 4. update_map.py 操作（op）清单

通用参数：`--file`（状态文件路径，默认 `story_map.json`）、`--changes`（JSON 数组，缺省读 stdin）、`--force`（init 覆盖已有文件）。所有指令要么全部成功要么全部拒绝。

| op | 必填 | 可选 | 说明 |
|----|------|------|------|
| `init` | `name` | `releases[]` | 创建文件；必须单独作为唯一一条指令 |
| `set_requirement` | 七要素中至少一个 | — | 更新原始需求字段 |
| `add_release` | `name` | `description` | 定义版本 |
| `add_journey` | `name` | — | 添加旅程步骤（不可重名） |
| `add_behavior` | `journey`、`name` | — | 在旅程下添加用户行为（旅程内不可重名） |
| `rename` | `type`、`new_name` | `journey`、`behavior`/`feature` | type=journey 时需 `journey`；type=behavior 时需 `journey`+`behavior`；type=feature 时需 `journey`+`feature` |
| `delete` | `type` | `journey`、`behavior`/`feature` | 删除旅程/行为会级联删除其下全部功能特性 |
| `add_feature` | `journey`、`name` | `behavior`（挂到行为下）、`who`、`what`、`when`、`why`、`dod`、`priority`、`release`、`description` | 同一旅程内特性不可重名 |
| `set_feature` | `journey`、`feature` + 至少一个待改字段 | `who`、`what`、`when`、`why`、`dod`、`priority`、`release`、`description` | 修改功能特性字段 |

校验规则：priority 只能是 must/should/could/wont（缺省为 "" 未规划，渲染为"未规划"统计）；release 必须已定义；所有名称非空且不重复。

## 4.5 import_journey.py — 从旅程图导入草稿

读 hgyjy-user-journey 的 `journey_map.json`，生成**草稿**变更指令（裸 JSON 数组，可直接喂给 update_map.py），不直接改状态。

```bash
python3 scripts/import_journey.py --journey journey_map.json \
    --story story_map.json --output draft_ops.json
python3 scripts/update_map.py --file story_map.json --changes "$(cat draft_ops.json)"
```

- `--story` 缺省 `./story_map.json`；文件不存在时脚本自动调用 update_map.py init。
- 幂等：已存在的旅程、已导入过的机会点（按 what 原文判定）自动跳过；已填的原始需求字段只补空、不覆盖。
- 特性命名：机会点原文截断到 24 字符，同旅程内自动去重（重名追加 `(2)`…）。
- 输出 JSON 到 `--output`（或 stdout）；审阅提示与"待验证清单"打印到 stderr，导入前必须转述给用户。
- 映射明细见 SKILL.md「阶段 0」。

## 5. 变更指令示例

```bash
# 1. 创建（单独一条）
python3 scripts/update_map.py --file story_map.json --changes \
  '[{"op":"init","name":"五轴切割换型一键调试"}]'

# 2. 批量：补全七要素 + 定义版本 + 建骨干
python3 scripts/update_map.py --file story_map.json --changes '[
  {"op":"set_requirement","source":"华南区客户季度回访","scenario":"五轴打样频繁换型",
   "pain_points":"人工示教单件 40 分钟","goals":"降到 10 分钟以内",
   "solution":"相机拍照定位 + 自动找正 + 参数模板一键下发",
   "value":"日产能 +30%","dod":"试运行 2 周无人工干预，误差 ≤ 0.05mm"},
  {"op":"add_release","name":"R1","description":"MVP：单相机定位闭环"},
  {"op":"add_release","name":"R2","description":"参数模板扩展"},
  {"op":"add_journey","name":"上料与拍照"},
  {"op":"add_journey","name":"自动找正"}
]'

# 3. 挂功能特性
python3 scripts/update_map.py --file story_map.json --changes '[
  {"op":"add_feature","journey":"自动找正","name":"视觉定位计算",
   "who":"系统","when":"拍照完成后自动","what":"识别工件特征并计算找正量",
   "why":"替代人工示教，压缩换型调试时间",
   "dod":"从拍照到输出结果 ≤ 3s，误差 ≤ 0.05mm","priority":"must","release":"R1"}
]'

# 4. 迭代：改归属、改 DoD、重命名
python3 scripts/update_map.py --file story_map.json --changes '[
  {"op":"set_feature","journey":"自动找正","feature":"视觉定位计算",
   "release":"R2","dod":"≤ 2s，误差 ≤ 0.03mm"},
  {"op":"rename","type":"journey","journey":"自动找正","new_name":"视觉找正与补偿"}
]'
```
