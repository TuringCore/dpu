`timescale 1ns/1ps

module dpu_tile_tb;
    localparam int DATA_W = 8;
    localparam int ACC_W  = 16;
    localparam int LEN_W  = 6;

    logic                         clk;
    logic                         rst_n;
    logic                         cfg_valid;
    logic                         cfg_ready;
    logic        [LEN_W-1:0]      cfg_len;
    logic                         in_valid;
    logic                         in_ready;
    logic signed [DATA_W-1:0]     in_a;
    logic signed [DATA_W-1:0]     in_b;
    logic                         out_valid;
    logic                         out_ready;
    logic signed [ACC_W-1:0]      out_sum;

    integer                       failures;
    integer                       random_idx;
    integer                       sample_idx;
    integer                       job_len;
    integer                       expected;
    integer                       a_i;
    integer                       b_i;
    integer                       gap_cycles;

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

    function automatic integer sat_add_model(input integer lhs, input integer rhs);
        integer raw_sum;
        integer max_val;
        integer min_val;
        begin
            raw_sum = lhs + rhs;
            max_val = (1 << (ACC_W - 1)) - 1;
            min_val = -(1 << (ACC_W - 1));
            if (raw_sum > max_val) begin
                sat_add_model = max_val;
            end else if (raw_sum < min_val) begin
                sat_add_model = min_val;
            end else begin
                sat_add_model = raw_sum;
            end
        end
    endfunction

    task automatic drive_reset;
        begin
            cfg_valid = 1'b0;
            cfg_len   = '0;
            in_valid  = 1'b0;
            in_a      = '0;
            in_b      = '0;
            out_ready = 1'b0;
            rst_n     = 1'b0;
            repeat (3) @(posedge clk);
            rst_n = 1'b1;
            @(posedge clk);
        end
    endtask

    task automatic start_job(input integer length);
        begin
            @(negedge clk);
            cfg_len   = length[LEN_W-1:0];
            cfg_valid = 1'b1;
            while (!cfg_ready) begin
                @(negedge clk);
            end
            @(posedge clk);
            @(negedge clk);
            cfg_valid = 1'b0;
            cfg_len   = '0;
        end
    endtask

    task automatic send_sample(
        input integer a_val,
        input integer b_val,
        input integer pre_gap_cycles
    );
        begin
            repeat (pre_gap_cycles) @(negedge clk);
            @(negedge clk);
            in_a     = a_val;
            in_b     = b_val;
            in_valid = 1'b1;
            while (!in_ready) begin
                @(negedge clk);
            end
            @(posedge clk);
            @(negedge clk);
            in_valid = 1'b0;
            in_a     = '0;
            in_b     = '0;
        end
    endtask

    task automatic expect_output(
        input integer expected_sum,
        input integer stall_cycles
    );
        integer actual_sum;
        begin
            out_ready = 1'b0;
            repeat (stall_cycles) begin
                @(posedge clk);
                if (out_valid) begin
                    actual_sum = $signed(out_sum);
                    if (actual_sum != expected_sum) begin
                        $display("Mismatch while stalled: expected %0d got %0d", expected_sum, actual_sum);
                        failures = failures + 1;
                    end
                end
            end

            while (!out_valid) begin
                @(posedge clk);
            end

            actual_sum = $signed(out_sum);
            if (actual_sum != expected_sum) begin
                $display("Output mismatch: expected %0d got %0d", expected_sum, actual_sum);
                failures = failures + 1;
            end

            out_ready = 1'b1;
            @(posedge clk);
            out_ready = 1'b0;

            if (out_valid !== 1'b0) begin
                @(posedge clk);
            end
        end
    endtask

    task automatic expect_idle_ready;
        begin
            @(posedge clk);
            if (!cfg_ready) begin
                $display("Expected cfg_ready while idle");
                failures = failures + 1;
            end
            if (in_ready) begin
                $display("Did not expect in_ready while idle");
                failures = failures + 1;
            end
        end
    endtask

    initial begin
        clk = 1'b0;
        forever #5 clk = ~clk;
    end

    initial begin
        failures = 0;
        drive_reset();
        expect_idle_ready();

        $display("Running zero-length job test");
        start_job(0);
        expect_output(0, 2);
        expect_idle_ready();

        $display("Running directed dot-product test");
        start_job(4);
        expected = 0;
        expected = sat_add_model(expected, 3 * 4);
        send_sample(3, 4, 0);
        expected = sat_add_model(expected, -2 * 5);
        send_sample(-2, 5, 1);
        expected = sat_add_model(expected, -8 * -1);
        send_sample(-8, -1, 0);
        expected = sat_add_model(expected, 7 * -3);
        send_sample(7, -3, 2);
        expect_output(expected, 1);
        expect_idle_ready();

        $display("Running positive saturation test");
        start_job(3);
        expected = 0;
        repeat (3) begin
            expected = sat_add_model(expected, 127 * 127);
            send_sample(127, 127, 0);
        end
        expect_output(expected, 0);

        $display("Running negative saturation test");
        start_job(3);
        expected = 0;
        repeat (3) begin
            expected = sat_add_model(expected, -128 * 127);
            send_sample(-128, 127, 1);
        end
        expect_output(expected, 3);

        $display("Running backpressure stability test");
        start_job(2);
        expected = 0;
        expected = sat_add_model(expected, 11 * -9);
        send_sample(11, -9, 0);
        expected = sat_add_model(expected, -7 * -8);
        send_sample(-7, -8, 0);
        repeat (4) begin
            @(posedge clk);
            if (!out_valid) begin
                $display("Expected out_valid during backpressure hold");
                failures = failures + 1;
            end
            if ($signed(out_sum) != expected) begin
                $display("Expected stable out_sum=%0d during backpressure, got %0d", expected, $signed(out_sum));
                failures = failures + 1;
            end
        end
        expect_output(expected, 0);

        $display("Running randomized regression");
        for (random_idx = 0; random_idx < 50; random_idx = random_idx + 1) begin
            job_len = $urandom_range(0, 8);
            start_job(job_len);
            expected = 0;
            for (sample_idx = 0; sample_idx < job_len; sample_idx = sample_idx + 1) begin
                a_i = $urandom_range(0, 255) - 128;
                b_i = $urandom_range(0, 255) - 128;
                gap_cycles = $urandom_range(0, 2);
                expected = sat_add_model(expected, a_i * b_i);
                send_sample(a_i, b_i, gap_cycles);
            end
            expect_output(expected, $urandom_range(0, 2));
            expect_idle_ready();
        end

        if (failures == 0) begin
            $display("PASS: all DPU tile tests succeeded");
            $finish;
        end else begin
            $fatal(1, "FAIL: %0d DPU tile checks failed", failures);
        end
    end

endmodule


