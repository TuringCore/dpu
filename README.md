# DPU prototype: build the first silicon cleanly on SKY130

## The objective

This repository is a small, verification-friendly diffusion processing unit (DPU) prototype aimed at one thing: reducing the cost and uncertainty of running diffusion inference on real silicon.

The goal is not to build a heroic chip on day one. The goal is to make the first silicon useful enough to answer the right questions quickly:

- Is the datapath correct under signed arithmetic and backpressure?
- Does the tile behave predictably at the interface boundary?
- Can this design be made with a clean, realistic SKY130 flow?
- What does the supply chain look like once the chip is no longer a prototype?

The design here is intentionally narrow: a signed `int8` dot-product tile with saturating accumulation, valid/ready interfaces, and explicit edge handling. That is enough to capture the core diffusion workload without pretending the full accelerator is already solved.

## What is in this repo

- `rtl/dpu_tile.sv` — core DPU tile RTL
- `tb/dpu_tile_tb.sv` — simulation testbench with randomized coverage
- `formal/dpu_tile_properties.sv` — formal properties and reference model
- `formal/dpu_tile.sby` — SymbiYosys proof job
- `docs/architecture.md` — architecture intent and scaling path
- `docs/verification.md` — verification strategy
- `docs/roadmap.md` — longer-term scaling notes
- `docs/SYNTHESIS.md` — sky130 synthesis flow
- `openlane/README.md` — full P&R with upstream OpenLane
- `Makefile` — simulation, formal, and synthesis entry points

## Why this is the right first silicon

Diffusion workloads spend most of their compute in repeated multiply-accumulate patterns. The simplest useful building block is therefore not a full accelerator, but a tile that can be reasoned about completely:

- signed `int8` operands
- saturating accumulation
- explicit lengths via `cfg_len`
- valid/ready handshake
- zero-length handling
- stable output under backpressure

That is exactly the kind of primitive that can be made small enough to prove, stable enough to tape out, and useful enough to scale later.

## Production path

The cleanest way to get this design to silicon is a single, disciplined sequence with decision points built in.

1. Freeze behavior before layout
   - lock arithmetic, saturation, backpressure, zero-length handling, and valid/ready semantics
   - if these are still ambiguous, the silicon plan is already too early

2. Make the simulation testbench the source of truth
   - cover normal dot products, overflow, zero-length jobs, backpressure, random signed inputs, and held output behavior
   - the behavioral model should be boring and explicit before any physical implementation starts

3. Close the formal contract
   - prove the core protocol invariants and arithmetic assumptions
   - ensure the reference model and implementation agree under the edge cases that matter
   - this is the point where the design moves from illustrative to engineering-grade

4. Run the checked-in SKY130 block hardening setup
   - run simulation, formal, mapped synthesis, then OpenLane using `openlane/config.json`
   - inspect timing, area, DRC/LVS, antenna, and routing reports; the target constraints are estimates, not foundry signoff
   - record the exact PDK and flow versions and review all waivers before selecting a submission route

5. Lock the manufacturing posture before the design becomes “final”
   - standard package, simple power rails, straightforward clocking, commodity bring-up board
   - a complicated package or custom board is a tax on the project, not a sign of seriousness

6. Choose the production path based on evidence, not optimism
   - if the goal is learning: use a prototype MPW/turnkey route and a standard package
   - if there is real demand: repeat a proven die in modest volume with a defined package/test partner
   - if demand scales: move to more direct foundry management and second-sourced packaging/test

This is the real roadmap: behavior first, proof next, physical estimate third, then manufacturing based on real learning and demand.

## Physical Design Flow

Two tiers:

