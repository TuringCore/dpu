set_units -time ns
create_clock -name core_clock -period 10 [get_ports clk]
set_input_delay 1.0 -clock core_clock [all_inputs -no_clocks]
set_output_delay 1.0 -clock core_clock [all_outputs]
set_load 5.0 [all_outputs]
