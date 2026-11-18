#!/usr/bin/env python3
"""hgyjy-user-story: 用户故事地图状态文件增量更新器。

对话过程中 LLM 不直接改写 story_map.json，而是产出结构化变更指令，
由本脚本统一校验并原子执行，保证状态文件始终合法。

用法:
    python3 update_map.py --file story_map.json --changes '[{"op":"add_journey","name":"..."}]'
    echo '[...]' | python3 update_map.py --file story_map.json

所有变更一次性校验、一次性写盘；任何一条非法则整体拒绝。
"""

import argparse
import json
import sys

VALID_PRIORITIES = {"must", "should", "could", "wont"}

REQUIREMENT_FIELDS = ("name", "source", "scenario", "pain_points",
                      "goals", "solution", "value", "dod")

FEATURE_FIELDS = ("name", "who", "what", "when", "why", "dod",
                  "priority", "release", "description")


class OpError(Exception):
    pass


def _s(v, field):
    if v is None:
        return None
    if not isinstance(v, str):
        raise OpError(f"字段 '{field}' 必须是字符串")
    v = v.strip()
    return v if v else None


def _req(data, *fields):
    missing = [f for f in fields if not data.get(f)]
    if missing:
        raise OpError(f"缺少必填参数: {', '.join(missing)}")


def _load(path, must_exist=True):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if must_exist:
            raise OpError(f"状态文件不存在: {path}（先用 op=init 创建）")
        return None
    except json.JSONDecodeError as e:
        raise OpError(f"状态文件不是合法 JSON: {e}")


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _find_journey(data, name):
    for j in data["journeys"]:
        if j["name"] == name:
            return j
    raise OpError(f"旅程步骤不存在: '{name}'")


def _all_features(journey):
    """旅程下全部功能特性：直接挂载的 + 各用户行为下的。"""
    feats = list(journey.get("features", []))
    for b in journey.get("behaviors", []):
        feats.extend(b.get("features", []))
    return feats


def _find_behavior(journey, name):
    for b in journey.get("behaviors", []):
        if b["name"] == name:
            return b
    raise OpError(f"用户行为不存在: '{name}'（旅程: {journey['name']}）")


def _find_feature(journey, name):
    for ft in _all_features(journey):
        if ft["name"] == name:
            return ft
    raise OpError(f"功能特性不存在: '{name}'（旅程: {journey['name']}）")


def _check_release(data, release):
    if release is None:
        return
    names = [r["name"] for r in data["releases"]]
    if release not in names:
        raise OpError(f"版本 '{release}' 未定义，已有版本: {names or '（无）'}")


def _check_priority(priority):
    if priority not in (None, "") and priority not in VALID_PRIORITIES:
        raise OpError(f"优先级 '{priority}' 非法，只能是: must/should/could/wont")


# ---------------- 操作实现 ----------------

def op_init(data, args, path, force):
    if data is not None and not force:
        raise OpError(f"{path} 已存在，如需重建请加 --force")
    name = _s(args.get("name"), "name")
    if not name:
        raise OpError("init 需要 name（原始需求名称）")
    data = {
        "requirement": {k: (name if k == "name" else "") for k in REQUIREMENT_FIELDS},
        "releases": [],
        "journeys": [],
    }
    for r in args.get("releases") or []:
        rn = _s(r.get("name"), "releases[].name")
        if not rn:
            raise OpError("releases[].name 不能为空")
        if any(x["name"] == rn for x in data["releases"]):
            raise OpError(f"版本重复: '{rn}'")
        data["releases"].append({"name": rn,
                                 "description": _s(r.get("description"), "description") or ""})
    return data, f"初始化原始需求「{name}」"


def op_set_requirement(data, args):
    _req(args)
    changed = []
    for k in REQUIREMENT_FIELDS:
        if k in args:
            v = _s(args.get(k), k)
            if v is None:
                raise OpError(f"字段 '{k}' 不能为空（如需清空请直接编辑会话）")
            data["requirement"][k] = v
            changed.append(k)
    if not changed:
        raise OpError("set_requirement 未提供任何字段")
    label = {"name": "需求名称", "source": "需求来源", "scenario": "业务场景",
             "pain_points": "现状痛点", "goals": "期望目标", "solution": "方案",
             "value": "价值", "dod": "DoD"}
    return data, "更新原始需求字段: " + ", ".join(label[c] for c in changed)


