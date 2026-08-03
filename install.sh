#!/bin/bash
# job-radar — 求职检索脚手架 安装脚本
# 自动检测已安装的 AI Agent，把本 skill 安装到对应 skills 目录。
# 支持：Claude Code / Codex CLI / Cursor / Gemini CLI / Trae / OpenCode / Rovo Dev / Hermes / WorkBuddy
# 用法：bash install.sh   （或双击；在仓库根目录运行）

set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL_NAME="job-radar"
SKILL_SRC="$HERE"

# Agent 配置：name|skills目录|检测命令
AGENTS=(
  "Claude Code|$HOME/.claude/skills|claude"
  "Codex CLI|$HOME/.codex/skills|codex"
  "Cursor|.cursor/skills|cursor"
  "Gemini CLI|$HOME/.gemini/skills|gemini"
  "Trae（国际版）|$HOME/.trae/skills|trae"
  "Trae（国内版）|$HOME/.trae-cn/skills|trae-cn"
  "OpenCode|.opencode/skills|opencode"
  "Rovo Dev|$HOME/.rovodev/skills|rovodev"
  "Hermes|$HOME/.hermes/skills|hermes"
  "WorkBuddy|$HOME/.workbuddy/skills|workbuddy"
)

echo ""
echo "🔥 job-radar — 求职检索脚手架 安装"
echo ""

detected=()
for entry in "${AGENTS[@]}"; do
  IFS='|' read -r name dest cmd <<< "$entry"
  if command -v "$cmd" &>/dev/null || [ -d "$(dirname "$dest")" ]; then
    detected+=("$name|$dest")
  fi
done

if [ ${#detected[@]} -eq 0 ]; then
  echo "未检测到已安装的 AI Agent。"
  echo ""
  echo "请手动选择安装位置（输入编号）："
  idx=1
  for entry in "${AGENTS[@]}"; do
    IFS='|' read -r name dest cmd <<< "$entry"
    echo "  $idx) $name  ->  $dest"
    idx=$((idx+1))
  done
  read -r choice
  line="${AGENTS[$((choice-1))]}"
  IFS='|' read -r name dest cmd <<< "$line"
  detected+=("$name|$dest")
fi

echo "检测到以下 Agent，开始安装 $SKILL_NAME："
for d in "${detected[@]}"; do
  IFS='|' read -r name dest <<< "$d"
  target="$dest/$SKILL_NAME"
  mkdir -p "$dest"
  # 非破坏式安装：仅覆盖代码文件，保留目标目录中已存在的用户数据
  # （用户数据已外移至 ~/.job-radar，不存放在 skill 目录内，重装不会丢失）
  cp -R "$SKILL_SRC/." "$target/"
  echo "  ✅ $name  ->  $target"
done

echo ""
echo "安装完成。在对应 Agent 中加载 job-radar skill 即可使用。"
echo "（首次使用运行：python scripts/brief.py 设置需求，再把 prompt.txt 发给 AI 检索。）"
