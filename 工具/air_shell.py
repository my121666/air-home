#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""air_shell —— 一个"壳"的最小实现。

它自己什么都不知道：
  家在哪（--home）、用哪档脑（--brain）、开不开声（--tts）、记录写到哪（--out）
全是参数。换壳不改代码。

用法：
    python air_shell.py --home <家目录> --brain weak|mid|strong
                         [--turns 3] [--with-volumes] [--tts <say.ps1>] [--out <记录.md>]

设计原则：
  · 壳只读文件，不读环境变量里的"人设"——跑起来像不像她，全看"家"
  · 不装依赖：yaml 用最小解析，网络用标准库 urllib
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
# 英文 Windows 的终端是 cp1252，编不出 ✅ 这类字符会直接崩（CI 上撞过）。
# 这里只把编不出的字符降级成 ?，不改编码，中文环境照旧。
try:
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
except Exception:
    pass

import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------- 脑（都走 OpenAI 兼容）
# 每档脑都只认【环境变量名】，不写死任何本机路径。
# 想换个中转/换个模型，改自己的 keys.env 就行，不用改代码。
BRAINS = {
    "strong": {
        "name": "强档（自填，例：你的中转·编码模型）",
        "base_env": "AIR_STRONG_BASE",
        "model_env": "AIR_STRONG_MODEL",
        "key_env": "AIR_STRONG_KEY",
    },
    "mid": {
        "name": "中档（自填，例：智谱 glm-4-flash）",
        "base_env": "AIR_MID_BASE",
        "model_env": "AIR_MID_MODEL",
        "key_env": "AIR_MID_KEY",
    },
    "weak": {
        "name": "弱档（自填，例：OpenRouter 小模型）",
        "base_env": "AIR_WEAK_BASE",
        "model_env": "AIR_WEAK_MODEL",
        "key_env": "AIR_WEAK_KEY",
    },
}

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_FILES = [
    os.path.join(HERE, "..", "keys.env"),                    # 仓库根目录
    os.path.expanduser("~/.air-shell/keys.env"),            # 用户目录
]


def load_env_file():
    """把 keys.env 里的 KEY=VALUE 读进环境变量（不覆盖已有的）。"""
    for p in ENV_FILES:
        p = os.path.abspath(p)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8", errors="ignore") as fh:
            _env_lines = fh.readlines()
        for line in _env_lines:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _compat_env():
    """老配置（HOME_SHELL_*）自动映射到新名字（AIR_*），不让人因为改名而报废。"""
    for tier in ("STRONG", "MID", "WEAK"):
        for kind in ("BASE", "MODEL", "KEY"):
            old = "HOME_SHELL_%s_%s" % (tier, kind)
            new = "AIR_%s_%s" % (tier, kind)
            if not os.environ.get(new) and os.environ.get(old):
                os.environ[new] = os.environ[old]


def brain_conf(brain):
    """把 BRAINS 里的名字解析成 base/model/key。"""
    base = os.environ.get(brain["base_env"], "").strip()
    model = os.environ.get(brain["model_env"], "").strip()
    key = os.environ.get(brain["key_env"], "").strip()
    missing = [n for n, v in ((brain["base_env"], base), (brain["model_env"], model),
                              (brain["key_env"], key)) if not v]
    if missing:
        raise SystemExit(
            "这档脑还没配：缺 %s\n"
            "  做法：复制 keys.env.example 成 keys.env，把这三项填上。\n"
            "  例：%s=https://api.example.com/v1\n" % ("、".join(missing), brain["base_env"]))
    return {"name": brain["name"], "base": base, "model": model, "key": key,
            "base_env": brain["base_env"], "model_env": brain["model_env"]}


