#!/usr/bin/env python3
"""hgyjy-user-journey: 用户旅程图确定性渲染器。

读取 journey_map.json，输出自包含 HTML（无外部依赖）：
  - 旅程信息面板（角色/场景与目标/用户预期）
  - 统计条（阶段数/痛点数/机会点数/假设阶段数）
  - SVG 情绪曲线（横轴=阶段，纵轴=-2..2）
  - 逐阶段泳道列：目标 → 行动 → 触点 → 想法 → 情绪 → 痛点 → 机会点
  - 关键时刻面板
  - 事实/假设分标（假设阶段橙色徽标）

用法:
    python3 render_journey.py --input journey_map.json --output journey_map.html
"""

import argparse
import html
import json
import sys

EMOTION_META = {
    -2: ("#dc2626", "😖", "非常消极"),
    -1: ("#ea580c", "🙁", "消极"),
    0: ("#64748b", "😐", "中性"),
    1: ("#16a34a", "🙂", "积极"),
    2: ("#059669", "😄", "非常积极"),
}

LIST_META = [
    ("actions", "用户行动", "#1d4ed8"),
    ("touchpoints", "触点", "#7c3aed"),
    ("thoughts", "想法 / 疑问", "#0e7490"),
    ("pain_points", "痛点", "#dc2626"),
    ("opportunities", "机会点", "#059669"),
]

JOURNEY_LABELS = [("persona", "角色"), ("scenario", "场景与目标"), ("expectations", "用户预期")]

LIST_FIELDS_KEYS = ("actions", "touchpoints", "thoughts", "pain_points", "opportunities")


def e(s):
    return html.escape(str(s), quote=True)


def esc_js(s):
    return json.dumps(str(s), ensure_ascii=False)


