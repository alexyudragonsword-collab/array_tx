# 变更日志

按里程碑记录做了什么、为什么。没做的在 `ROADMAP.md`。

## 未发布 / Unreleased

### 里程碑 1：4 单元 FR2 线阵、三种互耦来源、三种 DPD 方案、OTA 指标（2026-10-13）

**做了什么**

- 新库骨架：Project Cairn（AGENTS.md 六条铁律、ROADMAP 只写没做的、`cairn/LOG.md`）、CI（lint / test 3.10–3.12 / 示例冒烟 / vendor 漂移 `--strict`）。
- `src/arraytx/vendor/polartx`：polar_tx@8a10480 的 `src/polartx` 去掉 GUI 面后原样 vendor（86 个文件，83 verbatim，3 个沿用 polar_tx 的 extended/extracted）；
  pll_simulator@00e48a2 的 `export/clock_profile.py` 单独 vendor（polar_tx 的 pllsim pin 不含它）。`tools/vendor_check.py` 从 polar_tx 改编，只剥两行归属头。
- `config.py`：单一 YAML 真值 + 每个数字的 provenance（survey 块无 ref 不加载）+ 表单字段声明（给以后 GUI）。
- `standards.py`：`fr2_nr400`（28 GHz / 400 MHz / 120 kHz / 264 RB，TS 38.101-2 出处）与 `sub6_nr100`（polar_tx `nr_dtc()` 原样，回归锚）。
- `seeds.py` / `element.py` / `lo.py`：`SeedSequence` 派生每单元每损伤独立流；单元链经 polar_tx 预设工厂建、CFR 外移、包络满刻度固定（DPD 不改工作点）；
  `lo_pn_seed` 共用 LO；时钟剖面经鸭子类型适配器注入。
- `geometry.py` / `beam.py`：频域逐频点远场合成（斜视真算）、相移 / 真延时导向、斜视解析式、最高旁瓣方向。
- `coupling.py` / `touchstone.py`：analytic / survey / touchstone 三来源同一 `CouplingMatrix`、同一 `apply_coupling`；S=0 原样返回；.sNp 读写回读逐位。
- `metrics.py` / `dpd.py` / `sim.py`：OTA 与导通两域指标；none / per_element（导通口 ILA-GMP）/ array（远场 ILA-GMP）；`ArraySim.run_matrix`。
- 示例 ex00–ex04、`tools/fingerprint.py`（record / compare）、74 项测试。

**为什么这样做**

- 单元链不重写：polar_tx 的链是基带等效、增益归一的，直接当 PA 输出进互耦和远场；1 单元 S=0 与 polar_tx 逐位相同是全库的锚。
- CFR 外移与 fs_scale 固定：polar_tx 每次 run 按峰值重新归一化包络，DPD 扩展峰值后工作点会漂移，所以先跑一次参考再钉死。
- 互耦只做线性泄漏：PA_DPD 的 PA 无负载依赖，其 ROADMAP 也没有 load-pull 条目，不在这里编负载调制。

**里程碑数字**（survey 互耦 −16 dB，波束方向 OTA ACLR1，dBc；8 符号全尺寸）

| 扫描角 | 无 DPD | 每单元 ILA-GMP | 全阵列 ILA-GMP（OTA） | 旁瓣方向 无 / 每单元 / 全阵列 |
|---|---|---|---|---|
| 0° | −37.8 | −45.1 | −45.1 | −35.7 / −38.6 / −38.2（+47.1°） |
| 30° | −37.8 | −45.0 | −45.0 | −38.0 / −42.4 / −41.4（−13.4°） |
| 60° | −37.7 | −45.0 | −45.0 | −38.1 / −42.3 / −41.0（+7.7°） |

全阵列 DPD 追回 7.2–7.3 dB；analytic 与 survey 之差 ≤ 0.01 dB；互耦→0 时两种 DPD 差 0.03 dB；带边斜视与解析式误差 0.00 %。
被推翻的判断与原因见 `cairn/LOG.md`、`cairn/architecture-invariants.md`。
