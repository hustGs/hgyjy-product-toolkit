#!/usr/bin/env python3
"""hgyjy-user-journey: 用户旅程图状态文件增量更新器。

对话过程中 LLM 不直接改写 journey_map.json，而是产出结构化变更指令，
由本脚本统一校验并原子执行，保证状态文件始终合法。

用法:
    python3 update_journey.py --file journey_map.json --changes '[{"op":"add_stage","name":"认知"}]'
    echo '[...]' | python3 update_journey.py --file journey_map.json

所有变更一次性校验、一次性写盘；任何一条非法则整体拒绝。
"""

import argparse
import json
import sys

LIST_FIELDS = {"actions": "用户行动", "touchpoints": "触点",
               "thoughts": "想法/疑问", "pain_points": "痛点",
               "opportunities": "机会点"}

VALID_EMOTIONS = {-2, -1, 0, 1, 2}
EMOTION_LABELS = {-2: "非常消极", -1: "消极", 0: "中性", 1: "积极", 2: "非常积极"}
VALID_EVIDENCE = {"fact", "hypothesis"}
EVIDENCE_LABELS = {"fact": "事实", "hypothesis": "假设"}

JOURNEY_FIELDS = ("name", "persona", "scenario", "expectations")


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


def _find_stage(data, name):
    for s in data["stages"]:
        if s["name"] == name:
            return s
    raise OpError(f"阶段不存在: '{name}'")


def _check_list_field(field):
    if field not in LIST_FIELDS:
        raise OpError(f"列表字段非法: '{field}'，只能是: {', '.join(LIST_FIELDS)}")


def _list_op_target(stage, args):
    """返回 (目标列表, 字段中文名)。"""
    _req(args, "stage", "field")
    field = args["field"]
    _check_list_field(field)
    return stage.setdefault(field, []), LIST_FIELDS[field]


# ---------------- 操作实现 ----------------

def op_init(data, args, path, force):
    if data is not None and not force:
        raise OpError(f"{path} 已存在，如需重建请加 --force")
    name = _s(args.get("name"), "name")
    if not name:
        raise OpError("init 需要 name（旅程图名称）")
    data = {"journey": {k: (name if k == "name" else "") for k in JOURNEY_FIELDS},
            "stages": [], "moments": []}
    return data, f"初始化用户旅程「{name}」"


def op_set_journey(data, args):
    _req(args)
    changed = []
    for k in JOURNEY_FIELDS:
        if k in args:
            v = _s(args.get(k), k)
            if v is None:
                raise OpError(f"字段 '{k}' 不能为空")
            data["journey"][k] = v
            changed.append(k)
    if not changed:
        raise OpError("set_journey 未提供任何字段")
    label = {"name": "旅程名称", "persona": "角色", "scenario": "场景与目标",
             "expectations": "用户预期"}
    return data, "更新旅程信息: " + ", ".join(label[c] for c in changed)


def op_add_stage(data, args):
    _req(args, "name")
    name = _s(args["name"], "name")
    if any(s["name"] == name for s in data["stages"]):
        raise OpError(f"阶段重复: '{name}'")
    data["stages"].append({
        "name": name, "goal": _s(args.get("goal"), "goal") or "",
        "actions": [], "touchpoints": [], "thoughts": [],
        "emotion": None, "pain_points": [], "opportunities": [],
        "evidence": "fact",
    })
    return data, f"+ 阶段「{name}」"


def op_set_stage(data, args):
    _req(args, "stage")
    s = _find_stage(data, args["stage"])
    changed = []
    if "goal" in args:
        v = _s(args.get("goal"), "goal")
        if v is None:
            raise OpError("goal 不能为空")
        s["goal"] = v
        changed.append("目标")
    if "emotion" in args:
        v = args.get("emotion")
        if v is None:
            s["emotion"] = None
            changed.append("情绪(清空)")
        elif isinstance(v, int) and v in VALID_EMOTIONS:
            s["emotion"] = v
            changed.append(f"情绪({EMOTION_LABELS[v]})")
        else:
            raise OpError(f"情绪分非法: '{v}'，只能是 -2/-1/0/1/2 或 null")
    if "evidence" in args:
        v = _s(args.get("evidence"), "evidence")
        if v not in VALID_EVIDENCE:
            raise OpError(f"证据类型非法: '{v}'，只能是 fact/hypothesis")
        s["evidence"] = v
        changed.append(f"证据({EVIDENCE_LABELS[v]})")
    if not changed:
        raise OpError("set_stage 未提供任何字段")
    return data, f"~ 阶段「{s['name']}」更新: {', '.join(changed)}"


