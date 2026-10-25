"""Static SDXL UNet operator graph (``static_estimate``; nothing is executed).

Architecture constants follow the public SDXL-base UNet2DConditionModel config
(block_out_channels 320/640/1280, transformer depth 0/2/10, cross-attn dim 2048,
77 text tokens, 64-dim heads). Verify against the checkpoint config with
``compiler.torch_profiler`` when torch/diffusers are installed.
Attention is modelled UNFUSED (QK^T, softmax, AV as separate ops) and
elementwise residual adds are included as ``elementwise``.
"""
from __future__ import annotations

from dataclasses import dataclass

from .workload import Op, Workload

@dataclass(frozen=True)
class SDXLConfig:
    block_out: tuple[int, ...] = (320, 640, 1280)
    depths: tuple[int, ...] = (0, 2, 10)  # transformer depth per level
    layers_per_block: int = 2
    cross_dim: int = 2048
    text_tokens: int = 77
    head_dim: int = 64
    in_ch: int = 4
    time_dim: int = 1280
    add_embed_in: int = 2816
    vae_scale: int = 8


class _G:
    def __init__(self, B: int) -> None:
        self.B = B
        self.ops: list[Op] = []

    def conv(self, n: str, cin: int, cout: int, h: int, w: int, k: int = 3, stride: int = 1) -> None:
        oh, ow = h // stride, w // stride
        macs = self.B * oh * ow * cout * cin * k * k
        self.ops.append(Op(n, "conv2d", macs=macs, weight_elems=cout * cin * k * k + cout,
                           input_elems=self.B * cin * h * w, output_elems=self.B * cout * oh * ow,
                           gemm=(self.B * oh * ow, cout, cin * k * k),
                           shapes={"in": [self.B, cin, h, w], "out": [self.B, cout, oh, ow], "k": k, "stride": stride}))

    def lin(self, n: str, tokens: int, cin: int, cout: int, bias: bool = True, mult_out: int = 1) -> None:
        self.ops.append(Op(n, "linear", macs=self.B * tokens * cin * cout,
                           weight_elems=cin * cout + (cout if bias else 0),
                           input_elems=self.B * tokens * cin, output_elems=self.B * tokens * cout * mult_out,
                           gemm=(self.B * tokens, cout, cin), shapes={"tokens": tokens, "in": cin, "out": cout}))

    def vec(self, n: str, kind: str, elems: int, out: int | None = None, w: int = 0) -> None:
        self.ops.append(Op(n, kind, vector_elems=elems, input_elems=elems,
                           output_elems=elems if out is None else out, weight_elems=w))

    def resnet(self, n: str, cin: int, cout: int, h: int, w: int) -> None:
        self.vec(f"{n}.norm1", "groupnorm", self.B * cin * h * w, w=2 * cin)
        self.vec(f"{n}.act1", "activation", self.B * cin * h * w)
        self.conv(f"{n}.conv1", cin, cout, h, w)
        self.lin(f"{n}.time_proj", 1, 1280, cout)
        self.vec(f"{n}.time_add", "elementwise", self.B * cout * h * w)
        self.vec(f"{n}.norm2", "groupnorm", self.B * cout * h * w, w=2 * cout)
        self.vec(f"{n}.act2", "activation", self.B * cout * h * w)
        self.conv(f"{n}.conv2", cout, cout, h, w)
        if cin != cout:
            self.conv(f"{n}.shortcut", cin, cout, h, w, k=1)
        self.vec(f"{n}.residual_add", "elementwise", self.B * cout * h * w)

    def attn(self, n: str, lq: int, c: int, lk: int, kv_dim: int, heads: int) -> None:
        d = c // heads
        self.vec(f"{n}.ln", "layernorm", self.B * lq * c, w=2 * c)
        self.lin(f"{n}.to_q", lq, c, c, bias=False)
        self.lin(f"{n}.to_k", lk, kv_dim, c, bias=False)
        self.lin(f"{n}.to_v", lk, kv_dim, c, bias=False)
        self.ops.append(Op(f"{n}.qk", "attn_qk", macs=self.B * heads * lq * lk * d,
                           input_elems=self.B * (lq + lk) * c, output_elems=self.B * heads * lq * lk,
                           gemm=(lq, lk, d), shapes={"batch_heads": self.B * heads, "lq": lq, "lk": lk, "d": d}))
        self.vec(f"{n}.softmax", "softmax", self.B * heads * lq * lk)
        self.ops.append(Op(f"{n}.av", "attn_av", macs=self.B * heads * lq * lk * d,
                           input_elems=self.B * heads * lq * lk + self.B * lk * c, output_elems=self.B * lq * c,
                           gemm=(lq, d, lk), shapes={"batch_heads": self.B * heads, "lq": lq, "lk": lk, "d": d}))
        self.lin(f"{n}.to_out", lq, c, c)
        self.vec(f"{n}.residual_add", "elementwise", self.B * lq * c)

    def transformer(self, n: str, c: int, h: int, w: int, depth: int, cfg: SDXLConfig) -> None:
        L, heads = h * w, c // cfg.head_dim
        self.vec(f"{n}.norm", "groupnorm", self.B * c * h * w, w=2 * c)
        self.lin(f"{n}.proj_in", L, c, c)
        for i in range(depth):
            b = f"{n}.blk{i}"
            self.attn(f"{b}.self", L, c, L, c, heads)
            self.attn(f"{b}.cross", L, c, cfg.text_tokens, cfg.cross_dim, heads)
            self.vec(f"{b}.ff_ln", "layernorm", self.B * L * c, w=2 * c)
            self.lin(f"{b}.ff_geglu", L, c, 8 * c)
            self.vec(f"{b}.geglu_act", "activation", self.B * L * 4 * c, out=self.B * L * 4 * c)
            self.lin(f"{b}.ff_out", L, 4 * c, c)
            self.vec(f"{b}.ff_residual", "elementwise", self.B * L * c)
        self.lin(f"{n}.proj_out", L, c, c)
        self.vec(f"{n}.residual_add", "elementwise", self.B * L * c)


