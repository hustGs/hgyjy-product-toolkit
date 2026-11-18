#!/usr/bin/env python3
"""hgyjy-user-story: 用户故事地图渲染器。

读取 story_map.json（由 update_map.py 维护），生成自包含 HTML：
- 顶部：原始需求七要素面板（来源/场景/痛点/目标/方案/价值/DoD）
- 骨干：用户旅程步骤（横向）
- 卡片：功能特性（Who/What/When/DoD，MoSCoW 优先级色标，点击展开详情）
- Release 虚线分组 + 统计面板

用法:
    python3 render_map.py --input story_map.json --output story_map.html
    cat story_map.json | python3 render_map.py --output story_map.html
"""

import argparse
import json
import sys
from datetime import datetime
from html import escape

VALID_PRIORITIES = {"must", "should", "could", "wont", ""}

PRIORITY_META = {
    "must":   {"label": "Must",   "color": "#dc2626", "bg": "#fef2f2", "border": "#fca5a5"},
    "should": {"label": "Should", "color": "#ea580c", "bg": "#fff7ed", "border": "#fdba74"},
    "could":  {"label": "Could",  "color": "#2563eb", "bg": "#eff6ff", "border": "#93c5fd"},
    "wont":   {"label": "Won't",  "color": "#6b7280", "bg": "#f9fafb", "border": "#d1d5db"},
    "":       {"label": "",       "color": "#cbd5e1", "bg": "#ffffff", "border": "#e2e8f0"},
}

JOURNEY_PALETTE = [
    "#6366f1", "#8b5cf6", "#06b6d4", "#10b981",
    "#f59e0b", "#ef4444", "#ec4899", "#14b8a6",
]

REQ_FIELDS = (
    ("source", "需求来源"),
    ("scenario", "业务场景"),
    ("pain_points", "现状痛点"),
    ("goals", "期望目标"),
    ("solution", "方案"),
    ("value", "价值"),
    ("dod", "DoD"),
)


def validate_data(data):
    errors = []
    if not isinstance(data, dict):
        return ["输入必须是 JSON 对象"]
    req = data.get("requirement")
    if not isinstance(req, dict) or not req.get("name"):
        errors.append("缺少 requirement.name（原始需求名称）")
    for r in data.get("releases", []):
        if not r.get("name"):
            errors.append("releases[] 缺少 name")
    release_names = {r["name"] for r in data.get("releases", []) if r.get("name")}
    for j in data.get("journeys", []):
        jn = j.get("name", "?")
        if not jn:
            errors.append("journeys[] 缺少 name")
        flat = [(f"旅程'{jn}'", ft) for ft in j.get("features", [])]
        bseen = set()
        for b in j.get("behaviors", []):
            bn = b.get("name", "?")
            if not bn:
                errors.append(f"旅程'{jn}': 用户行为缺少 name")
            if bn in bseen:
                errors.append(f"旅程'{jn}': 用户行为重名 '{bn}'")
            bseen.add(bn)
            for ft in b.get("features", []):
                flat.append((f"旅程'{jn}'/行为'{bn}'", ft))
        seen = set()
        for tag, ft in flat:
            if not ft.get("name"):
                errors.append(f"{tag}: 功能特性缺少 name")
                continue
            if ft["name"] in seen:
                errors.append(f"{tag}: 功能特性重名 '{ft['name']}'（同一旅程内须唯一）")
            seen.add(ft["name"])
            pri = ft.get("priority") or ""
            if pri and pri not in VALID_PRIORITIES:
                errors.append(f"{tag} '{ft['name']}': 非法优先级 '{pri}'")
            rel = ft.get("release", "")
            if rel and rel not in release_names:
                errors.append(f"{tag} '{ft['name']}': 未定义版本 '{rel}'")
    return errors


def _kv(label, value):
    if not value:
        return ""
    return (f'<div class="kv"><span class="k">{escape(label)}</span>'
            f'<span class="v">{escape(value)}</span></div>')