def render_curve_svg(stages, col_w):
    """情绪曲线 SVG。x=阶段中心，y 从 2(顶) 到 -2(底)。无情绪的阶段断开连线。"""
    n = len(stages)
    if n == 0:
        return ""
    width = n * col_w
    left, right = 48, 30
    top, bottom = 24, 30
    height = 180
    plot_w = width - left - right
    plot_h = height - top - bottom
    cx = [left + plot_w * (i + 0.5) / n for i in range(n)]

    def cy(v):
        return top + plot_h * (2 - v) / 4

    parts = [f'<svg viewBox="0 0 {width} {height}" class="curve" '
             f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="情绪曲线">']

    # 网格线
    for v, lbl in ((2, "非常积极"), (1, "积极"), (0, "中性"), (-1, "消极"), (-2, "非常消极")):
        y = cy(v)
        cls = "grid0" if v == 0 else "grid"
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="{cls}"/>')
        parts.append(f'<text x="{left-6}" y="{y+4:.1f}" text-anchor="end" class="axlbl">{e(lbl)}</text>')

    # 零线加粗
    y0 = cy(0)
    parts.append(f'<line x1="{left}" y1="{y0:.1f}" x2="{width-right}" y2="{y0:.1f}" class="zero"/>')

    # 连线（只在有情绪的相邻阶段之间连；无情绪阶段断开）
    prev = None
    for i, s in enumerate(stages):
        emo = s.get("emotion")
        if emo is None:
            prev = None
            continue
        if prev is not None and prev[0] == i - 1:
            pi, pemo = prev
            color = EMOTION_META[emo][0]
            parts.append(f'<line x1="{cx[pi]:.1f}" y1="{cy(pemo):.1f}" x2="{cx[i]:.1f}" '
                         f'y2="{cy(emo):.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>')
        prev = (i, emo)

    # 阶段中心竖线 + 点
    for i, s in enumerate(stages):
        parts.append(f'<line x1="{cx[i]:.1f}" y1="{top}" x2="{cx[i]:.1f}" y2="{height-bottom}" class="vline"/>')
        emo = s.get("emotion")
        if emo is not None:
            color, face, _ = EMOTION_META[emo]
            y = cy(emo)
            parts.append(f'<circle cx="{cx[i]:.1f}" cy="{y:.1f}" r="9" fill="{color}"/>')
            parts.append(f'<text x="{cx[i]:.1f}" y="{y+4:.1f}" text-anchor="middle" class="dotface">{face}</text>')
        parts.append(f'<text x="{cx[i]:.1f}" y="{height-bottom+16:.1f}" text-anchor="middle" class="stagelbl">'
                     f'{e(s["name"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def render_stage_column(s):
    parts = [f'<div class="col{" hypo" if s.get("evidence") == "hypothesis" else ""}">']
    hypo_badge = ('<span class="badge-hypo">假设</span>'
                  if s.get("evidence") == "hypothesis" else
                  ('<span class="badge-fact">事实</span>' if s.get("evidence") == "fact" else ""))
    parts.append(f'<div class="colhead">{e(s["name"])}{hypo_badge}</div>')
    parts.append(f'<div class="goal"><span class="lbl">🎯 目标</span>{e(s.get("goal") or "—")}</div>')

    emo = s.get("emotion")
    if emo is None:
        emo_html = '<span class="emo-none">未评估</span>'
    else:
        color, face, label = EMOTION_META[emo]
        emo_html = (f'<span class="emo-chip" style="background:{color}">{face} {label}</span>')

    for field, label, color in LIST_META:
        items = s.get(field, [])
        lis = "".join(f"<li>{e(x)}</li>" for x in items) or '<li class="empty">—</li>'
        parts.append(f'<div class="block" style="--blk:{color}"><div class="blkhead">{e(label)}</div>'
                     f'<ul>{lis}</ul></div>')
    parts.append(f'<div class="block" style="--blk:#b45309"><div class="blkhead">情绪</div>{emo_html}</div>')
    parts.append("</div>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="用户旅程图渲染器")
    ap.add_argument("--input", default="journey_map.json")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[错误] 状态文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as ex:
        print(f"[错误] 状态文件不是合法 JSON: {ex}", file=sys.stderr)
        sys.exit(1)

    # ---------- 校验 ----------
    errors = []
    if not isinstance(data.get("journey"), dict):
        errors.append("缺少 journey 对象")
    else:
        for k in ("name", "persona", "scenario", "expectations"):
            if k not in data["journey"]:
                errors.append(f"journey 缺少字段: {k}")
    stages = data.get("stages", [])
    if not isinstance(stages, list):
        errors.append("stages 必须是数组")
        stages = []
    names = [s.get("name", "?") for s in stages]
    dup = {n for n in names if names.count(n) > 1}
    if dup:
        errors.append(f"阶段名重复: {', '.join(sorted(dup))}")
    for s in stages:
        for fld in LIST_FIELDS_KEYS:
            for item in s.get(fld, []):
                if not isinstance(item, str) or not item.strip():
                    errors.append(f"阶段「{s.get('name','?')}」的 {fld} 含空条目")
        emo = s.get("emotion")
        if emo is not None and emo not in EMOTION_META:
            errors.append(f"阶段「{s.get('name','?')}」情绪分非法: {emo}")
        ev = s.get("evidence")
        if ev is not None and ev not in ("fact", "hypothesis"):
            errors.append(f"阶段「{s.get('name','?')}」证据类型非法: {ev}")
    moments = data.get("moments", [])
    if not isinstance(moments, list):
        errors.append("moments 必须是数组")
        moments = []

    if errors:
        print("[错误] 状态文件校验失败：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    journey = data["journey"]
    n_pains = sum(len(s.get("pain_points", [])) for s in stages)
    n_opps = sum(len(s.get("opportunities", [])) for s in stages)
    n_hypo = sum(1 for s in stages if s.get("evidence") == "hypothesis")
    n_uneval = sum(1 for s in stages if s.get("emotion") is None)

    col_w = 250
    curve = render_curve_svg(stages, col_w)
    columns = "".join(render_stage_column(s) for s in stages)
    moments_html = ""
    for i, m in enumerate(moments, 1):
        moments_html += f'<li><span class="mom-idx">{i}</span>{e(m)}</li>'
    if not moments_html:
        moments_html = '<li class="empty">—</li>'

    info_rows = ""
    for k, lbl in JOURNEY_LABELS:
        info_rows += (f'<div class="inforow"><span class="infolbl">{lbl}</span>'
                      f'<span>{e(journey.get(k) or "—")}</span></div>')

    stats = (
        f'<div class="stat"><b>{len(stages)}</b><span>阶段</span></div>'
        f'<div class="stat"><b>{n_pains}</b><span>痛点</span></div>'
        f'<div class="stat"><b>{n_opps}</b><span>机会点</span></div>'
        f'<div class="stat {"warn" if n_hypo else ""}"><b>{n_hypo}</b><span>假设阶段</span></div>'
        f'<div class="stat {"warn" if n_uneval else ""}"><b>{n_uneval}</b><span>未评情绪</span></div>'
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(journey['name'])} — 用户旅程图</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
       background: #f1f5f9; color: #1e293b; padding: 24px; }}
.page {{ max-width: 1600px; margin: 0 auto; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
.sub {{ color: #64748b; font-size: 13px; margin-bottom: 16px; }}
.card {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
        padding: 16px 20px; margin-bottom: 16px; }}
.inforow {{ display: flex; gap: 12px; padding: 6px 0; border-bottom: 1px dashed #e2e8f0; font-size: 14px; }}
.inforow:last-child {{ border-bottom: none; }}
.infolbl {{ flex: 0 0 96px; color: #64748b; font-weight: 600; }}
.stats {{ display: flex; gap: 12px; flex-wrap: wrap; }}
.stat {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
        padding: 8px 18px; text-align: center; }}
.stat b {{ display: block; font-size: 20px; }}
.stat span {{ font-size: 12px; color: #64748b; }}
.stat.warn b {{ color: #ea580c; }}
.curve-wrap {{ overflow-x: auto; }}
svg.curve {{ width: 100%; min-width: 640px; height: auto; display: block; }}
svg.curve .grid {{ stroke: #e2e8f0; stroke-width: 1; }}
svg.curve .grid0 {{ stroke: #cbd5e1; stroke-width: 1; stroke-dasharray: 4 3; }}
svg.curve .zero {{ stroke: #94a3b8; stroke-width: 1.5; }}
svg.curve .vline {{ stroke: #f1f5f9; stroke-width: 1; }}
svg.curve .axlbl {{ font-size: 10px; fill: #94a3b8; }}
svg.curve .stagelbl {{ font-size: 11px; fill: #334155; font-weight: 600; }}
svg.curve .dotface {{ font-size: 9px; }}
.swim {{ display: flex; gap: 12px; overflow-x: auto; padding-bottom: 8px; }}
.col {{ flex: 0 0 {col_w}px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
       padding: 10px 12px; }}
.col.hypo {{ border-color: #fdba74; background: #fff7ed; }}
.colhead {{ font-weight: 700; font-size: 15px; margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }}
.badge-hypo {{ background: #ea580c; color: #fff; font-size: 10px; font-weight: 600;
               padding: 1px 7px; border-radius: 999px; }}
.badge-fact {{ background: #e2e8f0; color: #475569; font-size: 10px; font-weight: 600;
               padding: 1px 7px; border-radius: 999px; }}
.goal {{ font-size: 13px; background: #fff; border-left: 3px solid #f59e0b; padding: 6px 8px;
        border-radius: 0 6px 6px 0; margin-bottom: 10px; }}
.goal .lbl {{ display: block; font-size: 11px; color: #b45309; font-weight: 700; margin-bottom: 2px; }}
.block {{ margin-bottom: 10px; }}
.blkhead {{ font-size: 11px; font-weight: 700; color: var(--blk); margin-bottom: 4px;
            border-bottom: 1px solid #e2e8f0; padding-bottom: 2px; }}
.block ul {{ list-style: none; }}
.block li {{ font-size: 12.5px; padding: 3px 0 3px 12px; position: relative; line-height: 1.5; }}
.block li::before {{ content: "·"; position: absolute; left: 2px; color: var(--blk); font-weight: 700; }}
.block li.empty, li.empty {{ color: #cbd5e1; }}
.emo-chip {{ display: inline-block; color: #fff; font-size: 12px; font-weight: 600;
             padding: 2px 10px; border-radius: 999px; }}
.emo-none {{ font-size: 12px; color: #cbd5e1; }}
.moments ul {{ list-style: none; }}
.moments li {{ font-size: 14px; padding: 6px 0; display: flex; gap: 10px; align-items: baseline;
               border-bottom: 1px dashed #e2e8f0; }}
.moments li:last-child {{ border-bottom: none; }}
.mom-idx {{ flex: 0 0 22px; height: 22px; line-height: 22px; text-align: center; background: #1e293b;
           color: #fff; border-radius: 50%; font-size: 11px; font-weight: 700; }}
.legend {{ font-size: 12px; color: #64748b; display: flex; gap: 18px; flex-wrap: wrap; margin-bottom: 8px; }}
.h2 {{ font-size: 15px; font-weight: 700; margin-bottom: 10px; }}
@media print {{
  body {{ background: #fff; padding: 0; }}
  @page {{ size: A3 landscape; margin: 10mm; }}
  .card {{ box-shadow: none; border: 1px solid #e2e8f0; break-inside: avoid; }}
}}
</style>
</head>
<body>
<div class="page">
  <h1>{e(journey['name'])} <span style="font-size:13px;color:#64748b;font-weight:400">用户旅程图</span></h1>
  <div class="sub">hgyjy-user-journey 生成 · 阶段事实与假设已分标 · 滚动查看全部阶段</div>

  <div class="card"><div class="h2">旅程信息</div>{info_rows}</div>

  <div class="card"><div class="stats">{stats}</div></div>

  <div class="card">
    <div class="h2">情绪曲线</div>
    <div class="legend">
      <span>😄 非常积极</span><span>🙂 积极</span><span>😐 中性</span>
      <span>🙁 消极</span><span>😖 非常消极</span><span>⚠ 橙色列 = 基于假设，需验证</span>
    </div>
    <div class="curve-wrap">{curve or '<p class="empty">尚无阶段</p>'}</div>
  </div>

  <div class="card">
    <div class="h2">阶段泳道</div>
    <div class="swim">{columns or '<p class="empty">尚无阶段</p>'}</div>
  </div>

  <div class="card moments">
    <div class="h2">关键时刻（Moments of Truth）</div>
    <ul>{moments_html}</ul>
  </div>
</div>
</body>
</html>
"""
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"已生成 {args.output}（{len(stages)} 个阶段，{n_pains} 个痛点，{n_opps} 个机会点，"
          f"{n_hypo} 个假设阶段）")


if __name__ == "__main__":
    main()