def op_add_release(data, args):
    _req(args, "name")
    name = _s(args["name"], "name")
    if any(r["name"] == name for r in data["releases"]):
        raise OpError(f"版本已存在: '{name}'")
    data["releases"].append({"name": name,
                             "description": _s(args.get("description"), "description") or ""})
    return data, f"+ 版本「{name}」"


def op_add_journey(data, args):
    _req(args, "name")
    name = _s(args["name"], "name")
    if any(j["name"] == name for j in data["journeys"]):
        raise OpError(f"旅程步骤重复: '{name}'")
    data["journeys"].append({"name": name, "features": [], "behaviors": []})
    return data, f"+ 旅程步骤「{name}」"


def op_add_behavior(data, args):
    _req(args, "journey", "name")
    j = _find_journey(data, args["journey"])
    name = _s(args["name"], "name")
    behaviors = j.setdefault("behaviors", [])
    if any(b["name"] == name for b in behaviors):
        raise OpError(f"用户行为重复: '{name}'（旅程: {j['name']}）")
    behaviors.append({"name": name, "features": []})
    return data, f"+ 用户行为「{name}」（旅程: {j['name']}）"


def op_rename(data, args):
    _req(args, "type", "new_name")
    new_name = _s(args["new_name"], "new_name")
    t = args["type"]
    if t == "journey":
        _req(args, "journey")
        j = _find_journey(data, args["journey"])
        old = j["name"]
        if any(x["name"] == new_name for x in data["journeys"]):
            raise OpError(f"旅程步骤重复: '{new_name}'")
        j["name"] = new_name
        return data, f"~ 旅程步骤「{old}」→「{new_name}」"
    if t == "behavior":
        _req(args, "journey", "behavior")
        j = _find_journey(data, args["journey"])
        b = _find_behavior(j, args["behavior"])
        old = b["name"]
        if any(x["name"] == new_name for x in j.get("behaviors", [])):
            raise OpError(f"用户行为重复: '{new_name}'（旅程: {j['name']}）")
        b["name"] = new_name
        return data, f"~ 用户行为「{old}」→「{new_name}」"
    if t == "feature":
        _req(args, "journey", "feature")
        j = _find_journey(data, args["journey"])
        ft = _find_feature(j, args["feature"])
        old = ft["name"]
        if any(x["name"] == new_name for x in _all_features(j)):
            raise OpError(f"功能特性重复: '{new_name}'（旅程: {j['name']}）")
        ft["name"] = new_name
        return data, f"~ 功能特性「{old}」→「{new_name}」"
    raise OpError(f"type 只能是 journey/behavior/feature，收到: '{t}'")


def op_delete(data, args):
    _req(args, "type")
    t = args["type"]
    if t == "journey":
        _req(args, "journey")
        j = _find_journey(data, args["journey"])
        n = len(_all_features(j))
        data["journeys"].remove(j)
        return data, f"- 旅程步骤「{j['name']}」（含 {n} 个功能特性）"
    if t == "behavior":
        _req(args, "journey", "behavior")
        j = _find_journey(data, args["journey"])
        b = _find_behavior(j, args["behavior"])
        n = len(b["features"])
        j["behaviors"].remove(b)
        return data, f"- 用户行为「{b['name']}」（旅程: {j['name']}，含 {n} 个功能特性）"
    if t == "feature":
        _req(args, "journey", "feature")
        j = _find_journey(data, args["journey"])
        ft = _find_feature(j, args["feature"])
        for container in [j.get("features", [])] + [b["features"] for b in j.get("behaviors", [])]:
            if ft in container:
                container.remove(ft)
                break
        return data, f"- 功能特性「{ft['name']}」（旅程: {j['name']}）"
    raise OpError(f"type 只能是 journey/behavior/feature，收到: '{t}'")


