"""Accelerator architecture parameters (all values are hypotheses, not measurements)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass
class ArchConfig:
    name: str = "dpu-32tops"
    int8_tops: float = 32.0            # peak, counting 1 MAC = 2 ops
    int4_speedup: float = 2.0          # INT4 MAC rate relative to INT8 (hypothesis)
    clock_ghz: float = 1.0
    compute_utilization: float = 0.7   # achievable fraction of peak on MAC ops
    vector_gelems_per_s: float = 256.0 # non-MAC elementwise throughput
    softmax_cost_per_elem: float = 4.0 # vector-element equivalents per softmax element
    sram_mb: float = 16.0
    sram_act_fraction: float = 0.5     # share of SRAM usable for activations (rest: weight tiles / double buffer)
    sram_bw_gbs: float = 4000.0
    dram_bw_gbs: float = 200.0
    dram_gb: float = 16.0
    dma_startup_us: float = 1.0
    precision_convert_gelems_per_s: float = 512.0
    weight_bits: int = 8
    act_bits: int = 8
    power_w: float = 75.0

    def validate(self) -> None:
        for k, v in asdict(self).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v <= 0:
                raise ValueError(f"{k} must be > 0")
        if self.weight_bits not in (4, 8, 16) or self.act_bits not in (8, 16):
            raise ValueError("weight_bits in {4,8,16}, act_bits in {8,16}")
        if not 0 < self.compute_utilization <= 1 or not 0 < self.sram_act_fraction < 1:
            raise ValueError("utilization in (0,1], sram_act_fraction in (0,1)")

    @classmethod
    def load(cls, path: str) -> "ArchConfig":
        with open(path, encoding="utf-8") as f:
            c = cls(**json.load(f))
        c.validate()
        return c
