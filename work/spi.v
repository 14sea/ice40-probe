// SPI fixture: the fifth hard-IP fixture, and the second built from the
// hard-IP inventory's verdicts (after I2C).
//
// Same gap as I2C and SPRAM: each SB_SPI has twenty-five outputs that leave
// the block through `slf_op_*` segments on ipcon tiles, which a whitelist of
// `lutff_*/out` / `io_*/D_IN_*` / `ram/RDATA_*` / `mult/O_*` never matches, so
// every SPI output net looked like a net with no source.
//
// Twenty-five, not nineteen.  The inventory's first pass reported nineteen
// because its own Verilog connected MCSNO0/MCSNOE0 and left MCSNO1..3 and
// MCSNOE1..3 open, so six endpoints on (0,21) and (0,22) were never placed.
// That number was a property of the testbench, not of the device.  Every one
// of the twenty-five outputs is consumed here, per instance: an output nothing
// reads is not routed, its segment never enters the graph, and its identity
// could not be exercised.
//
// Both instances are placed.  Their enabling bits are laid out differently --
// the left instance keeps SPI_ENABLE_0/1 in IO tile (7,0) and SPI_ENABLE_2/3
// in (6,0), while the right instance splits them 0/2 in (23,0) and 1/3 in
// (24,0) -- so a one-instance fixture would leave half of that untested.
//
// Which instance is selected is decided by BUS_ADDR74, and `make spi-evidence`
// establishes that mapping by building all sixteen four-bit values rather than
// by quoting a log: only "0b0000" (X0/Y0/spi_0) and "0b0010" (X25/Y0/spi_1)
// are accepted at all.
//
// SI/SCKI/SCSNI/MI come from fabric registers rather than the dedicated pads,
// so that "the enable bits are set" and "the dedicated pins are muxed to the
// IP" cannot be confused in this fixture.
module top(
    input  clk,
    output LED_R,
    output LED_G,
    output LED_B
);
    reg [7:0] bus_address = 0;
    reg       strobe = 0;
    reg       serial_in = 0;
    reg       serial_clock = 0;
    reg       chip_select = 0;
    reg       master_in = 0;

    always @(posedge clk) begin
        bus_address  <= bus_address + 1'b1;
        strobe       <= ~strobe;
        serial_in    <= ~serial_in;
        serial_clock <= serial_in;
        chip_select  <= serial_clock;
        master_in    <= chip_select;
    end

    wire [7:0] data_left,   data_right;
    wire [3:0] csn_left,    csn_right,    csn_oe_left,  csn_oe_right;
    wire ack_left,  irq_left,  wakeup_left;
    wire so_left,   so_oe_left,   mo_left,   mo_oe_left;
    wire sck_left,  sck_oe_left;
    wire ack_right, irq_right, wakeup_right;
    wire so_right,  so_oe_right,  mo_right,  mo_oe_right;
    wire sck_right, sck_oe_right;

    SB_SPI #(
        .BUS_ADDR74("0b0000")             // selects spi_0 at X0/Y0
    ) spi_left (
        .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(strobe),
        .SBADRI7(bus_address[7]), .SBADRI6(bus_address[6]),
        .SBADRI5(bus_address[5]), .SBADRI4(bus_address[4]),
        .SBADRI3(bus_address[3]), .SBADRI2(bus_address[2]),
        .SBADRI1(bus_address[1]), .SBADRI0(bus_address[0]),
        .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
        .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
        .MI(master_in), .SI(serial_in),
        .SCKI(serial_clock), .SCSNI(chip_select),
        .SBDATO7(data_left[7]), .SBDATO6(data_left[6]),
        .SBDATO5(data_left[5]), .SBDATO4(data_left[4]),
        .SBDATO3(data_left[3]), .SBDATO2(data_left[2]),
        .SBDATO1(data_left[1]), .SBDATO0(data_left[0]),
        .SBACKO(ack_left), .SPIIRQ(irq_left), .SPIWKUP(wakeup_left),
        .SO(so_left), .SOE(so_oe_left), .MO(mo_left), .MOE(mo_oe_left),
        .SCKO(sck_left), .SCKOE(sck_oe_left),
        .MCSNO0(csn_left[0]), .MCSNO1(csn_left[1]),
        .MCSNO2(csn_left[2]), .MCSNO3(csn_left[3]),
        .MCSNOE0(csn_oe_left[0]), .MCSNOE1(csn_oe_left[1]),
        .MCSNOE2(csn_oe_left[2]), .MCSNOE3(csn_oe_left[3])
    );

    SB_SPI #(
        .BUS_ADDR74("0b0010")             // selects spi_1 at X25/Y0
    ) spi_right (
        .SBCLKI(clk), .SBRWI(1'b1), .SBSTBI(strobe),
        .SBADRI7(bus_address[7]), .SBADRI6(bus_address[6]),
        .SBADRI5(bus_address[5]), .SBADRI4(bus_address[4]),
        .SBADRI3(bus_address[3]), .SBADRI2(bus_address[2]),
        .SBADRI1(bus_address[1]), .SBADRI0(bus_address[0]),
        .SBDATI7(1'b0), .SBDATI6(1'b0), .SBDATI5(1'b0), .SBDATI4(1'b0),
        .SBDATI3(1'b0), .SBDATI2(1'b0), .SBDATI1(1'b0), .SBDATI0(1'b0),
        .MI(chip_select), .SI(master_in),
        .SCKI(serial_in), .SCSNI(serial_clock),
        .SBDATO7(data_right[7]), .SBDATO6(data_right[6]),
        .SBDATO5(data_right[5]), .SBDATO4(data_right[4]),
        .SBDATO3(data_right[3]), .SBDATO2(data_right[2]),
        .SBDATO1(data_right[1]), .SBDATO0(data_right[0]),
        .SBACKO(ack_right), .SPIIRQ(irq_right), .SPIWKUP(wakeup_right),
        .SO(so_right), .SOE(so_oe_right), .MO(mo_right), .MOE(mo_oe_right),
        .SCKO(sck_right), .SCKOE(sck_oe_right),
        .MCSNO0(csn_right[0]), .MCSNO1(csn_right[1]),
        .MCSNO2(csn_right[2]), .MCSNO3(csn_right[3]),
        .MCSNOE0(csn_oe_right[0]), .MCSNOE1(csn_oe_right[1]),
        .MCSNOE2(csn_oe_right[2]), .MCSNOE3(csn_oe_right[3])
    );

    assign LED_R = ~(^data_left  ^ so_left  ^ so_oe_left
                     ^ mo_left  ^ mo_oe_left  ^ sck_left  ^ sck_oe_left
                     ^ ^csn_left  ^ ^csn_oe_left);
    assign LED_G = ~(^data_right ^ so_right ^ so_oe_right
                     ^ mo_right ^ mo_oe_right ^ sck_right ^ sck_oe_right
                     ^ ^csn_right ^ ^csn_oe_right);
    assign LED_B = ~(ack_left ^ irq_left ^ wakeup_left
                     ^ ack_right ^ irq_right ^ wakeup_right);
endmodule
