#!/usr/bin/env python3
"""hgyjy-product-toolkit CI 校验。

检查项:
  1. kimi.plugin.json 可解析，name/version/description 合法
  2. version 为完整 x.y.z（可带 -rc.N 预发布后缀）
  3. interface 必填槽位齐全（displayName/shortDescription/longDescription/
     developerName/tryPrompts/brandColor/defaultLocale/locales/skillOverrides）
  4. defaultLocale 为 zh-CN 时 locales/en-US.json 存在且键位与 manifest 对齐
  5. skillOverrides 的键与 skills/ 下目录名一致
  6. 打 tag（v*）推送时：tag 去 v 后必须等于 manifest version

退出码非 0 即校验失败。
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")
REQUIRED_INTERFACE = ["displayName", "shortDescription", "longDescription",
                      "developerName", "tryPrompts", "brandColor",
                      "defaultLocale", "locales", "skillOverrides"]
LOCALE_KEYS = ["displayName", "shortDescription", "longDescription",
               "developerName", "tryPrompts", "skillOverrides"]

errors = []


def check(cond, msg):
    if not cond:
        errors.append(msg)


manifest_path = os.path.join(ROOT, "kimi.plugin.json")
try:
    with open(manifest_path, "r", encoding="utf-8") as f:
        m = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as ex:
    print(f"[FAIL] kimi.plugin.json 不可读: {ex}")
    sys.exit(1)

check(re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", m.get("name", "") or ""),
      f"name 非法: {m.get('name')}")
ver = m.get("version", "")
check(bool(SEMVER.match(ver or "")), f"version 必须是完整 x.y.z: '{ver}'")
check(bool(m.get("description")), "description 缺失")

iface = m.get("interface", {})
for k in REQUIRED_INTERFACE:
    check(k in iface, f"interface.{k} 缺失")
check(iface.get("defaultLocale") in ("zh-CN", "en-US"),
      f"defaultLocale 必须是 zh-CN/en-US: {iface.get('defaultLocale')}")
check(isinstance(iface.get("tryPrompts"), list) and 1 <= len(iface.get("tryPrompts", [])) <= 3,
      "tryPrompts 需 1-3 条")
check(len(iface.get("shortDescription", "")) <= 20,
      f"shortDescription 超 20 字符: {iface.get('shortDescription')}")
check(len(iface.get("longDescription", "")) <= 500,
      "longDescription 超 500 字符")

other = "en-US.json" if iface.get("defaultLocale") == "zh-CN" else "zh-CN.json"
locale_path = os.path.join(ROOT, "locales", other)
try:
    with open(locale_path, "r", encoding="utf-8") as f:
        loc = json.load(f)
    for k in LOCALE_KEYS:
        check(k in loc, f"locales/{other} 缺键: {k}")
except FileNotFoundError:
    errors.append(f"locales/{other} 缺失")

skills_dir = os.path.join(ROOT, "skills")
skill_names = sorted(d for d in os.listdir(skills_dir)
                     if os.path.isdir(os.path.join(skills_dir, d))) if os.path.isdir(skills_dir) else []
check(bool(skill_names), "skills/ 下没有任何 skill")
overrides = set((iface.get("skillOverrides") or {}).keys())
check(overrides == set(skill_names),
      f"skillOverrides 键 ({sorted(overrides)}) 与 skills/ 目录 ({skill_names}) 不一致")
for s in skill_names:
    check(os.path.isfile(os.path.join(skills_dir, s, "SKILL.md")),
          f"skills/{s}/SKILL.md 缺失")

tag = os.environ.get("CI_COMMIT_TAG", "")
if tag:
    check(tag.startswith("v"), f"tag 须以 v 开头: {tag}")
    check(tag[1:] == ver, f"tag {tag} 与 manifest version {ver} 不一致")

if errors:
    print("[FAIL] 校验未通过：")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
print(f"[OK] 校验通过: {m['name']} v{ver}, skills: {', '.join(skill_names)}")