def generate_html(data):
    req = data["requirement"]
    req_name = escape(req.get("name", ""))
    releases = data.get("releases", [])
    journeys = data.get("journeys", [])
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    col_w = 230

    all_features = [ft for j in journeys
                    for ft in j.get("features", []) + [f for b in j.get("behaviors", [])
                                                       for f in b.get("features", [])]]
    total = len(all_features)

    def _stats_html():
        parts = [f'<span class="stat-item"><b>{total}</b> 功能特性</span>']
        parts.append('<span class="stat-sep">|</span>')
        for p in ("must", "should", "could", "wont"):
            m = PRIORITY_META[p]
            cnt = sum(1 for f in all_features if f.get("priority") == p)
            if cnt:
                parts.append(
                    f'<span class="stat-badge" style="background:{m["bg"]};color:{m["color"]};'
                    f'border:1px solid {m["border"]}">{escape(m["label"])} {cnt}</span>')
        unassigned = sum(1 for f in all_features if not f.get("priority"))
        if unassigned:
            parts.append(f'<span class="stat-item">未标优先级: <b>{unassigned}</b></span>')
        parts.append('<span class="stat-sep">|</span>')
        for rel in releases:
            cnt = sum(1 for f in all_features if f.get("release") == rel["name"])
            parts.append(f'<span class="stat-item">{escape(rel["name"])}: <b>{cnt}</b></span>')
        backlog = sum(1 for f in all_features if not f.get("release"))
        if backlog:
            parts.append(f'<span class="stat-item">未规划: <b>{backlog}</b></span>')
        return "\n".join(parts)

    def _req_panel():
        rows = "".join(
            f'<div class="req-row"><span class="req-label">{label}</span>'
            f'<span class="req-value">{escape(req.get(key) or "—")}</span></div>'
            for key, label in REQ_FIELDS)
        return f'<details class="req-panel" open><summary>原始需求</summary>{rows}</details>'

    def _journey_row():
        cells = []
        for ji, j in enumerate(journeys):
            color = JOURNEY_PALETTE[ji % len(JOURNEY_PALETTE)]
            n = len(j.get("features", [])) + sum(len(b.get("features", []))
                                                 for b in j.get("behaviors", []))
            cells.append(
                f'<div class="journey-cell" style="width:{col_w}px;background:{color}">'
                f'<div class="journey-name">{escape(j["name"])}</div>'
                f'<div class="journey-count">{n} 个特性</div></div>')
        return "".join(cells)

    def _feature_card(ft):
        pri = ft.get("priority", "")
        m = PRIORITY_META.get(pri, PRIORITY_META[""])
        name = escape(ft.get("name", ""))
        body = (_kv("Who", ft.get("who"))
                + _kv("What", ft.get("what"))
                + _kv("When", ft.get("when"))
                + _kv("Why", ft.get("why"))
                + _kv("DoD", ft.get("dod"))
                + _kv("补充", ft.get("description")))
        body_html = f'<div class="card-body">{body}</div>' if body else ""
        pri_html = (f'<span class="card-pri" style="color:{m["color"]}">{escape(m["label"])}</span>'
                    if pri else "")
        return (
            f'<details class="story-card" style="border-left:4px solid {m["color"]};'
            f'background:{m["bg"]};border-top:1px solid {m["border"]};'
            f'border-right:1px solid {m["border"]};border-bottom:1px solid {m["border"]}">'
            f'<summary><span class="card-title">{name}</span>{pri_html}</summary>'
            f'{body_html}</details>')

    def _release_sections():
        sections = []
        buckets = [(rel["name"], rel.get("description", "")) for rel in releases]
        if any(not f.get("release") for f in all_features):
            buckets.append(("", ""))
        for rname, rdesc in buckets:
            if rname:
                label = escape(rname)
                if rdesc:
                    label += f' <span class="rel-desc">— {escape(rdesc)}</span>'
            else:
                label = "未规划"
            cols = []
            for j in journeys:
                blocks = []
                for b in j.get("behaviors", []):
                    bcards = "".join(_feature_card(f) for f in b.get("features", [])
                                     if (f.get("release") or "") == rname)
                    if bcards:
                        blocks.append(f'<div class="behavior-label">{escape(b["name"])}</div>{bcards}')
                blocks.append("".join(_feature_card(f) for f in j.get("features", [])
                                      if (f.get("release") or "") == rname))
                cards = "".join(blocks) or '<div class="empty-slot"></div>'
                cols.append(f'<div class="story-col" style="width:{col_w}px">{cards}</div>')
            sections.append(
                f'<div class="release-section">'
                f'<div class="release-divider"><div class="release-line"></div>'
                f'<div class="release-badge">{label}</div></div>'
                f'<div class="map-row stories-row">{"".join(cols)}</div></div>')
        return "".join(sections)

    map_w = max(len(journeys) * col_w, col_w)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{req_name} — 用户故事地图</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,
