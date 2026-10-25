# OpenLane (full P&R, local/manual)

CI only runs a lightweight Yosys synthesis check (`make sky130-synth-yosys-only`).
Full place-and-route and signoff is run locally with **upstream OpenLane**
([The-OpenROAD-Project/OpenLane](https://github.com/The-OpenROAD-Project/OpenLane)).
We do not depend on the `efabless/openlane` Docker image in CI, which keeps the
repo independent of any single maintained fork and CI fast and reliable.

## Why two tiers

| Tier | Where | Purpose |
| --- | --- | --- |
| Yosys synthesis | CI | Fast check that RTL synthesizes cleanly (no Docker, PDK-agnostic) |
| OpenLane P&R | Local/manual | Hardening run: floorplan, placement, CTS, routing, STA, and physical verification reports |

The OpenLane design configuration, timing constraints, and pin ordering are in this
directory. They target `dpu_tile` with `DATA_W=8`, `ACC_W=16`, and `LEN_W=6`.
The run is block-level implementation collateral, not a tapeout signoff package:
review all reports and complete the project- and shuttle-specific checks before
submitting GDSII.

## Running upstream OpenLane locally

Prerequisites: Docker, git, make, Python 3.

```sh
git clone https://github.com/The-OpenROAD-Project/OpenLane.git
cd OpenLane
make            # installs the PDK (sky130A) and pulls the tooling image
make test       # sanity check of the install
```

From the repository root, set `OPENLANE_ROOT` to that checkout and run:

```sh
export OPENLANE_ROOT=/path/to/OpenLane
make sky130-synth
```

The target uses the checked-in `openlane/config.json`. Alternatively, from the
OpenLane checkout run `make mount`, then
`./flow.tcl -design /path/to/dpu/openlane`.

See `docs/SYNTHESIS.md` for the synthesis-only flow.