def build_sdxl_unet(batch: int, resolution: int, cfg: SDXLConfig = SDXLConfig()) -> list[Op]:
    """Operator list for ONE UNet forward at effective batch ``batch``."""
    if resolution % (cfg.vae_scale * 4) != 0:
        raise ValueError("resolution must be a multiple of 32 for SDXL (3-level UNet, VAE x8)")
    g = _G(batch)
    h = w = resolution // cfg.vae_scale
    g.lin("time_embed.l1", 1, 320, cfg.time_dim)
    g.lin("time_embed.l2", 1, cfg.time_dim, cfg.time_dim)
    g.lin("add_embed.l1", 1, cfg.add_embed_in, cfg.time_dim)
    g.lin("add_embed.l2", 1, cfg.time_dim, cfg.time_dim)
    g.conv("conv_in", cfg.in_ch, cfg.block_out[0], h, w)
    skips = [(cfg.block_out[0], h, w)]
    prev = cfg.block_out[0]
    n_lvl = len(cfg.block_out)
    for lvl, c in enumerate(cfg.block_out):
        for i in range(cfg.layers_per_block):
            g.resnet(f"down{lvl}.res{i}", prev, c, h, w)
            prev = c
            if cfg.depths[lvl]:
                g.transformer(f"down{lvl}.attn{i}", c, h, w, cfg.depths[lvl], cfg)
            skips.append((c, h, w))
        if lvl < n_lvl - 1:
            g.conv(f"down{lvl}.downsample", c, c, h, w, stride=2)
            h, w = h // 2, w // 2
            skips.append((c, h, w))
    c = cfg.block_out[-1]
    g.resnet("mid.res0", c, c, h, w)
    g.transformer("mid.attn", c, h, w, cfg.depths[-1], cfg)
    g.resnet("mid.res1", c, c, h, w)
    for lvl in reversed(range(n_lvl)):
        c = cfg.block_out[lvl]
        for i in range(cfg.layers_per_block + 1):
            sc, _, _ = skips.pop()
            g.vec(f"up{lvl}.cat{i}", "concat", g.B * (prev + sc) * h * w)
            g.resnet(f"up{lvl}.res{i}", prev + sc, c, h, w)
            prev = c
            if cfg.depths[lvl]:
                g.transformer(f"up{lvl}.attn{i}", c, h, w, cfg.depths[lvl], cfg)
        if lvl > 0:
            g.vec(f"up{lvl}.upsample_nn", "resample", g.B * c * h * w * 4)
            h, w = h * 2, w * 2
            g.conv(f"up{lvl}.upsample_conv", c, c, h, w)
    g.vec("conv_out.norm", "groupnorm", g.B * prev * h * w, w=2 * prev)
    g.vec("conv_out.act", "activation", g.B * prev * h * w)
    g.conv("conv_out", prev, cfg.in_ch, h, w)
    return g.ops


def build_sdxl_workload(resolution: int = 1024, batch_size: int = 1, steps: int = 20,
                        guidance: bool = True, dtype: str = "fp16") -> Workload:
    """Static workload. UNet batch is doubled when classifier-free guidance is on.

    VAE decode and text encoders are NOT modelled statically (listed under ``unsupported``).
    """
    eff = batch_size * (2 if guidance else 1)
    return Workload(
        model="sdxl-base-unet", resolution=resolution, batch_size=batch_size, steps=steps,
        guidance=guidance, dtype=dtype, ops=build_sdxl_unet(eff, resolution),
        provenance={"ops": "static_estimate", "timing": "not_measured",
                    "attention": "unfused QK/softmax/AV",
                    "cfg": "UNet effective batch = 2*batch_size when guidance"},
        measured={"gpu_timings": None, "end_to_end_latency_s": None, "peak_gpu_memory_bytes": None},
        unsupported=[{"component": "vae_decoder", "reason": "not modelled in static graph; run torch profiler"},
                     {"component": "text_encoders", "reason": "not modelled in static graph; run torch profiler"}],
    )
