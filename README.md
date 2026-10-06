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
- `Makefile` — simulation and formal entry points

## Why this is the right first silicon

Diffusion workloads spend most of their compute in repeated multiply-accumulate patterns. The simplest useful building block is therefore not a full accelerator, but a tile that can be reasoned about completely:

- signed `int8` operands
- saturating accumulation
- explicit lengths via `cfg_len`
- valid/ready handshake
- zero-length handling
- stable output under backpressure

That is exactly the kind of primitive that can be made small enough to prove, stable enough to tape out, and useful enough to scale later.

## Build it in this order

The cleanest path to silicon is not a broad roadmap. It is a narrow sequence of concrete actions that keeps the design honest.

### 1. Freeze the functionality

Before any layout work, the core behavior must be pinned down in one place:

- fix the arithmetic semantics
- fix the saturation behavior
- fix output hold behavior under backpressure
- fix zero-length handling
- fix valid/ready expectations at the boundaries

If these are not nailed down early, physical design will become a tax on ambiguity.

### 2. Make the testbench authoritative

The simulation testbench should be the first source of truth for behavior. It should cover:

- normal dot products
- saturated overflow cases
- zero-length jobs
- valid/ready backpressure
- random signed inputs
- held output stability

The goal is to make the behavioral model boring and explicit before formal work begins.

### 3. Close the formal properties

Formal verification is not the first step in the sense of “prove everything at once.” It is the step that turns design intent into a checkable contract.

At minimum, the design should be able to prove:

- no illegal arithmetic under range assumptions
- output correctness for a known reference model
- stable output under backpressure
- valid/ready invariants hold
- zero-length and empty jobs do not violate the protocol

This is where the project becomes engineering-grade rather than illustrative.

### 4. Run the physical estimates early

Once the RTL is stable, the next step is to estimate the real cost of implementation on SKY130:

- area target
- achievable frequency
- power estimate
- package options
- IO strategy
- thermal assumptions

This is not a theoretical step. It is the moment when the chip stops being a nice idea and starts becoming a real manufacturing object.

### 5. Choose a package strategy before you get married to the design

The most common mistake in small silicon programs is treating package selection as a late-stage detail. It is not. For a first DPU, plan for:

- standard package with manageable IO
- simple power rails and clocking
- easy bring-up board design
- straightforward test setup

A complicated package makes a simple chip expensive and slow to debug.

### 6. Get the manufacturing path lined up early

For SKY130, the real question is not “can this be made?” but “what is the lowest-risk route to a first useful wafer run?”

The best operational setup is usually:

- build with OpenLane/OpenROAD and SKY130
- freeze the RTL and constraints
- obtain benchmark-quality area/timing data
- engage a prototype manufacturing partner or MPW route
- keep board design and packaging choices simple

The point is to reduce schedule risk, not to chase a dramatic mythology around the first silicon.

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

## What the current repo already supports

At the moment, the repository is positioned as a credible first tile rather than a full-production chip.

It already provides:

- simulation coverage for core input patterns and edge cases
- a reference model for comparison
- formal property scaffolding around interface and arithmetic behavior
- a small architectural shape that is easy to scale into a larger array

This is enough to justify the move into a physical implementation pass.

## SKY130 production path: the practical sequence

The following is the sequence we recommend for producing the first silicon as cleanly as possible.

### Phase 1: behavioral closure

Deliverables:

- final arithmetic semantics
- verified backpressure behavior
- stable output semantics under held valid signals
- deterministic zero-length cases
- simulation testbench passing

Decision gate:

- if the behavioral contract is not stable, do not start physical design

### Phase 2: formal closure

Deliverables:

- lint-clean RTL
- formal proof of core protocol invariants
- reference model alignment
- documentation sufficient to hand off to a layout engineer

Decision gate:

- if the protocol remains fuzzy, the design is not ready for tape-out

### Phase 3: physical estimation

Deliverables:

- first OpenLane/OpenROAD flow
- area and timing estimate
- power estimate
- package and IO review
- DRC/LVS triage on the first pass

Decision gate:

- if the design cannot be closed with sane area and frequency assumptions, simplify the architecture before manufacturing

### Phase 4: manufacturing handoff

Deliverables:

- quote from at least two prototype manufacturing routes
- package selection locked
- board bring-up plan defined
- test fixture and debug plan prepared

Decision gate:

- if there is no clean bring-up path, do not tape out

### Phase 5: bring-up and learning

Deliverables:

- packaged silicon returns
- board-level validation in place
- performance and power measurements
- go/no-go decision: iterate tile, scale to array, or change architecture

This is not the glamorous phase, but it is the one that tells you whether the chip is actually worth building.

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

The old idea of “just use one path and hope” is not a strategy. There are three realistic categories of manufacturing engagement for a SKY130 prototype.

### Option A: MPW or turnkey ASIC services

