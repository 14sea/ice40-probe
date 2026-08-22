// PLL fixture: puts a hard-IP source into the configured-net graph.
//
// Why this shape:
//   * icebox's pllinfo_db["5k"] places PLLOUT_A at io tile (12,31) block 1 and
//     PLLOUT_B at (13,31) block 0, so a PLL output is delivered through an IO
//     tile's D_IN path -- it is NOT a segment of its own.  A driver model that
//     only pattern-matches `io_*/D_IN_*` therefore counts a PLL output by
//     accident, without ever consulting the PLL configuration.
//   * LOCK is deliberately unused: with LOCK connected nextpnr reports "PLL has
//     LOCK output, need to pass all outputs via LUT" and routes every PLL
//     output through a LUT, which would make the LUT -- not the PLL -- the
//     driver in the graph and defeat the purpose of the fixture.
//   * Port A's GLOBAL output is used as a clock so it reaches a glb_netwk;
//     port B's CORE output is consumed as DATA, not as a clock, so nextpnr
//     cannot promote it to a global and it stays in fabric routing.  That is
//     what makes the core path and the global path two distinct components
//     rather than one promoted global net.
module top(
    input  clk_pad,
    output LED_R,
    output LED_G,
    output LED_B,
    output GLOBAL_CONFLICT_PROBE,
    output GLOBAL_CONFLICT_PROBE_B
);
    wire global_a;
    wire core_b;

    SB_PLL40_2F_PAD #(
        .FEEDBACK_PATH("SIMPLE"),
        .PLLOUT_SELECT_PORTA("GENCLK"),
        .PLLOUT_SELECT_PORTB("GENCLK_HALF"),
        .DIVR(4'b0000),
        .DIVF(7'b0111111),
        .DIVQ(3'b100),
        .FILTER_RANGE(3'b001)
    ) pll (
        .PACKAGEPIN(clk_pad),
        .PLLOUTGLOBALA(global_a),
        .PLLOUTCOREB(core_b),
        .RESETB(1'b1),
        .BYPASS(1'b0)
    );

    // Port A global output: used as a clock, so it lands on a global network.
    reg [23:0] counter = 0;
    always @(posedge global_a)
        counter <= counter + 1'b1;

    // Port B core output: sampled as data, so it stays in fabric routing.
    reg [3:0] sampled = 0;
    always @(posedge global_a)
        sampled <= {sampled[2:0], core_b};

    assign LED_R = ~counter[23];
    assign LED_G = ~(^sampled);
    assign LED_B = ~(counter[22] ^ sampled[3]);

    // Pin 13 occupies the fabric global-buffer input tile for glb_netwk_7.
    // This data output keeps a driven local route next to that input, allowing
    // a single routing-bit flip to exercise PLL-vs-fabric global contention.
    assign GLOBAL_CONFLICT_PROBE = sampled[0];
    assign GLOBAL_CONFLICT_PROBE_B = sampled[1];
endmodule
