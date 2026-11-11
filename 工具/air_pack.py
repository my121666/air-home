#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""air_pack —— 把一个 `.air` 打成包（带清单与校验和）。

    python tools/air_pack.py 示例/阿柚
    python tools/air_pack.py 示例/阿柚 -o D:/备份/阿柚.airpack

产出：
    <名字>.airpack      zip 包，里面多一份 manifest.json
    manifest.json 记：每个文件的路径 / 大小 / sha256，以及摘要大小这类硬指标

不打进去：keys.env、__pycache__、*.pyc、.git —— 那些不是"她"。
"""
import argparse
import hashlib
import json
import os
import sys
import time
import zipfile

SKIP_DIRS = {".git", "__pycache__", ".idea", ".vscode"}
SKIP_FILES = {"keys.env", ".env", "manifest.json"}
MAX_DIGEST_WARN = 2048          # 摘要硬指标：超过小模型会被压死


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(root):
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES or fn.endswith(".pyc"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            items.append({
                "path": rel,
                "size": os.path.getsize(p),
                "sha256": sha256_of(p),
            })
    items.sort(key=lambda x: x["path"])
    return items


def find_manifest_entry(items):
    for name in ("air.yaml", "home.yaml"):
        for it in items:
            if it["path"] == name:
                return name, it
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("home", help="要打包的 .air 目录")
    ap.add_argument("-o", "--out", default=None, help="输出文件名（默认同名 .airpack）")
    args = ap.parse_args()

    root = os.path.abspath(args.home)
    if not os.path.isdir(root):
        print("不是目录:", root)
        return 2

    yaml_name, yaml_item = find_manifest_entry(collect(root))
    if not yaml_name:
        print("❌ 这个目录里没有 air.yaml（也没有 home.yaml）——不像一个 AIR")
        return 1

    items = collect(root)
    digest = next((it for it in items if it["path"] == "记忆/digest.md"), None)
    manifest = {
        "format": "air/0",
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": os.path.basename(root),
        "entry": yaml_name,
        "count": len(items),
        "total_bytes": sum(it["size"] for it in items),
        "digest_bytes": digest["size"] if digest else 0,
        "files": items,
    }

    out = args.out or (root.rstrip("\\/") + ".airpack")
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for it in items:
            z.write(os.path.join(root, it["path"]), it["path"])

    print("✅ 打好：%s" % out)
    print("   文件 %d 个 · 共 %.1f KB · 包体 %.1f KB"
          % (manifest["count"], manifest["total_bytes"] / 1024, os.path.getsize(out) / 1024))
    if manifest["digest_bytes"] > MAX_DIGEST_WARN:
        print("   ⚠️ 摘要 %.1f KB，超过 2 KB —— 小模型（≤8B）会记不住，建议精简"
              % (manifest["digest_bytes"] / 1024))
    else:
        print("   摘要 %.1f KB（安全）" % (manifest["digest_bytes"] / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