Best for:

- first silicon with minimal internal process overhead
- teams that want wafers, package, and test handled by a service provider
- fast learnings without building a deep manufacturing org

Good partners to evaluate include:

- MOSIS
- Europractice
- CMC Microsystems
- commercial ASIC service houses with SKY130 experience

Use this when the goal is speed and clean execution.

### Option B: direct foundry + external OSAT

Best for:

- more control over wafers, packaging, and test
- teams that want a cleaner path to repeatable production
- stronger institutional process management

This is usually a better fit once the design is stable and production interest appears real.

### Option C: educational or tiny prototype runs

Best for:

- macro experiments
- educational demonstrations
- non-production validation

This is not the right route for the first serious accelerator prototype unless the project is intentionally small.

## Recommended first path

For this repository, the practical choice is:

1. use OpenLane + SKY130 for internal design and layout iteration
2. keep the first die small and boring
3. package it in a standard part
4. use a commercial prototype route or institutional brokerage for the first tape-out
5. bring it up on a simple commodity board

This preserves open tooling while reducing the points of failure that kill small silicon programs: package issues, supply friction, and weak bring-up planning.

## Supply chain decision: simple value stream map

A good way to think about the manufacturing path is as a value stream, not a roadmap.

```text
Design freeze
   -> RTL verification
   -> formal closure
   -> OpenLane flow
   -> prototype quote
   -> wafer run
   -> packaging + test
   -> bring-up board
   -> pilot deployment
   -> demand-led scale-up
```

A useful way to read this is:

- if the design has not been verified, the supply chain is still guessing
- if the package is not selected, the board is still under-specified
- if the test flow is not planned, yield learning is delayed
- if the customer or use-case is not clear, the volume plan is unreliable

The value stream has to be governed by real bottlenecks, not by abstract optimism.

## Supply chain tradeoffs: what to optimize for

### Case 1: low volume, high learning value

If the aim is to learn about the architecture and benchmark feasibility, the cheapest production choice is usually:

- standard package
- lower complexity PCB
- prototype MPW or brokered run
- conservative IO and power design
- minimal custom test hardware

This is the lowest-risk route to real data.

### Case 2: pilot deployment with genuine pull

If there is real customer or internal demand, the better move is:

- repeat a proven die in modest lots
- lock package and board assembly vendor early
- use a second-source packaging path if needed
- standardize on a design that can be repeated without redesign

At this point, the priority is repeatability, not novelty.

### Case 3: higher volume, more control

If demand scales, the design should move toward:

- direct foundry engagement where that adds real operational leverage
- a second packaging/test vendor for resilience
- stronger inventory planning for long-lead components
- modular board and chip design so capacity is added by replication, not re-architecture

This is when the manufacturing footprint becomes strategic rather than tactical.

## Where manufacturing should happen

A steady-state split that makes practical sense is:

- wafer fabrication: foundry path with dependable access to SKY130 capacity and process support
- packaging/test: contract OSAT with strong process discipline and good engineering support
- board assembly: close to the system integration team or deployment location for fast iteration

That split keeps the design flexible. The chip stays reusable, the package remains standard, and the board system can scale with demand without forcing a redesign every time the plan changes.

## Recommended long-term steady-state path

### Stage A: prototype and measurement

- first silicon through a prototype run or turnkey manufacturing partner
- standard package and simple bring-up board
- objective: prove the economics and behavior on real hardware

### Stage B: pilot deployment

- repeat the same silicon in modest volumes
- validate thermal behavior, software compatibility, and utilization
- keep the architecture stable enough to learn from real demand

### Stage C: supply planning

- secure repeatable wafer access
- qualify packaging and test partners
- avoid exotic package or board choices unless there is real customer pull
- build inventory against real demand, not hype

### Stage D: scale by replication, not by redesign

- expand via more identical packaged parts rather than a new tape-out every quarter
- preserve modular interfaces so the system can be scaled cleanly
- only move to a more custom production path when the commercial case is real

That is the steady-state manufacturing model that keeps risk low and optionality high.

## Bottom line

The cleanest way to build this program is simple:

1. make the behavior obvious
2. prove the protocol
3. estimate the implementation early
4. choose easy packaging and board strategy
5. manufacture through a low-risk prototype path
6. scale only when the demand is real

This is how you produce silicon without turning the first chip into a speculative monument. It is a good design discipline, and it is also the safest commercial strategy.

## References and useful links

- [OpenLane](https://openlane.readthedocs.io/en/latest/)
- [SKY130 PDK](https://github.com/google/skywater-pdk)
- [OpenROAD Project](https://theopenroadproject.org/)
- [SymbiYosys](https://symbiyosys.readthedocs.io/)

The key idea is straightforward: build the smallest credible tile, prove it, make it manufacturable, and do not confuse early learning with final product strategy.
