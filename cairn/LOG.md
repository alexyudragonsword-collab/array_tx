# Project Cairn 日志

本文件按时间倒序记录实质进展——新条目在顶。每条只写摘要与指针（数字写原值）；结论沉淀到 `cairn/<topic>.md`。

## 2026-10-13 · Project Cairn 初始化（ccr-411c6423-uxcjms）

- 新库 array_tx 建骨架：AGENTS.md（六条铁律）、ROADMAP（只写没做的）、CHANGELOG、`.cairn/config.yaml`（track / zh / provider none）。
- 上游 pin 核对：polar_tx `8a10480584e61af62c432f3fc2848745167056a3`、PA_DPD `08b9725595748b290c76d1b70355f7e6014a709e`、
  pll_simulator `00e48a2f6f7c11c0b6f106234f1490493d43e082`；三库均公开。
- 设计前读到的、推翻 prompt 假设的事实：polar_tx 三拓扑不是经 `PhaseModulator` 切换，而是三个同签名 TX 类；
  polar_tx 钉的 pllsim（931cfaf）不含 `export/clock_profile.py`，该文件须从 pll_simulator@00e48a2 单独 vendor；
  PA_DPD 和 polar_tx 的 ROADMAP 都没有 load-pull 条目（prompt 说"未动的项"，实际是没有这一项）。
- 历史迁移模式：`start_fresh`。细节见 `AGENTS.md`、`.cairn/config.yaml`、`cairn/architecture-invariants.md`。
