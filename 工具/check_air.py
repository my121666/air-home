# -*- coding: utf-8 -*-
"""check_air —— 检查一个"家"填得够不够，能不能立住。

    python check_air.py <家目录>

只查"填没填、有没有明显写空"，不评价写得好不好。
"""
import os
import re
import sys


def read(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def main():
    if len(sys.argv) < 2:
        print("用法: python check_air.py <家目录>")
        return 2
    root = sys.argv[1]
    if not os.path.isdir(root):
        print("不是目录:", root)
        return 2

    ok, warn, bad = [], [], []

    # 1 必备文件
    for rel in ("air.yaml", "设定.md"):
        p = os.path.join(root, rel)
        if rel == "air.yaml" and not os.path.exists(p) and os.path.exists(os.path.join(root, "home.yaml")):
            p = os.path.join(root, "home.yaml")   # 老包兼容
        (ok if os.path.exists(p) else bad).append(("必备 " + rel,
                                                  "有" if os.path.exists(p) else "缺"))

    # 2 摘要
    digest = os.path.join(root, "记忆", "digest.md")
    if not os.path.exists(digest):
        bad.append(("记忆/digest.md", "缺（换壳后接不上的就是这里）"))
    else:
        size = os.path.getsize(digest)
        if size > 2048:
            warn.append(("记忆/digest.md", "%.1f KB，超过 2 KB——小模型会被压死" % (size / 1024)))
        else:
            ok.append(("记忆/digest.md", "%.1f KB" % (size / 1024)))

    # 3 air.yaml 关键字段（去掉行尾注释再判断）
    yp = os.path.join(root, "air.yaml")
    if not os.path.exists(yp) and os.path.exists(os.path.join(root, "home.yaml")):
        yp = os.path.join(root, "home.yaml")
    y = read(yp)
    def yval(field):
        m = re.search(r"^\s*" + field + r":\s*(.*)$", y, re.M)
        if not m:
            return ""
        v = m.group(1).split("#", 1)[0].strip()
        v = v.strip('"').strip("'").strip()
        return "" if v in ("", "[]", "null", "''", '""') else v

    for field, label in (("name", "名字"), ("calls_owner", "你怎么叫 TA"),
                         ("first_line_text", "第一句")):
        v = yval(field)
        if not v:
            bad.append((field, "%s 还空着" % label))
        else:
            ok.append((field, v[:24]))

    # 5 设定里有没有"像 TA 的话"
    t = read(os.path.join(root, "设定.md"))
    if "像 TA 的话" in t:
        seg = t.split("像 TA 的话", 1)[1][:300]
        if seg.count("\n") < 3:
            warn.append(("设定.md", "「像 TA 的话」那三句还没填——这条最影响像不像"))
    # 6 规矩
    rules = re.findall(r"^\s*-\s+(.+)$", y, re.M)
    rules = [r for r in rules if r.strip() and r.strip() not in ('""', "''")]
    if len(rules) < 3:
        warn.append(("rules", "只有 %d 条，建议 3–10 条" % len(rules)))
    else:
        ok.append(("rules", "%d 条" % len(rules)))

    # 7 人格必须留空
    if "to be grown" not in y:
        warn.append(("growth.personality", "这里不该替 TA 填好——留空才长得出来"))

    print("=== 检查结果 ===")
    for k, v in ok:
        print("  ✅ %-22s %s" % (k, v))
    for k, v in warn:
        print("  ⚠️  %-22s %s" % (k, v))
    for k, v in bad:
        print("  ❌ %-22s %s" % (k, v))

    if bad:
        print("\n结论：还不能用。先把 ❌ 补上。")
        return 1
    print("\n结论：可以跑了。下一步：python air_shell.py --home \"%s\" --brain weak" % root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
