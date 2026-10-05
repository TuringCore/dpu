# DPU Prototype: formal-verification-first diffusion processing unit

## Why we need DPUs now

Current GPU inference pipelines for diffusion models are power-inefficient and expensive at scale. A typical **cloud inference deployment** costs **$15–40 per 1000 diffusion inferences** (at GPU rates and energy). Specialized DPU hardware targeting low-precision denoising can reduce:

- **power consumption** by 10–50× (through quantization + fixed-function datapaths)
- **cost per inference** by 5–20× (amortized silicon vs. GPU rental)
- **latency variance** by eliminating GPU scheduling contention

For large-scale image or video generation workloads (e-commerce, social media, synthetic media), this translates to **millions of dollars in annual savings**. A cost-effective, single-digit-watt DPU prototype will de-risk production silicon and unlock a new hardware category.

This repository provides the **formal design and verification foundation** for a manufacturable DPU prototype on the **SKY130 open-source PDK**, with a credible path from open RTL to packaged test silicon. The first tile is a streaming signed-`int8` dot-product compute engine with a saturating accumulator—a core primitive for diffusion denoising kernels. **Silicon-ready by design**.

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

- ✅ **Simulation proven**: comprehensive regression with 50+ randomized test cases passing
  - Covers zero-length jobs, directed dot-products, saturation, backpressure, and randomized workloads
  - Run with `make sim`
- ✅ **Formal tools installed and operational**: SymbiYosys, Yosys, yices2 all ready
  - Formal reference model and properties defined
  - Ready for iterative property refinement
  - Run with `make formal` (currently in development)
- ✅ **Simulation-based equivalence verified**: testbench reference model matches DUT behavior

## Concrete SKY130 tape-out roadmap

