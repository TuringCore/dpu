# SDXL benchmark audit

**Audit snapshot:** repository tip `ec9e6d6` (merge of PR #9; latest implementation change
`5c09b61`), inspected 2026-10-25. The available clone is shallow and has no local `main`
ref; findings apply to the checked-out tip. “PASS” means the code or evidence meets the
stated requirement, not that a run occurred unless explicitly stated.

## Requirement assessment

| Requirement | Assessment | Evidence and limitation |
|---|---|---|
| Profiler loads the requested Hugging Face checkpoint | **PASS (code path); NOT VERIFIED (execution)** | `compiler/torch_profiler.py` loads `StableDiffusionXLPipeline.from_pretrained`; revision is optional in the legacy CLI. This environment has neither torch nor Diffusers, so no weights were loaded. |
| Quantization transforms weights and changes execution | **FAIL (before this change)** | Existing `weight_bits` fields only configure the analytical simulator; no inference quantizer exists. The new `benchmarks/run_sdxl.py` adds an optional bitsandbytes INT8-weight path for UNet linear layers and checks runtime INT8 quantization state. It has not been executed here. |
| Complete 1024², batch-1, 20-step SDXL generation | **NOT VERIFIED** | Existing profiler can call the full pipeline, but only one timed run is implemented and no run artifacts exist. Runtime dependencies, CUDA, and GPU are absent here. |
| Real executed graph, tensor shapes, and arithmetic requirements | **FAIL** | `compiler/sdxl_graph.py` builds a guessed, unfused static UNet graph from constants; it omits VAE/text encoders. The old CUDA profiler records leaf-module time, not tensor shapes or operator-level MACs. The new runner captures profiler shapes and a module graph on GPU, but those artifacts are not available yet. |
| GPU device timing and synchronization | **NOT VERIFIED** | Existing code uses CUDA events and synchronizes once around a single measured call. It lacks repeated samples/median and a fixed scheduler. The new runner uses synchronized wall-clock samples and records denoiser CUDA events, but no GPU run was possible. |
| Simulator consumes the exact quantized graph/configuration | **FAIL** | `benchmarks.evaluate` consumes a workload JSON; no bridge exists from executed PyTorch traces to the static workload, and quantized weights are not extracted. |
| Simulator models memory, SRAM, compute, and unsupported ops | **FAIL** | The roofline model has coarse bandwidth/SRAM/compute and fixed DMA-startup estimates, but no dependency scheduling or tiling calibration. It formerly skipped `supported=False` operators; it now raises rather than returning a misleading partial latency. This is still an analytical model, not cycle-level or numerical execution. |
| Model quality versus a reference | **FAIL (before this change); NOT VERIFIED (new runner)** | No prior evaluation exists. The new runner requires a matching FP16 image for INT8 and reports paired pixel MSE/PSNR, which is only a numerical proxy—not a semantic image-quality metric. No comparison was run. |
| Verified benchmark results prominently documented | **FAIL (before this change)** | README previously described future GPU measurements and a static/placeholder comparison. This audit adds an explicit status table; all execution values remain “Not measured” or “Not simulated.” |
| Economic comparison grounded in measured data | **FAIL** | `simulator/economics.py` is an assumption-driven scenario model; the example GPU, hardware costs, power, utilization, and volumes are placeholders. No cost-per-image conclusion is supportable. |

## Checks run and observed blocker

- `python -m benchmarks.profile --model sdxl --resolution 1024 --steps 20 --measure --output /tmp/dpu-sdxl-static.json`
  completed only the static path: 1,841 guessed ops and 6,761.2 GMAC per UNet forward. It
  printed that CUDA timings were **not measured**.
- `python -m benchmarks.evaluate ...` with the existing 32-TOPS, economics, and GPU example
  configurations produced an analytical output. It is not a measured DPU/GPU comparison:
  VAE/text encoders are absent and all GPU/economic inputs are assumptions.
- Python 3.12.3 is present; `torch`, `diffusers`, `transformers`, `bitsandbytes`, and `pytest`
  are absent. `nvidia-smi` is not installed and `torch.cuda.is_available()` cannot be checked
  because torch is absent. Thus GPU availability and model-accessible revision could not be
  verified. The Hugging Face API lookup was blocked by DNS/network restrictions.
- See [`benchmarks/results/execution_blocker.json`](../../benchmarks/results/execution_blocker.json)
  for the machine-readable environment blocker.

## Regression / misleading-claim review

- Static SDXL constants and the 6.76-TMAC figure are not checked against the pinned checkpoint.
- The analytical simulator is sequential and assumes optimistic operator-level overlap/buffering;
  no discrete-event schedule, real DMA trace, simulator calibration, or hardware reference exists.
- Quantization bit-width in architecture files is not evidence of device arithmetic. Only the new
  optional benchmark path attempts INT8 weight conversion; convolution and the text/VAE components
  remain FP16, and the execution path still requires real backend verification.
- The former unsupported-op skip could make a partial workload appear complete; unsupported and
  unknown operation kinds now cause a hard error.
- The current roadmap's scaling, SoC, and tape-out work remains planned; this repository has a
  single RTL dot-product tile, not an SDXL-capable DPU.
- The configured DPU power, throughput, and economics are assumptions. The README table does not
  promote any of them to measured results.

## Remaining work before an apples-to-apples result

1. Run the new pinned-revision FP16 and bitsandbytes INT8 commands on a CUDA GPU; retain complete
   result JSON, profiler trace, module graph, images, and versions. Evaluate semantic quality
   against an accepted reference metric in addition to pixel error.
2. Build a validated importer from those exact runtime traces and quantization metadata to a
   workload schema that accounts for all operators, shapes, weights, and per-image pipeline
   components. Refuse unsupported operators.
3. Implement/calibrate a dependency-aware DPU performance model, validate memory and compute
   estimates against microbenchmarks, then simulate the same workload under all three supplied
   architecture configurations.
4. Obtain measured GPU power and defensible DPU power/cost inputs before publishing throughput,
   energy, or cost comparisons. Never interpret modeled timing as silicon measurement.

No GPU run, model download, quality comparison, or exact-workload DPU simulation is claimed by
this audit.
