"""Optional MEASURED profiling of the real SDXL pipeline (needs torch + diffusers + CUDA).

Not exercised by CPU CI. Imports are lazy so the rest of the package works without torch.
Records per-leaf-module GPU time (CUDA events), memory, and end-to-end latency. Module
types without a mapping are reported under ``unsupported`` instead of being dropped.
"""
from __future__ import annotations

from typing import Any

SUPPORTED = ("Conv2d", "Linear", "GroupNorm", "LayerNorm", "SiLU", "GELU", "Dropout", "Identity",
             "Upsample", "LoRACompatibleConv", "LoRACompatibleLinear")


def cuda_available() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except ImportError:
        return False


def measure_sdxl(workload_meta: dict[str, Any], model_id: str, revision: str | None,
                 prompt: str, seed: int = 0, warmup: int = 1) -> dict[str, Any]:
    """Run the SDXL pipeline on CUDA and return a ``measured`` dict (raises if CUDA missing)."""
    import torch
    from diffusers import StableDiffusionXLPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable: GPU timings cannot be measured")
    dtype = torch.float16 if workload_meta["dtype"] == "fp16" else torch.bfloat16
    pipe = StableDiffusionXLPipeline.from_pretrained(model_id, revision=revision, torch_dtype=dtype).to("cuda")
    res, steps = workload_meta["resolution"], workload_meta["steps"]
    bs = workload_meta["batch_size"]

    def run() -> None:
        g = torch.Generator("cuda").manual_seed(seed)
        pipe(prompt=[prompt] * bs, height=res, width=res, num_inference_steps=steps, generator=g)

    for _ in range(warmup):
        run()
    torch.cuda.synchronize()

    stats: dict[str, dict[str, Any]] = {}
    unsupported: dict[str, int] = {}
    handles = []

    def make(name: str):
        def pre(_m, _i):
            s = torch.cuda.Event(enable_timing=True)
            s.record()
            stats[name]["_s"].append(s)

        def post(_m, _i, _o):
            e = torch.cuda.Event(enable_timing=True)
            e.record()
            stats[name]["_e"].append(e)
        return pre, post

    for name, mod in pipe.unet.named_modules():
        if next(mod.children(), None) is not None:
            continue
        t = type(mod).__name__
        if t not in SUPPORTED:
            unsupported[t] = unsupported.get(t, 0) + 1
            continue
        stats[name] = {"type": t, "_s": [], "_e": []}
        pre, post = make(name)
        handles += [mod.register_forward_pre_hook(pre), mod.register_forward_hook(post)]

    torch.cuda.reset_peak_memory_stats()
    t0, t1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    t0.record()
    run()
    t1.record()
    torch.cuda.synchronize()
    for h in handles:
        h.remove()
    per_module = []
    for name, s in stats.items():
        ms = sum(a.elapsed_time(b) for a, b in zip(s["_s"], s["_e"]))
        per_module.append({"name": name, "type": s["type"], "calls": len(s["_s"]), "total_ms": ms})
    return {
        "provenance": "measured",
        "end_to_end_latency_s": t0.elapsed_time(t1) / 1e3,
        "peak_gpu_memory_bytes": int(torch.cuda.max_memory_allocated()),
        "per_module": per_module,
        "unsupported_module_types": unsupported,
        "device": torch.cuda.get_device_name(0),
        "versions": {"torch": torch.__version__, "cuda": torch.version.cuda},
        "model_id": model_id, "revision": revision, "seed": seed,
        "note": "hook timing is per leaf module; fused attention/SDPA is not a module and is not captured separately",
    }
