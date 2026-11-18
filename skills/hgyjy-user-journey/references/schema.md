# journey_map.json 结构与操作指令

## 目录

- 状态文件结构
- 字段表
- 操作指令完整表
- 完整示例

## 状态文件结构

```json
{
  "journey": {
    "name": "工艺工程师首次使用 LPBF 知识智能体",
    "persona": "LPBF 工艺工程师，3 年设备调试经验…",
    "scenario": "新机型首件打印出现球化缺陷，需要在 2 小时内定位原因…",
    "expectations": "像问有经验的师傅一样直接得到答案…"
  },
  "stages": [
    {
      "name": "首次提问",
      "goal": "把缺陷现象描述清楚，得到可用答案",
      "actions": ["用手机拍下缺陷照片，文字描述粉末批次与参数"],
      "touchpoints": ["车间工位电脑上的智能体对话界面"],
      "thoughts": ["怕描述不清楚，系统听不懂行话"],
      "emotion": -1,
      "pain_points": ["缺陷术语口头化，担心检索不到匹配案例"],
      "opportunities": ["支持图片+参数表混合输入，自动提取关键工艺字段"],
      "evidence": "fact"
    }
  ],
  "moments": [
    "首次提问得到带出处、可直接执行的候选原因列表（信任建立瞬间）"
  ]
}
```

## 字段表

### 旅程级（journey）

| 字段 | 必填 | 说明 |
|------|------|------|
| name | ✅ | 旅程图名称（一句话：角色+场景） |
| persona | ✅ | 角色：具体到经验/技能/处境 |
| scenario | ✅ | 场景与目标：含时间压力或约束 |
| expectations | ✅ | 用户预期：心里期待什么样的体验 |

### 阶段级（stages[]）

| 字段 | 必填 | 说明 |
|------|------|------|
| name | ✅ | 阶段名，名词短语，图内唯一 |
| goal | ✅ | 该阶段用户目标 |
| actions | ✅ | 用户行动列表（可空，空≠—） |
| touchpoints | ✅ | 触点列表 |
| thoughts | ✅ | 想法/疑问列表，原话式 |
| emotion | ❌ | -2/-1/0/1/2 或 null（未评估） |
| pain_points | ✅ | 痛点列表 |
| opportunities | ✅ | 机会点列表 |
| evidence | ✅ | fact（事实）/ hypothesis（假设），默认 fact |

### 图级（moments[]）

关键时刻字符串列表，每个一条完整句子。

## 操作指令完整表

所有指令以 JSON 对象数组传入 `update_journey.py`，原子执行。

| op | 必填参数 | 可选参数 | 说明 |
|----|---------|---------|------|
| `init` | name | — | 创建状态文件；已存在需 `--force`；必须单独作为唯一指令 |
| `set_journey` | 至少一个字段 | persona, scenario, expectations | 更新旅程信息字段（name 也支持，但改角色建议另起新图） |
| `add_stage` | name | goal | 添加阶段（阶段名不可重） |
| `set_stage` | stage | goal, emotion, evidence | 更新阶段属性；emotion 传 null 清空 |
| `rename` | type=stage, stage, new_name | — | 阶段重命名（目标名不可与现有重复） |
| `delete` | type=stage, stage | — | 删除阶段（级联删除其全部内容，删前向用户确认） |
| `add_item` | stage, field, value | — | 向列表字段追加一条（同阶段同字段去重） |
| `set_item` | stage, field, index, value | — | 修改第 index 条（1-based） |
| `remove_item` | stage, field, index | — | 删除第 index 条（1-based） |
| `add_moment` | value | — | 添加关键时刻（去重） |
| `remove_moment` | index | — | 删除第 index 个关键时刻（1-based） |

- `field` 只接受：`actions` / `touchpoints` / `thoughts` / `pain_points` / `opportunities`
- `evidence` 只接受：`fact` / `hypothesis`
- `emotion` 只接受：-2 / -1 / 0 / 1 / 2 / null
- 任一指令非法 → 整批拒绝，状态文件不变

## 完整示例

```bash
# 1. 初始化
python3 scripts/update_journey.py --file journey_map.json --changes \
  '[{"op":"init","name":"工艺工程师首次使用 LPBF 知识智能体"}]'

# 2. 写旅程信息 + 建阶段
python3 scripts/update_journey.py --file journey_map.json --changes '[
  {"op":"set_journey",
   "persona":"LPBF 工艺工程师，3 年经验，熟悉工艺参数但不熟悉新机型",
   "scenario":"新机型首件打印出现球化缺陷，需 2 小时内定位原因",
   "expectations":"像问有经验的师傅一样直接得到答案"},
  {"op":"add_stage","name":"首次提问","goal":"把缺陷现象描述清楚，得到可用答案"}
]'

# 3. 填维度 + 标情绪证据
python3 scripts/update_journey.py --file journey_map.json --changes '[
  {"op":"add_item","stage":"首次提问","field":"actions","value":"拍照并文字描述缺陷"},
  {"op":"add_item","stage":"首次提问","field":"pain_points","value":"答案没有引用出处，无法判断可信度"},
  {"op":"set_stage","stage":"首次提问","emotion":-1,"evidence":"hypothesis"}
]'

# 4. 关键时刻 + 渲染
python3 scripts/update_journey.py --file journey_map.json --changes \
  '[{"op":"add_moment","value":"首次得到带出处、可直接执行的候选原因列表"}]'
python3 scripts/render_journey.py --input journey_map.json --output journey_map.html
```
