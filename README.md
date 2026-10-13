# array_tx

多单元阵列发射机的行为级仿真框架。每个阵列单元是一条 vendored [polar_tx](https://github.com/alexyudragonsword-collab/polar_tx) 链路；
本库加的是阵列这一层：互耦矩阵进链路、按真实带宽算的波束斜视、阵列级 DPD，以及只在远场（OTA）方向上读的 EVM / ACLR / 谱模板。
polar_tx 的姊妹库（polar_tx ROADMAP D：GUI 里不再加架构、不做接收机）。

状态：里程碑 1 完成——4 单元 λ/2 线阵、FR2 28 GHz / 400 MHz / 120 kHz、三种互耦来源、三种 DPD 方案、OTA 指标。
数字见 `cairn/LOG.md`，没做的见 `ROADMAP.md`。

## 快速开始

```bash
pip install -e ".[test,dev]"
python examples/ex00_single_element_equals_polartx.py   # sub-6、S=0、1 单元：与 polar_tx 逐位相同
python examples/ex03_scan_angle_x_dpd.py                # 扫描角 × DPD 方案的 OTA EVM / ACLR 表
pytest -q                                               # 82 项
ARRAYTX_SMOKE=1 python examples/ex04_aclr_vs_direction.py   # 短突发（CI 用的尺寸）
```

每个示例先打印它用的相位调制引擎；response / dtc_openloop 引擎出的杂散与互调结论一律标"线性化引擎，不能背书"。

## 一次仿真的数据流

```
standard（制式）→ 波形 x → CFR（公共）→ [DPD] → 导向（相移 | 真延时）
  → 单元 k 的 polar_tx 链路 → y_k（导通口，只做诊断）
  → apply_coupling：r_k = y_k + Σ_j S_kj(f)·y_j   （三种来源，同一条路径）
  → far_field(θ)：频域逐频点相位 → OTA EVM / ACLR / SEM（波束方向 + 旁瓣方向）
```

```python
from arraytx import ArraySim, load_config
sim = ArraySim(load_config("configs/fr2_4el_survey.yaml"))
r = sim.run(theta0_deg=30.0, scheme="array")      # none | per_element | array
print(r.info["engine_line"]); print(r.beam.row()); print(r.sidelobe.row())
```

## 配置（铁律 1：唯一真值）

`configs/fr2_4el_survey.yaml` 是默认配置，其它三个只改一个块：

| 文件 | 差别 |
|---|---|
| `fr2_4el_survey.yaml` | 默认：survey 互耦（相邻 −16 dB，相位随频率线性走） |
| `fr2_4el_analytic.yaml` | `coupling.source: analytic`（频率平坦） |
| `fr2_4el_touchstone.yaml` | `coupling.source: touchstone`，读由 analytic 写出的 `.s4p`（逐位相同） |
| `sub6_1el_anchor.yaml` | sub-6、1 单元、S = 0、单元误差关：与 polar_tx 逐位相同的回归锚 |

外部数字写成 `{value, source, ref}`；纯标量就是 `source: assumed`。`coupling.survey` 块里没有 ref 的数字加载时直接报错。
每个字段的单位 / 说明 / 取值在 `arraytx.config.form_fields()` 里声明（给以后的 GUI 用）。

## 示例

| 示例 | 看什么 |
|---|---|
| `ex00_single_element_equals_polartx` | 1 单元 = polar_tx `nr_dtc().run()` 逐位相同；OTA 与导通指标重合 |
| `ex01_coupling_sources` | analytic / survey / touchstone 同台；touchstone == analytic 逐位 |
| `ex02_coupling_strength_sweep` | 互耦从 0 扫到 −10 dB，三方案 OTA ACLR / EVM；S=0 时收敛 |
| `ex03_scan_angle_x_dpd` | 0 / 30 / 60° × 三方案，波束与旁瓣方向；带边斜视 vs 解析；导通诊断 |
| `ex04_aclr_vs_direction` | ACLR 随方向：非线性互调往哪辐射（方向图零点已标出） |

## 模块

| 模块 | 职责 | 铁律 |
|---|---|---|
| `config.py` | YAML → 数据类树，provenance，表单字段声明 | 1 |
| `standards.py` | `fr2_nr400`（TS 38.101-2 出处）、`sub6_nr100`（polar_tx 原样） | — |
| `seeds.py` | `SeedSequence` 派生：每单元、每损伤独立流 | 5 |
| `element.py` / `lo.py` | polar_tx 预设建链、固定 fs_scale、单元误差抽了再置零、共用 LO / 时钟剖面 | 5 |
| `geometry.py` / `beam.py` | 线阵几何、相移 / 真延时导向、频域远场合成、斜视解析式 | 4 |
| `coupling.py` / `touchstone.py` | 三来源 → `CouplingMatrix` → 唯一的 `apply_coupling`；.sNp 读写 | 3 |
| `metrics.py` | `ota_metrics`（验收）与 `conducted_metrics`（诊断） | 2 |
| `dpd.py` | none / per_element（导通口 ILA-GMP）/ array（远场 ILA-GMP） | — |
| `sim.py` / `report.py` | `ArraySim` 串联；引擎行与免责声明 | — |
| `tools/fingerprint.py` | 重构前后逐位比对 | 6 |
| `tools/vendor_check.py` | vendor 树对上游 pin 的漂移检查（`--strict`） | — |

## 规则

读 `AGENTS.md`（六条铁律）、`ROADMAP.md`（只写没做的）、`cairn/LOG.md`（数字原值与被推翻的判断）、`CONTRIBUTING.md`。
