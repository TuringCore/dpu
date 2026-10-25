"""Level-A analytical roofline model. Output is SIMULATED, not measured.

Per operator: time = dma_startup + max(compute_time, dram_time, sram_time)
  * MAC ops: macs / (int8_tops/2 * 1e12 * util [* int4 speedup if weights and acts are 4-bit-capable])
    INT4 speedup applies only when weight_bits == 4 (W4A8 assumed to run at the INT8 MAC rate
    unless ``int4_speedup`` > 1 is explicitly hypothesised; default config uses the INT8 rate for W4A8).
  * Vector ops: elems (x softmax_cost for softmax) / vector throughput.
  * DRAM traffic: weights are streamed from DRAM once per op per denoising step (never assumed
    resident). Activations: inputs and outputs spill to DRAM only if the op's in+out footprint
    exceeds the activation share of SRAM; otherwise they stay on chip. Unfused attention scores
    therefore spill when large. W4 weights are dequantised on the fly (conversion cost charged).
No tiling/reuse inefficiency beyond ``compute_utilization`` is modelled here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from compiler.workload import MAC_KINDS, Op, Workload

from .config import ArchConfig

LABEL = "SIMULATED (analytical roofline); not a measurement"


@dataclass
class OpResult:
    name: str
    kind: str
    time_s: float
    compute_s: float
    dram_s: float
    sram_s: float
    dram_bytes: float
    bound: str
    spilled: bool


@dataclass
class SimResult:
    label: str
    arch: str
    per_op: list[OpResult] = field(default_factory=list)
    step_latency_s: float = 0.0
    total_latency_s: float = 0.0
    images_per_s: float = 0.0
    compute_utilization: float = 0.0
    dram_bytes_per_step: float = 0.0
    dram_bytes_total: float = 0.0
    max_sram_footprint_bytes: float = 0.0
    bound_time_share: dict[str, float] = field(default_factory=dict)
    weights_fit_on_chip: bool = False
    weights_fit_dram: bool = True
    notes: list[str] = field(default_factory=list)


def _op_time(op: Op, a: ArchConfig) -> OpResult:
    wb, ab = a.weight_bits / 8, a.act_bits / 8
    weight_b = op.weight_elems * wb
    act_b = (op.input_elems + op.output_elems) * ab
    act_cap = a.sram_mb * 1e6 * a.sram_act_fraction
    spilled = act_b > act_cap
    dram_b = weight_b + (act_b if spilled else 0)
    if op.kind in MAC_KINDS:
        rate = a.int8_tops / 2 * 1e12 * a.compute_utilization
        if a.weight_bits == 4:
            rate *= a.int4_speedup
        compute = op.macs / rate
    else:
        scale = a.softmax_cost_per_elem if op.kind == "softmax" else 1.0
        compute = op.vector_elems * scale / (a.vector_gelems_per_s * 1e9)
    if a.weight_bits == 4 and op.weight_elems:
        compute += op.weight_elems / (a.precision_convert_gelems_per_s * 1e9)
    dram = dram_b / (a.dram_bw_gbs * 1e9)
    sram = (weight_b + act_b) / (a.sram_bw_gbs * 1e9)
    t = max(compute, dram, sram)
    bound = "compute" if t == compute else ("dram" if t == dram else "sram")
    if dram_b:
        t += a.dma_startup_us * 1e-6
    return OpResult(op.name, op.kind, t, compute, dram, sram, dram_b, bound, spilled)


def simulate(w: Workload, a: ArchConfig) -> SimResult:
    a.validate()
    r = SimResult(LABEL, a.name)
    for op in w.ops:
        if not op.supported:
            r.notes.append(f"unsupported op skipped: {op.name}")
            continue
        r.per_op.append(_op_time(op, a))
    r.step_latency_s = sum(o.time_s for o in r.per_op)
    r.dram_bytes_per_step = sum(o.dram_bytes for o in r.per_op)
    # per_image_ops (VAE/text encoder), when present, run once per image
    extra = [_op_time(op, a) for op in w.per_image_ops if op.supported]
    extra_t = sum(o.time_s for o in extra)
    if not w.per_image_ops:
        r.notes.append("VAE decode and text encoders are NOT included (no per_image_ops in workload); latency is a lower bound")
    r.total_latency_s = r.step_latency_s * w.steps + extra_t
    r.dram_bytes_total = r.dram_bytes_per_step * w.steps + sum(o.dram_bytes for o in extra)
    r.images_per_s = w.batch_size / r.total_latency_s if r.total_latency_s else 0.0
    peak_macs_s = a.int8_tops / 2 * 1e12 * (a.int4_speedup if a.weight_bits == 4 else 1)
    r.compute_utilization = w.total_macs() / (r.step_latency_s * peak_macs_s) if r.step_latency_s else 0.0
    ab = a.act_bits / 8
    r.max_sram_footprint_bytes = max(
        (min((o.input_elems + o.output_elems) * ab, a.sram_mb * 1e6 * a.sram_act_fraction) for o in w.ops),
        default=0.0)
    shares: dict[str, float] = {}
    for o in r.per_op:
        shares[o.bound] = shares.get(o.bound, 0.0) + o.time_s
    r.bound_time_share = {k: v / r.step_latency_s for k, v in shares.items()} if r.step_latency_s else {}
    wbytes = w.weight_elems() * a.weight_bits / 8
    r.weights_fit_on_chip = wbytes <= a.sram_mb * 1e6 * (1 - a.sram_act_fraction)
    r.weights_fit_dram = wbytes <= a.dram_gb * 1e9
    if not r.weights_fit_dram:
        r.notes.append("model weights exceed external memory capacity: configuration infeasible")
    return r


def by_kind(r: SimResult) -> dict[str, float]:
    out: dict[str, float] = {}
    for o in r.per_op:
        out[o.kind] = out.get(o.kind, 0.0) + o.time_s
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def sweep(w: Workload, a: ArchConfig, param: str, values: list[float]) -> list[tuple[float, SimResult]]:
    from dataclasses import replace
    return [(v, simulate(w, replace(a, **{param: v}))) for v in values]
