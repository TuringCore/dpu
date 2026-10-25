`timescale 1ns/1ps

// Cycle-accurate performance characterization of dpu_tile.
// Emits machine-readable "PERF key=value" lines consumed by scripts/perf_report.py.
module dpu_tile_perf_tb;
    localparam int DATA_W = 8;
    localparam int ACC_W  = 16;
    localparam int LEN_W  = 6;
    localparam int MAX_LEN = (1 << LEN_W) - 1;
    localparam int NUM_JOBS = 1000;

    logic                         clk = 1'b0;
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

    dpu_tile #(.DATA_W(DATA_W), .ACC_W(ACC_W), .LEN_W(LEN_W)) dut (.*);

    always #5 clk = ~clk;

    longint unsigned cycle;
    always_ff @(posedge clk) cycle <= rst_n ? cycle + 1 : 0;

    // Runs one job of `len` MACs with a consumer that stalls `out_stall` cycles.
    task automatic run_job(input int len, input int out_stall, output longint unsigned latency);
        longint unsigned start;
        begin
            out_ready = 1'b0;
            while (!cfg_ready) @(posedge clk);
            start = cycle;
            cfg_valid = 1'b1; cfg_len = len[LEN_W-1:0];
            @(posedge clk); cfg_valid = 1'b0;
            for (int i = 0; i < len; i++) begin
                in_valid = 1'b1; in_a = 8'sd3; in_b = -8'sd2;
                @(posedge clk);
                while (!in_ready) @(posedge clk);
            end
            in_valid = 1'b0;
            while (!out_valid) @(posedge clk);
            repeat (out_stall) @(posedge clk);
            out_ready = 1'b1;
            latency = cycle - start;
            @(posedge clk);
            out_ready = 1'b0;
        end
    endtask

    longint unsigned lat, t0, t1, total_macs;
    int lens [3];

    initial begin
        lens[0] = 1; lens[1] = 16; lens[2] = MAX_LEN;
        rst_n = 1'b0; cfg_valid = 0; cfg_len = 0; in_valid = 0; in_a = 0; in_b = 0; out_ready = 0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        @(posedge clk);

        foreach (lens[k]) begin
            run_job(lens[k], 0, lat);
            $display("PERF latency_len_%0d_cycles=%0d", lens[k], lat);
        end

        run_job(MAX_LEN, 8, lat);
        $display("PERF latency_len_%0d_stall8_cycles=%0d", MAX_LEN, lat);

        t0 = cycle; total_macs = 0;
        for (int j = 0; j < NUM_JOBS; j++) begin
            run_job(MAX_LEN, 0, lat);
            total_macs += MAX_LEN;
        end
        t1 = cycle;
        $display("PERF sustained_cycles=%0d", t1 - t0);
        $display("PERF sustained_macs=%0d", total_macs);
        $display("PERF jobs=%0d", NUM_JOBS);
        $display("PERF max_len=%0d", MAX_LEN);
        $finish;
    end

    initial begin
        #100000000;
        $fatal(1, "perf testbench timeout");
    end
endmodule
