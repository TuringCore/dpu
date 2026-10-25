"""CLI: python -m benchmarks.profile --model sdxl --resolution 1024 --steps 20 --output results/sdxl.json"""
from __future__ import annotations

import argparse
import os
import platform
import sys

from compiler.sdxl_graph import build_sdxl_workload
from compiler.torch_profiler import cuda_available, measure_sdxl


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model", default="sdxl", choices=["sdxl"])
    p.add_argument("--resolution", type=int, default=1024)
    p.add_argument("--steps", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--dtype", default="fp16", choices=["fp16", "bf16"])
    p.add_argument("--no-guidance", action="store_true")
    p.add_argument("--measure", action="store_true", help="also run real pipeline on CUDA")
    p.add_argument("--model-id", default="stabilityai/stable-diffusion-xl-base-1.0")
    p.add_argument("--revision", default=None, help="HF revision to pin (recorded in output)")
    p.add_argument("--prompt", default="a photograph of an astronaut riding a horse")
    p.add_argument("--output", required=True)
    a = p.parse_args(argv)

    wl = build_sdxl_workload(a.resolution, a.batch_size, a.steps, not a.no_guidance, a.dtype)
    wl.environment = {"python": sys.version.split()[0], "platform": platform.platform()}
    if a.measure:
        if not cuda_available():
            print("CUDA unavailable: GPU timings NOT measured; emitting static estimate only.", file=sys.stderr)
        else:
            wl.measured = measure_sdxl(wl.to_dict(), a.model_id, a.revision, a.prompt)
            wl.provenance["timing"] = "measured"
    os.makedirs(os.path.dirname(os.path.abspath(a.output)), exist_ok=True)
    wl.to_json(a.output)
    print(f"wrote {a.output}: {len(wl.ops)} ops, {wl.total_macs()/1e9:.1f} GMACs per UNet forward "
          f"(static estimate, 1 MAC = 2 FLOPs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
