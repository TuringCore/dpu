SIM_OUT := simv

.PHONY: sim clean formal sky130-synth sky130-synth-local sky130-synth-yosys-only perf perf-sim perf-synth f2-help f2-prepare f2-register f2-launch

# Frozen tile configuration
DATA_W ?= 8
ACC_W  ?= 16
LEN_W  ?= 6
PDK_ROOT ?= $(HOME)/.volare
SKY130_LIB ?= $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib
SYNTH_DIR := build/synth
YOSYS_READ := read_verilog -sv rtl/dpu_tile.sv; chparam -set DATA_W $(DATA_W) -set ACC_W $(ACC_W) -set LEN_W $(LEN_W) dpu_tile; hierarchy -top dpu_tile

sim:
	iverilog -g2012 -Wall -o $(SIM_OUT) rtl/dpu_tile.sv tb/dpu_tile_tb.sv
	vvp $(SIM_OUT)

formal:
	@if ! command -v sby >/dev/null 2>&1; then \
		echo "SymbiYosys (sby) is not installed. Install yosys + sby to run formal proofs."; \
		exit 1; \
	fi
	sby -f formal/dpu_tile.sby
	sby -f formal/dpu_tile_cover.sby

# Requires Docker + OpenLane (see openlane/README.md); runs the full flow.
sky130-synth:
	@if [ -z "$$OPENLANE_ROOT" ]; then \
		echo "Set OPENLANE_ROOT to an upstream OpenLane checkout. See openlane/README.md."; \
		exit 1; \
	fi
	@if [ ! -f "$$OPENLANE_ROOT/flow.tcl" ]; then \
		echo "No flow.tcl found under OPENLANE_ROOT=$$OPENLANE_ROOT."; \
		exit 1; \
	fi
	cd $${OPENLANE_ROOT:-.} && make mount MOUNT_CMD='./flow.tcl -design $(CURDIR)/openlane'

# Lightweight, PDK-agnostic synthesis check (used in CI); no Docker, no liberty.
sky130-synth-yosys-only:
	@command -v yosys >/dev/null 2>&1 || { echo "yosys is not installed"; exit 1; }
	@mkdir -p $(SYNTH_DIR)
	yosys -p "$(YOSYS_READ); synth -top dpu_tile -flatten; check -assert; stat; write_verilog -noattr $(SYNTH_DIR)/dpu_tile_generic.v"

# Maps to sky130_fd_sc_hd cells; needs the sky130 liberty (set SKY130_LIB or PDK_ROOT).
sky130-synth-local:
	@command -v yosys >/dev/null 2>&1 || { echo "yosys is not installed"; exit 1; }
	@test -f "$(SKY130_LIB)" || { echo "Liberty not found: $(SKY130_LIB). Set SKY130_LIB or PDK_ROOT."; exit 1; }
	@mkdir -p $(SYNTH_DIR)
	yosys -q -p "$(YOSYS_READ); synth -top dpu_tile -flatten; dfflibmap -liberty $(SKY130_LIB); abc -liberty $(SKY130_LIB); opt_clean -purge; check -assert; tee -o $(SYNTH_DIR)/stat.txt stat -liberty $(SKY130_LIB); write_verilog -noattr $(SYNTH_DIR)/dpu_tile_sky130.v"

# Performance scorecard: cycle-accurate sim + yosys stat/ltp -> printed table.
PERF_DIR := build/perf
perf-sim:
	@mkdir -p $(PERF_DIR)
	iverilog -g2012 -o $(PERF_DIR)/perf.vvp rtl/dpu_tile.sv tb/dpu_tile_perf_tb.sv
	vvp $(PERF_DIR)/perf.vvp | tee $(PERF_DIR)/sim.log

perf-synth:
	@command -v yosys >/dev/null 2>&1 || { echo "yosys is not installed"; exit 1; }
	@mkdir -p $(PERF_DIR)
	yosys -p "$(YOSYS_READ); synth -top dpu_tile -flatten; check -assert; stat; ltp -noff" > $(PERF_DIR)/synth.log

perf: perf-sim perf-synth
	python3 scripts/perf_report.py --sim $(PERF_DIR)/sim.log --synth $(PERF_DIR)/synth.log --data-w $(DATA_W) --acc-w $(ACC_W) --len-w $(LEN_W)

# AWS EC2 F2 / FPGA deployment helpers.
# The repo's RTL is synthesizable and verifiable without vendor tooling, but the F2 flow
# needs an already-generated bitstream and the AWS CLI (or an equivalent deployment toolchain).
F2_SCRIPT := scripts/f2_deploy.py

BITSTREAM ?= build/f2/dpu_bitstream.bin
S3_BUCKET ?= my-dpu-fpga-bucket
S3_PREFIX ?= dpu/f2
AFI_NAME ?= dpu-f2-image
AFI_DESCRIPTION ?= DPU FPGA image for diffusion inference experiments
AWS_REGION ?= us-east-1
INSTANCE_TYPE ?= f2
AMI_ID ?=
KEY_NAME ?=
SECURITY_GROUP ?=

f2-help:
	python3 $(F2_SCRIPT) --help

f2-prepare:
	python3 $(F2_SCRIPT) prepare --bitstream $(BITSTREAM) --output-dir build/f2 --bucket $(S3_BUCKET) --prefix $(S3_PREFIX)

f2-register:
	python3 $(F2_SCRIPT) register --bitstream $(BITSTREAM) --name "$(AFI_NAME)" --description "$(AFI_DESCRIPTION)" --bucket $(S3_BUCKET) --prefix $(S3_PREFIX) --region $(AWS_REGION)

f2-launch:
	python3 $(F2_SCRIPT) launch --instance-type $(INSTANCE_TYPE) --ami $(AMI_ID) --key-name $(KEY_NAME) --security-group $(SECURITY_GROUP)

clean:
	rm -f $(SIM_OUT) *.vcd
	rm -rf formal/output build
