.PHONY: sim clean formal sky130-synth

SIM_OUT := simv
OPENLANE_IMAGE := efabless/openlane:latest

sim:
	iverilog -g2012 -Wall -o $(SIM_OUT) rtl/dpu_tile.sv tb/dpu_tile_tb.sv
	vvp $(SIM_OUT)

formal:
	@if ! command -v sby >/dev/null 2>&1; then \
		echo "SymbiYosys (sby) is not installed. Install yosys + sby to run formal proofs."; \
		exit 1; \
	fi
	sby -f formal/dpu_tile.sby

sky130-synth:
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "Docker is required for the SKY130 OpenLane flow."; \
		exit 1; \
	fi
	docker run --rm -v "$$(pwd):/work" -w /work $(OPENLANE_IMAGE) \
		sh -lc "cd /work && openlane --run_file openlane/config.json"

clean:
	rm -f $(SIM_OUT) *.vcd
	rm -rf formal/output
