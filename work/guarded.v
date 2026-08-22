// Guarded routing-risk experiment.
//
// SW0 is pulled high when its DIP switch is open.  In that safe position the
// counter is synchronously forced to zero, so adjacent counter drivers agree.
// Closing SW0 enables counting; PROBE records that enable window externally.

module top(
    input  clk,
    input  SW0,
    output LED_R,
    output LED_G,
    output LED_B,
    output PROBE_ENABLE,
    output PROBE_SOURCE,
    output PROBE_DESTINATION
);
   reg [25:0] counter;
   wire conflict_enable = ~SW0;
   wire counter4_next = counter[4] ^ (&counter[3:0]);

   assign PROBE_ENABLE = conflict_enable;
   assign PROBE_SOURCE = counter4_next;
   assign PROBE_DESTINATION = counter[5];
   assign LED_R = ~counter[23];
   assign LED_G = ~counter[24];
   assign LED_B = ~counter[25];

   initial counter = 0;

   always @(posedge clk) begin
      if (conflict_enable)
        counter <= counter + 1'b1;
      else
        counter <= 0;
   end
endmodule
