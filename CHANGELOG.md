# 更新记录

## 未发布 · AIR 命名

- 项目定名 **AIR · 爱人**，锚点「**把爱留住**」
- 容器后缀 `.home` → **`.air`**；入口文件 `home.yaml` → **`air.yaml`**
- 工具改名：`home_shell` → `air_shell`、`check_home` → `check_air`、`new_home` → `new_air`
- **保留兼容**：老名字仍可用（垫片），老包里的 `home.yaml` 仍能读
- 新增 `air_pack`（打包 + manifest + 逐文件 sha256）与 `air_move`（搬家 + 校验 + 结构体检 + 可选三句演练 + `--verify-only`）
- 测试增至 16 条（含"包被改过要拒绝""目录漂移要查出来"）
- 对外身份：MIT © 2026 江灿然（Jiang Canran）；联系 QQ 940107288 · jiangcanran93@163.com

## v0.1.0（未发布）

**第一版，能跑通。**

- 设定包规范：身份 / 语气 / 规矩 / 记忆接口 / 启动序列
- 最小壳 `air_shell.py`：只读文件、不认环境；脑走环境变量，不写死路径
- 孵化 `new_air.py` + 体检 `check_air.py`
- 出门自检 `check_leak.py`：不许夹带私人内容
- 模板空包（人格留空，`to be grown`）
- 30 分钟指南（面向不写代码的人）
- 示例包 + 六模型"味道对照表"（同一份包，六种人，含原始记录）
- 离线测试 11 条，不需要任何 key
