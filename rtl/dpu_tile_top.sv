module dpu_tile_top #(
    parameter int DATA_W = 8,
    parameter int ACC_W  = 16,
    parameter int LEN_W  = 6
) (
    input  logic                         clk,
    input  logic                         rst_n,
    input  logic                         cfg_valid,
    output logic                         cfg_ready,
    input  logic        [LEN_W-1:0]      cfg_len,
    input  logic                         in_valid,
    output logic                         in_ready,
    input  logic signed [DATA_W-1:0]     in_a,
    input  logic signed [DATA_W-1:0]     in_b,
    output logic                         out_valid,
    input  logic                         out_ready,
    output logic signed [ACC_W-1:0]      out_sum
);

    dpu_tile #(
        .DATA_W(DATA_W),
        .ACC_W(ACC_W),
        .LEN_W(LEN_W)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .cfg_valid(cfg_valid),
        .cfg_ready(cfg_ready),
        .cfg_len(cfg_len),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_a(in_a),
        .in_b(in_b),
        .out_valid(out_valid),
        .out_ready(out_ready),
        .out_sum(out_sum)
    );

endmodule
