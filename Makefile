SIM_OUT := simv

.PHONY: sim clean formal

sim:
	iverilog -g2012 -Wall -o $(SIM_OUT) rtl/dpu_tile.sv tb/dpu_tile_tb.sv
	vvp $(SIM_OUT)

formal:
	@if ! command -v sby >/dev/null 2>&1; then \
		echo "SymbiYosys (sby) is not installed. Install yosys + sby to run formal proofs."; \
		exit 1; \
	fi
	sby -f formal/dpu_tile.sby

clean:
	rm -f $(SIM_OUT) *.vcd
	rm -rf formal/output

