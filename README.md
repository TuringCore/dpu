# DPU: diffusion economics on AWS EC2 F2

## Objective

This repository is a research and deployment path for one question that matters more than any headline TOPS number: can a small DPU tile prove that diffusion inference is economically cheaper on an FPGA-first platform than on a GPU, and therefore justify a custom ASIC?

The project is intentionally scoped to an answerable experiment:

- build a measured baseline for a real diffusion model on a real GPU,
- deploy the DPU tile or a small matrix engine to an AWS EC2 F2 FPGA instance,
- run the same prompt set and scheduler settings on both,
- compare end-to-end images/sec, cost per image, energy per image, and throughput-per-dollar,
- decide whether the ASIC tape-out is justified.

This is not a claim that the final ASIC is done. It is a disciplined path to answer the product question before committing silicon.

## The core experiment

The experiment is a direct, apples-to-apples inference economics check for diffusion generation. The DPU is evaluated as a real system, not as a theoretical chip.

The minimum viable deployment plan is:

1. Choose a model and a test set.
2. Measure a GPU baseline on the same model under the same scheduler, prompt set, step count, resolution, and batching assumptions.
3. Deploy a DPU bitstream to EC2 F2 and measure the same model on the FPGA.
4. Sweep the relevant quantization regime: FP16 baseline, INT8, W8A8, and W4A8 if the pipeline supports it.
5. Use a measured cost model to compute cost per 1,000 images and energy per image.
6. Only then decide whether the ASIC path is credible.

## Why a diffusion economics experiment is the right goal

Diffusion inference is a memory-sensitive, latency-sensitive, and utilization-sensitive workload. The right benchmark is not one-number peak throughput. The right benchmark is:

- image quality at fixed prompts and seeds,
- end-to-end latency per image,
- throughput sustained under operational load,
- total system cost including host, memory, power, cooling, and utilization,
- energy per generated image,
- cost per useful output under a real service model.

A chip that wins on raw arithmetic but loses on memory traffic, utilization, or software stack maturity will not beat a GPU in production.

## Recommended experiment parameters

The repo currently focuses on SDXL, and that is a good first model because it is both relevant and pressure-tested by diffusion generation workloads. The experimental plan should keep the model fixed and vary the hardware and quantization regime.

### Model and workload

Primary workload:

- SDXL base, 1024x1024 output, CFG enabled
- prompt set: 20 to 50 representative prompts, not just one happy-path request
- scheduler: fixed for all runs; e.g. Euler or DPM-style scheduler as chosen by the baseline
- denoising steps: 20 steps for the comparative baseline; optional 30/50 step sweeps for quality/cost tradeoff
- batch size: 1 for latency and economics, plus a small batch sweep for throughput
- seed control: fixed seeds for same outputs across GPU and FPGA runs

Secondary workloads:

- SDXL with lightweight quantized checkpoints
- a smaller diffusion model for saturation and scaling analysis, if needed for FPGA resource planning
- optional `FLUX`-style or other modern diffusion family if the software stack supports it; keep it as a second scene, not the first gate

### Quantization regime

The architecture question is not just “what is the bit-width?” but “what quality and system cost do we actually get?”

Recommended sweep:

- FP16 GPU baseline
- INT8 or W8A8 execution on GPU and DPU
- W4A8 for weights only if the DPU or host runtime can support it without unacceptable quality loss
- optional A16W8 or A8W8 for sensitivity analysis if the software stack and accelerator allow it

For the DPU tile, the most useful evidence comes from a controlled set of comparisons:

- same scheduler and prompt set
- same number of steps
- same output resolution
- same batch assumptions
- same measure of image quality or acceptable divergence vs FP16 reference

The key metric is not just output fidelity. It is quality at a fixed cost budget.

## What to measure on each platform

### GPU baseline

For the GPU, measure the actual deployed system, not just the chip:

- power at wall or board level
- throughput in images/sec
- latency per image under queueing and warm-read conditions
- memory footprint and activation spillover
- software stack: PyTorch/Transformers/Diffusers optimization mode, fused attention, compile options, and quantized runtime
- datacenter instance rental cost or total cost of ownership if running on cloud

This must be done on a real CUDA environment with fixed artifacts and a reproducible request stream.

### FPGA deployment on AWS EC2 F2

For the FPGA path, the measurement must include:

- bitstream build and deployment to the F2 instance
- host-to-device DMA and runtime latency
- utilization of the DPU tile, memory bandwidth, and DRAM transfers
- sustained throughput under the same prompts and scheduler
- energy and total power draw of the FPGA instance
- cost of the EC2 instance plus host overhead and flash/DRAM assumptions

The F2 path proves the architecture under real conditions, not just in simulation. It also exposes whether the real bottleneck is compute, bandwidth, or software orchestration.

## The economic comparison

