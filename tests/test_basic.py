# -*- coding: utf-8 -*-
"""离线测试：不需要任何 API key，也不联网。

跑法：python -m unittest discover -s tests -v
"""
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "工具"))

TEMPLATE = os.path.join(ROOT, "模板", "空包")
EXAMPLE = os.path.join(ROOT, "示例", "阿柚")


def read(p):
    return open(p, encoding="utf-8", errors="ignore").read()


class TestMiniYaml(unittest.TestCase):
    def test_parse_name_and_rules(self):
        import air_shell
        meta = air_shell.mini_yaml(os.path.join(EXAMPLE, "air.yaml"))
        self.assertEqual(meta.get("version"), "0")
        self.assertEqual(meta.get("kind"), "home")

    def test_rules_are_a_list(self):
        import air_shell
        meta = air_shell.mini_yaml(os.path.join(EXAMPLE, "air.yaml"))
        rules = meta.get("rules")
        self.assertIsInstance(rules, list)
        self.assertGreaterEqual(len(rules), 3)


class TestLoadHome(unittest.TestCase):
    def test_example_loads(self):
        import air_shell
        meta, text, used, rules, first = air_shell.load_home(EXAMPLE, with_volumes=False)
        self.assertIn("设定", "".join(used))
        self.assertGreater(len(text), 100)
        self.assertGreaterEqual(len(rules), 3)
        self.assertTrue(first)
        self.assertNotIn("你好，我是", first)

    def test_volumes_optional(self):
        import air_shell
        _, plain, _, _, _ = air_shell.load_home(EXAMPLE, with_volumes=False)
        _, rich, _, _, _ = air_shell.load_home(EXAMPLE, with_volumes=True)
        self.assertGreaterEqual(len(rich), len(plain))


class TestTemplate(unittest.TestCase):
    def test_template_has_all_parts(self):
        for rel in ("air.yaml", "设定.md", "记忆/digest.md", "声/说明.txt"):
            self.assertTrue(os.path.exists(os.path.join(TEMPLATE, rel)), rel)

    def test_personality_left_empty(self):
        """人格必须留空——这是硬规矩，工具不许给默认性格。"""
        y = read(os.path.join(TEMPLATE, "air.yaml"))
        self.assertIn("to be grown", y)

    def test_digest_under_2kb(self):
        size = os.path.getsize(os.path.join(TEMPLATE, "记忆", "digest.md"))
        self.assertLessEqual(size, 2048, "模板摘要不该超过 2 KB")

    def test_template_first_line_empty(self):
        y = read(os.path.join(TEMPLATE, "air.yaml"))
        m = re.search(r"first_line_text:\s*(.*)", y)
        self.assertIsNotNone(m)
        self.assertIn('""', m.group(1), "模板第一句必须留空，等使用者自己写")


class TestNoSecrets(unittest.TestCase):
    """仓库里不许出现看起来像真 key 的串。"""

    PAT = re.compile(r"sk-[A-Za-z0-9]{20,}|ak_[A-Za-z0-9]{20,}")

    def test_no_live_keys(self):
        bad = []
        for dirpath, dirnames, filenames in os.walk(ROOT):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "tests")]
            for fn in filenames:
                if not fn.endswith((".py", ".md", ".yaml", ".example", ".txt")):
                    continue
                p = os.path.join(dirpath, fn)
                if self.PAT.search(read(p)):
                    bad.append(os.path.relpath(p, ROOT))
        self.assertEqual(bad, [], "疑似真实 key：%s" % bad)


class TestCheckHome(unittest.TestCase):
    def test_example_passes(self):
        import check_air
        sys.argv = ["check_air.py", EXAMPLE]
        self.assertEqual(check_air.main(), 0)

    def test_empty_template_fails(self):
        import check_air
        sys.argv = ["check_air.py", TEMPLATE]
        self.assertEqual(check_air.main(), 1, "空模板应该被判为还不能用")


