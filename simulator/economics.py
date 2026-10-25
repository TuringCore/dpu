"""Explicit economic model. EVERY input is an assumption supplied by the user via a scenario file;
no foundry price or process figure is built in. Results inherit the label of their inputs.

Cost conventions
  * hardware purchase cost (capex) is kept separate from cloud rental ($/h), which is not used here.
  * cost per busy hour = (capex/lifetime_hours + overhead/yr/8760) / utilization + energy_per_busy_hour
  * energy_per_busy_hour = power_w * pue / 1000 * electricity $/kWh
  * cost per 1000 images = cost per busy hour / (images_per_s * 3600) * 1000
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field


@dataclass
class DpuEconomics:
    label: str = "assumed scenario"
    die_area_mm2: float = 100.0
    wafer_diameter_mm: float = 300.0
    wafer_price_usd: float = 10000.0
    yield_fraction: float = 0.7
    packaging_test_usd: float = 30.0
    memory_usd_per_gb: float = 3.0
    memory_gb: float = 16.0
    pcb_power_delivery_usd: float = 60.0
    host_share_usd: float = 150.0     # host system cost attributed to one accelerator
    nre_usd: float = 20e6
    volume_units: float = 50000.0
    power_w: float = 75.0             # accelerator + host share at the wall, before PUE
    pue: float = 1.4                  # cooling + datacenter overhead multiplier
    utilization: float = 0.6
    electricity_usd_per_kwh: float = 0.10
    lifetime_years: float = 3.0
    overhead_usd_per_year: float = 100.0   # software + operations per unit

    def dies_per_wafer(self) -> float:
        d, a = self.wafer_diameter_mm, self.die_area_mm2
        return max(math.pi * (d / 2) ** 2 / a - math.pi * d / math.sqrt(2 * a), 0.0)

    def die_cost(self) -> float:
        n = self.dies_per_wafer() * self.yield_fraction
        if n <= 0:
            raise ValueError("no good dies per wafer")
        return self.wafer_price_usd / n

    def unit_hardware_cost(self, include_nre: bool = True) -> float:
        c = (self.die_cost() + self.packaging_test_usd + self.memory_usd_per_gb * self.memory_gb
             + self.pcb_power_delivery_usd + self.host_share_usd)
        return c + (self.nre_usd / self.volume_units if include_nre else 0.0)


@dataclass
class GpuBaseline:
    name: str
    label: str                 # "measured" | "assumed"
    images_per_s: float
    power_w: float
    purchase_usd: float
    host_share_usd: float = 0.0
    pue: float = 1.4
    utilization: float = 0.6
    electricity_usd_per_kwh: float = 0.10
    lifetime_years: float = 3.0
    overhead_usd_per_year: float = 100.0
    source: str = ""


def _cost_per_1000(capex: float, power_w: float, pue: float, util: float, kwh: float,
                   years: float, overhead_yr: float, ips: float) -> dict[str, float]:
    if ips <= 0:
        raise ValueError("images_per_s must be positive")
    hours = years * 8760
    busy_hr = (capex / hours + overhead_yr / 8760) / util + power_w * pue / 1000 * kwh
    per_img_j = power_w * pue / ips
    return {"cost_per_busy_hour_usd": busy_hr,
            "cost_per_1000_images_usd": busy_hr / (ips * 3600) * 1000,
            "energy_per_image_j": per_img_j,
            "images_per_s_per_hw_usd": ips / capex}


def dpu_cost(e: DpuEconomics, ips: float, include_nre: bool = True) -> dict[str, float]:
    capex = e.unit_hardware_cost(include_nre)
    out = _cost_per_1000(capex, e.power_w, e.pue, e.utilization, e.electricity_usd_per_kwh,
                         e.lifetime_years, e.overhead_usd_per_year, ips)
    out["unit_hardware_cost_usd"] = capex
    out["die_cost_usd"] = e.die_cost()
    return out


def gpu_cost(g: GpuBaseline) -> dict[str, float]:
    return _cost_per_1000(g.purchase_usd + g.host_share_usd, g.power_w, g.pue, g.utilization,
                          g.electricity_usd_per_kwh, g.lifetime_years, g.overhead_usd_per_year,
                          g.images_per_s)


@dataclass
class Comparison:
    label: str
    dpu: dict[str, float]
    gpu: dict[str, float]
    advantage_x: float                      # gpu cost per 1000 / dpu cost per 1000 (>1 favours DPU)
    breakeven_volume_units: float | None    # None: DPU unit cost >= throughput-equivalent GPU cost
    required_images_per_s: dict[str, float] = field(default_factory=dict)
    sensitivity: dict[str, list[tuple[float, float]]] = field(default_factory=dict)


def compare(e: DpuEconomics, dpu_ips: float, g: GpuBaseline, targets: tuple[float, ...] = (2, 3, 5)) -> Comparison:
    d, gc = dpu_cost(e, dpu_ips), gpu_cost(g)
    adv = gc["cost_per_1000_images_usd"] / d["cost_per_1000_images_usd"]
    # volume at which NRE is repaid vs buying throughput-equivalent GPU capacity
    gpu_equiv = (g.purchase_usd + g.host_share_usd) * dpu_ips / g.images_per_s
    per_unit_saving = gpu_equiv - e.unit_hardware_cost(include_nre=False)
    be = e.nre_usd / per_unit_saving if per_unit_saving > 0 else None
    # cost per image falls monotonically with ips; solve by bisection for each target
    req: dict[str, float] = {}
    for t in targets:
        goal = gc["cost_per_1000_images_usd"] / t
        lo, hi = dpu_ips * 1e-3, dpu_ips * 1e4
        if dpu_cost(e, hi)["cost_per_1000_images_usd"] > goal:
            continue  # unreachable: energy/overhead floor above goal
        for _ in range(100):
            mid = math.sqrt(lo * hi)
            if dpu_cost(e, mid)["cost_per_1000_images_usd"] > goal:
                lo = mid
            else:
                hi = mid
        req[f"{t:g}x"] = hi
    sens: dict[str, list[tuple[float, float]]] = {}
    from dataclasses import replace
    sens["utilization"] = [(u, gc_adv(replace(e, utilization=u), dpu_ips, g)) for u in (0.2, 0.4, 0.6, 0.8, 1.0)]
    sens["yield_fraction"] = [(y, gc_adv(replace(e, yield_fraction=y), dpu_ips, g)) for y in (0.3, 0.5, 0.7, 0.9)]
    return Comparison(f"{e.label} vs {g.name} ({g.label})", d, gc, adv, be, req, sens)


def gc_adv(e: DpuEconomics, ips: float, g: GpuBaseline) -> float:
    return gpu_cost(g)["cost_per_1000_images_usd"] / dpu_cost(e, ips)["cost_per_1000_images_usd"]


def load_economics(path: str) -> DpuEconomics:
    with open(path, encoding="utf-8") as f:
        return DpuEconomics(**json.load(f))


def load_gpu(path: str) -> GpuBaseline:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("label") not in ("measured", "assumed"):
        raise ValueError("GPU baseline 'label' must be 'measured' or 'assumed'")
    return GpuBaseline(**d)


def to_dict(c: Comparison) -> dict:
    return asdict(c)
