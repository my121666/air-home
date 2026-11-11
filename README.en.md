# AIR — keep the love.

**A minimal, model-agnostic "identity pack + memory digest" that keeps an AI companion
recognizably itself across models and platforms.**

Platforms shut down. Models get replaced. Your companion's identity and the things it remembers
should live in *your* files, not someone else's servers.

```
an AIR   = a <name>.air directory + air.yaml
pack     = identity (who), tone (how it speaks), rules (hard limits),
           memory interface (what it remembers), boot sequence (first line)
memory   = a ≤2 KB digest to start with; small models cannot swallow more
```

## What is proven here (measured, not claimed)

- A **4 KB pack** is enough for a **2.6B model** to say the exact first line and use the right name.
- The **same pack** across six models produces six different voices — first line identical in 5/6.
- A **2.6B model with 80 KB of memory** returns nothing by the third turn. **Memory must be tiered.**

See `示例/味道对照表.md` (Chinese) for the raw transcripts.

## Quick start

```bash
python 工具/new_air.py D:\MyTA          # scaffold
#   fill 设定.md and 记忆/digest.md
python 工具/check_air.py D:\MyTA        # check: empty fields, cliché first line, digest size
python 工具/air_shell.py --home D:\MyTA --brain weak
```

Configure a brain by copying `keys.env.example` to `keys.env` (any OpenAI-compatible endpoint).

## Pack & move

```bash
python 工具/air_pack.py D:\MyTA                                  # manifest + per-file sha256
python 工具/air_move.py MyTA.airpack E:\elsewhere\MyTA.air       # verify + structural check
python 工具/air_move.py MyTA.airpack D:\MyTA --verify-only        # detect drift, no copy
```

**One changed byte is rejected.**

## Rules we will not cross

No companions for minors. No impersonation with a real person's face or voice.
No promise that "it will never change" — memory can be made thick; models will be replaced.

## License

[MIT](LICENSE) © 2026 江灿然 (Jiang Canran) · contact: jiangcanran93@163.com

<sub>中文说明见 [README.md](README.md)</sub>
