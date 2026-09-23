# Roadmap

## Phase 0: bootstrap

- define a minimal DPU tile spec
- create first RTL artifact
- stand up simulation and formal scaffolding
- document a believable path to silicon

## Phase 1: single-tile confidence

- close functional bugs in `dpu_tile`
- add lint-clean coding style and explicit reset intent
- expand formal properties to cover corner-case protocol timing
- gather first synthesis area/frequency estimates

## Phase 2: diffusion-oriented scaling

- replicate the tile into a small vector or systolic cluster
- add local SRAM or register-file buffering
- support simple command descriptors for batched workloads
- define kernel mappings for convolution / attention / MLP workloads
- evaluate quantization points that preserve model quality

## Phase 3: prototype SoC integration

- wrap the accelerator in a simple peripheral interface
- add interrupt/status reporting
- integrate clock/reset generation assumptions
- add memory subsystem assumptions or an AXI-like streaming adapter
- run FPGA bring-up before ASIC commitment

## Phase 4: tape-out preparation

- replace placeholder memories/macros with PDK-appropriate implementations
- complete DFT planning and scan strategy
- run synthesis, floorplanning, CTS, routing, STA, and DRC/LVS
- sign off power, IR drop, and electromigration for the prototype target
- package test collateral and bring-up firmware for first silicon