class TestPackMove(unittest.TestCase):
    """打包 / 搬家：全程离线，不需要任何 key。"""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.pack = os.path.join(self.tmp, "阿柚.airpack")
        self.dest = os.path.join(self.tmp, "搬到.air")

    def _pack(self):
        import air_pack
        sys.argv = ["air_pack.py", EXAMPLE, "-o", self.pack]
        self.assertEqual(air_pack.main(), 0)
        self.assertTrue(os.path.exists(self.pack))

    def test_pack_creates_manifest(self):
        import json, zipfile
        self._pack()
        with zipfile.ZipFile(self.pack) as z:
            m = json.loads(z.read("manifest.json").decode("utf-8"))
        self.assertEqual(m["format"], "air/0")
        self.assertGreaterEqual(m["count"], 3)
        self.assertIn("files", m)

    def test_move_verifies_and_checks_structure(self):
        import air_move
        self._pack()
        sys.argv = ["air_move.py", self.pack, self.dest]
        self.assertEqual(air_move.main(), 0)
        self.assertTrue(os.path.exists(os.path.join(self.dest, "air.yaml")))

    def test_move_detects_tampered_pack(self):
        import air_move, zipfile
        self._pack()
        bad = os.path.join(self.tmp, "坏.airpack")
        with zipfile.ZipFile(self.pack) as z:
            items = {n: z.read(n) for n in z.namelist()}
        items["air.yaml"] = items["air.yaml"].replace("阿柚".encode(), "阿柏".encode())
        with zipfile.ZipFile(bad, "w", zipfile.ZIP_DEFLATED) as z:
            for n, d in items.items():
                z.writestr(n, d)
        sys.argv = ["air_move.py", bad, os.path.join(self.tmp, "坏.air")]
        self.assertEqual(air_move.main(), 1, "包被改过就该拒绝")

    def test_verify_only_detects_drift(self):
        import air_move
        self._pack()
        sys.argv = ["air_move.py", self.pack, self.dest]
        air_move.main()
        with open(os.path.join(self.dest, "记忆", "digest.md"), "a", encoding="utf-8") as f:
            f.write("\n偷偷加一行\n")
        sys.argv = ["air_move.py", self.pack, self.dest, "--verify-only"]
        self.assertEqual(air_move.main(), 1, "改过的目录应被查出来")

    def test_pack_rejects_non_air_dir(self):
        import air_pack
        empty = os.path.join(self.tmp, "空的")
        os.makedirs(empty, exist_ok=True)
        sys.argv = ["air_pack.py", empty, "-o", os.path.join(self.tmp, "x.airpack")]
        self.assertEqual(air_pack.main(), 1)


