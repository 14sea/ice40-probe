// fill the UP5K: 60 independent 64-bit LFSRs, XOR-reduced to the RGB pins
module top(input [3:0] SW, input clk, output LED_R, output LED_G, output LED_B);
   localparam N = 60;
   reg [63:0] lfsr [0:N-1];
   integer j;
   initial for (j = 0; j < N; j = j + 1) lfsr[j] = 64'h1 + j;
   genvar g;
   generate
      for (g = 0; g < N; g = g + 1) begin : bank
         always @(posedge clk)
            lfsr[g] <= {lfsr[g][62:0],
                        lfsr[g][63] ^ lfsr[g][62] ^ lfsr[g][60] ^ lfsr[g][59] ^ SW[g % 4]};
      end
   endgenerate
   wire [N-1:0] tap0, tap1, tap2;
   generate
      for (g = 0; g < N; g = g + 1) begin : taps
         assign tap0[g] = lfsr[g][0];
         assign tap1[g] = lfsr[g][21];
         assign tap2[g] = lfsr[g][42];
      end
   endgenerate
   assign LED_R = ^tap0;
   assign LED_G = ^tap1;
   assign LED_B = ^tap2;
endmodule
