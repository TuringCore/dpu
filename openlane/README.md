# SKY130 standalone signoff scaffold for the DPU tile
#
# This is intentionally minimal and intentionally standalone. It does not depend on
# a Caravel harness or any vendor-specific wrapper. The purpose is to provide a
# clean, OpenLane-compatible foundation for synthesis and physical signoff on
# SKY130.
#
# Usage:
#   docker run --rm -it -v $(pwd):/work -w /work efabless/openlane:latest \
#     sh -lc "cd /work && openlane --run_file openlane/config.json"

This design is intentionally structured as a standalone IP block. For the first
SKY130 signoff-quality run, the DPU tile is wrapped in `rtl/dpu_tile_top.sv` so
that the OpenLane project can target a single top-level module without a custom
board or Caravel dependency.

Next steps:
  1. Freeze the final parameter set for the tapeout configuration.
  2. Adjust the SDC constraints to match the chosen target frequency.
  3. Re-run synthesis and place-and-route with the actual sky130 PDK install.
  4. Iterate on DRC/LVS before committing to a real MPW submission.