class TestAirMcp(unittest.TestCase):
    """air_mcp 的协议与工具（离线，不需要 key）。"""

    def _client(self):
        import subprocess, json, os
        env = dict(os.environ, AIR_HOME=EXAMPLE, PYTHONIOENCODING="utf-8")
        p = subprocess.Popen([sys.executable, "-X", "utf8",
                              os.path.join(ROOT, "工具", "air_mcp.py")],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding="utf-8",
                             bufsize=1, env=env)
        return p

    def _rpc(self, p, obj):
        import json
        p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        p.stdin.flush()
        return json.loads(p.stdout.readline())

    def test_initialize_and_tools(self):
        p = self._client()
        try:
            r = self._rpc(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            self.assertEqual(r["result"]["serverInfo"]["name"], "air-mcp")
            self.assertIn("protocolVersion", r["result"])
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            p.stdin.flush()
            r = self._rpc(p, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            names = [t["name"] for t in r["result"]["tools"]]
            self.assertEqual(sorted(names), sorted(["air_load", "air_boot", "air_digest",
                                                    "air_pack", "air_move"]))
        finally:
            p.stdin.close()
            p.terminate()

    def test_air_boot_uses_home(self):
        p = self._client()
        try:
            self._rpc(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            p.stdin.flush()
            r = self._rpc(p, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                              "params": {"name": "air_boot", "arguments": {}}})
            text = r["result"]["content"][0]["text"]
            self.assertIn("启动序列", text)
            self.assertIn("先生", text)      # 示例包里怎么称呼对方
        finally:
            p.stdin.close()
            p.terminate()

    def test_digest_rejects_over_2kb(self):
        p = self._client()
        try:
            self._rpc(p, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
            p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
            p.stdin.flush()
            big = "啊" * 800        # UTF-8 中文 3 字节 → 2400 字节，超 2048
            r = self._rpc(p, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                              "params": {"name": "air_digest", "arguments": {"text": big}}})
            text = r["result"]["content"][0]["text"]
            self.assertTrue("拒绝" in text or "超过" in text, text[:120])
        finally:
            p.stdin.close()
            p.terminate()


class TestExplainError(unittest.TestCase):
    """A4：报错必须说人话——每类错误都给出"该动哪一处"。"""

    def _explain(self, exc):
        import air_shell
        return air_shell.explain_error(exc, {"name": "弱档", "base_env": "AIR_WEAK_BASE",
                                             "model_env": "AIR_WEAK_MODEL"})

    def test_401_says_key(self):
        import urllib.error
        msg = self._explain(urllib.error.HTTPError("u", 401, "Unauthorized", {}, None))
        self.assertIn("钥匙不对", msg)
        self.assertIn("keys.env", msg)

    def test_404_says_model_or_v1(self):
        import urllib.error
        msg = self._explain(urllib.error.HTTPError("u", 404, "Not Found", {}, None))
        self.assertIn("404", msg)
        self.assertTrue("/v1" in msg or "模型名" in msg)

    def test_429_says_not_your_fault(self):
        import urllib.error
        msg = self._explain(urllib.error.HTTPError("u", 429, "Too Many", {}, None))
        self.assertIn("限速", msg)

    def test_5xx_says_not_your_config(self):
        import urllib.error
        msg = self._explain(urllib.error.HTTPError("u", 502, "Bad Gateway", {}, None))
        self.assertIn("不是你配错", msg)

    def test_connection_refused_says_three_things(self):
        import urllib.error
        msg = self._explain(urllib.error.URLError(ConnectionRefusedError(10061, "refused")))
        self.assertIn("连不上", msg)
        self.assertIn("代理", msg)

    def test_bad_json_says_wrong_url(self):
        msg = self._explain(json.JSONDecodeError("x", "<html>", 0))
        self.assertIn("/v1", msg)

    def test_unknown_error_still_human(self):
        msg = self._explain(ValueError("something odd"))
        self.assertIn("没跑通", msg)
        self.assertIn("keys.env", msg)

    def test_never_dumps_traceback(self):
        import urllib.error
        for exc in (urllib.error.HTTPError("u", 403, "Forbidden", {}, None),
                    urllib.error.URLError("dns fail"),
                    ValueError("boom")):
            msg = self._explain(exc)
            self.assertNotIn("Traceback", msg)
            self.assertNotIn("urllib.error", msg)


class TestShellRun(unittest.TestCase):
    """端到端跑 air_shell：抓的是"用户真会遇到的第一句"。

    这一组存在的直接原因：air_shell 曾经把 --home 写成 args.air，
    19 条测试全过，但脚本一跑就 AttributeError。
    """

    def _run(self, *argv, env_extra=None):
        import subprocess
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        env.pop("AIR_WEAK_BASE", None)
        env.pop("AIR_WEAK_MODEL", None)
        env.pop("AIR_WEAK_KEY", None)
        if env_extra:
            env.update(env_extra)
        p = subprocess.run([sys.executable, "-X", "utf8",
                            os.path.join(ROOT, "工具", "air_shell.py")] + list(argv),
                           capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def test_missing_home_says_so(self):
        code, out = self._run("--home", os.path.join(ROOT, "不存在的家"), "--turns", "1")
        self.assertEqual(code, 1)
        self.assertIn("这个家不存在", out)
        self.assertNotIn("Traceback", out)

    def test_empty_home_says_so(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            code, out = self._run("--home", tmp, "--turns", "1")
            self.assertEqual(code, 1)
            self.assertIn("什么都没读到", out)

    def test_unconfigured_brain_says_which_env(self):
        code, out = self._run("--home", TEMPLATE, "--brain", "weak", "--turns", "1")
        self.assertEqual(code, 1)
        self.assertIn("这档脑还没配", out)
        self.assertIn("AIR_WEAK_BASE", out)

    def test_unreachable_brain_gives_human_line(self):
        """真跑一遍 --home：能走到 chat()，失败也必须是中文人话、退出码 2。"""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            out_md = os.path.join(tmp, "记录.md")
            code, out = self._run("--home", TEMPLATE, "--brain", "weak", "--turns", "1",
                                  "--timeout", "8", "--out", out_md,
                                  env_extra={"AIR_WEAK_BASE": "http://127.0.0.1:9/v1",
                                             "AIR_WEAK_MODEL": "x",
                                             "AIR_WEAK_KEY": "k"})
            self.assertEqual(code, 2, out[:300])
            self.assertIn("连不上", out)
            self.assertNotIn("Traceback", out)
            self.assertTrue(os.path.exists(out_md), "失败也要留下记录")
            self.assertIn("没接上", read(out_md))
            self.assertIn("家：", read(out_md))


if __name__ == "__main__":
    unittest.main()
