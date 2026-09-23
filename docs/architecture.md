# DPU Prototype Architecture

## Goal

This repository starts with a deliberately small hardware block that is still relevant to diffusion inference: a streaming dot-product tile. Diffusion U-Nets, attention blocks, and MLP layers spend most of their time in multiply-accumulate heavy kernels. A low-risk prototype for formal verification and early silicon exploration is therefore a narrow, quantized MAC engine with a clean handshake and bounded arithmetic.

## First silicon-worthy block

The initial RTL in `rtl/dpu_tile.sv` implements one `dpu_tile` with:

- signed `int8` inputs (`in_a`, `in_b`)
- signed saturating accumulator (`ACC_W`, default 24 bits)
- a `cfg_len` register that defines the dot-product length for the next job
- valid/ready input and output interfaces
- deterministic handling of zero-length jobs

That makes the block small enough for tractable property checking while still representing a core primitive that can later be arrayed into a larger accelerator.

## Interface summary

### Configuration channel

- `cfg_valid/cfg_ready`
- `cfg_len`

A configuration transaction starts a new dot-product job.

### Input stream

- `in_valid/in_ready`
- `in_a`, `in_b`

Each accepted beat performs one signed multiply-accumulate.

### Output stream

- `out_valid/out_ready`
- `out_sum`

After `cfg_len` products have been consumed, the final accumulated result is produced and held stable until accepted.

## Why this is diffusion-relevant

A production diffusion accelerator would need far more than a single lane, but this tile covers several important design concerns early:

1. **Quantized inference feasibility**: many deployment flows investigate reduced precision for denoising workloads.
2. **Streaming control correctness**: valid/ready bugs multiply quickly when a tile is replicated into arrays.
3. **Saturation and bounded arithmetic**: fixed-point edge cases must be understood before a larger datapath is frozen.
4. **Composable microarchitecture**: a proven lane can be replicated into SIMD, systolic, or clustered architectures.

## Natural next architectural steps

After this first tile is stable, the next useful increments would be:

1. multi-lane vector MAC tile (`4x` or `8x` lanes)
2. local scratchpad or double-buffered line buffer
3. fused bias / scale / activation stage for denoising layers
4. DMA-friendly command interface for batched work submission
5. array-level scheduler for convolution, attention, and MLP kernels

## Cost/performance philosophy

For a low-cost demonstrator, the prototype should emphasize:

- narrow datapaths where quantization allows it
- regular control and simple routing
- streaming dataflow with shallow buffering
- proof-friendly interfaces that reduce integration risk
- enough arithmetic structure to measure meaningful PPA trends in synthesis

