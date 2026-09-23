# Verification Strategy

## Scope of the current verification foundation

This repository now includes two complementary verification layers:

1. **Simulation** via `tb/dpu_tile_tb.sv`
2. **Formal collateral** via `formal/dpu_tile_properties.sv` and `formal/dpu_tile.sby`

The simulation suite is intended to be runnable with open-source tooling available on a typical workstation. The formal collateral captures the key safety and interface properties required before scaling the block.

## Properties covered

The current property set focuses on the most important early invariants:

- reset clears the tile into an idle, ready-to-configure state
- input samples are only accepted while a job is active
- zero-length jobs produce a zero output deterministically
- output validity matches completion of exactly `cfg_len` accepted products
- output data remains stable while `out_valid=1` and `out_ready=0`
- configuration readiness drops while the tile is active or waiting to retire an output
- output and ready signals track a reference model of the same protocol

## Simulation coverage

The testbench exercises:

- zero-length job handling
- a directed signed dot-product example
- positive saturation
- negative saturation
- output backpressure / hold behavior
- randomized regression across varying lengths and input gaps

## Recommended proof-growth plan

To evolve this into a stronger formal signoff package, extend the property set with:

1. cover properties for representative workloads
2. stronger liveness assumptions/assertions around eventual output acceptance
3. equivalence checking against a higher-level executable reference model
4. end-to-end array-level proofs once multiple tiles are connected
5. assumptions on command legality and multi-job scheduling rules

## Pre-tape-out verification additions

Before any serious shuttle or foundry handoff, verification should also include:

- lint and synthesis warnings driven to zero or documented
- CDC/RDC analysis for any multi-clock design revisions
- constrained-random regression in a second simulator
- gate-level or netlist-level smoke checks after synthesis
- power intent checks if retention or clock gating is introduced