def op_add_feature(data, args):
    _req(args, "journey", "name")
    j = _find_journey(data, args["journey"])
    name = _s(args["name"], "name")
    if any(x["name"] == name for x in _all_features(j)):
        raise OpError(f"功能特性重复: '{name}'（旅程: {j['name']}）")
    behavior = _s(args.get("behavior"), "behavior")
    if behavior:
        target = _find_behavior(j, behavior)["features"]
    else:
        target = j.setdefault("features", [])
    ft = {k: "" for k in FEATURE_FIELDS}
    ft["name"] = name
    for k in ("who", "when", "why", "dod", "description"):
        ft[k] = _s(args.get(k), k) or ""
    ft["what"] = _s(args.get("what"), "what") or ft["name"]
    ft["priority"] = _s(args.get("priority"), "priority") or ""
    _check_priority(ft["priority"])
    ft["release"] = _s(args.get("release"), "release")
    _check_release(data, ft["release"])
    target.append(ft)
    tags = []
    if behavior:
        tags.append(f"行为: {behavior}")
    if ft["priority"]:
        tags.append(ft["priority"])
    if ft["release"]:
        tags.append(ft["release"])
    return data, f"+ 功能特性「{name}」（旅程: {j['name']}" + (", " + ", ".join(tags) if tags else "") + "）"


def op_set_feature(data, args):
    _req(args, "journey", "feature")
    j = _find_journey(data, args["journey"])
    ft = _find_feature(j, args["feature"])
    changed = []
    for k in ("who", "when", "why", "dod", "description", "what"):
        if k in args:
            v = _s(args.get(k), k)
            if v is None:
                raise OpError(f"字段 '{k}' 不能为空")
            ft[k] = v
            changed.append(k)
    if "priority" in args:
        v = _s(args.get("priority"), "priority")
        _check_priority(v)
        ft["priority"] = v
        changed.append("priority")
    if "release" in args:
        v = _s(args.get("release"), "release")
        _check_release(data, v)
        ft["release"] = v
        changed.append("release")
    if not changed:
        raise OpError("set_feature 未提供任何字段")
    return data, f"~ 功能特性「{ft['name']}」更新字段: {', '.join(changed)}"


DISPATCH = {
    "set_requirement": op_set_requirement,
    "add_release": op_add_release,
    "add_journey": op_add_journey,
    "add_behavior": op_add_behavior,
    "rename": op_rename,
    "delete": op_delete,
    "add_feature": op_add_feature,
    "set_feature": op_set_feature,
}


def main():
    ap = argparse.ArgumentParser(description="用户故事地图状态文件增量更新器")
    ap.add_argument("--file", default="story_map.json", help="状态文件路径")
    ap.add_argument("--changes", help="变更指令 JSON 数组（缺省从 stdin 读取）")
    ap.add_argument("--force", action="store_true", help="init 时允许覆盖已存在文件")
    args = ap.parse_args()

    raw = args.changes if args.changes else sys.stdin.read()
    try:
        changes = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[错误] 变更指令不是合法 JSON: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(changes, list) or not changes:
        print("[错误] 变更指令必须是非空 JSON 数组", file=sys.stderr)
        sys.exit(1)

    try:
        data = _load(args.file, must_exist=not (changes[0].get("op") == "init"))
        summaries = []
        for i, ch in enumerate(changes):
            if not isinstance(ch, dict) or not ch.get("op"):
                raise OpError(f"第 {i+1} 条指令缺少 op 字段")
            op = ch["op"]
            if op == "init":
                if i != 0 or len(changes) > 1:
                    raise OpError("init 必须单独作为唯一一条指令")
                data, summary = op_init(data, ch, args.file, args.force)
            else:
                if data is None:
                    raise OpError(f"状态文件不存在: {args.file}")
                fn = DISPATCH.get(op)
                if not fn:
                    raise OpError(f"未知 op: '{op}'，支持: init/{'/'.join(DISPATCH)}")
                data, summary = fn(data, ch)
            summaries.append(summary)
        _save(args.file, data)
    except OpError as e:
        print(f"[错误] {e}", file=sys.stderr)
        sys.exit(1)

    print(f"已应用 {len(summaries)} 条变更 → {args.file}")
    for s in summaries:
        print(f"  {s}")


if __name__ == "__main__":
    main()
