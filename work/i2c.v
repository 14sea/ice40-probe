// I2C fixture: the fourth hard-IP fixture, after PLL, SPRAM and the on-chip
// oscillators.  The hard-IP inventory (`make hard-ip-inventory`) established
// that SB_I2C has fifteen outputs which enter the programmable fabric through
// `slf_op_*` segments on ipcon tiles -- the same segment class as SPRAM read
// data, and the same reason a `lutff_*/out` / `io_*/D_IN_*` / `ram/RDATA_*` /
// `mult/O_*` whitelist never sees them.
//
// Both instances are placed, because they are not symmetric in configuration:
// I2C_ENABLE_0 and I2C_ENABLE_1 of the left instance sit in two different IO
// tiles ((13,31) and (12,31)), while both bits of the right instance sit in
// one tile ((19,31)).  A fixture with only one of them would leave half of
// that layout untested -- the failure mode that made this project report 19
// SPI endpoints when the device has 25.
//
// Which instance nextpnr picks is decided by BUS_ADDR74, not by placement
// constraints: "0b0001" is the only value accepted for i2c_0 and "0b0011" the
// only one for i2c_1.
//
// SCLI/SDAI are driven from fabric registers rather than from the dedicated
// pads.  That is deliberate: it keeps the enabling bits' meaning honest.  If
// the pads were used, "the enable bits are set" and "the dedicated pins are
// muxed to the IP" would be indistinguishable in this fixture.
//
// Every one of the fifteen outputs per instance is consumed.  An output that
// nothing reads is not routed, its `slf_op` segment never enters the graph,
// and an identity for it could not be exercised -- the empty-shell fixture
// this project has hit twice before (PLL through LOCK, SPRAM with POWEROFF
// low).
module top(
    input  clk,
    output LED_R,
    output LED_G,
    output LED_B
);
    reg [7:0] bus_address = 0;
    reg       strobe = 0;
    reg       scl_in = 0;
    reg       sda_in = 0;

    always @(posedge clk) begin
        bus_address <= bus_address + 1'b1;
        strobe      <= ~strobe;
        scl_in      <= ~scl_in;
        sda_in      <= scl_in;
    end

    wire [7:0] data_left,  data_right;
    wire ack_left,  irq_left,  wakeup_left;
    wire scl_out_left,  scl_oe_left,  sda_out_left,  sda_oe_left;
    wire ack_right, irq_right, wakeup_right;
    wire scl_out_right, scl_oe_right, sda_out_right, sda_oe_right;

    SB_I2C #(
        .I2C_SLAVE_INIT_ADDR("0b1111100001"),
        .BUS_ADDR74("0b0001")             // selects i2c_0 at X0/Y31
    ) i2c_left (
        .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(strobe),
        .SBADRI7(bus_address[7]), .SBADRI6(bus_address[6]),
        .SBADRI5(bus_address[5]), .SBADRI4(bus_address[4]),
        .SBADRI3(bus_address[3]), .SBADRI2(bus_address[2]),
        .SBADRI1(bus_address[1]), .SBADRI0(bus_address[0]),
        .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
        .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
        .SCLI(scl_in), .SDAI(sda_in),
        .SBDATO7(data_left[7]), .SBDATO6(data_left[6]),
        .SBDATO5(data_left[5]), .SBDATO4(data_left[4]),
        .SBDATO3(data_left[3]), .SBDATO2(data_left[2]),
        .SBDATO1(data_left[1]), .SBDATO0(data_left[0]),
        .SBACKO(ack_left), .I2CIRQ(irq_left), .I2CWKUP(wakeup_left),
        .SCLO(scl_out_left), .SCLOE(scl_oe_left),
        .SDAO(sda_out_left), .SDAOE(sda_oe_left)
    );

    SB_I2C #(
        .I2C_SLAVE_INIT_ADDR("0b1111100010"),
        .BUS_ADDR74("0b0011")             // selects i2c_1 at X25/Y31
    ) i2c_right (
        .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(strobe),
        .SBADRI7(bus_address[7]), .SBADRI6(bus_address[6]),
        .SBADRI5(bus_address[5]), .SBADRI4(bus_address[4]),
        .SBADRI3(bus_address[3]), .SBADRI2(bus_address[2]),
        .SBADRI1(bus_address[1]), .SBADRI0(bus_address[0]),
        .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
        .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
        .SCLI(sda_in), .SDAI(scl_in),
        .SBDATO7(data_right[7]), .SBDATO6(data_right[6]),
        .SBDATO5(data_right[5]), .SBDATO4(data_right[4]),
        .SBDATO3(data_right[3]), .SBDATO2(data_right[2]),
        .SBDATO1(data_right[1]), .SBDATO0(data_right[0]),
        .SBACKO(ack_right), .I2CIRQ(irq_right), .I2CWKUP(wakeup_right),
        .SCLO(scl_out_right), .SCLOE(scl_oe_right),
        .SDAO(sda_out_right), .SDAOE(sda_oe_right)
    );

    assign LED_R = ~(^data_left  ^ scl_out_left  ^ scl_oe_left
                                 ^ sda_out_left  ^ sda_oe_left);
    assign LED_G = ~(^data_right ^ scl_out_right ^ scl_oe_right
                                 ^ sda_out_right ^ sda_oe_right);
    assign LED_B = ~(ack_left ^ irq_left ^ wakeup_left
                     ^ ack_right ^ irq_right ^ wakeup_right);
endmodule
