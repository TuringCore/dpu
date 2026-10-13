# SKY130 synthesis flow

Target configuration: `DATA_W=8`, `ACC_W=16`, `LEN_W=6`, sky130 (`sky130_fd_sc_hd`), 100 MHz (10 ns).
The Makefile overrides the RTL defaults via `chparam`.

## Targets

| Target | Needs | Description |
| --- | --- | --- |
| `make sky130-synth-yosys-only` | yosys | PDK-agnostic synthesis + `check -assert`; used in CI |
| `make sky130-synth-local` | yosys + sky130 liberty | Maps flops (`dfflibmap`) and logic (`abc`) to `sky130_fd_sc_hd` cells, writes `build/synth/stat.txt` and `build/synth/dpu_tile_sky130.v` |
| `make sky130-synth` | Docker + upstream OpenLane | Full OpenLane flow; see `openlane/README.md` |

## Yosys with sky130 libraries

`sky130-synth-local` uses the liberty file
`$(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib`
(override with `SKY130_LIB=...`). The PDK can be installed with the upstream OpenLane
`make` or with [volare](https://github.com/efabless/volare). `.lef` files
(`.../sky130_fd_sc_hd/lef/`) are not used by Yosys; they are consumed by OpenROAD
during P&R in OpenLane.

```sh
make sky130-synth-local PDK_ROOT=$HOME/.volare
```

## Expected mappings and constraints

- Registers map to `sky130_fd_sc_hd__dfxtp_*` (or `dfrtp_*` with async reset).
- Combinational logic (multiplier, adder, saturation) maps to `nand/nor/a21oi/xor/xnor/mux2` cells via ABC.
- `check -assert` must pass: no combinational loops, no undriven/multi-driven wires.
- Timing: 100 MHz target; timing closure is evaluated by STA in OpenLane, not in the Yosys check.
