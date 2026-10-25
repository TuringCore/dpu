"""Versioned, machine-readable workload description (schema ``dpu-workload/1``).

Counting convention (explicit, used everywhere):
  * 1 MAC = 1 multiply + 1 add = 2 FLOPs.
  * ``macs`` counts only multiply-accumulate work (conv, linear, attention matmuls).
  * ``vector_elems`` counts elements touched by non-MAC ops (norm, softmax, activations,
    elementwise); no FLOP weight is applied to them.
  * Byte counts are per single UNet forward pass at the effective batch (CFG included).

Provenance of every numeric field is tagged:
  * ``static_estimate`` - derived from graph shapes, nothing executed.
  * ``measured``        - observed on real hardware (only ever set by a GPU profiler run).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "dpu-workload/1"

MAC_KINDS = frozenset({"conv2d", "linear", "attn_qk", "attn_av"})
VECTOR_KINDS = frozenset({"softmax", "groupnorm", "layernorm", "activation", "elementwise",
                          "resample", "concat"})
KNOWN_KINDS = MAC_KINDS | VECTOR_KINDS


@dataclass
class Op:
    name: str
    kind: str
    macs: int = 0
    vector_elems: int = 0
    weight_elems: int = 0
    input_elems: int = 0
    output_elems: int = 0
    #: (M, N, K) GEMM view for MAC ops, when meaningful
    gemm: tuple[int, int, int] | None = None
    #: shape annotations
    shapes: dict[str, Any] = field(default_factory=dict)
    #: measured GPU time in ms (None => not measured)
    measured_ms: float | None = None
    supported: bool = True
    note: str = ""

    @property
    def flops(self) -> int:
        return 2 * self.macs


@dataclass
class Workload:
    model: str
    resolution: int
    batch_size: int
    steps: int
    guidance: bool
    dtype: str
    ops: list[Op]
    #: ops executed once per image outside the denoising loop (VAE, text encoders); may be empty
    per_image_ops: list[Op] = field(default_factory=list)
    provenance: dict[str, str] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)
    #: measured end-to-end numbers (None when not measured)
    measured: dict[str, Any] = field(default_factory=dict)
    unsupported: list[dict[str, str]] = field(default_factory=list)
    schema: str = SCHEMA_VERSION

    # ---- aggregates (per UNet forward) ----
    def total_macs(self) -> int:
        return sum(o.macs for o in self.ops)

    def total_flops(self) -> int:
        return 2 * self.total_macs()

    def weight_elems(self) -> int:
        return sum(o.weight_elems for o in self.ops)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["summary"] = {
            "unet_macs_per_forward": self.total_macs(),
            "unet_flops_per_forward": self.total_flops(),
            "unet_weight_elems": self.weight_elems(),
            "num_ops": len(self.ops),
            "counting_convention": "1 MAC = 2 FLOPs; vector ops counted in elements only",
        }
        return d

    def to_json(self, path: str | None = None) -> str:
        text = json.dumps(self.to_dict(), indent=2, sort_keys=False)
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text + "\n")
        return text

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Workload":
        if d.get("schema") != SCHEMA_VERSION:
            raise ValueError(f"unsupported workload schema {d.get('schema')!r}; expected {SCHEMA_VERSION}")

        def op(x: dict[str, Any]) -> Op:
            x = dict(x)
            if x.get("gemm") is not None:
                x["gemm"] = tuple(x["gemm"])
            return Op(**x)

        return cls(
            model=d["model"], resolution=d["resolution"], batch_size=d["batch_size"],
            steps=d["steps"], guidance=d["guidance"], dtype=d["dtype"],
            ops=[op(o) for o in d["ops"]],
            per_image_ops=[op(o) for o in d.get("per_image_ops", [])],
            provenance=d.get("provenance", {}), environment=d.get("environment", {}),
            measured=d.get("measured", {}), unsupported=d.get("unsupported", []),
        )

    @classmethod
    def load(cls, path: str) -> "Workload":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
