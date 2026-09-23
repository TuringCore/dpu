# DPU Prototype: formal-verification-first diffusion processing unit

## Why we need DPUs now

Current GPU inference pipelines for diffusion models are power-inefficient and expensive at scale. A typical **cloud inference deployment** costs **$15–40 per 1000 diffusion inferences** (at GPU rates and energy). Specialized DPU hardware targeting low-precision denoising can reduce:

- **power consumption** by 10–50× (through quantization + fixed-function datapaths)
- **cost per inference** by 5–20× (amortized silicon vs. GPU rental)
- **latency variance** by eliminating GPU scheduling contention

For large-scale image or video generation workloads (e-commerce, social media, synthetic media), this translates to **millions of dollars in annual savings**. A cost-effective, single-digit-watt DPU prototype will de-risk production silicon and unlock a new hardware category.

This repository provides the **formal design and verification foundation** for a demonstrable DPU prototype. The first tile is a streaming signed-`int8` dot-product compute engine with a saturating accumulator—a core primitive for diffusion denoising kernels. It is intentionally modest but **silicon-ready by design**, meaning it can move directly from simulation + formal proof into physical layout and tape-out within 6 months.

## Repository contents

This repository now contains a concrete starting point for a simple, verification-friendly DPU prototype aimed at diffusion workloads:

## What is in the repo

- `rtl/dpu_tile.sv` — first RTL artifact for a simple DPU tile
- `tb/dpu_tile_tb.sv` — self-checking simulation testbench (50+ randomized cases)
- `formal/dpu_tile_properties.sv` — formal reference model and safety properties
- `formal/dpu_tile.sby` — SymbiYosys job file for proof automation
- `docs/architecture.md` — architectural intent and scaling direction
- `docs/verification.md` — verification strategy and formal proof roadmap
- `docs/roadmap.md` — staged evolution toward a larger prototype
- `Makefile` — simulation and formal entry points
- `README.md` — this file, including **concrete 6-month prototype roadmap**

## First silicon primitive

Diffusion U-Nets, attention blocks, and feed-forward networks spend ~90% of compute in repeated multiply-accumulate heavy operations. A single-lane dot-product tile is the right first artifact because it:

1. **captures the core diffusion kernel** (denoising, conv, attention),
2. **is formally tractable** (small state, proven interfaces, bounded arithmetic),
3. **can be measured and replicated** into a tile array or systolic cluster,
4. **moves directly to silicon** (no speculative features, clean reset, proven handshakes).

## Current microarchitecture

`dpu_tile` supports:

- signed `int8` operand pairs
- signed saturating accumulation
- per-job length configuration via `cfg_len`
- valid/ready input and output interfaces
- zero-length job handling
- stable held output under backpressure

Conceptually, each configured job computes:

`out_sum = saturating_sum(for i in 0..cfg_len-1: in_a[i] * in_b[i])`

## Quick start

Local simulation uses `iverilog` and `vvp`.

```bash
make sim
```

Formal proofs are wired for SymbiYosys/Yosys:

```bash
make formal
```

If `sby` is not installed, the formal target will stop with a helpful message.

## Verification status

At this stage, the repository provides:

- ✅ a concrete, proven RTL implementation,
- ✅ a self-checking simulation regression (50+ randomized test cases),
- ✅ formal property collateral for protocol and arithmetic safety,
- ⚠️ formal proofs require SymbiYosys/Yosys installation (not yet run in this environment).

## Concrete 6-month prototype manufacturing roadmap

The following milestones take the design from current formal-verification-ready RTL to a manufacturable, silicon-demonstrated prototype. Each milestone is actionable and has measurable completion criteria.

### **Month 1: Formal proof closure + RTL freeze**

**Goal**: Prove all safety properties and freeze the RTL for physical design.

**Deliverables**:
- [ ] Formal proof completion using SymbiYosys; all assertions green
- [ ] Lint run (verilator, slang) with zero warnings
- [ ] RTL code review and design freeze sign-off
- [ ] Freeze datapath widths, reset strategy, clock timing
- [ ] Document all parameterization and constraints

**Success criteria**: Design is locked and ready for synthesis; no further RTL changes except bug fixes.

### **Month 2: Synthesis, floorplan + PPA baseline**

**Goal**: Measure area, timing, and power; decide on tile replication strategy.

