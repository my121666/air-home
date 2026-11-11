# -*- coding: utf-8 -*-
"""兼容垫片：老名字 home_shell.py → 新名字 air_shell.py。

这是给"已经按旧文档跑过的人"留的路，将来会删。新代码请直接用 air_shell.py。
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "air_shell.py")
sys.argv[0] = TARGET
runpy.run_path(TARGET, run_name="__main__")