def op_rename(data, args):
    _req(args, "type", "stage", "new_name")
    if args["type"] != "stage":
        raise OpError("rename 目前只支持 type=stage")
    new_name = _s(args["new_name"], "new_name")
    s = _find_stage(data, args["stage"])
    old = s["name"]
    if any(x["name"] == new_name for x in data["stages"]):
        raise OpError(f"阶段重复: '{new_name}'")
    s["name"] = new_name
    return data, f"~ 阶段「{old}」→「{new_name}」"


def op_delete(data, args):
    _req(args, "type", "stage")
    if args["type"] != "stage":
        raise OpError("delete 目前只支持 type=stage")
    s = _find_stage(data, args["stage"])
    data["stages"].remove(s)
    return data, f"- 阶段「{s['name']}」"


def op_add_item(data, args):
    _req(args, "value")
    s = _find_stage(data, args["stage"])
    target, label = _list_op_target(s, args)
    value = _s(args["value"], "value")
    if value in target:
        raise OpError(f"阶段「{s['name']}」的{label}中已存在: '{value}'")
    target.append(value)
    return data, f"+ {label}「{value}」（阶段: {s['name']}）"


def op_set_item(data, args):
    _req(args, "index", "value")
    s = _find_stage(data, args["stage"])
    target, label = _list_op_target(s, args)
    idx = args["index"]
    if not isinstance(idx, int) or not (1 <= idx <= len(target)):
        raise OpError(f"序号非法: '{idx}'，{label}现有 {len(target)} 条（1-based）")
    value = _s(args["value"], "value")
    old = target[idx - 1]
    target[idx - 1] = value
    return data, f"~ 阶段「{s['name']}」{label}第 {idx} 条: 「{old}」→「{value}」"


def op_remove_item(data, args):
    _req(args, "index")
    s = _find_stage(data, args["stage"])
    target, label = _list_op_target(s, args)
    idx = args["index"]
    if not isinstance(idx, int) or not (1 <= idx <= len(target)):
        raise OpError(f"序号非法: '{idx}'，{label}现有 {len(target)} 条（1-based）")
    old = target.pop(idx - 1)
    return data, f"- {label}「{old}」（阶段: {s['name']}）"


def op_add_moment(data, args):
    _req(args, "value")
    value = _s(args["value"], "value")
    if value in data["moments"]:
        raise OpError(f"关键时刻已存在: '{value}'")
    data["moments"].append(value)
    return data, f"+ 关键时刻「{value}」"


def op_remove_moment(data, args):
    _req(args, "index")
    idx = args["index"]
    if not isinstance(idx, int) or not (1 <= idx <= len(data["moments"])):
        raise OpError(f"序号非法: '{idx}'，关键时刻现有 {len(data['moments'])} 条（1-based）")
    old = data["moments"].pop(idx - 1)
    return data, f"- 关键时刻「{old}」"


DISPATCH = {
    "set_journey": op_set_journey,
    "add_stage": op_add_stage,
    "set_stage": op_set_stage,
    "rename": op_rename,
    "delete": op_delete,
    "add_item": op_add_item,
    "set_item": op_set_item,
    "remove_item": op_remove_item,
    "add_moment": op_add_moment,
    "remove_moment": op_remove_moment,
}


def main():
    ap = argparse.ArgumentParser(description="用户旅程图状态文件增量更新器")
    ap.add_argument("--file", default="journey_map.json", help="状态文件路径")
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
