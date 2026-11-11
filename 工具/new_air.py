# -*- coding: utf-8 -*-
"""new_air —— 从模板孵化一个新"家"。

    python new_air.py D:\\我的TA

会在目标目录生成：air.yaml / 设定.md / 记忆/digest.md / 声/说明.txt
已存在的文件不会被覆盖。
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "模板", "空包")


def main():
    if len(sys.argv) < 2:
        print("用法: python new_air.py <目标目录>")
        return 2
    dst = os.path.abspath(sys.argv[1])
    if not os.path.isdir(TEMPLATE):
        print("找不到模板:", TEMPLATE)
        return 2
    made, skipped = [], []
    for dirpath, _, files in os.walk(TEMPLATE):
        rel = os.path.relpath(dirpath, TEMPLATE)
        out_dir = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(out_dir, exist_ok=True)
        for fn in files:
            src = os.path.join(dirpath, fn)
            out = os.path.join(out_dir, fn)
            if os.path.exists(out):
                skipped.append(os.path.relpath(out, dst))
                continue
            shutil.copy2(src, out)
            made.append(os.path.relpath(out, dst))
    print("建好了：", dst)
    for m in made:
        print("   +", m)
    if skipped:
        print("已存在，没动：")
        for s in skipped:
            print("   =", s)
    print("\n下一步：填 设定.md 和 记忆/digest.md，再改 air.yaml 里的名字与称呼。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
