# 变更日志

按里程碑记录做了什么、为什么。没做的在 `ROADMAP.md`。

## 未发布 / Unreleased

### 共用 LO 接真实时钟剖面：pll_simulator 的 18 个预设随包提供，EVM / ACLR 随 LO 扫描（2026-10-13）

- `src/arraytx/data/clock_profiles/`：pll_simulator@00e48a2 用自己的 `export --clock-profile` 导出的全部 18 个预设（文件内 `source:` 行带提交号），未经编辑。
  config 里 `element.lo.clock_profile: "bundled:<preset>"`，或相对 config 文件的路径。
- `lo.py`：`resolve_profile`、`list_bundled`、`rms_phase_rad`（可按 DTC 的锁定近似在环路带宽以下压平）。剖面按 (f_c / f0)² 换算到载频。
- 示例 ex05 与 5 项测试。数字见 `cairn/LOG.md`。
- 为什么：FR2 链的 EVM 完全由 LO 决定（上一条 LOG），而共用 LO 这条路此前只用合成夹具测过。

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
| 0° | −37.8 | −45.5 | −45.5 | −35.7 / −38.7 / −38.4（+47.1°） |
| 30° | −37.8 | −45.5 | −45.4 | −38.0 / −42.4 / −41.8（−13.4°） |
| 60° | −37.7 | −45.4 | −45.3 | −38.1 / −42.3 / −41.4（+7.7°） |

全阵列 DPD 追回 7.6–7.7 dB；analytic 与 survey 之差 ≤ 0.01 dB；互耦→0 时两种 DPD 差 0.09 dB；带边斜视与解析式误差 0.00 %。
默认 GMP 是无记忆 7 阶（7 系数）：扫描表明这条链几乎无记忆，记忆抽头只伤 ACLR2（`cairn/LOG.md`）。
被推翻的判断与原因见 `cairn/LOG.md`、`cairn/architecture-invariants.md`。
