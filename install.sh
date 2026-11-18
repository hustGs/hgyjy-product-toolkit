#!/usr/bin/env bash
# hgyjy-product-toolkit 跨 harness 安装脚本
# 把 skills/ 下的两个 skill 链接（或拷贝）到目标工具的技能发现目录。
#
# 用法:
#   ./install.sh                 # 安装到 claude-code + opencode，全局
#   ./install.sh claude-code     # 只装一个
#   ./install.sh all --project   # 装到当前项目的项目级目录
#   ./install.sh opencode --copy # 拷贝而非符号链接（Windows/特殊文件系统用）
#
# 说明: 默认用符号链接，仓库保持单一事实源，git pull 即更新；
# 若工具不跟随符号链接，加 --copy。

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS=(hgyjy-user-story hgyjy-user-journey)

TARGETS="${1:-all}"
SCOPE="global"
MODE="link"
for arg in "$@"; do
  case "$arg" in
    --project) SCOPE="project" ;;
    --copy)    MODE="copy" ;;
    --global)  SCOPE="global" ;;
  esac
done

dest_for() {
  local tool="$1"
  if [ "$SCOPE" = "project" ]; then
    case "$tool" in
      claude-code) echo "$PWD/.claude/skills" ;;
      opencode)    echo "$PWD/.opencode/skills" ;;
      workbuddy)   echo "$PWD/.workbuddy/skills" ;;
      codex)       echo "$PWD/.agents/skills" ;;
    esac
  else
    case "$tool" in
      claude-code) echo "$HOME/.claude/skills" ;;
      opencode)    echo "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills" ;;
      workbuddy)   echo "$HOME/.workbuddy/skills" ;;
      codex)       echo "$HOME/.agents/skills" ;;
    esac
  fi
}

install_one() {
  local tool="$1" dest skill name
  dest="$(dest_for "$tool")"
  mkdir -p "$dest"
  for skill in "${SKILLS[@]}"; do
    name="$dest/$skill"
    rm -rf "$name"
    if [ "$MODE" = "link" ]; then
      ln -s "$REPO_DIR/skills/$skill" "$name"
    else
      cp -r "$REPO_DIR/skills/$skill" "$name"
    fi
    echo "  [ok] $tool -> $name"
  done
}

case "$TARGETS" in
  all)        tools=(claude-code opencode workbuddy) ;;
  claude-code|opencode|workbuddy|codex) tools=("$TARGETS") ;;
  *) echo "未知目标: $TARGETS（可选 claude-code / opencode / workbuddy / codex / all）"; exit 1 ;;
esac

echo "安装 skills: ${SKILLS[*]} → ${tools[*]} ($SCOPE, $MODE)"
for t in "${tools[@]}"; do
  install_one "$t"
done
echo "完成。新开一个会话即可触发（「梳理原始需求」「分析用户旅程」）。"
echo "注意: OpenCode 添加/修改 skill 后需重启会话才会被发现。"
