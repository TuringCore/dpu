"""CLI: workload JSON + arch config + economics scenario + GPU baseline -> SIMULATED comparison report."""
from __future__ import annotations

import argparse
import json

from compiler.workload import Workload
from simulator.config import ArchConfig
from simulator.economics import compare, load_economics, load_gpu, to_dict
from simulator.roofline import by_kind, simulate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workload", required=True)
    p.add_argument("--arch", required=True)
    p.add_argument("--economics", required=True)
    p.add_argument("--gpu", required=True)
    p.add_argument("--output")
    a = p.parse_args(argv)
    wl, arch = Workload.load(a.workload), ArchConfig.load(a.arch)
    sim = simulate(wl, arch)
    cmp = compare(load_economics(a.economics), sim.images_per_s, load_gpu(a.gpu))
    report = {
        "label": "SIMULATED; economics inputs are ASSUMPTIONS; GPU baseline label shown in comparison",
        "workload": {"model": wl.model, "resolution": wl.resolution, "steps": wl.steps,
                     "batch_size": wl.batch_size, "provenance": wl.provenance},
        "arch": arch.name,
        "latency_s": sim.total_latency_s, "step_latency_s": sim.step_latency_s,
        "images_per_s": sim.images_per_s, "compute_utilization": sim.compute_utilization,
        "dram_bytes_per_image_step": sim.dram_bytes_per_step,
        "bound_time_share": sim.bound_time_share, "time_by_op_kind_s": by_kind(sim),
        "notes": sim.notes, "economics": to_dict(cmp),
    }
    text = json.dumps(report, indent=2)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
