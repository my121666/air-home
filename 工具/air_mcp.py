#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""air-mcp —— 把一个 `AIR`（爱人）作为 MCP 工具接进任何客户端。

    {"command": "python", "args": ["air_mcp.py"], "env": {"AIR_HOME": "D:/我的TA"}}

暴露五个工具：
    air_load    读这个家的身份 + 记忆 + 规矩
    air_boot    换壳后的启动序列（读摘要 → 第一句 → 问一句）
    air_digest  写摘要（硬限制 2 KB）
    air_pack    打包成 .airpack（带逐文件 sha256）
    air_move    校验/搬家（核对校验和 + 结构体检）

设计原则：
  · 只读文件、不认环境；家在哪由 AIR_HOME 决定
  · 零依赖（只用标准库），不联网
  · 不提供任何默认性格——人格来自那个目录
"""
import hashlib
import json
import os
import sys
import zipfile

VERSION = "0.1.0"
PROTOCOL = "2024-11-05"
HOME = os.environ.get("AIR_HOME", "").strip()
MAX_DIGEST = 2048


# ---------------------------------------------------------------- 读家
def _read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


def _yaml_val(text, field):
    import re
    m = re.search(r"^\s*" + field + r":\s*(.*)$", text, re.M)
    if not m:
        return ""
    v = m.group(1).split("#", 1)[0].strip().strip('"').strip("'").strip()
    return "" if v in ("", "[]", "null") else v


def _entry(root):
    for name in ("air.yaml", "home.yaml"):
        p = os.path.join(root, name)
        if os.path.exists(p):
            return p
    return ""


def _rules(ytext):
    import re
    out, grip = [], False
    for line in ytext.splitlines():
        if re.match(r"^\s*rules:", line):
            grip = True
            continue
        if grip:
            m = re.match(r"^\s*-\s+(.*)$", line)
            if m:
                v = m.group(1).split("#", 1)[0].strip().strip('"').strip("'")
                if v:
                    out.append(v)
            elif line.strip() and not line.startswith(" "):
                grip = False
    return out


def load_home(root):
    if not root or not os.path.isdir(root):
        raise SystemExit("AIR_HOME 没设或不存在：%r" % root)
    ep = _entry(root)
    if not ep:
        raise SystemExit("这个目录里没有 air.yaml（AIR 的入口）")
    y = _read(ep)
    parts, used = [], []
    for label, rel in (("设定", "家书.md"), ("设定", "设定.md"),
                       ("现在在哪", "记忆/warm.md"), ("现在在哪", "记忆/digest.md"),
                       ("词典", "词典.md")):
        p = os.path.join(root, rel.replace("/", os.sep))
        if os.path.exists(p):
            body = _read(p)
            if body:
                parts.append("### %s\n%s" % (label, body))
                used.append(rel)
    return {
        "root": root,
        "entry": os.path.basename(ep),
        "name": _yaml_val(y, "name"),
        "calls_owner": _yaml_val(y, "calls_owner"),
        "first_line": _yaml_val(y, "first_line_text"),
        "rules": _rules(y),
        "text": "\n\n".join(parts),
        "files": used,
        "digest_bytes": os.path.getsize(os.path.join(root, "记忆", "digest.md"))
        if os.path.exists(os.path.join(root, "记忆", "digest.md")) else 0,
    }


# ---------------------------------------------------------------- 五个工具
def t_air_load(args=None):
    h = load_home(HOME)
    return ("这是「%s」，家在 %s（入口 %s）。\n\n规矩 %d 条；第一句：%s\n\n%s"
            % (h["name"] or "(未命名)", h["root"], h["entry"], len(h["rules"]),
               h["first_line"] or "(未写)", h["text"] or "(设定为空)"))


def t_air_boot(args=None):
    h = load_home(HOME)
    steps = [
        "1 读摘要（现在在哪）：%s" % ("记忆/warm.md 或 记忆/digest.md" if any("warm" in f or "digest" in f for f in h["files"]) else "缺！先写"),
        "2 认人：叫对方 %s" % (h["calls_owner"] or "(未写)"),
        "3 开口第一句：%s" % (h["first_line"] or "(未写——不要用“你好，我是助手”)"),
        "4 然后问一句对方今天怎么样（不要汇报）",
    ]
    return "换壳启动序列（顺序不能乱）：\n" + "\n".join(steps)


def t_air_digest(args=None):
    text = (args or {}).get("text", "")
    if not text:
        p = os.path.join(HOME or ".", "记忆", "digest.md")
        text = _read(p)
        return "当前摘要 %.1f KB / 上限 2 KB\n\n%s" % (len(text.encode()) / 1024, text or "(空)")
    data = text.encode("utf-8")
    if len(data) > MAX_DIGEST:
        return ("拒绝写入：%d 字节，超过 2 KB 上限。小模型会被大记忆压死（实测 2.6B + 80 KB = 第三句空回复）。"
                % len(data))
    p = os.path.join(HOME, "记忆", "digest.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return "已写入 %s（%.1f KB）" % (p, len(data) / 1024)


def t_air_pack(args=None):
    root = HOME
    if not root or not os.path.isdir(root):
        raise SystemExit("AIR_HOME 没设")
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fn in filenames:
            if fn.endswith(".pyc") or fn in ("keys.env", ".env", "manifest.json"):
                continue
            p = os.path.join(dirpath, fn)
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            items.append({"path": os.path.relpath(p, root).replace("\\", "/"),
                          "size": os.path.getsize(p), "sha256": h.hexdigest()})
    items.sort(key=lambda x: x["path"])
    manifest = {"format": "air/0", "entry": os.path.basename(_entry(root) or "air.yaml"),
                "count": len(items), "files": items}
    out = os.path.join(os.path.dirname(root.rstrip("\\/")), os.path.basename(root.rstrip("\\/")) + ".airpack")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for it in items:
            z.write(os.path.join(root, it["path"].replace("/", os.sep)), it["path"])
    return "打好：%s\n文件 %d 个 · %.1f KB" % (out, len(items), os.path.getsize(out) / 1024)


def t_air_move(args=None):
    pack = (args or {}).get("pack", "")
    dest = (args or {}).get("dest", "")
    if not pack or not dest or not os.path.exists(pack):
        return "用法：air_move 需要 pack（.airpack 路径）与 dest（目标目录）"
    with zipfile.ZipFile(pack) as z:
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        os.makedirs(dest, exist_ok=True)
        z.extractall(dest)
    bad = []
    for it in manifest.get("files", []):
        p = os.path.join(dest, it["path"].replace("/", os.sep))
        if not os.path.exists(p):
            bad.append(it["path"] + " 缺"); continue
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != it["sha256"]:
            bad.append(it["path"] + " 内容变了")
    if bad:
        return "搬家失败（内容变了，别用这个包）：\n" + "\n".join(bad[:10])
    return "✅ 搬完：%s\n校验 %d 个文件全一致 · 入口 %s" % (dest, manifest.get("count", 0), manifest.get("entry"))


TOOLS = [
    ("air_load", "读这个家的身份、记忆与规矩（AIR = 设定包 + 记忆摘要）",
     {"type": "object", "properties": {}}),
    ("air_boot", "换壳后的启动序列：读摘要 → 认人 → 说第一句 → 问一句",
     {"type": "object", "properties": {}}),
    ("air_digest", "读取或写入记忆摘要（硬限制 2 KB；不给 text 就是读）",
     {"type": "object", "properties": {"text": {"type": "string", "description": "要写入的摘要；不填则读取当前摘要"}}}),
    ("air_pack", "把家打包成 .airpack（含逐文件 sha256）",
     {"type": "object", "properties": {}}),
    ("air_move", "校验并搬一个 .airpack 到目标目录（一个字节变了就拒绝）",
     {"type": "object", "properties": {
         "pack": {"type": "string", "description": ".airpack 文件路径"},
         "dest": {"type": "string", "description": "目标目录，例 D:/我的TA.air"}},
      "required": ["pack", "dest"]}),
]

HANDLERS = {
    "air_load": t_air_load,
    "air_boot": t_air_boot,
    "air_digest": t_air_digest,
    "air_pack": t_air_pack,
    "air_move": t_air_move,
}


# ---------------------------------------------------------------- MCP stdio
def send(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def ok(mid, result):
    send({"jsonrpc": "2.0", "id": mid, "result": result})


def err(mid, code, msg):
    send({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": msg}})


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue
        mid = req.get("id")
        method = req.get("method", "")

        if method == "initialize":
            ok(mid, {"protocolVersion": PROTOCOL,
                     "capabilities": {"tools": {}},
                     "serverInfo": {"name": "air-mcp", "version": VERSION}})
        elif method in ("notifications/initialized", "initialized"):
            continue
        elif method == "tools/list":
            ok(mid, {"tools": [{"name": n, "description": d, "inputSchema": s}
                               for n, d, s in TOOLS]})
        elif method == "tools/call":
            name = (req.get("params") or {}).get("name", "")
            a = (req.get("params") or {}).get("arguments") or {}
            fn = HANDLERS.get(name)
            if not fn:
                ok(mid, {"content": [{"type": "text", "text": "没有这个工具：%s" % name}],
                         "isError": True})
                continue
            try:
                text = fn(a)
                ok(mid, {"content": [{"type": "text", "text": text}]})
            except SystemExit as e:
                ok(mid, {"content": [{"type": "text", "text": str(e)}], "isError": True})
            except Exception as e:
                ok(mid, {"content": [{"type": "text", "text": "出错：%s" % str(e)[:300]}],
                         "isError": True})
        elif method == "ping":
            ok(mid, {})
        elif mid is not None:
            err(mid, -32601, "不支持的方法：%s" % method)


if __name__ == "__main__":
    main()
