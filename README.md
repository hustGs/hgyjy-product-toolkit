# hgyjy-product-toolkit

hgyjy 产品工具包 —— 用户故事地图 × 用户旅程图双件套（Kimi 自定义插件）。

## 组成

| Skill | 用途 | 状态文件 |
|-------|------|---------|
| `hgyjy-user-story` | 原始需求七要素 → 旅程骨干 → 功能特性（Who/What/When/Why/DoD），MoSCoW 优先级 + 版本泳道 | `story_map.json` |
| `hgyjy-user-journey` | 角色×场景体验旅程：行动/触点/想法/情绪/痛点/机会点，事实/假设分标，情绪曲线 + 关键时刻 | `journey_map.json` |

桥接：`hgyjy-user-story/scripts/import_journey.py` 把旅程图的机会点导入为故事地图草稿。

## 使用

**Kimi**：插件页 → **自定义** → **我创建的** 中安装。对话中说出「梳理原始需求」「做用户故事地图」「分析用户旅程」等即触发对应 skill。

**Claude Code / OpenCode / WorkBuddy**（SKILL.md 是 Agent Skills 开放标准，直接可用）：

```bash
bash install.sh                  # claude-code + opencode + workbuddy，全局符号链接
bash install.sh workbuddy --copy # 拷贝模式（不跟随符号链接的环境）
bash install.sh all --project    # 装到当前项目（随仓库走，团队共享）
```

| 工具 | 全局发现路径 | 项目级 |
|------|-------------|--------|
| Claude Code | `~/.claude/skills/<name>/` | `.claude/skills/<name>/` |
| OpenCode | `~/.config/opencode/skills/<name>/`（兼容 `~/.claude/skills/`） | `.opencode/skills/<name>/`（兼容 `.claude/skills/`） |
| WorkBuddy | `~/.workbuddy/skills/<name>/` | `.workbuddy/skills/<name>/` |

WorkBuddy 也可走 UI：技能面板 → 添加技能 → 上传技能，分别上传两个 skill 目录打的 zip（zip 根目录即 skill 文件夹，SKILL.md 在其根部）。

注意：OpenCode / WorkBuddy 添加 skill 后需**重启会话**才被发现；WorkBuddy 执行 shell 时工作目录不是 skill 目录，脚本调用用 `${CODEBUDDY_SKILL_DIR}` 全路径（两个 SKILL.md 命令参考已注明）；Kimi 侧新版本走插件页「版本历史」，其余工具侧靠 `git pull` + 重装（符号链接模式 pull 即生效）。

## 版本管理

- manifest 版本（`kimi.plugin.json` 的 `version`）是唯一发布版本号，必须与 git tag 一致（tag `v1.0.0` ↔ version `1.0.0`），CI 会强制校验。
- 每次发布：改 `version` → 打同号 tag 推送 → CI 自动打包 `.kplugin` 并创建 Release（GitHub / GitLab 行为一致，制品附加其中，manifest 位于压缩包根部）。
- 发插件新版本：`publish_user_plugin` 发布后用插件页「版本历史」选择切换。

## 目录结构

```
kimi.plugin.json      # 插件 manifest（version 字段即发布版本）
locales/en-US.json    # 界面英文文案（manifest 正文为 zh-CN）
skills/<skill>/       # SKILL.md + scripts/ + references/ + LICENSE
ci/validate.py        # CI 校验：manifest/版本/tag 一致性
.gitlab-ci.yml        # validate + tag 打包 Release（GitLab）
.github/workflows/ci.yml  # 同行为 GitHub Actions 版
```