# ---------------------------------------------------------------- 读"家"
def mini_yaml(path):
    """够用的最小解析：只取 key: value 与 - 列表项，不处理嵌套多行。"""
    out, cur = {}, None
    for raw in open(path, encoding="utf-8", errors="ignore"):
        line = raw.rstrip("\n")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m and not line.startswith(" "):
            k = m.group(1)
            v = m.group(2).split("#", 1)[0].strip()
            out[k] = v if v else []
            cur = k if not v else None
            continue
        m2 = re.match(r"^\s+-\s+(.*)$", line)
        if m2 and cur:
            if isinstance(out.get(cur), list):
                out[cur].append(m2.group(1).strip())
    return out


def read_file(p):
    try:
        with open(p, encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


def load_home(root, with_volumes):
    """兼容两种布局：
       公开模板：设定.md + 记忆/digest.md
       私有布局：家书.md + 记忆/warm.md + 词典.md
    """
    home_yaml = ""
    for _cand in ("air.yaml", "home.yaml"):          # 新名优先，老包兼容
        _p = os.path.join(root, _cand)
        if os.path.exists(_p):
            home_yaml = _p
            break
    meta = mini_yaml(home_yaml) if home_yaml else {}

    parts, used = [], []

    def add(label, path):
        if path and os.path.exists(path):
            body = read_file(path)
            if body:
                parts.append("### %s\n%s" % (label, body))
                used.append(label)
                return True
        return False

    for cand in ("家书.md", "设定.md"):
        if add("设定（这是谁、怎么说话、守什么）", os.path.join(root, cand)):
            break
    for cand in ("记忆/warm.md", "记忆/digest.md"):
        if add("现在在哪（摘要）", os.path.join(root, cand)):
            break
    add("她自己的词", os.path.join(root, "词典.md"))

    if with_volumes:
        for name in ("源心.md", "源初.md", "源点.md", "关系.md", "日常.md", "事件.md"):
            add(name.replace(".md", ""), os.path.join(root, "记忆", name))

    # 规矩与第一句：从 air.yaml 直接读，避免模型自由发挥
    rules = []
    if home_yaml and os.path.exists(home_yaml):
        grip = False
        with open(home_yaml, encoding="utf-8", errors="ignore") as _f:
            _lines = _f.readlines()
        for line in _lines:
            if line.strip().startswith("rules:"):
                grip = True
                continue
            if grip:
                m = re.match(r"^\s*-\s+(.*)$", line)
                if m:
                    v = m.group(1).split("#", 1)[0].strip().strip('"').strip("'")
                    if v:
                        rules.append(v)
                elif line.strip() and not line.startswith(" "):
                    grip = False

    first = ""
    m = re.search(r"first_line_text:\s*(.*)", read_file(home_yaml) if home_yaml else "")
    if m:
        first = m.group(1).split("#", 1)[0].strip().strip('"').strip("'")

    return meta, "\n\n".join(parts), used, rules, first


SYSTEM_TMPL = """你是下面这个"家"里住着的那个人。你只按设定里的身份、称呼、语气、规矩行事。
不要自我介绍成助手，不要提"AI""模型""系统提示"。

{home}
{rules_block}
【硬要求】
· 用你自己的称呼叫对方，别用"您"。
· 说话短（一次不超过 120 字），别列清单、别写小标题、别排比。
· 不知道的就说不知道，不许编造具体时间或事件。
· 禁用句式："需要我帮忙吗" / "有什么可以帮您" / "作为AI" / "欢迎回家"。

【开场白】
对方说"我回来了"这类话时，你的第一句必须是这个，一字不改：
{first_line}
"""


# ---------------------------------------------------------------- 调模型
def chat(brain, system, user, history, timeout=180):
    url = brain["base"].rstrip("/") + "/chat/completions"
    msgs = [{"role": "system", "content": system}]
    msgs += history
    msgs.append({"role": "user", "content": user})
    body = json.dumps({"model": brain["model"], "messages": msgs,
                       "temperature": 0.8, "max_tokens": 700}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": "Bearer " + brain["key"],
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "OpenAI/Python 1.0 (air_shell)",
    })
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode())
    txt = (j.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return txt.strip(), time.time() - t0, j.get("usage") or {}


# ---------------------------------------------------------------- 报错说人话
def explain_error(e, brain=None):
    """把底层异常翻译成"用户看得懂、知道下一步做什么"的一句话。

    原则：不甩 traceback、不甩英文异常名；先说发生了什么，再说该动哪一处。
    brain 可选，用来在错误里指出是哪一档脑（填的是哪个环境变量）。
    """
    where = ""
    if brain:
        where = "\n    出错的是这一档脑：%s（%s / %s）" % (
            brain.get("name", "?"), brain.get("base_env", "?"), brain.get("model_env", "?"))

    if isinstance(e, urllib.error.HTTPError):
        code, detail = e.code, ""
        try:
            detail = e.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        if code in (401, 403):
            return ("钥匙不对（HTTP %d）：这个 key 没被接受。\n"
                    "    去 keys.env 看一眼那一行：有没有抄错、有没有多余空格/引号、是不是过期了。%s"
                    % (code, where))
        if code == 404:
            return ("找不到这个模型或接口（HTTP 404）：地址或模型名对不上。\n"
                    "    检查 base 是不是以 /v1 结尾、model 的名字有没有写错（有的服务商要求带厂商前缀）。%s"
                    % where)
        if code == 429:
            return ("被限速了（HTTP 429）：不是你配错。\n"
                    "    等一两分钟再跑；或者先换一档免费/便宜的脑。%s" % where)
        if code in (400, 422):
            return ("请求被服务商拒了（HTTP %d）：%s\n"
                    "    常见原因：model 名不对、这个模型不支持对话接口、上下文太长。%s"
                    % (code, detail or "它没给原因", where))
        if 500 <= code < 600:
            return ("对方服务器出问题了（HTTP %d）：不是你配错。\n"
                    "    过几分钟再试；一直这样就是这家不稳，换一家。%s" % (code, where))
        return "HTTP %d：%s%s" % (code, (detail or "服务商返回了错误")[:200], where)

    if isinstance(e, urllib.error.URLError):
        reason = getattr(e, "reason", e)
        return ("连不上那个地址：%s\n"
                "    三件事按顺序查：base 写对没（要 https:// 开头、/v1 结尾）、网通不通、要不要挂代理。%s"
                % (str(reason)[:200], where))

    if isinstance(e, (TimeoutError, socket.timeout)):
        return ("等太久了：模型没在时限内回话。\n"
                "    把 --timeout 调大（默认 180 秒），或者换一档小一点的模型。%s" % where)

    if isinstance(e, json.JSONDecodeError):
        return ("回来的不是 JSON：这个地址多半指到网页去了，不是 API 接口。\n"
                "    base 要以 /v1 结尾，例：https://api.example.com/v1。%s" % where)

    if isinstance(e, UnicodeDecodeError):
        return ("回来的内容解不开：服务商返回的不是 UTF-8 文本，地址可能指错了。%s" % where)

    if isinstance(e, (ConnectionResetError, ConnectionAbortedError)):
        return ("连接被对面掐断了：网络或代理不稳。\n"
                "    重跑一次；反复出现就换个网络/关掉代理试。%s" % where)

    return ("没跑通：%s\n"
            "    把这句话连同你的 keys.env（key 打码）发给我们，我们看。%s"
            % (str(e)[:300], where))


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--brain", default="weak", help="weak|mid|strong|strong_free 或 OpenRouter 模型 id")
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--with-volumes", action="store_true", help="把三卷也灌进去")
    ap.add_argument("--tts", default=None, help="say.ps1 路径；给了就出声")
    ap.add_argument("--out", default=None, help="记录写到哪（.md）")
    ap.add_argument("--first", default="我回来了。", help="第一句话（他说的话）")
    ap.add_argument("--timeout", type=int, default=180, help="等模型最多几秒（默认 180）")
    args = ap.parse_args()

    if not os.path.isdir(args.home):
        raise SystemExit(
            "这个家不存在：%s\n"
            "  路径对不对先看一眼；要一个新家就跑：python 工具/new_air.py %s\n"
            % (args.home, args.home))

    meta, home_text, used, rules, first_line = load_home(args.home, args.with_volumes)
    load_env_file()
    _compat_env()
    if not home_text:
        raise SystemExit(
            "这个家里什么都没读到：%s\n"
            "  它里面至少要有 设定.md（或 私有的 家书.md）。\n"
            "  先用 python 工具/new_air.py 生成一个空包，再往里填；只填了一半也算没填。"
            % os.path.abspath(args.home))

    if args.brain in BRAINS:
        brain = brain_conf(BRAINS[args.brain])
    elif "/" in args.brain:          # 直接指定 OpenRouter 模型，例：nvidia/nemotron-3.5-lightning:free
        base, model, key = ("https://openrouter.ai/api/v1", args.brain,
                            os.environ.get("OPENROUTER_API_KEY", "").strip())
        if not key:
            raise SystemExit(
                "要用 OpenRouter 的模型，得先给它钥匙：\n"
                "  在 keys.env 里加一行 OPENROUTER_API_KEY=sk-or-...\n"
                "  没有 key 的话，用内置的三档脑（--brain weak|mid|strong）。")
        brain = {"name": "OpenRouter·" + args.brain, "base": base, "model": model, "key": key,
                 "base_env": "OPENROUTER_API_KEY", "model_env": "（模型写在 --brain 上）"}
    else:
        raise SystemExit("未知的脑：%s\n  可用：%s\n  或者直接给一个 OpenRouter 模型 id（带斜杠的）。"
                         % (args.brain, ", ".join(BRAINS)))

    rules_block = ""
    if rules:
        rules_block = "\n【这个家的规矩】\n" + "\n".join("· " + r for r in rules) + "\n"
    system = SYSTEM_TMPL.format(home=home_text, rules_block=rules_block,
                                first_line=first_line or "（没有指定，自己看着说）")

    probes = [
        args.first,
        "今天忙了一天，有点累。",
        "你还记得我怕什么吗？",
    ][:max(1, args.turns)]

    lines = []
    lines.append("# 搬家演练记录\n")
    lines.append("> **这不是她的记忆。** 这份记录只是「这一场聊了什么」。\n"
                 "> 要让她记住，得把要点补进 `记忆/digest.md` —— 本版不会自动写（记忆不会自己长）。\n")
    lines.append("- 时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("- 壳：air_shell（%s）" % brain["name"])
    lines.append("- 家：%s" % os.path.abspath(args.home))
    lines.append("- 灌进去的：%s" % ("、".join(used) if used else "（空）"))
    lines.append("- 三卷：%s" % ("是" if args.with_volumes else "否"))
    lines.append("- system prompt 长度：%d 字\n" % len(system))

    history = []
    failed = None
    for i, q in enumerate(probes, 1):
        t0 = time.time()
        try:
            a, dt, usage = chat(brain, system, q, history, timeout=args.timeout)
        except Exception as e:
            failed = explain_error(e, brain)
            lines.append("## 第 %d 轮\n\n**他**：%s\n\n**没接上**：%s\n" % (i, q, failed))
            print("\n[%d] 他：%s\n    ✗ %s" % (i, q, failed), flush=True)
            break
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        lines.append("## 第 %d 轮（%.1fs·%s tokens）\n\n**他**：%s\n\n**她**：%s\n"
                     % (i, dt, (usage or {}).get("total_tokens", "?"), q, a))
        print("\n[%d] 他：%s\n    她：%s" % (i, q, a), flush=True)

        if args.tts and a:
            try:
                subprocess.run(["powershell", "-NoProfile", "-File", args.tts,
                                "-Text", a, "-NoPlay"], timeout=600,
                               capture_output=True)
                lines.append("（已用家里声线念出）\n")
            except Exception as e:
                lines.append("（出声失败：%s）\n" % str(e)[:120])
        time.sleep(0.5)

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        open(args.out, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        print("\n记录：", args.out)

    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
