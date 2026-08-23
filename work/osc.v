// Oscillator fixture: the third hard-IP fixture.
//
// icebox annotates two of the UP5K padin -> global-network entries as HSOSC and
// LSOSC, which is the same shape as the PLL global path: the oscillator feeds a
// global network without any source segment of its own in the graph.  If that
// holds, both oscillator-driven globals are undriven nets in the model and a
// second source routed onto one of them produces no conflict.
//
// Both oscillators are enabled and both clocks are consumed, so neither can be
// optimised away.  PU/EN are tied high: with them low the block builds, routes
// and produces nothing -- the same class of empty-shell fixture as a PLL wired
// through a LUT because LOCK was connected.
// OSC_CONFLICT_PROBE exists only so that a LUT output reaches the local nets
// of io tile (12,31), whose `fabout` sits in the same configured net as the
// HFOSC-driven global.  Without a driver on one of that mux's eight sources
// there is no way to construct a second source for the global, and the known
// positive below could not exist.  Package sg48 bonds out (12,31) block 1 as
// pin 35; the LFOSC's corresponding tile (12,0) has no bonded pin, which is why
// only the HFOSC side has a named positive.
module top(
    output LED_R,
    output LED_G,
    output LED_B,
    output OSC_CONFLICT_PROBE
);
    wire clk_hf;
    wire clk_lf;

    SB_HFOSC #(
        .CLKHF_DIV("0b10")        // 48 MHz / 4 = 12 MHz
    ) hfosc (
        .CLKHFPU(1'b1),
        .CLKHFEN(1'b1),
        .CLKHF(clk_hf)
    );

    SB_LFOSC lfosc (
        .CLKLFPU(1'b1),
        .CLKLFEN(1'b1),
        .CLKLF(clk_lf)
    );

    reg [23:0] fast = 0;
    always @(posedge clk_hf)
        fast <= fast + 1'b1;

    reg [7:0] slow = 0;
    always @(posedge clk_lf)
        slow <= slow + 1'b1;

    assign LED_R = ~fast[23];
    assign LED_G = ~slow[7];
    assign LED_B = ~(fast[22] ^ slow[6]);
    assign OSC_CONFLICT_PROBE = fast[5] ^ slow[3];
endmodule
