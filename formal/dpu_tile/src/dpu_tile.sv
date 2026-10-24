`timescale 1ns/1ps

module dpu_tile #(
    parameter int DATA_W = 8,
    parameter int ACC_W  = 24,
    parameter int LEN_W  = 8
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

    logic                            active_q;
    logic        [LEN_W-1:0]         remaining_q;
    logic signed [ACC_W-1:0]         acc_q;
    logic                            out_valid_q;
    logic signed [ACC_W-1:0]         out_sum_q;

    localparam logic signed [ACC_W-1:0] ACC_MAX = {1'b0, {(ACC_W-1){1'b1}}};
    localparam logic signed [ACC_W-1:0] ACC_MIN = {1'b1, {(ACC_W-1){1'b0}}};

    function automatic logic signed [ACC_W-1:0] sat_add_product(
        input logic signed [ACC_W-1:0]      lhs,
        input logic signed [DATA_W-1:0]     rhs_a,
        input logic signed [DATA_W-1:0]     rhs_b
    );
        logic signed [(2*DATA_W)-1:0] product;
        logic signed [ACC_W:0]        lhs_ext;
        logic signed [ACC_W:0]        product_ext;
        logic signed [ACC_W:0]        raw_sum;
        logic signed [ACC_W:0]        max_ext;
        logic signed [ACC_W:0]        min_ext;
        begin
            product     = rhs_a * rhs_b;
            lhs_ext     = {lhs[ACC_W-1], lhs};
            product_ext = {{(ACC_W + 1 - (2 * DATA_W)){product[(2 * DATA_W) - 1]}}, product};
            raw_sum     = lhs_ext + product_ext;
            max_ext     = $signed({{2{1'b0}}, {(ACC_W - 1){1'b1}}});
            min_ext     = $signed({{2{1'b1}}, {(ACC_W - 1){1'b0}}});

            if (raw_sum > max_ext) begin
                sat_add_product = ACC_MAX;
            end else if (raw_sum < min_ext) begin
                sat_add_product = ACC_MIN;
            end else begin
                sat_add_product = raw_sum[ACC_W-1:0];
            end
        end
    endfunction

    wire cfg_fire = cfg_valid && cfg_ready;
    wire in_fire  = in_valid && in_ready;
    wire out_fire = out_valid_q && out_ready;

    assign cfg_ready = !active_q && !out_valid_q;
    assign in_ready  = active_q && !out_valid_q;
    assign out_valid = out_valid_q;
    assign out_sum   = out_sum_q;

    initial begin
        if (ACC_W < (2 * DATA_W)) begin
            $fatal(1, "ACC_W must be at least 2*DATA_W for safe product accumulation.");
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_q    <= 1'b0;
            remaining_q <= '0;
            acc_q       <= '0;
            out_valid_q <= 1'b0;
            out_sum_q   <= '0;
        end else begin
            if (out_fire) begin
                out_valid_q <= 1'b0;
            end

            if (cfg_fire) begin
                acc_q <= '0;
                if (cfg_len == '0) begin
                    active_q    <= 1'b0;
                    remaining_q <= '0;
                    out_valid_q <= 1'b1;
                    out_sum_q   <= '0;
                end else begin
                    active_q    <= 1'b1;
                    remaining_q <= cfg_len;
                    out_sum_q   <= out_sum_q;
                end
            end else if (in_fire) begin
                acc_q <= sat_add_product(acc_q, in_a, in_b);
                if (remaining_q == {{(LEN_W - 1){1'b0}}, 1'b1}) begin
                    active_q    <= 1'b0;
                    remaining_q <= '0;
                    out_valid_q <= 1'b1;
                    out_sum_q   <= sat_add_product(acc_q, in_a, in_b);
                end else begin
                    remaining_q <= remaining_q - 1'b1;
                end
            end
        end
    end

endmodule


