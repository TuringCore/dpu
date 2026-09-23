module dpu_tile_properties;
    localparam int DATA_W = 8;
    localparam int ACC_W  = 16;
    localparam int LEN_W  = 4;

    logic                         clk;
    logic                         rst_n;
    (* anyseq *) logic            cfg_valid;
    logic                         cfg_ready;
    (* anyseq *) logic [LEN_W-1:0] cfg_len;
    (* anyseq *) logic            in_valid;
    logic                         in_ready;
    (* anyseq *) logic signed [DATA_W-1:0] in_a;
    (* anyseq *) logic signed [DATA_W-1:0] in_b;
    logic                         out_valid;
    (* anyseq *) logic            out_ready;
    logic signed [ACC_W-1:0]      out_sum;

    logic                         model_active_q;
    logic [LEN_W-1:0]             model_remaining_q;
    logic signed [ACC_W-1:0]      model_acc_q;
    logic                         model_out_valid_q;
    logic signed [ACC_W-1:0]      model_out_sum_q;
    logic                         past_valid_q;

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

    function automatic logic signed [ACC_W-1:0] sat_add_product_model(
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
                sat_add_product_model = {1'b0, {(ACC_W - 1){1'b1}}};
            end else if (raw_sum < min_ext) begin
                sat_add_product_model = {1'b1, {(ACC_W - 1){1'b0}}};
            end else begin
                sat_add_product_model = raw_sum[ACC_W-1:0];
            end
        end
    endfunction

    initial clk = 1'b0;
    always #1 clk = ~clk;

    initial begin
        rst_n = 1'b0;
        #2;
        rst_n = 1'b1;
    end

    always_ff @(posedge clk) begin
        past_valid_q <= 1'b1;

        if (!rst_n) begin
            model_active_q    <= 1'b0;
            model_remaining_q <= '0;
            model_acc_q       <= '0;
            model_out_valid_q <= 1'b0;
            model_out_sum_q   <= '0;
        end else begin
            if (model_out_valid_q && out_ready) begin
                model_out_valid_q <= 1'b0;
            end

            if (cfg_valid && cfg_ready) begin
                model_acc_q <= '0;
                if (cfg_len == '0) begin
                    model_active_q    <= 1'b0;
                    model_remaining_q <= '0;
                    model_out_valid_q <= 1'b1;
                    model_out_sum_q   <= '0;
                end else begin
                    model_active_q    <= 1'b1;
                    model_remaining_q <= cfg_len;
                end
            end else if (in_valid && in_ready) begin
                model_acc_q <= sat_add_product_model(model_acc_q, in_a, in_b);
                if (model_remaining_q == {{(LEN_W - 1){1'b0}}, 1'b1}) begin
                    model_active_q    <= 1'b0;
                    model_remaining_q <= '0;
                    model_out_valid_q <= 1'b1;
                    model_out_sum_q   <= sat_add_product_model(model_acc_q, in_a, in_b);
                end else begin
                    model_remaining_q <= model_remaining_q - 1'b1;
                end
            end
        end
    end

    always_ff @(posedge clk) begin
        if (past_valid_q && rst_n) begin
            if ($past(cfg_valid && !cfg_ready)) begin
                assume(cfg_valid);
                assume($stable(cfg_len));
            end
            if ($past(in_valid && !in_ready)) begin
                assume(in_valid);
                assume($stable(in_a));
                assume($stable(in_b));
            end
        end
    end

    always_ff @(posedge clk) begin
        if (!past_valid_q || !rst_n) begin
            assert(!out_valid);
            assert(cfg_ready);
        end else begin
            assert(out_valid == model_out_valid_q);
            assert(out_sum == model_out_sum_q);
            assert(cfg_ready == (!model_active_q && !model_out_valid_q));
            assert(in_ready == (model_active_q && !model_out_valid_q));
            if ($past(out_valid && !out_ready)) begin
                assert(out_valid);
                assert($stable(out_sum));
            end
        end
    end

endmodule