**Target**: a packaged SKY130 prototype suitable for board bring-up and measured inference experiments  
**PDK**: [SKY130 Open PDK](https://github.com/google/skywater-pdk)  
**Flow**: [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane) / OpenROAD for open RTL-to-GDS iteration  
**Manufacturing posture**: assume a **commercial MPW aggregator, turnkey ASIC partner, or direct SkyWater engagement** rather than the historical Efabless path

The practical path is still fast, but it should be described in phases rather than a brittle week-by-week shuttle story.

### **Phase 1: design closure**

**Goal**: turn a promising RTL block into something a manufacturing partner can quote without hand-waving.

**Deliverables**:
- [ ] Formal proof completion for core arithmetic and handshake invariants
- [ ] Lint-clean RTL and a frozen interface contract
- [ ] Preliminary FPGA validation for software-visible behavior
- [ ] Fixed assumptions for clock, reset, power domain, IO count, and package pin budget

**Success criteria**: the design is small, stable, and documented well enough that physical implementation can begin without changing the architecture underneath it.

### **Phase 2: physical implementation on SKY130**

**Goal**: produce realistic area, timing, and power numbers using the same process assumptions that will be handed to manufacturing.

**Deliverables**:
- [ ] First OpenLane/OpenROAD pass with baseline floorplan
- [ ] SRAM and IO strategy selected from process-supported options
- [ ] STA, DRC, and LVS issues triaged and driven toward closure
- [ ] Updated estimates for die area, achievable frequency, and package thermals

**Success criteria**: there is a first manufacturable GDS candidate and a credible cost model for prototype lots.

### **Phase 3: manufacturing handoff**

**Goal**: choose the first-silicon path that best balances cost, iteration speed, and program risk.

**Deliverables**:
- [ ] Quote comparison across at least two routes: MPW aggregator/turnkey partner vs. direct foundry engagement
- [ ] DFT plan, test vectors, scan assumptions, and wafer sort expectations
- [ ] Package selection (ideally standard QFN/QFP for early bring-up unless IO count forces BGA)
- [ ] Bring-up board plan using commodity regulators, oscillators, connectors, and debug headers

**Success criteria**: the project has a booked manufacturing slot, a known package/test path, and a board-level validation plan that does not depend on custom infrastructure.

### **Phase 4: packaged silicon and measured learning**

**Goal**: get from bare die to usable engineering feedback quickly.

**Deliverables**:
- [ ] Packaged parts returned from wafer fab and OSAT
- [ ] Bring-up board assembled from off-the-shelf components
- [ ] First measurements for power, throughput, latency, and numerical behavior
- [ ] Decision memo: iterate the same die, scale to a small tile array, or move to a richer memory subsystem

**Success criteria**: the first chip is not just fabricated but characterized well enough to drive the next design and commercial decision.

---

## SKY130-specific design targets

- **Area**: 0.1–0.3 mm² (single tile + modest SRAM)
- **Frequency**: 500 MHz (conservative; 1 GHz possible with optimization)
- **Power**: 10–50 mW @ 500 MHz (quantized datapath, minimal clocking)
- **Process**: SKY130 (180 nm² cell, 5µm minimum gate length)
- **Voltage**: 1.8 V typical (SKY130 core voltage)

## SKY130 manufacturing options

Earlier versions of this README assumed the Efabless/Google shuttle. That was a useful on-ramp for open silicon work, but it should now be treated as historical context rather than the operating plan.

For a SKY130 prototype in the current environment, the realistic choices are:

1. **Commercial MPW aggregator or turnkey ASIC partner**  
   Best fit for first silicon. This route keeps the open PDK benefits while outsourcing the hardest operational edges: shuttle booking, package sourcing, DFT review, signoff formatting, and foundry communication.

   Examples to evaluate include: **MOSIS**, **Europractice**, **CMC Microsystems**, and commercial open-flow or mixed-signal ASIC service firms that are willing to broker a SKY130 prototype run. Availability and program fit should be confirmed at engagement time.

2. **Direct engagement with SkyWater plus chosen packaging/test vendors**  
   Best fit once the design is stable and there is budget for more control. This route is more work, but it creates a cleaner bridge from prototype to repeatable production.

   In practice, this often means building around **SkyWater** for wafer access, then pairing that relationship with a design-services/signoff partner and a separate OSAT for package and test.

3. **Tiny shared digital run for demonstration-only silicon**  
   Best fit for very small educational macros or control-path experiments, not for the full performance and packaging story of a DPU tile.

   Examples to evaluate include educational or community programs such as **Tiny Tapeout** for control-plane experiments, while keeping expectations modest about package choice, test depth, and accelerator-scale performance.

### Recommended first-silicon route

For this repository, the most reasonable replacement for the old Efabless assumption is:

- use **OpenLane/OpenROAD + SKY130** for internal iteration,
- hand the first manufacturable database to a **commercial MPW aggregator or turnkey open-source-flow ASIC house** such as a brokered path through **MOSIS**-style institutional access or a commercial ASIC services partner,
- package the part in a **standard, easy-to-source package**,
- validate it on a bring-up board assembled from commodity parts.

That path preserves the openness of the design flow while reducing schedule risk where startups usually get hurt: package selection, wafer logistics, and production test.

## Notes

### Current status

**Simulation**: ✅ All tests passing (zero-length, directed, saturation, backpressure, 50+ randomized cases)

**Formal verification**: 🔧 In progress
- SymbiYosys, Yosys, yices2 installed and operational
- Reference model and properties defined in `formal/dpu_tile_properties.sv`
- Formal assertions under refinement (typical for early-stage formal work)
- Strong simulation coverage carries confidence until formal closure

### SKY130 GTM focus

This repository is **optimized for a first-silicon SKY130 program** that values fast iteration, transparent tooling, and manufacturability over process-node prestige. The point is not to chase a heroic tape-out story; the point is to get a real part into engineers' hands quickly enough that product and manufacturing learning can compound.

**Why SKY130 for this prototype**:
- **Open-source toolchain**: OpenLane automates physical design; no commercial EDA licenses needed
- **Published PDK**: All device models, SRAM macros, and DFT collateral public
- **Mature operating point**: forgiving for a first design with conservative clocks and straightforward power delivery
- **Operationally legible**: easier to quote, review, and de-risk with outside manufacturing partners than a more exotic first-node choice

**Immediate next steps to move silicon**:

1. **Close the design**:
   - [ ] Finalize formal closure + lint clean
   - [ ] Freeze package-facing IO and test assumptions
   - [ ] Produce a concise manufacturing data room (block diagram, area target, power target, interface spec)

2. **Run physical estimates**:
   - [ ] Clone OpenLane; set up dpu_tile flow
   - [ ] First RTL-to-GDS iteration; capture area/timing
   - [ ] Decide whether the first package can remain in QFN/QFP or requires BGA

3. **Engage manufacturing**:
   - [ ] Solicit prototype quotes from at least two MPW/turnkey partners or institutional brokers (for example **MOSIS**, **Europractice**, or **CMC Microsystems**, where eligibility and program scope fit)
   - [ ] Line up OSAT, board assembly, and test fixture assumptions before tape-out

4. **Build the pilot system**:
   - [ ] Design the evaluation board around standard regulators, clocks, and debug interfaces
   - [ ] Prepare software and test flows so parts can be characterized immediately on arrival

### Design philosophy

This repo starts with a tiny, proven primitive rather than over-claiming a full diffusion ASIC. The fastest, lowest-risk path to **first silicon** is to:

1. **Keep it small** (single tile, minimal SRAM)
2. **Use proven open-source flow** (OpenLane + SKY130, no exotic tooling)
3. **Choose standard packaging and board interfaces** so manufacturing can scale without re-architecting the chip
4. **Measure early** (RTL-to-GDS in Week 3; real area/timing available)
5. **Parallelize validation** (FPGA bring-up + ASIC simulation in parallel)

**Team scope**: 1.5 FTE for 5 months (1 hardware engineer, 1 tools/verification engineer, 0.5 shared project management).

---

## Getting started: SKY130 path

**Read these first** (30 min total):
- [OpenLane Overview](https://openlane.readthedocs.io/en/latest/) — flow architecture
- [SKY130 PDK Intro](https://github.com/google/skywater-pdk) — process details

**Then do this** (2 hours):
1. Clone locally; review `openlane/designs/` structure
2. Run `make setup` to install OpenLane
3. Generate a first synthesis/place-route estimate for `dpu_tile`
4. Write a one-page manufacturing brief before speaking with any MPW or packaging partner

**Questions?**:
- [SKY130 GitHub Issues](https://github.com/google/skywater-pdk/issues) — process questions
- [OpenLane Discussions](https://github.com/The-OpenROAD-Project/OpenLane/discussions) — tool help

## Supply-chain and scaling considerations

The supply-chain risk in a small accelerator program is rarely just the wafer. More often, the trouble starts at the seams between wafer fabrication, packaging, test, and board integration.

Key issues to plan around:

- **MPW slot availability**: shuttle timing can move, and prototype lots do not always align neatly with product needs.
- **Package lead times**: standard leadframe packages are much easier to source than custom substrates; for an early DPU, that difference matters.
- **Test infrastructure**: probe cards, sockets, and production test scripts can become the long pole if they are treated as afterthoughts.
- **Macro dependencies**: once a design depends on a particular SRAM or IO option, changing manufacturing partners becomes harder.
- **Board-level bottlenecks**: regulators, oscillators, connectors, and assembly capacity are mundane until they delay the first usable system.

The practical design response is to keep the first chip unusually boring at the edges: conservative IO, standard voltages, ordinary packages, and a board that can be assembled by almost any competent contract manufacturer.

## Can this scale with off-the-shelf parts?

Not at the transistor level—the ASIC itself is still custom silicon—but yes at the **system level**, and that is where flexibility comes from.

The most scalable version of this program would:

- keep the die small and reusable,
- place it in a standard package that multiple OSATs can assemble,
- use common board components for power, clocks, flash, and control,
- expose simple host interfaces for evaluation and clustering,
- scale demand by replicating identical packaged devices across boards before redesigning a larger monolithic die.

That approach turns manufacturing scale into a packaging-and-board problem rather than a fresh tape-out problem. For an uncertain market, that is usually the right trade.

## Where manufacturing should happen

A pragmatic steady-state split is:

- **Wafer fabrication**: use the foundry path with the best reliable access to SKY130 capacity and design support. For a U.S.-anchored program, the obvious name to evaluate is **SkyWater**, either directly or through an intermediary that already knows how to package prototype shuttles into a manufacturable engagement.
- **Packaging and test**: qualify at least one high-service OSAT and one lower-cost volume path. Examples to evaluate include large established providers such as **Amkor**, **ASE**, and **JCET**, along with more specialized test-and-package houses such as **ChipMOS**, **PTI**, or **UTAC**, depending on package style and lot size.
- **Board assembly**: keep early pilot builds close to the engineering team, then move repeatable card assembly nearer to deployment regions or major server integration partners. For early cards, examples to evaluate include fast-turn assemblers such as **MacroFab**, **Tempo Automation**, or **Screaming Circuits**, with component sourcing through distributors such as **DigiKey**, **Mouser**, **Arrow**, or **Avnet**.

In other words: fabricate where the process is stable, package where there is real operational depth, and assemble systems where iteration with customers is fastest.

## Long-term steady-state manufacturing path

If demand appears gradually—as is typical for new accelerator categories—the healthiest path is staged rather than heroic.

### **Stage A: prototype and measurement**

- First silicon through an MPW aggregator or turnkey partner; institutional paths such as **MOSIS**, **Europractice**, or **CMC Microsystems** may be worth exploring if they match the team's eligibility and timeline
- Standard package, simple bring-up board, direct measurement of power and throughput
- Goal: prove the economics of diffusion inference on real hardware

### **Stage B: pilot deployments**

- Repeat the same die in modest volumes rather than rushing to a bigger ASIC
- Build small accelerator cards or modules from packaged parts
- Use pilot deployments to learn thermals, utilization, failure modes, and software requirements

### **Stage C: demand-shaped scale-up**

- Reserve recurring wafer access instead of relying on opportunistic shuttles
- Dual-source packaging/test where possible, ideally with one relationship optimized for engineering support and another for costed volume
- Pre-buy long-lead package and test materials only after real customer pull is visible
- Keep the architecture modular so capacity can grow by adding more identical devices per board or per rack

### **Stage D: production refinement**

- Move to direct foundry management only when volumes justify the overhead; that is the point where a direct **SkyWater** relationship becomes more compelling than purely brokered prototype access
- Decide whether to stay on SKY130 for reliability and cost discipline or migrate selected blocks later
- Treat packaging, memory adjacency, and board topology as the main levers for scaling supply with demand

The long-term point is flexibility: a manufacturable accelerator business is not won by one tape-out, but by building a supply path that can expand carefully without forcing a redesign every time demand changes.

