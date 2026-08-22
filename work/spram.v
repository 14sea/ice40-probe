// SPRAM fixture: the UP5K single-port RAM is hard IP living in ipcon tiles, so
// its read-data outputs are another source class that a LUT/IO/RAM-read/DSP
// whitelist may or may not recognise.
//
// POWEROFF is active-low and must be driven high for normal operation; leaving
// it low is the classic way to end up with a fixture that builds, routes, and
// silently does nothing.
module top(
    input  clk,
    output LED_R,
    output LED_G,
    output LED_B
);
    reg [13:0] address = 0;
    reg [15:0] pattern = 16'h1234;
    reg        write_enable = 0;

    always @(posedge clk) begin
        address <= address + 1'b1;
        pattern <= {pattern[14:0], pattern[15] ^ pattern[13]};
        write_enable <= ~write_enable;
    end

    wire [15:0] read_data;

    SB_SPRAM256KA spram (
        .ADDRESS(address),
        .DATAIN(pattern),
        .MASKWREN(4'b1111),
        .WREN(write_enable),
        .CHIPSELECT(1'b1),
        .CLOCK(clk),
        .STANDBY(1'b0),
        .SLEEP(1'b0),
        .POWEROFF(1'b1),          // active low: 1 = powered
        .DATAOUT(read_data)
    );

    // Consume the read port so it cannot be optimised away.
    assign LED_R = ~read_data[0];
    assign LED_G = ~(^read_data[7:1]);
    assign LED_B = ~(^read_data[15:8]);
endmodule
