# DPU: a diffusion-inference accelerator research platform

## The objective

This repository is a small, verification-friendly diffusion processing unit (DPU) prototype aimed at one thing: reducing the cost and uncertainty of running diffusion inference on real silicon.

The goal is not to build a heroic chip on day one. The goal is to answer the economic and architectural questions *before* committing to silicon, and to validate the answer on an FPGA first:

- Which SDXL operators dominate, and are they compute- or memory-bound?
- How much quantization, SRAM and external bandwidth does a competitive design need?
- Can a fixed-function accelerator reach at least a 2x lower cost per equivalent-quality image than an optimized GPU?
- Is the datapath correct under signed arithmetic and backpressure?

## SDXL Inference Benchmarks

**Status: no real GPU inference or exact-workload DPU simulation has been verified.** The
environment audit could not load the model or establish GPU availability. No performance,
power, image-quality, or cost result below is represented as a measurement.

<!-- SDXL_BENCHMARK_TABLE:START -->
| Metric | GPU FP16 | GPU Quantized | Turing DPU Simulated |
| --- | --- | --- | --- |
| Model | SDXL base 1.0; revision not resolved | SDXL base 1.0; revision not resolved | Exact quantized workload unavailable |
| Precision | Not measured | Not measured | Not simulated |
| End-to-end latency | Not measured | Not measured | Not simulated |
| Images per second | Not measured | Not measured | Not simulated |
| Memory requirement | Not measured | Not measured | Not simulated |
| Power | Not measured | Not measured | Not estimated |
| Cost per 1,000 images | Not calculated | Not calculated | Not calculated |
| Measurement status | Not run: environment blocker | Not run: environment blocker | Not simulated from an executed graph |
<!-- SDXL_BENCHMARK_TABLE:END -->

GPU columns are intended for synchronized measurements of actual CUDA inference. DPU figures,
when available, will be analytical performance estimates—not measured silicon performance.
The static graph and placeholder economic examples elsewhere in this README are not comparable
benchmark results. Full audit and limitations: [`docs/research/benchmark_audit.md`](docs/research/benchmark_audit.md);
environment blocker: [`benchmarks/results/execution_blocker.json`](benchmarks/results/execution_blocker.json).

To reproduce on a CUDA machine, install the GPU dependencies and bitsandbytes:

```bash
python -m pip install "torch>=2.1" "diffusers>=0.27" "transformers>=4.38" \
  "accelerate>=0.27" bitsandbytes
```

Pin the exact
40-character model commit SHA and use that same SHA for both commands; the scheduler, dimensions,
steps, guidance, prompt, and seed are fixed by the runner:

```bash
python -m benchmarks.run_sdxl --revision <40-character-model-commit-sha> --mode fp16 \
  --output-dir benchmarks/results/fp16
python -m benchmarks.run_sdxl --revision <same-commit-sha> --mode bnb-int8 \
  --reference-results benchmarks/results/fp16/results.json \
  --output-dir benchmarks/results/bnb-int8
```

Each successful run writes machine-readable `results.json`, raw synchronized latency samples,
`operator_trace.json`, `module_graph.json`, profiler operator summaries, and the generated image.
The quantized command validates that the FP16 artifact uses the same model revision, prompt,
seed, scheduler, and generation settings. INT8 reports runtime quantized-state evidence and
paired pixel MSE/PSNR; pixel error is not a semantic image-quality metric. The DPU simulator
does not yet import these runtime traces, so no
exact-workload DPU command or result is claimed. Three explicitly hypothetical architecture
inputs are in `configs/dpu_low_cost.json`, `configs/dpu_balanced.json`, and
`configs/dpu_high_performance.json`.

After creating both GPU artifacts, refresh the table with
`python -m benchmarks.readme_table --results-dir benchmarks/results --readme README.md`.

The design here is intentionally narrow: a signed `int8` dot-product tile with saturating accumulation, valid/ready interfaces, and explicit edge handling. That is enough to capture the core diffusion workload without pretending the full accelerator is already solved.

## What is in this repo

Hardware (unchanged):

- `rtl/dpu_tile.sv` — core DPU tile RTL
- `tb/` — simulation and cycle-count testbenches
- `formal/` — formal properties, reference model, SymbiYosys jobs
- `Makefile` — `make sim`, `make formal`, `make perf`
- `docs/architecture.md`, `docs/verification.md`, `docs/roadmap.md` — architecture, verification, scaling notes
- `openlane/`, `docs/SYNTHESIS.md` — earlier SKY130 block-hardening setup, retained for reference only and no longer the project path

Research platform (Python 3.11+, milestone 1):

- `compiler/` — versioned workload schema (`dpu-workload/1`), static SDXL UNet graph, optional CUDA profiler (`torch_profiler.py`)
- `benchmarks/profile.py` — profiling CLI; `benchmarks/evaluate.py` — workload + architecture + economics + GPU baseline -> report
- `simulator/` — `config.py` (architecture parameters), `roofline.py` (analytical roofline model), `economics.py` (cost model)
- `configs/` — example architecture, economics and GPU-baseline files (**placeholders, not real quotes or measurements**)
- `tests/` — CPU-only pytest suite; CI in `.github/workflows/python-research.yml`
- `docs/architecture/current_state.md` — repository audit; `docs/research/diffusion_accelerator.md` — findings, evidence vs hypotheses

## Why this is the right first silicon

