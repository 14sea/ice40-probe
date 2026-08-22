module guarded_tb;
   reg clk = 0;
   reg sw0 = 1;
   wire led_r, led_g, led_b;
   wire probe_enable, probe_source, probe_destination;
   reg [25:0] expected = 0;
   integer mismatch_count = 0;
   integer i;

   chip dut(
      .io_12_31_1(clk),
      .io_22_0_1(sw0),
      .io_4_31_0(led_b),
      .io_5_31_0(led_r),
      .io_6_31_0(led_g),
      .io_5_0_0(probe_enable),
      .io_6_0_1(probe_source),
      .io_8_31_0(probe_destination)
   );

   always #1 clk = ~clk;

   task check_probes;
      begin
         if (probe_source !== (expected[4] ^ (&expected[3:0])))
           $fatal(1, "source mismatch at counter=%0d", expected);
         if (probe_destination !== expected[5])
           $fatal(1, "destination mismatch at counter=%0d", expected);
      end
   endtask

   initial begin
      // Safe switch position: reset asserted, both candidate drivers agree.
      repeat (2) @(negedge clk);
      if (probe_enable !== 0 || probe_source !== 0 || probe_destination !== 0)
        $fatal(1, "guarded reset state is not safe");

      // Enabled window: exactly half of a 64-state period predicts contention.
      sw0 = 0;
      for (i = 0; i < 64; i = i + 1) begin
         @(negedge clk);
         expected = expected + 1'b1;
         if (probe_enable !== 1)
           $fatal(1, "enable marker is low during enabled window");
         check_probes();
         if (probe_source != probe_destination)
           mismatch_count = mismatch_count + 1;
      end
      if (mismatch_count != 32)
        $fatal(1, "expected 32/64 mismatches, got %0d", mismatch_count);

      // Opening SW0 must return the design to the agreeing state.
      sw0 = 1;
      @(negedge clk);
      expected = 0;
      check_probes();
      if (probe_enable !== 0)
        $fatal(1, "enable marker did not clear");
      $display("PASS: guarded baseline, mismatch duty 32/64, safe recovery");
      $finish;
   end
endmodule