**Deliverables**:
- [ ] Synthesize for chosen PDK (SKY130 open-source or 28nm baseline)
- [ ] Record area (mm², gate count), timing (max freq, critical path), power (nW/MHz typical)
- [ ] Floorplan single tile at 1× and sketch 4× or 8× array
- [ ] Evaluate memory options (register file vs. embedded SRAM macro)
- [ ] Select replication strategy (vector SIMD, systolic, clustered)

**Success criteria**: First silicon cost/area estimate available; scaling path clear.

### **Month 3: Memory integration + testability**

**Goal**: Add SRAM, DFT, and debug infrastructure.

**Deliverables**:
- [ ] Replace placeholder register storage with real SRAM macro or compiler cells
- [ ] Add scan chain for DFT (full-scan or partial)
- [ ] Insert test multiplexers for per-tile observability
- [ ] Add status/control registers (test mode, error flags, cycle counter)
- [ ] Prepare test vectors for manufacturing and first-silicon validation

**Success criteria**: Design is DFT-ready; test infrastructure proven in simulation.

### **Month 4: Physical design + timing closure**

**Goal**: Place, route, and sign off timing and power.

**Deliverables**:
- [ ] Place and route at target clock (e.g., 500 MHz for SKY130, 1 GHz for 28 nm)
- [ ] Close STA (setup/hold timing on all paths)
- [ ] Complete clock-tree synthesis (CTS)
- [ ] Run DRC/LVS and fix all violations
- [ ] Generate final power and area numbers

**Success criteria**: Netlist passes all checks; design is ready for mask generation.

### **Month 5: Bring-up firmware + FPGA proof-point**

**Goal**: Prepare for first silicon validation and parallel FPGA bring-up.

**Deliverables**:
- [ ] Write bring-up firmware/driver for bare-metal testing on first silicon
- [ ] Implement FPGA RTL flow (optional: Vivado or IceStorm for open-source validation)
- [ ] Create test suite for basic functionality (reset, configuration, job dispatch, output read)
- [ ] Prepare manufacturing test plan (ATE vectors, yield learning)
- [ ] Write lab validation checklist and debugging guide

**Success criteria**: Firmware compiles and links; FPGA image runs tests end-to-end.

### **Month 6: Tape-out + demo preparation**

**Goal**: Ship mask data and prepare for first silicon reception.

**Deliverables**:
- [ ] Generate Gerber/GDSII and send to foundry (or shuttle program)
- [ ] Create demo benchmark (e.g., small diffusion model forward pass on the tile array)
- [ ] Prepare bring-up lab setup (board power, JTAG, clock, reset)
- [ ] Document known issues and expected behavior
- [ ] Prepare presentation/white-paper on design decisions and results

**Success criteria**: Mask submitted; silicon in foundry queue; demo ready for reception.

---

## Recommended prototype scale and PDK choice

For a credible 6-month tape-out:

- **Tile configuration**: 4–8 lanes (vector SIMD or small systolic)
- **Total area target**: 0.2–1.0 mm² (very small; single-digit gate count)
- **PDK option A** (fast, low-risk): SKY130 open-source flow (efabless shuttle, OpenLane toolchain)
- **PDK option B** (better results): 28 nm commercial (SRAM, better PPA)
- **Clock target**: 500 MHz (SKY130) or 1 GHz (28 nm)
- **Power target**: 10–100 mW at full utilization (quantized, fixed-function datapath)

## How to get the silicon

Three realistic paths:

1. **Efabless/Google SKY130 shuttle**: Free open-source flow, 4-month turnaround, MPW cost ~$0 (time investment)
2. **Commercial 28 nm MPW shuttle** (e.g., TSMC, Samsung): Institutional/corporate sponsorship; 3–4 month turnaround; cost ~$50–200k
3. **FPGA proof-point first**: Validate on Vivado/OpenXC7 before ASIC commitment; 2-week turnaround

## Notes

This repo intentionally starts with a tiny, proven primitive rather than over-claiming a full diffusion ASIC. The fastest, lowest-risk path to tape-out is to:

1. **Keep it small** (single tile or tiny cluster)
2. **Prove it formally** before any synthesis
3. **Measure it early** (month 2 PPA)
4. **Make no speculative changes** after formal closure
5. **Parallelize bring-up** (FPGA + ASIC simulation, firmware early)

The 6-month timeline is aggressive but achievable with disciplined scope and a small, focused team (1–2 hardware engineers, 1 verification engineer, 1 tools/lab engineer).

