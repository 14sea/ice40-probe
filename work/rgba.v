// RGBA fixture: the negative case of the hard-IP survey.
//
// SB_RGBA_DRV is the one surveyed block that gets no driver identity, and the
// reason is not "not modelled yet" but "there is nothing to model": it drives
// three package pins and reads five fabric inputs, and has no output that
// enters the programmable fabric at all.  A negative is only worth as much as
// the enumeration behind it, so `rgba_check.py` accounts for every one of the
// block's twenty-eight database ports and runs the same endpoint search that
// finds fifteen for I2C and twenty-five for SPI.
//
// The block has to be really instantiated and really enabled, otherwise the
// negative is vacuous: "no fabric output" is trivially true of a design that
// contains no RGB driver.  RGBA_DRV_EN is read back from the built ASC, and
// the same bit is asserted clear in a design without the block.
//
// CURREN and RGBLEDEN are tied high; with them low the block builds, routes
// and does nothing -- the empty-shell shape this project has hit with a PLL
// wired through LOCK and an SPRAM left powered off.
module top(
    input  clk,
    output RGB0,
    output RGB1,
    output RGB2
);
    reg [23:0] counter = 0;

    always @(posedge clk)
        counter <= counter + 1'b1;

    SB_RGBA_DRV #(
        .CURRENT_MODE("0b1"),             // half current
        .RGB0_CURRENT("0b000001"),
        .RGB1_CURRENT("0b000001"),
        .RGB2_CURRENT("0b000001")
    ) rgba (
        .CURREN(1'b1),
        .RGBLEDEN(1'b1),
        .RGB0PWM(counter[23]),
        .RGB1PWM(counter[22]),
        .RGB2PWM(counter[21]),
        .RGB0(RGB0),
        .RGB1(RGB1),
        .RGB2(RGB2)
    );
endmodule