The design must be compared using the same formula on both paths.

Recommended outputs:

- latency per image
- images/sec at fixed batch size
- energy per image
- cost per 1,000 images
- hardware cost per image over a fixed utilization window
- images/s per hardware dollar
- break-even volume for an ASIC if the FPGA prototype signals that the DPU path is competitive

The repo already contains a cost model in `simulator/economics.py`, and that should be fed by measured values rather than placeholder assumptions.

In other words, the final question is not:

- “What is the peak TOPS of the DPU tile?”

It is:

- “How many equivalent-quality images can we deliver per dollar, per watt, and per hour, under a realistic deployment?”

## Deployment path to AWS EC2 F2

This repo is already organized around a specific, testable deployment flow.

### Stage 1: GPU baseline and loaded workload

- run the SDXL workload and record real latency, throughput, memory, and power
- keep one exact prompt set and fixed seeds
- store all artifacts and inference metadata in a results directory
- record whether the run is FP16, INT8, or quantized GPU runtime

### Stage 2: FPGA DPU prototype on EC2 F2

- synthesize the tile or a small matrix engine to an FPGA bitstream
- deploy to the EC2 F2 instance
- implement a minimal inference host that streams the relevant SDXL subgraphs or a simplified diffusion step
- validate bit-exact numerical behavior against the Python reference or the simulator
- measure the same prompts and seeds as the GPU baseline

### Stage 3: quantization and model sweep

- compare FP16 vs INT8 vs W8A8 vs W4A8 quality and cost
- record the quality-loss frontier at a constant image budget
- determine the minimum quantization that still meets a required quality floor

### Stage 4: economics and tape-out decision

- feed: measured GPU cost, measured FPGA cost, DPU throughput, memory traffic, and power into the simulator
- compute cost per 1,000 images under realistic utilization percentages
- decide whether the DPU can beat the GPU by a meaningful margin at equal quality
- if yes, size the ASIC and define the tape-out path
- if no, stop before ASIC design and redirect effort toward the next bottleneck

## Decision gate

The path is worth continuing only if the measured FPGA prototype shows a credible route to a 2x to 5x cost-per-image advantage at similar quality under realistic utilization.

What would count as compelling evidence?

- same prompt set, scheduler, and seed conditions on GPU and FPGA
- measured latency and power data from both
- reproducible end-to-end inference results
- a DPU configuration that keeps memory and DMA under control
- clear evidence of cost-per-image improvement after accounting for instance, power, and system overhead

Without that evidence, the custom silicon is merely a design hypothesis.

## Long-term service model and ASIC path

Once the FPGA prototype is proven, the natural next step is not “build a chip immediately” but “run a paid inference service on the FPGA path.”

That gives a clean bridge between prototype and ASIC economics:

- run inference at a small service scale on GPU or FPGA,
- record utilization, error rate, queue depth, maintenance overhead, and cash-flow reality,
- learn the cost structure of diffusion serving,
- convert the measured service to a data-center ASIC design target,
- only then commit to silicon with a real economic story.

This is the correct path to a data-center ASIC: not “chip-first,” but “service-first proof, then silicon.”

## Repository shape

The software and hardware pieces already match this plan:

- `rtl/` — DPU tile RTL and verification assets
- `formal/` — proofs and invariants around the tile
- `simulator/` — roofline and economic model for throughput, power, and cost
- `compiler/` and `benchmarks/` — workload extraction and inference benchmarking
- `configs/` — workload, architecture, and economic scenarios
- `tests/` — CPU-only verification for the research pipeline

The key remaining step is measurement discipline: replace placeholder assumptions with real benchmark evidence from GPU and FPGA runs.

## Quick start

```bash
cd /dpu
python -m pip install -e .[dev]
python -m pytest -q
python -m benchmarks.profile --resolution 1024 --steps 20 --output results/sdxl.json
python -m benchmarks.evaluate --workload results/sdxl.json --arch configs/dpu_32tops.json \
  --economics configs/economics_scenario_a.json --gpu configs/gpu_baseline_example.json
```

These commands are tooling scaffolding. The real proof happens when the same workload is measured on an actual GPU and an actual FPGA deployment.

## References and historical context

This repo is aligned with the central real-world lesson of accelerated inference: product economics are determined by total system cost and utilization, not by raw flops in a vacuum.

- NVIDIA RTX 4090 / H100 class systems show how software stack, memory bandwidth, and inference pipeline maturity dominate peak arithmetic claims.
- An FPGA prototype that is slower in absolute throughput but materially cheaper in total system cost can still win the economics test if utilization and power hold.
- A custom ASIC wins only when the measured workload, quantization, and service-level assumptions all line up.

The project path is therefore straightforward: measure the real GPU, measure the real FPGA, prove the DPU economics, then scale toward ASIC tape-out only when the numbers support it.
