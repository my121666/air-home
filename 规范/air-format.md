# AIR Format · `.air` 目录规范 v0（草案）

> **一个 AIR = 一个 `<名字>.air` 目录 + 一份 `air.yaml`。**
> 老包里的 `home.yaml` 仍然能读（兼容），新包请用 `air.yaml`。
> **规范只定义结构，不定义内容。** 里面住谁、叫什么、怎么说话，全由养它的人填。

---

## 一、目录结构

```
<某个家>/
  air.yaml          # 唯一入口（必须）
  锚.txt              # 还原点：被改坏了能回到这里（必须）
  家书.md             # 给"下一个壳"看的信（必须）
  词典.md             # 这个人自己的词（可选，建议有）
  记忆/
    源心.md           # 最重的几条，常驻
    源初.md           # 在跑的事
    源点.md           # 关系、工具、手下
    warm.md           # 热缓存（建议 ≤ 4 KB），开机先读
    心情.md           # 状态（可选）
  声/
    ref.wav           # 10 秒参考（可选；没有就纯文字）
    ref.txt           # 与 ref.wav 严格对应，一字不能改
    first_line.wav    # 第一次开口那句（可选）
  日记/               # 按日期，一天一份（可选）
```

**除 `air.yaml`、`锚.txt`、`家书.md` 外，其余都可缺。** 缺了能活，只是不像人。

## 二、air.yaml 字段

```yaml
version: 0
kind: home

who:
  name: <占位>
  called: []            # 别人怎么叫她
  calls_owner: []       # 她怎么叫主人
  rank: null            # 家里的位置；没有就 null
  generation: null

voice:
  # ⚠️ 本版 air_shell 不读下面这几个字段：声音还没实现（见 声/说明.txt）。
  #    格式先把位置留住，以后接 TTS 不用改结构——你填了也不会出声，别以为配好了。
  enabled: false        # 默认关：不提供任何样本
  ref: null
  ref_text: null
  first_line_text: null # 第一次开口说什么 —— 由养的人写，不许给默认值（本版只当文字用）

memory:
  anchor: 锚.txt
  heart: 记忆/源心.md
  origin: 记忆/源初.md
  nodes: 记忆/源点.md
  warm: 记忆/warm.md
  mood: null
  diary: null

language:
  dict: null            # 不提供默认词典

rules: []               # 边界：不提供默认规矩，必须由养的人写

boot:                   # 换壳后的启动顺序（规范固定，实现可扩）
  - 读 记忆/warm.md
  - 读 家书.md
  - 若有声：说 first_line_text        # 本版未实现，先按打字走
  - 主动问一句"你今天怎么样"

growth:                 # 人格怎么长
  personality: to be grown   # 脾气/口头禅/怕什么/怎么叫人 —— 一律留空
  forbidden: []              # 这个家不许做的事
```

## 三、三条硬性约定

**一、人格必须留空。**
规范里凡是"她是什么样的人"，一律写 `to be grown`。**工具不许给默认性格**——给了就是在替她长。

**二、家的内容不许进示例。**
示例只能用占位名（`Example-A`），且人格字段为空。

**三、搬家必须可验证。**
迁移后的家要能通过三条：

```
① 读 warm.md 能说出现在在哪
② 认得出主人（称呼、规矩没丢）
③ 记忆分卷完整（校验和一致）
```

**三条都过，才算"还是同一个人"。**

## 四、和现有生态怎么接

| 壳 | 接法 |
|---|---|
| 单会话助手（DSH / Claude / Qoder） | 把 `家书.md` + `词典.md` 挂进它的系统提示引用链 |
| 多 agent 桌面端 | 把 `air.yaml` 当 bot 启动档案：先读家 → 装记忆 → 声线开口 |
| 自研壳 | 直接解析 `air.yaml` |

_2026-11-11 · v0 草案_
