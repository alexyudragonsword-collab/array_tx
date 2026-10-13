# 贡献规则

polar_tx 的 `CONTRIBUTING.md` 全部适用（断言物理而非快照；vendor 树是可校验副本不是 fork；度量约定显式；引擎有效域；
指标输入不足就抛错不出 NaN）。本文件只写本库多出来的部分。

## 0. 环境

```bash
pip install -e ".[test,dev]"
# vendor 漂移检查需要三个上游在本地（默认 /home/user/<repo>，或 --siblings repo=path，或 ARRAYTX_SIBLING_<repo>）
python tools/vendor_check.py --strict --siblings polar_tx=... PA_DPD=... pll_simulator=...
```

## 1. 六条铁律

见 `AGENTS.md`。每条铁律改动都要让 `cairn/architecture-invariants.md` 里对应的守护测试跟着改；没有测试守着的铁律不算铁律。

## 2. 外部数字

进 config / `standards.py` 的每个外部数字带 `source`（survey / derived / assumed / measured）和出处。拿不到出处就标 `assumed`。
`tests/test_config.py::test_all_numbers_sourced` 扫描全部 `configs/*.yaml`。

## 3. 指纹

重构前后在同一台机器上：

```bash
python tools/fingerprint.py record before.json
# ... 改代码 ...
python tools/fingerprint.py record after.json
python tools/fingerprint.py compare before.json after.json
```

重构必须 `bit-identical`；修复只许动它解释得了的数，并在提交信息里列出。

## 4. 提交

只提交到 `ccr-411c6423-uxcjms`。提交信息写为什么，带实测数字。每个里程碑结束：CHANGELOG 一条、`cairn/LOG.md` 一条、ROADMAP 删做完的。
