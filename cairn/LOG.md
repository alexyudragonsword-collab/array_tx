# Project Cairn 日志

本文件按时间倒序记录实质进展——新条目在顶。每条只写摘要与指针（数字写原值）；结论沉淀到 `cairn/<topic>.md`。

## 2026-10-13 · 里程碑 1 完成：4 单元 FR2 线阵、三种互耦、三种 DPD、OTA 指标（ccr-411c6423-uxcjms）

- 验收逐条（全尺寸 8 符号，fs 1.96608 GS/s；`tests/`  项、`tools/vendor_check.py --strict` 86 文件无漂移）：
  (1) sub-6 / S=0 / 1 单元与 polar_tx `nr_dtc().run()` 逐位相同：True，EVM −39.91 dB 两边一致（ex00）。
  (2) 互耦→0 时每单元 vs 全阵列 DPD 的 OTA ACLR1 差 0.03 dB（< 0.5，ex02）。
  (4) 带边斜视：30° 实测 ±0.24/−0.23°、60° ±0.72/−0.70°，与 asin(sinθ0·f0/(f0+Δf)) 误差 0.00 %（ex03）。
  (5) analytic→.s4p→touchstone：矩阵与三方案远场全部逐位相同（ex01）。(6) 所有 config 数字带 source，survey 块无 ref 不加载。
- **核心数字（波束方向 OTA ACLR1，survey 互耦 −16 dB，相移导向）**：0°/30°/60° 无 DPD −37.8/−37.8/−37.7 dBc；
  每单元 −45.1/−45.0/−45.0；全阵列 −45.1/−45.0/−45.0。全阵列 DPD 追回 7.2–7.3 dB；与每单元差 +0.01…+0.03 dB。
  EVM：无 DPD −26.3…−26.4 dB，两种 DPD −28.0…−28.1 dB。旁瓣方向（30° 波束的 −13.4°）：无 DPD −38.0、每单元 −42.4、全阵列 −41.4 dBc。
- **analytic 与 survey 之差**：三方案在波束方向 ≤ 0.01 dB（ex01），远低于 2 dB 阈值——结论对耦合值不敏感，但原因是下一条，不是模型稳健。
- **被推翻的判断 1**："互耦打开后每单元 DPD 比互耦为零时差"不成立：相邻耦合从 0 扫到 −10 dB，三方案 ACLR1 只动 0.02–0.08 dB（ex02）。
  线性泄漏 + 相位协变的 DPA ⇒ 泄漏是各单元非线性的线性组合，每单元线性化后波束方向不受影响（详见 `architecture-invariants.md`）。
  要分开两种 DPD 需要负载依赖的 PA（ROADMAP A2 / B4）。全阵列 DPD 只在旁瓣方向比每单元差约 1 dB（ex03/ex04），这是互耦与 PA 偏差共同的印记。
- **被推翻的判断 2**：斜视不进波束 EVM——60° 相移 vs 真延时 EVM 差 0.0002 dB（见 invariants 笔记），斜视是指向效应。
- 发现：5 阶 GMP 把 ACLR2 从 −50.6 推到 −47.5 dBc（ROADMAP B5）；方向图零点里 ACLR 可到 −14 dBc（ex04 涂灰）。
- 耗时（本机）：ex00 2.0 s、ex01 18.6 s、ex02 31.2 s、ex03 21.6 s、ex04 51.4 s；单次 `sim.run` 无 DPD 0.6–0.8 s，带 DPD 1.6–2.3 s。
- 下一步：A1 拿实测 .sNp 切 touchstone；A2 等负载依赖的 PA；B5 扫 GMP 阶数 vs ACLR2；C1 表单接前端。

## 2026-10-13 · Project Cairn 初始化（ccr-411c6423-uxcjms）

- 新库 array_tx 建骨架：AGENTS.md（六条铁律）、ROADMAP（只写没做的）、CHANGELOG、`.cairn/config.yaml`（track / zh / provider none）。
- 上游 pin 核对：polar_tx `8a10480584e61af62c432f3fc2848745167056a3`、PA_DPD `08b9725595748b290c76d1b70355f7e6014a709e`、
  pll_simulator `00e48a2f6f7c11c0b6f106234f1490493d43e082`；三库均公开。
- 设计前读到的、推翻 prompt 假设的事实：polar_tx 三拓扑不是经 `PhaseModulator` 切换，而是三个同签名 TX 类；
  polar_tx 钉的 pllsim（931cfaf）不含 `export/clock_profile.py`，该文件须从 pll_simulator@00e48a2 单独 vendor；
  PA_DPD 和 polar_tx 的 ROADMAP 都没有 load-pull 条目（prompt 说"未动的项"，实际是没有这一项）。
- 历史迁移模式：`start_fresh`。细节见 `AGENTS.md`、`.cairn/config.yaml`、`cairn/architecture-invariants.md`。