- **Lightweight:** Yosys synthesis in CI (`make sky130-synth-yosys-only`) for fast validation, no Docker.
- **Block hardening:** OpenLane P&R locally with upstream [OpenLane](https://github.com/The-OpenROAD-Project/OpenLane), using the checked-in design config, SDC, and pin-order file (see `openlane/README.md` and `docs/SYNTHESIS.md`). This is not full tapeout signoff.

## SKY130 submission: next steps

This repository currently implements one parameterized dot-product tile, not a
complete Stable Diffusion accelerator or a pad-limited chip. Before submitting
to a shuttle or foundry, the project still needs to:

1. Freeze the RTL/interface and supported parameter values; complete functional,
   formal, lint, and gate-level verification, and resolve or document warnings.
2. Run the configured OpenLane hardening flow and review timing/STA, DRC, LVS,
   antenna, density, and routing results against the selected submission
   program's rules; repeat after any changes and archive the reports.
3. Define the actual chip-level integration: required accelerator/system
   wrapper, IO/pad ring and ESD strategy, package, power distribution, clock and
   reset implementation, and board-level interface. This block configuration
   does not provide these.
4. Complete program-required DFT/scan, power integrity (IR drop/EM), reliability,
   and signoff checks; these are not currently implemented or demonstrated here.
5. Select a SKY130 shuttle/foundry route and follow its current submission
   checklist for PDK/flow versions, permitted cells/macros, GDS/OASIS and
   LEF/abstract views, netlists, timing/physical reports, waivers, licensing,
   and submission metadata.
6. Prepare the bring-up plan and deliverables (test vectors, firmware or host
   tooling, board, and validation plan) with the submission partner.

## Supply chain tradeoffs

The manufacturing decision is not about picking a single best path; it is about choosing the right tradeoff at the right maturity stage.

- Low-volume / high-learning path: standard package, minimal custom test hardware, prototype run, conservative IO. Best when the priority is learning and de-risking.
- Pilot deployment path: modest lot size, repeatable die, defined board assembly and OSAT, focus on repeatability rather than novelty. Best when the workload is real and the project needs operating data.
- Scale-up path: direct foundry management, second-source packaging/test, inventory planning, modular board design. Best when the silicon is clearly proving value and volume is becoming predictable.

The main bottleneck is usually not the wafer alone. It is the combination of package, test flow, board integration, and the ability to repeat the design without re-architecting it.

## Where manufacturing should happen

A practical steady-state split is:

- wafer fabrication: foundry or prototype partner with dependable SKY130 access and process support
- packaging and test: external OSAT with strong engineering support and repeatable throughput
- board assembly: close to the integration team or deployment region for faster iteration and easier field support

The objective is flexibility: keep the chip reusable, the package standard, and the system design modular enough that capacity can scale by replication rather than redesign.

## Quick start

Local simulation:

```bash
make sim
```

Formal verification:

```bash
make formal
```

If `sby` is not installed, the formal target will stop with a clear message rather than failing silently.

## SKY130-specific guidance

For this program, the right assumptions are intentionally conservative:

- process: SKY130
- flow: OpenLane/OpenROAD
- first package: simple, standard, easy to source
- voltage: standard rails, no exotic power domains
- board: commodity regulators and debug headers
- objective: first useful silicon, then scale

A chip designed for the first available package, board, and test flow is easier to manufacture and easier to learn from.

## Real manufacturing choices

There are three realistic routes for a SKY130 prototype.

### Option A: MPW or turnkey ASIC services

Best for:

- first silicon with minimal internal process overhead
- teams that want wafers, package, and test handled by a service provider
- fast learning without building a deep manufacturing org

Good partners to evaluate include:

- MOSIS
- Europractice
- CMC Microsystems
- commercial ASIC service houses with SKY130 experience

Use this when the goal is speed and clean execution.

### Option B: direct foundry + external OSAT

Best for:

- more control over wafers, packaging, and test
- cleaner repeatable production path
- stronger process management once the design is stable

This is usually a better fit once there is real product pull.

### Option C: educational or tiny prototype runs

Best for:

- macro experiments
- educational demonstrations
- non-production validation

This is not the route for a serious first accelerator prototype unless the program is intentionally small.

## Recommended production posture

For this repository, the practical choice is:

1. use OpenLane + SKY130 for internal iteration
2. keep the first die small and boring
3. package it in a standard part
4. use a commercial prototype route or institutional brokerage for the first tape-out
5. bring it up on a simple commodity board

That preserves open tooling while reducing the points of failure that kill small silicon programs: package issues, supply friction, and weak bring-up planning.

## References and useful links

- [OpenLane](https://openlane.readthedocs.io/en/latest/)
- [SKY130 PDK](https://github.com/google/skywater-pdk)
- [OpenROAD Project](https://theopenroadproject.org/)
- [SymbiYosys](https://symbiyosys.readthedocs.io/)

The key idea is straightforward: build the smallest credible tile, prove it, make it manufacturable, and do not confuse early learning with final product strategy.
