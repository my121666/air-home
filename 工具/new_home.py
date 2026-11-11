# -*- coding: utf-8 -*-
"""兼容垫片：老名字 new_home.py → 新名字 new_air.py。

这是给"已经按旧文档跑过的人"留的路，将来会删。新代码请直接用 new_air.py。
"""
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "new_air.py")
sys.argv[0] = TARGET
runpy.run_path(TARGET, run_name="__main__")
