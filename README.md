# array_tx

多单元阵列发射机的行为级仿真框架。每个阵列单元是一条 vendored [polar_tx](https://github.com/alexyudragonsword-collab/polar_tx) 链路；
本库加的是阵列这一层：互耦矩阵进链路、按真实带宽算的波束斜视、阵列级 DPD，以及只在远场（OTA）方向上读的 EVM / ACLR / 谱模板。

状态：里程碑 1 进行中（4 单元 λ/2 线阵、FR2 28 GHz / 400 MHz、三种互耦来源、三种 DPD 方案）。

## 快速开始

```bash
pip install -e .[test]
python examples/ex00_single_element_equals_polartx.py   # sub-6、S=0、1 单元：与 polar_tx 逐位相同
python examples/ex03_scan_angle_x_dpd.py                # 扫描角 × DPD 方案的 OTA EVM / ACLR 表
pytest -q
```

每个示例先打印它用的相位调制引擎；response / dtc_openloop 引擎出的杂散与互调结论一律标"线性化引擎，不能背书"。

## 规则

读 `AGENTS.md`（六条铁律）、`ROADMAP.md`（只写没做的）、`cairn/LOG.md`（数字原值与被推翻的判断）。
