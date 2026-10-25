# Diffusion accelerator research (milestone 1)

Legend: **[E]** evidence reproducible from this repo's code; **[H]** hypothesis; **[A]** assumption. No GPU was available, so **no measured results exist yet**.

## Reproduce
```
pip install pytest
python -m pytest -q
python -m benchmarks.profile --model sdxl --resolution 1024 --steps 20 --output results/sdxl.json
python -m benchmarks.evaluate --workload results/sdxl.json --arch configs/dpu_32tops.json \
   --economics configs/economics_scenario_a.json --gpu configs/gpu_baseline_example.json
```
With CUDA + `pip install .[gpu]`, add `--measure` to record real per-module timings, peak memory and latency (`compiler/torch_profiler.py`, untested in CI). Counting convention: 1 MAC = 2 FLOPs.

## Findings
- **[E] Workload (static estimate, unfused attention, CFG on, 1024², batch 1):** ~6.76 TMACs (13.5 TFLOPs) per denoising step; ~2.57 B UNet weights. Static graph is derived from the SDXL-base config constants and not yet cross-checked against a loaded checkpoint (**unverified**). VAE and text encoders are not modelled.
- **[E] Dominant operators (32-TOPS example, INT8):** linear/GEMM layers (incl. attention projections and GEGLU) take ~54% of step time, convolutions ~20%, softmax ~13% (cost factor is **[A]**), attention matmuls ~10%.
- **[E under the model] Compute- vs memory-bound:** ~97% of step time is compute-bound at 200 GB/s because the model streams ~35 GB/step of traffic (INT8) against ~0.7 s compute. Activation spill is included; the model ignores tiling inefficiency, so this is optimistic about memory.
- **Quantization benefit, SRAM value, bandwidth need, minimum viable configuration:** not yet answered; need parameter sweeps (`simulator.roofline.sweep` exists) and the quantization framework (next milestone). **[H]** W4 halves weight traffic but not compute.
- **Economics [A]:** with placeholder inputs (config files labelled as such) the example 32-TOPS DPU does *not* beat the placeholder GPU (advantage 0.38x, ~0.07 images/s vs 0.5 placeholder). This only shows the tooling works; it supports no conclusion about the 2x question.

## Uncertainties
Real GPU throughput (must be measured, incl. optimized attention/compile/TensorRT), foundry/memory/packaging costs, achievable utilization, fused-attention memory traffic, VAE/text encoder cost, quality loss from INT8/INT4.

## Next experiment
Measure SDXL on a real GPU with `--measure` (and an optimized baseline), replace `gpu_baseline_example.json` with that result, then run bandwidth/SRAM sweeps and size the array against the 2x/3x/5x required-throughput outputs.
