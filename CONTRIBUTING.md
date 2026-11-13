# 贡献规则

polar_tx 的 `CONTRIBUTING.md` 全部适用（断言物理而非快照；vendor 树是可校验副本不是 fork；度量约定显式；引擎有效域；
指标输入不足就抛错不出 NaN）。本文件只写本库多出来的部分。

## 0. 环境

```bash
pip install -e ".[test,dev]"
# vendor 漂移检查需要三个上游在本地（默认 /home/user/<repo>，或 --siblings repo=path，或 ARRAYTX_SIBLING_<repo>）
python tools/vendor_check.py --strict --siblings polar_tx=... PA_DPD=... pll_simulator=...
pytest -m "not examples"          # 单元测试，本机约 1.5 分钟（CI 的 test 任务就是这条）
pytest -m examples                # 每个示例跑一次冒烟尺寸（CI 的 examples 任务，三个 Python 并行）
```

新示例的冒烟分支要短：用最小能走通流程的阵列和角度，答案留给全尺寸（ex13 / ex15 冒烟用 4 × 4 而非 8 × 8）。

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

在 `feat/*` 分支上开发，开 PR 合 `main`（默认分支，2026-11-06 起），不直接推 `main`；一个 PR 只做一件事（例：重新 pin 与改数字的研究分两个 PR）。提交信息写为什么，带实测数字。每个里程碑结束：CHANGELOG 一条、`cairn/LOG.md` 一条、ROADMAP 删做完的。

## 5. GUI

- 页面不算物理：`webui/www/app.js` 只调 `/api/*`；控件来自 `/api/spec`（`guispec.controls()` = `form_fields()`），数字来自报告（`guiutil`）。
  要加一个控件，先在 `config.py` 加字段；要加一个指标或图，先在 `guiutil` 算出来、在 `guispec.METRICS / PLOTS` 声明，再画。
- 页面与宿主对账：`tests/test_webui.py::test_the_page_speaks_only_routes_the_host_answers`——app.js 里每个 `api("...")` 都得是宿主答的路由。
- 页面测试跑在真 Chromium 里（`pip install -e ".[gui-test]"`，`python -m playwright install chromium`）；本机没有就跳过，
  CI 的 `test-gui` 任务 `ARRAYTX_REQUIRE_BROWSER=1` 把跳过算失败。`ARRAYTX_CHROMIUM=/path/chrome` 指定二进制。
- 启动：`arraytx-gui [--config x.yaml] [--port 8766] [--workers 2] [--tab | --no-browser]`。
