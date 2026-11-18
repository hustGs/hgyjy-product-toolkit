#!/usr/bin/env python3
"""hgyjy-user-story: 从 hgyjy-user-journey 的旅程图输出导入草稿。

读取 journey_map.json（用户旅程图状态文件），生成一份**草稿**变更指令
JSON 数组，供人工/LLM 审阅修订后交给 update_map.py 执行。不直接改状态。

映射规则:
  journey.persona + scenario   → requirement.scenario（带【旅程图】出处标注）
  各阶段 pain_points 汇总      → requirement.pain_points
  journey.expectations         → requirement.goals
  阶段名序列                    → add_journey 骨干草稿（名词短语，建议改动词短语）
  阶段 opportunities[]          → add_feature 草稿（what=机会点原文，why=同阶段痛点）
  阶段 emotion <= -1            → 对应特性草稿建议 priority=must（可在审阅时推翻）
  阶段 evidence==hypothesis     → 特性 description 标注「源自假设阶段·待验证」

用法:
  python3 import_journey.py --journey journey_map.json \
      [--story story_map.json] [--output draft_ops.json]

  # 审阅修订后应用
  python3 update_map.py --file story_map.json --changes "$(cat draft_ops.json)"
"""

import argparse
import json
import os
import subprocess
import sys

UPDATE_MAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_map.py")

EMOTION_MUST_THRESHOLD = -1
NAME_MAX = 24


def _short(text, used):
    """特性名：截断到 NAME_MAX，保证同一旅程内唯一。"""
    name = text if len(text) <= NAME_MAX else text[:NAME_MAX] + "…"
    if name not in used:
        used.add(name)
        return name
    i = 2
    while f"{name}({i})" in used:
        i += 1
    name = f"{name}({i})"
    used.add(name)
    return name


def main():
    ap = argparse.ArgumentParser(description="从旅程图导入故事地图草稿")
    ap.add_argument("--journey", required=True, help="journey_map.json 路径")
    ap.add_argument("--story", default="story_map.json",
                    help="目标 story_map.json（缺省 ./story_map.json，不存在则自动 init）")
    ap.add_argument("--output", help="草稿指令输出路径（缺省打印到 stdout）")
    args = ap.parse_args()

    try:
        with open(args.journey, "r", encoding="utf-8") as f:
            jmap = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as ex:
        print(f"[错误] 无法读取旅程图: {ex}", file=sys.stderr)
        sys.exit(1)

    journey = jmap.get("journey", {})
    stages = jmap.get("stages", [])
    if not journey.get("name") or not isinstance(stages, list):
        print("[错误] journey_map.json 结构不完整（缺少 journey.name 或 stages）", file=sys.stderr)
        sys.exit(1)

    # 目标故事地图：不存在则用 update_map.py 现场 init（仍走脚本，不直接写 JSON）
    if not os.path.exists(args.story):
        r = subprocess.run([sys.executable, UPDATE_MAP, "--file", args.story,
                            "--changes", json.dumps([{"op": "init", "name": journey["name"]}],
                                                    ensure_ascii=False)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr.strip() or r.stdout.strip(), file=sys.stderr)
            sys.exit(1)
        print(f"已初始化故事地图: {args.story}", file=sys.stderr)

    try:
        with open(args.story, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except json.JSONDecodeError as ex:
        print(f"[错误] 故事地图不是合法 JSON: {ex}", file=sys.stderr)
        sys.exit(1)

    ops = []
    notes = []       # 审阅提示
    warnings = []    # 假设/待验证清单

    pains = []
    for s in stages:
        for p in s.get("pain_points", []):
            if p not in pains:
                pains.append(p)

    req = {}
    if not (existing or {}).get("requirement", {}).get("scenario"):
        req["scenario"] = (f"【源自旅程图《{journey['name']}》】角色：{journey.get('persona', '')}。"
                           f"场景：{journey.get('scenario', '')}")
    if pains and not (existing or {}).get("requirement", {}).get("pain_points"):
        req["pain_points"] = "；".join(f"（{s['name']}）{p}" for s in stages
                                       for p in s.get("pain_points", []))
    if not (existing or {}).get("requirement", {}).get("goals"):
        req["goals"] = journey.get("expectations", "")
    if not (existing or {}).get("requirement", {}).get("source"):
        req["source"] = "hgyjy-user-journey 用户旅程图分析输出"

    if req:
        op = {"op": "set_requirement"}
        op.update(req)
        ops.append(op)

    existing_journeys = ({j["name"] for j in existing.get("journeys", [])}
                         if existing else set())
    for s in stages:
        if s["name"] in existing_journeys:
            continue
        ops.append({"op": "add_journey", "name": s["name"]})
        note = f"旅程步骤「{s['name']}」源自旅程图阶段（名词短语，建议改动词短语）"
        if s.get("goal"):
            note += f"，原阶段目标: {s['goal']}"
        notes.append(note)

    def _journey_features(jname):
        """返回该旅程已有特性的 (名称集合, what 原文集合)。"""
        names, whats = set(), set()
        if existing:
            for j in existing.get("journeys", []):
                if j["name"] != jname:
                    continue
                pool = list(j.get("features", []))
                for b in j.get("behaviors", []):
                    pool.extend(b.get("features", []))
                names = {f["name"] for f in pool}
                whats = {f.get("what") for f in pool}
        return names, whats

    for s in stages:
        hypo = s.get("evidence") == "hypothesis"
        stage_pains = s.get("pain_points", [])
        why = "；".join(stage_pains)
        suggest_must = (s.get("emotion") is not None
                        and s.get("emotion") <= EMOTION_MUST_THRESHOLD)
        used, existing_whats = _journey_features(s["name"])
        for opp_text in s.get("opportunities", []):
            if opp_text in existing_whats:
                continue
            name = _short(opp_text, used)
            desc = ""
            if hypo:
                desc = "【源自旅程图假设阶段·内容待验证】"
                warnings.append(f"「{name}」（{s['name']}）来自假设阶段")
            ft = {"op": "add_feature", "journey": s["name"], "name": name,
                  "what": opp_text, "why": why, "description": desc}
            if suggest_must:
                ft["priority"] = "must"
                notes.append(f"「{name}」已按情绪低谷（{s['emotion']}）预填 must，可推翻")
            ops.append(ft)

    out = ops
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"草稿已写出 {args.output}（{len(ops)} 条指令）", file=sys.stderr)
    else:
        print(text)

    print(f"\n===== 导入摘要（{len(ops)} 条草稿指令）=====", file=sys.stderr)
    for n in notes:
        print(f"  [审阅] {n}", file=sys.stderr)
    if warnings:
        print(f"  --- 待验证（{len(warnings)} 条，来自假设阶段）---", file=sys.stderr)
        for w in warnings:
            print(f"  [待验证] {w}", file=sys.stderr)
    print("审阅修订后执行: python3 update_map.py --file story_map.json "
          "--changes \"$(cat 草稿.json)\"", file=sys.stderr)


if __name__ == "__main__":
    main()
