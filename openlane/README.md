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
| OpenLane P&R | Local/manual | Floorplan, placement, CTS, routing, STA, DRC/LVS for MPW signoff |

## Running upstream OpenLane locally

Prerequisites: Docker, git, make, Python 3.

```sh
git clone https://github.com/The-OpenROAD-Project/OpenLane.git
cd OpenLane
make            # installs the PDK (sky130A) and pulls the tooling image
make test       # sanity check of the install
```

Then, from this repo, point OpenLane at a design directory containing `config.json`
(top `dpu_tile`, `DATA_W=8`, `ACC_W=16`, `LEN_W=6`, 100 MHz i.e. `CLOCK_PERIOD=10` ns,
SDC from the existing constraints) and run:

```sh
export OPENLANE_ROOT=/path/to/OpenLane
make sky130-synth        # requires Docker + OpenLane
```

or directly inside the OpenLane checkout: `make mount` then `./flow.tcl -design /path/to/dpu/openlane`.

See `docs/SYNTHESIS.md` for the synthesis-only flow.
