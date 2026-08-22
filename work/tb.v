module tb;
   reg clk = 0;
   wire led_r, led_g, led_b;
   reg [2:0] state;
   reg expected_r, expected_g, expected_b;
   integer i;

   chip dut(
      .io_12_31_1(clk),
      .io_4_31_0(led_b),  // pin 39
      .io_5_31_0(led_r),  // pin 40
      .io_6_31_0(led_g)   // pin 41
   );

   initial begin
      $display("state  LED_R LED_G LED_B");
      for (i = 0; i < 8; i = i + 1) begin
         state = i;
         dut.n24 = state[0];
         dut.n25 = state[1];
         dut.n26 = state[2];
`ifdef EXPECT_MUT2
         expected_r = ~state[0];
         expected_g = ~state[1];
         expected_b =  state[2];
`elsif EXPECT_MUT3
         expected_r =  state[0];
         expected_g = ~state[1];
         expected_b = ~state[2];
`else
         expected_r = ~state[0];
         expected_g = ~state[1];
         expected_b = ~state[2];
`endif
         #1;
         $display("%3d      %b     %b     %b", i, led_r, led_g, led_b);
         if ({led_r, led_g, led_b} !== {expected_r, expected_g, expected_b})
            $fatal(1, "unexpected LED output for state %0d", i);
      end
      $display("PASS");
      $finish;
   end
endmodule