Diffusion workloads spend most of their compute in repeated multiply-accumulate patterns. The simplest useful building block is therefore not a full accelerator, but a tile that can be reasoned about completely:

- signed `int8` operands
- saturating accumulation
- explicit lengths via `cfg_len`
- valid/ready handshake
- zero-length handling
- stable output under backpressure

That is exactly the kind of primitive that can be made small enough to prove, stable enough to prototype on an FPGA, and useful enough to scale later.

## Economic rationale

Custom silicon is not automatically cheaper than a GPU: the case depends on a stable, high-volume workload, measured end-to-end efficiency, and amortizing development and manufacturing costs. Compare complete systems (memory, host, power, utilization, support), not chip or hourly prices. Hardware purchase cost is kept separate from cloud rental prices.

The central question: **can a diffusion-specialized ASIC, using ahead-of-time quantization and an optimized memory hierarchy, achieve at least 2x lower cost per equivalent-quality image than an optimized GPU?** Everything below exists to answer that rigorously.

## The experiment that justifies (or kills) the ASIC

1. **Measure the GPU baseline** (real, not assumed). With CUDA and `pip install .[gpu]`:
   `python -m benchmarks.profile --model sdxl --resolution 1024 --steps 20 --measure --output results/sdxl.json`
   Records per-module GPU time, peak memory and end-to-end latency, tagged `measured`. Repeat on the best optimized configuration available (fused attention, `torch.compile`, TensorRT, FP8/INT8) on e.g. RTX 4090/5090 and a datacenter GPU. Without CUDA the tool emits a static estimate only and says timings were not measured.
2. **Characterise the workload.** The versioned JSON holds per-operator MACs (1 MAC = 2 FLOPs), weight/activation sizes and arithmetic intensity, with measured and static data kept distinct.
3. **Simulate candidate DPUs** with the analytical roofline model (`simulator/roofline.py`): INT8/INT4 throughput, SRAM, DRAM bandwidth/capacity, DMA cost, softmax/vector cost. The current model streams weights from DRAM and does not model on-chip weight caching. Results are labelled SIMULATED.
4. **Price it** with `simulator/economics.py`: die area, wafer price, yield, packaging, memory, board, host, cooling/PUE, NRE, volume, utilization, electricity, lifetime. All inputs are user-supplied scenarios; no foundry prices are built in. Outputs: cost per 1,000 images, energy per image, images/s per hardware dollar, break-even volume, utilization/yield sensitivity, and the throughput needed for a 2x/3x/5x advantage.
5. **Decide.** Replace `configs/gpu_baseline_example.json` and `configs/economics_scenario_a.json` with measured and quoted values:
   ```bash
   python -m benchmarks.evaluate --workload results/sdxl.json --arch configs/dpu_32tops.json \
       --economics configs/economics_scenario_a.json --gpu configs/gpu_baseline_example.json
   ```
   If no plausible parameter set reaches 2x at equal image quality, stop before building silicon.

Current status: with placeholder inputs the example 32-TOPS DPU is *worse* than the placeholder GPU (0.38x). That demonstrates the tooling only; it is not evidence either way. The ~6.76-TMAC/step SDXL value (CFG on, 1024x1024, unfused attention) and ~97% compute-bound result are static analytical estimates, not cross-checked against loaded weights or executed operators. See `docs/research/diffusion_accelerator.md` and the benchmark audit above.

Still to build: discrete-event simulator, quantization quality experiments (INT8, W4, W4A8), architecture frontier search, parameter sweeps.

## Path to hardware: FPGA prototype first

FPGA is the prototype vehicle, replacing the earlier SKY130 shuttle plan. It validates RTL and the dataflow without a tape-out, and gives real, measured numbers to calibrate the simulator. It does **not** demonstrate production-ASIC PPA; FPGA clocks, area and power must not be extrapolated naively to an ASIC.

Planned stages (none implemented yet beyond stage 0):

0. **Existing tile**: signed int8 dot product with saturating accumulation, proven in simulation and formally. Synthesizes to any FPGA toolchain unchanged.
1. **Reusable components**, each with a self-checking testbench (formal where practical): parameterized MAC-array wrapper built from the tile semantics, explicit accumulator-width handling, configurable requantization/rescaling, a simple SRAM scratchpad interface (BRAM/URAM), and a basic DMA command interface.
2. **Single matrix engine on a mid-range FPGA card** (an accelerator card with HBM or DDR is preferable so bandwidth is realistic). Run INT8 GEMM and convolution layers extracted from the SDXL workload JSON.
3. **Calibrate the simulator**: compare measured cycles, utilization and DRAM traffic per layer against the roofline model; fix the model where they disagree.
4. **Scale-out study**: use the calibrated model to choose array size, SRAM and bandwidth for an ASIC, then decide on silicon using the economics above.

Success criteria for the FPGA stage: bit-exact match with the reference model on real layer data, and simulator-vs-hardware per-layer cycle error documented. The architecture should be chosen by the simulator; do not build large RTL before it points at a configuration.

## Quick start

```bash
pip install "pytest>=8"
python -m pytest -q                     # CPU-only tests
python -m benchmarks.profile --resolution 1024 --steps 20 --output results/sdxl.json
make sim                                # RTL simulation (needs iverilog)
make formal                             # formal proofs (needs yosys + sby)
```

Generated results under `results/` and model artifacts are not committed.

## References

- [SymbiYosys](https://symbiyosys.readthedocs.io/)
- [Hugging Face Diffusers](https://huggingface.co/docs/diffusers)
