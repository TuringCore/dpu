`ifndef VERILATOR
module testbench;
  reg [4095:0] vcdfile;
  reg clock;
`else
module testbench(input clock, output reg genclock);
  initial genclock = 1;
`endif
  reg genclock = 1;
  reg [31:0] cycle = 0;
  reg [0:0] PI_rst_n;
  wire [0:0] PI_clk = clock;
  dpu_tile_properties UUT (
    .rst_n(PI_rst_n),
    .clk(PI_clk)
  );
`ifndef VERILATOR
  initial begin
    if ($value$plusargs("vcd=%s", vcdfile)) begin
      $dumpfile(vcdfile);
      $dumpvars(0, testbench);
    end
    #5 clock = 0;
    while (genclock) begin
      #5 clock = 0;
      #5 clock = 1;
    end
  end
`endif
  initial begin
`ifndef VERILATOR
    #1;
`endif
    // UUT.$auto$async2sync.\cc:107:execute$1535  = 1'b0;
    // UUT.$auto$async2sync.\cc:107:execute$1547  = 1'b0;
    // UUT.$auto$async2sync.\cc:107:execute$1553  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$1539  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$1545  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$1551  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$1557  = 1'b0;
    // UUT.$auto$async2sync.\cc:116:execute$1563  = 1'b0;
    UUT._witness_.anyinit_procdff_1449 = 1'b0;
    UUT._witness_.anyinit_procdff_1450 = 1'b0;
    UUT._witness_.anyinit_procdff_1451 = 1'b0;
    UUT._witness_.anyinit_procdff_1452 = 16'b0000000000000000;
    UUT._witness_.anyinit_procdff_1453 = 1'b0;
    UUT._witness_.anyinit_procdff_1454 = 1'b0;
    UUT._witness_.anyinit_procdff_1455 = 4'b1000;
    UUT._witness_.anyinit_procdff_1456 = 1'b0;
    UUT._witness_.anyinit_procdff_1457 = 8'b00000000;
    UUT._witness_.anyinit_procdff_1458 = 8'b00000000;
    UUT.dut._witness_.anyinit_procdff_1328 = 1'b1;
    UUT.dut._witness_.anyinit_procdff_1333 = 4'b0001;
    UUT.dut._witness_.anyinit_procdff_1338 = 16'b1000000000000000;
    UUT.dut._witness_.anyinit_procdff_1343 = 1'b1;
    UUT.dut._witness_.anyinit_procdff_1348 = 16'b1111111111111111;
    UUT.model_active_q = 1'b0;
    UUT.model_out_valid_q = 1'b1;
    UUT.model_remaining_q = 4'b0000;
    UUT.past_valid_q = 1'b0;

    // state 0
    PI_rst_n = 1'b1;
    UUT.cfg_len = 4'b0000;
    UUT.cfg_valid = 1'b0;
    UUT.in_a = 8'b10000000;
    UUT.in_b = 8'b10000000;
    UUT.in_valid = 1'b0;
    UUT.out_ready = 1'b0;
  end
  always @(posedge clock) begin
    // state 1
    if (cycle == 0) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 2
    if (cycle == 1) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 3
    if (cycle == 2) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 4
    if (cycle == 3) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 5
    if (cycle == 4) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 6
    if (cycle == 5) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 7
    if (cycle == 6) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 8
    if (cycle == 7) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 9
    if (cycle == 8) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 10
    if (cycle == 9) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 11
    if (cycle == 10) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 12
    if (cycle == 11) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 13
    if (cycle == 12) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 14
    if (cycle == 13) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 15
    if (cycle == 14) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 16
    if (cycle == 15) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 17
    if (cycle == 16) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 18
    if (cycle == 17) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 19
    if (cycle == 18) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 20
    if (cycle == 19) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 21
    if (cycle == 20) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    // state 22
    if (cycle == 21) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b1;
    end

    // state 23
    if (cycle == 22) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b0000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b00000000;
      UUT.in_b <= 8'b00000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b1;
    end

    // state 24
    if (cycle == 23) begin
      PI_rst_n <= 1'b1;
      UUT.cfg_len <= 4'b1000;
      UUT.cfg_valid <= 1'b0;
      UUT.in_a <= 8'b10000000;
      UUT.in_b <= 8'b10000000;
      UUT.in_valid <= 1'b0;
      UUT.out_ready <= 1'b0;
    end

    genclock <= cycle < 24;
    cycle <= cycle + 1;
  end
endmodule
