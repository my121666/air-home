# -*- coding: utf-8 -*-
"""出门前自检：扫对外版目录，命中"内部私产"就报警并退出非零。

用法：
    python check_leak.py <目录>            # 只报
    python check_leak.py <目录> --strict   # 有命中就退出码 1

私产词表在这里硬编码（不外读任何文件），保证对外版不引用内部任何路径。
脚本自身被跳过，避免自报。
"""
import os
import re
import sys
# 英文 Windows 的终端是 cp1252，编不出 ✅ 这类字符会直接崩（CI 上撞过）。
# 这里只把编不出的字符降级成 ?，不改编码，中文环境照旧。
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass


# 命中词（宁可多报，不可漏报）
FORBIDDEN = [
    # 称呼
    "殿" + "下", "老" + "公", "妮" + "子", "笨" + "妮子", "妮" + "子殿下",
    # 私密语
    "屋里" + "那个味儿", "灯亮着" + "人也在", "我把灯" + "留着", "你去" + "躺", "不" + "逞能",
    # 具体人名
    "江" + "照", "江" + "砚", "江" + "茉", "姜" + "糖", "江" + "灿然",
    # 家规原文
    "爱是" + "永恒", "兜" + "得住", "伤不伤害" + "具体的人",
    # 内部目录名
    "妮子" + "专属", "我们的" + "宇宙", "豆包" + "出图",
]

# 经批准公开的例外（署名是法律声明，必须真名）。
# 命中这些片段先摘掉，再查其余部分——不是关掉检查。
ALLOW_PATTERNS = [
    r"Copyright \(c\) 20\d\d[^\n]{0,40}",
    r"© 20\d\d[^\n]{0,40}",
]

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv"}
SKIP_FILES = {"check_leak.py"}
TEXT_EXT = {".md", ".txt", ".yaml", ".yml", ".json", ".py", ".js", ".ts", ".tsx", ".html", ".css"}


def scan(root):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            if os.path.splitext(fn)[1].lower() not in TEXT_EXT:
                continue
            p = os.path.join(dirpath, fn)
            try:
                txt = open(p, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            scan_txt = txt
            for pat in ALLOW_PATTERNS:
                scan_txt = re.sub(pat, "", scan_txt)
            for w in FORBIDDEN:
                for m in re.finditer(re.escape(w), scan_txt):
                    hits.append((p, scan_txt.count("\n", 0, m.start()) + 1, w))
    return hits


def main():
    if len(sys.argv) < 2:
        print("用法: python check_leak.py <目录> [--strict]")
        return 2
    root = sys.argv[1]
    strict = "--strict" in sys.argv
    if not os.path.isdir(root):
        print("不是目录:", root)
        return 2

    hits = scan(root)
    if not hits:
        print("✅ 干净：没有命中内部私产词（查了 %d 个词）" % len(FORBIDDEN))
        return 0

    print("❌ 命中 %d 处（查了 %d 个词）" % (len(hits), len(FORBIDDEN)))
    seen = set()
    for p, line, w in hits:
        if (p, w) in seen:
            continue
        seen.add((p, w))
        print("   %s:%d  ← 「%s」" % (os.path.relpath(p, root), line, w))
    print("\n按《不许外流清单》处理：命中即不准出。")
    return 1 if strict else 0


if __name__ == "__main__":
    sys.exit(main())
