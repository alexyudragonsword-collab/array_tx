---
type: project_topic
status: active
summary: 六条铁律各自落在哪个模块、由哪些测试守着
tags: [invariants, tests, architecture]
contains: [decision]
created: 2026-10-13
updated: 2026-10-13
related: [AGENTS.md]
authoring_mode: ai_generated
---

# 架构铁律与守护测试

| # | 铁律 | 实现位置 | 守护测试 |
|---|---|---|---|
| 1 | 配置是唯一真值 | `config.py`（`ArrayConfig`、`load_config`、`FORM_FIELDS`） | `tests/test_config.py` |
| 2 | 验收指标只在空间读 | `metrics.py`（`DirectionMetrics.domain`、`conducted_*` 只做诊断） | `tests/test_metrics.py` |
| 3 | 互耦进链路，三来源同一路径 | `coupling.py`（`apply_coupling` 唯一入口；S=0 短路） | `tests/test_coupling.py`、`tests/test_touchstone.py` |
| 4 | 波束斜视按真实带宽算 | `beam.py`（`far_field` 频域逐频点） | `tests/test_beam.py` |
| 5 | 单元差异是种子可复现的随机实例 | `seeds.py`（`SeedSequence` 派生命名流）、`element.py`（抽了再置零） | `tests/test_seeds.py` |
| 6 | 数值指纹 | `tools/fingerprint.py` | `tests/test_fingerprint.py` |

## 设计决定

- **互耦观测口**：每单元 DPD 默认观测自己的 PA 前向输出（`per_element_observe: pa_output`），因为前向定向耦合器看不到从天线口返回的耦合波；
  `antenna_port` 作为可选项保留。里程碑 1 互耦是线性泄漏，负载调制等上游 PA 有负载依赖（ROADMAP A2）。
- **工作点固定**：DPD 会扩展峰值，polar_tx 链路默认按峰值重新归一化包络；本库先跑一次参考得到 `fs_scale`，之后一律 `fs_scale_fixed`。
- **共用 LO**：所有单元同一个 `lo_pn_seed`（DTC 相位调制器的独立 LO 流），抖动仍按单元独立；时钟剖面经适配器注入 PSD，不改 polar_tx。
- **逐位相同的边界**：S 恰为全零时 `apply_coupling` 原样返回；单元误差开关关闭时增益 ×1.0、相位 ×(1+0j)、时延 0 跳过分数延时——这三条是"1 单元 = polar_tx 逐位相同"成立的前提。