"Noto Sans SC","PingFang SC","Microsoft YaHei",sans-serif;background:#f1f5f9;color:#1e293b;
line-height:1.5;min-height:100vh}}
.container{{max-width:100%;padding:20px}}
header{{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;
margin-bottom:12px;gap:12px}}
h1{{font-size:1.4rem;font-weight:700;color:#0f172a}}
.meta{{font-size:.8rem;color:#64748b}}
.legend{{display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.legend-item{{display:flex;align-items:center;gap:4px;font-size:.78rem}}
.legend-dot{{width:12px;height:12px;border-radius:3px}}
.req-panel{{background:#fff;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.06);
margin-bottom:14px;font-size:.85rem}}
.req-panel summary{{cursor:pointer;font-weight:700;color:#0f172a;padding:10px 16px;
list-style-position:inside}}
.req-row{{display:flex;gap:12px;padding:6px 16px;border-top:1px solid #f1f5f9}}
.req-label{{flex:0 0 84px;font-weight:600;color:#475569;font-size:.8rem}}
.req-value{{flex:1;color:#1e293b;white-space:pre-wrap}}
.stats-bar{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:10px 16px;
background:#fff;border-radius:8px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06);
font-size:.82rem}}
.stat-item b{{color:#0f172a}}
.stat-sep{{color:#cbd5e1;margin:0 2px}}
.stat-badge{{padding:2px 8px;border-radius:4px;font-size:.78rem;font-weight:500}}
.map-scroll{{overflow-x:auto;padding-bottom:16px}}
.map-inner{{min-width:{map_w}px}}
.map-row{{display:flex}}
.journey-cell{{color:#fff;font-weight:700;padding:10px 12px;border-radius:6px 6px 0 0;
margin-right:4px;text-align:center}}
.journey-name{{font-size:.92rem}}
.journey-count{{font-size:.7rem;font-weight:400;opacity:.85;margin-top:2px}}
.behavior-label{{font-size:.72rem;font-weight:700;color:#475569;background:#e2e8f0;
border-radius:4px;padding:2px 8px;margin:2px 0}}
.release-section{{margin-top:0}}
.release-divider{{position:relative;display:flex;align-items:center;margin:14px 0 8px}}
.release-line{{flex:1;height:2px;background:repeating-linear-gradient(
90deg,#94a3b8 0,#94a3b8 6px,transparent 6px,transparent 12px)}}
.release-badge{{position:absolute;left:0;background:#fff;padding:2px 14px;border-radius:12px;
font-size:.82rem;font-weight:700;color:#334155;border:2px solid #94a3b8;white-space:nowrap}}
.release-badge .rel-desc{{font-weight:400;color:#64748b;font-size:.78rem}}
.stories-row{{gap:4px}}
.story-col{{padding:4px 4px 8px;min-height:40px;display:flex;flex-direction:column;gap:6px}}
.story-card{{border-radius:6px;padding:0;cursor:pointer;transition:box-shadow .15s;
box-shadow:0 1px 2px rgba(0,0,0,.05)}}
.story-card:hover{{box-shadow:0 4px 12px rgba(0,0,0,.1)}}
.story-card summary{{display:flex;justify-content:space-between;align-items:center;gap:6px;
padding:8px 10px;list-style:none}}
.story-card summary::-webkit-details-marker{{display:none}}
.story-card summary::before{{content:"\\25B8";color:#94a3b8;font-size:.7rem;
flex:0 0 auto;transition:transform .12s}}
.story-card[open] summary::before{{transform:rotate(90deg)}}
.card-title{{font-size:.82rem;font-weight:600;color:#1e293b;flex:1}}
.card-pri{{font-size:.7rem;font-weight:600;flex:0 0 auto}}
.card-body{{padding:2px 10px 8px 22px;border-top:1px dashed #e2e8f0}}
.kv{{display:flex;gap:8px;padding:3px 0;font-size:.76rem}}
.kv .k{{flex:0 0 44px;font-weight:600;color:#64748b}}
.kv .v{{flex:1;color:#334155;white-space:pre-wrap}}
.empty-slot{{min-height:20px}}
.print-btn{{position:fixed;bottom:20px;right:20px;padding:8px 20px;background:#6366f1;color:#fff;
border:none;border-radius:8px;font-size:.85rem;cursor:pointer;box-shadow:0 2px 8px rgba(99,102,241,.3);
z-index:100}}
.print-btn:hover{{background:#4f46e5}}
@media print{{
  body{{background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .container{{padding:8px}}
  .print-btn{{display:none}}
  .map-scroll{{overflow:visible}}
  @page{{size:A3 landscape;margin:10mm}}
}}
</style>
</head>
<body>
<div class="container">
<header>
  <div>
    <h1>{req_name}</h1>
    <div class="meta">原始需求 &middot; 用户故事地图 &middot; 生成于 {now}</div>
  </div>
  <div class="legend">
    {"".join(
        f'<span class="legend-item"><span class="legend-dot" style="background:{PRIORITY_META[p]["color"]}"></span>{escape(PRIORITY_META[p]["label"])}</span>'
        for p in ("must", "should", "could", "wont"))}
  </div>
</header>
{_req_panel()}
<div class="stats-bar">
{_stats_html()}
</div>
<div class="map-scroll">
<div class="map-inner">
  <div class="map-row journey-row-wrap">{_journey_row()}</div>
  {_release_sections()}
</div>
</div>
</div>
<button class="print-btn" onclick="window.print()">&#128424; 打印</button>
</body>
</html>'''
    return html


def main():
    parser = argparse.ArgumentParser(description="用户故事地图 HTML 渲染器")
    parser.add_argument("--input", "-i", help="输入 JSON 文件路径（缺省从 stdin 读取）")
    parser.add_argument("--output", "-o", required=True, help="输出 HTML 文件路径")
    args = parser.parse_args()

    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"[错误] 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)

    errors = validate_data(data)
    if errors:
        for err in errors:
            print(f"[错误] {err}", file=sys.stderr)
        sys.exit(1)

    html = generate_html(data)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"地图已生成: {args.output}")


if __name__ == "__main__":
    main()
