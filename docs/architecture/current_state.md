# Current state of the DPU repository (audit)

## What exists
- `rtl/dpu_tile.sv`: single streaming signed-int8 dot-product tile (`DATA_W`=8, `ACC_W`=16 default in the Makefile, `LEN_W`=6), saturating accumulation, `cfg_len`-defined job length, valid/ready on config/input/output, zero-length handling, output held under backpressure.
- `tb/`: randomized self-checking testbench and a cycle-count perf testbench. `formal/`: SymbiYosys prove + cover jobs with a reference model.
- `openlane/` + `docs/SYNTHESIS.md`: SKY130 flow for the tile (`make sky130-synth*`). CI (`.github/workflows/sky130-smoke.yml`) runs sim, formal, lint, synthesis.
- `scripts/perf_report.py`: sim + yosys scorecard.

## What is missing for a diffusion accelerator
Matrix array, SRAM scratchpad, DMA, vector/softmax units, requantization, compiler/scheduler, any workload characterisation, any cost model. Until this milestone there was no evidence for what architecture to build.

## Audit status
- RTL tests (`make sim`, `make formal`) were **not run** in the audit environment: `iverilog`, `yosys`, `sby`, `verilator` are not installed there. No pre-existing failures were observed, but none were verified either; CI is the reference.
- RTL, SKY130 configs and docs were not modified. SKY130 synthesis says nothing about production-node PPA.

## Mapping tile -> matrix engine (plan, no RTL yet)
One `dpu_tile` is one MAC lane with a serial reduction. A matrix engine is an R x C array of such lanes sharing broadcast operands, with ACC_W widened to >= 2*DATA_W + ceil(log2(K)) (or kept saturating by design), plus a requantisation stage. The saturating semantics of the tile define the reference for accumulator behaviour. RTL extensions are deferred until the simulator picks a configuration.

## New in this milestone (Python only)
`compiler/` (workload schema, static SDXL graph, optional torch profiler), `benchmarks/` (CLIs), `simulator/` (roofline, economics), `configs/`, `tests/`.
