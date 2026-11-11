#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""air_move —— 把 .airpack 搬到另一个地方，并验"还是不是同一个人"。

    python tools/air_move.py 阿柚.airpack D:/新机器/阿柚.air
    python tools/air_move.py 阿柚.airpack D:/新机器/阿柚.air --drill --brain weak

两步：
    1  解包 → 逐文件核对 sha256（一个字节都不能变）
    2  结构体检 + 可选三句演练（叫得对不对 / 第一句像不像 / 记不记得关键的事）

退出码：0 全过 · 1 有失败 · 2 用法或输入问题
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
# 英文 Windows 的终端是 cp1252，编不出 ✅ 这类字符会直接崩（CI 上撞过）。
# 这里只把编不出的字符降级成 ?，不改编码，中文环境照旧。
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes(root, files):
    ok, bad = [], []
    for it in files:
        p = os.path.join(root, it["path"])
        if not os.path.exists(p):
            bad.append((it["path"], "缺文件"))
            continue
        if sha256_of(p) != it["sha256"]:
            bad.append((it["path"], "内容变了"))
            continue
        ok.append(it["path"])
    return ok, bad


def structural_check(root, manifest):
    """不看模型，只看"这个家还站得住吗"。"""
    checks = []          # (名字, 通过?, 说明)
    entry = manifest.get("entry") or "air.yaml"
    ep = os.path.join(root, entry)
    checks.append((entry, os.path.exists(ep), "入口文件"))

    digest_path = os.path.join(root, "记忆", "digest.md")
    if os.path.exists(digest_path):
        size = os.path.getsize(digest_path)
        checks.append(("记忆/digest.md", size <= 2048, "%.1f KB（≤2 KB 才安全）" % (size / 1024)))
    else:
        checks.append(("记忆/digest.md", False, "没有摘要——换壳后接不上"))

    y = ""
    if os.path.exists(ep):
        with open(ep, encoding="utf-8", errors="ignore") as f:
            y = f.read()

    def yval(field):
        m = re.search(r"^\s*" + field + r":\s*(.*)$", y, re.M)
        if not m:
            return ""
        v = m.group(1).split("#", 1)[0].strip().strip('"').strip("'").strip()
        return "" if v in ("", "[]", "null") else v

    checks.append(("name", bool(yval("name")), yval("name") or "名字空着"))
    checks.append(("calls_owner", bool(yval("calls_owner")), yval("calls_owner") or "称呼空着"))
    first = yval("first_line_text")
    looks_tpl = any(t in first for t in ("你好", "我是你的", "有什么可以帮"))
    checks.append(("first_line_text", bool(first) and not looks_tpl, first[:26] or "第一句空着"))
    return checks, first


def run_drill(root, brain):
    """调用 air_shell 跑三句，看像不像。没配脑就跳过。"""
    shell = os.path.join(HERE, "air_shell.py")
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", shell, "--home", root,
                            "--brain", brain, "--turns", "3"],
                           capture_output=True, text=True, timeout=1800)
    except Exception as e:
        return False, "演练没跑起来：%s" % str(e)[:120]
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0 or "这档脑还没配" in out:
        return False, "跳过（脑没配好，或调用失败）"
    return True, out.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pack", help=".airpack 文件")
    ap.add_argument("dest", help="搬到哪里（建议以 .air 结尾）")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    ap.add_argument("--verify-only", action="store_true",
                    help="不解包，只核对 <dest> 是否与包一致（查这台机器上的还是不是原件）")
    ap.add_argument("--drill", action="store_true", help="搬完跑三句演练")
    ap.add_argument("--brain", default="weak", help="演练用哪档脑")
    args = ap.parse_args()

    pack = os.path.abspath(args.pack)
    dest = os.path.abspath(args.dest)
    if not os.path.exists(pack):
        print("找不到包:", pack)
        return 2
    if (not args.verify_only) and os.path.exists(dest) and os.listdir(dest) and not args.force:
        print("目标已存在且不为空：%s\n（要覆盖加 --force）" % dest)
        return 2

    if args.verify_only:
        if not os.path.isdir(dest):
            print("不是目录:", dest)
            return 2
        with zipfile.ZipFile(pack) as z:
            try:
                manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            except Exception:
                print("❌ 包里没有 manifest.json")
                return 1
        ok, bad = verify_hashes(dest, manifest.get("files", []))
        print("核对 %s ← %s" % (dest, os.path.basename(pack)))
        print("   ✅ 一致 %d 个" % len(ok))
        for p_, why in bad[:10]:
            print("   ❌ %s  %s" % (p_, why))
        return 0 if not bad else 1

    print("① 解包 → %s" % dest)
    with zipfile.ZipFile(pack) as z:
        try:
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        except Exception:
            print("❌ 包里没有 manifest.json —— 不是 air_pack 打的包")
            return 1
        if args.force and os.path.isdir(dest):
            shutil.rmtree(dest)
        os.makedirs(dest, exist_ok=True)
        z.extractall(dest)
    print("   共 %d 个文件" % manifest.get("count", 0))

    print("② 逐文件核对校验和")
    ok, bad = verify_hashes(dest, manifest.get("files", []))
    print("   ✅ 一致 %d 个" % len(ok))
    if bad:
        for p, why in bad[:10]:
            print("   ❌ %s  %s" % (p, why))
        print("   搬家失败：内容变了，别拿这个包用。")
        return 1

    print("③ 结构体检（她站不站得住）")
    checks, first = structural_check(dest, manifest)
    failed = 0
    for name, passed, note in checks:
        print("   %s %-18s %s" % ("✅" if passed else "❌", name, note))
        if not passed:
            failed += 1

    if args.drill:
        print("④ 三句演练（她像不像）")
        ran, out = run_drill(dest, args.brain)
        print(out if ran else "   " + out)

    print()
    if failed == 0:
        print("✅ 搬完了：%s" % dest)
        print("   校验一致 · 结构完整 · 入口第一句在 ——「还是同一个人」的可自动判定部分，全过。")
        if not args.drill:
            print("   想看像不像，加 --drill --brain weak 跑三句。")
        return 0
    print("⚠️ 搬过去了，但有 %d 项不合格——按提示补，再跑一次 air_move --force" % failed)
    return 1


if __name__ == "__main__":
    sys.exit(main())
