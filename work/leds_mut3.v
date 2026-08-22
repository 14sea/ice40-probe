// Reading file 'leds_mut3.asc'..

module chip (input io_12_31_1, output io_4_31_0, output io_5_31_0, output io_6_31_0);

wire io_12_31_1;
// (0, 0, 'glb_netwk_4')
// (4, 27, 'lutff_global/clk')
// (4, 28, 'lutff_global/clk')
// (4, 29, 'lutff_global/clk')
// (4, 30, 'lutff_global/clk')
// (5, 27, 'lutff_global/clk')
// (11, 30, 'neigh_op_tnr_2')
// (11, 30, 'neigh_op_tnr_6')
// (11, 31, 'span4_horz_r_2')
// (12, 30, 'neigh_op_top_2')
// (12, 30, 'neigh_op_top_6')
// (12, 31, 'fabout')
// (12, 31, 'io_1/D_IN_0')
// (12, 31, 'io_1/PAD')
// (12, 31, 'local_g1_6')
// (12, 31, 'span4_horz_r_6')
// (13, 30, 'neigh_op_tnl_2')
// (13, 30, 'neigh_op_tnl_6')
// (13, 31, 'span4_horz_r_10')
// (14, 31, 'span4_horz_r_14')
// (15, 31, 'span4_horz_l_14')

reg n2 = 0;
// (3, 26, 'neigh_op_tnr_1')
// (3, 27, 'neigh_op_rgt_1')
// (3, 28, 'neigh_op_bnr_1')
// (4, 26, 'neigh_op_top_1')
// (4, 27, 'local_g0_1')
// (4, 27, 'lutff_1/in_2')
// (4, 27, 'lutff_1/out')
// (4, 28, 'neigh_op_bot_1')
// (5, 26, 'neigh_op_tnl_1')
// (5, 27, 'neigh_op_lft_1')
// (5, 28, 'neigh_op_bnl_1')

reg n3 = 0;
// (3, 26, 'neigh_op_tnr_2')
// (3, 27, 'neigh_op_rgt_2')
// (3, 28, 'neigh_op_bnr_2')
// (4, 26, 'neigh_op_top_2')
// (4, 27, 'local_g1_2')
// (4, 27, 'lutff_2/in_1')
// (4, 27, 'lutff_2/out')
// (4, 28, 'neigh_op_bot_2')
// (5, 26, 'neigh_op_tnl_2')
// (5, 27, 'neigh_op_lft_2')
// (5, 28, 'neigh_op_bnl_2')

reg n4 = 0;
// (3, 26, 'neigh_op_tnr_3')
// (3, 27, 'neigh_op_rgt_3')
// (3, 28, 'neigh_op_bnr_3')
// (4, 26, 'neigh_op_top_3')
// (4, 27, 'local_g3_3')
// (4, 27, 'lutff_3/in_1')
// (4, 27, 'lutff_3/out')
// (4, 28, 'neigh_op_bot_3')
// (5, 26, 'neigh_op_tnl_3')
// (5, 27, 'neigh_op_lft_3')
// (5, 28, 'neigh_op_bnl_3')

reg n5 = 0;
// (3, 26, 'neigh_op_tnr_4')
// (3, 27, 'neigh_op_rgt_4')
// (3, 28, 'neigh_op_bnr_4')
// (4, 26, 'neigh_op_top_4')
// (4, 27, 'local_g0_4')
// (4, 27, 'lutff_4/in_2')
// (4, 27, 'lutff_4/out')
// (4, 28, 'neigh_op_bot_4')
// (5, 26, 'neigh_op_tnl_4')
// (5, 27, 'neigh_op_lft_4')
// (5, 28, 'neigh_op_bnl_4')

reg n6 = 0;
// (3, 26, 'neigh_op_tnr_5')
// (3, 27, 'neigh_op_rgt_5')
// (3, 28, 'neigh_op_bnr_5')
// (4, 26, 'neigh_op_top_5')
// (4, 27, 'local_g2_5')
// (4, 27, 'lutff_5/in_2')
// (4, 27, 'lutff_5/out')
// (4, 28, 'neigh_op_bot_5')
// (5, 26, 'neigh_op_tnl_5')
// (5, 27, 'neigh_op_lft_5')
// (5, 28, 'neigh_op_bnl_5')

reg n7 = 0;
// (3, 26, 'neigh_op_tnr_6')
// (3, 27, 'neigh_op_rgt_6')
// (3, 28, 'neigh_op_bnr_6')
// (4, 26, 'neigh_op_top_6')
// (4, 27, 'local_g0_6')
// (4, 27, 'lutff_6/in_2')
// (4, 27, 'lutff_6/out')
// (4, 28, 'neigh_op_bot_6')
// (5, 26, 'neigh_op_tnl_6')
// (5, 27, 'neigh_op_lft_6')
// (5, 28, 'neigh_op_bnl_6')

reg n8 = 0;
// (3, 26, 'neigh_op_tnr_7')
// (3, 27, 'neigh_op_rgt_7')
// (3, 28, 'neigh_op_bnr_7')
// (4, 26, 'neigh_op_top_7')
// (4, 27, 'local_g0_7')
// (4, 27, 'lutff_7/in_2')
// (4, 27, 'lutff_7/out')
// (4, 28, 'neigh_op_bot_7')
// (5, 26, 'neigh_op_tnl_7')
// (5, 27, 'neigh_op_lft_7')
// (5, 28, 'neigh_op_bnl_7')

reg n9 = 0;
// (3, 27, 'neigh_op_tnr_0')
// (3, 28, 'neigh_op_rgt_0')
// (3, 29, 'neigh_op_bnr_0')
// (4, 27, 'neigh_op_top_0')
// (4, 28, 'local_g3_0')
// (4, 28, 'lutff_0/in_1')
// (4, 28, 'lutff_0/out')
// (4, 29, 'neigh_op_bot_0')
// (5, 27, 'neigh_op_tnl_0')
// (5, 28, 'neigh_op_lft_0')
// (5, 29, 'neigh_op_bnl_0')

reg n10 = 0;
// (3, 27, 'neigh_op_tnr_1')
// (3, 28, 'neigh_op_rgt_1')
// (3, 29, 'neigh_op_bnr_1')
// (4, 27, 'neigh_op_top_1')
// (4, 28, 'local_g3_1')
// (4, 28, 'lutff_1/in_1')
// (4, 28, 'lutff_1/out')
// (4, 29, 'neigh_op_bot_1')
// (5, 27, 'neigh_op_tnl_1')
// (5, 28, 'neigh_op_lft_1')
// (5, 29, 'neigh_op_bnl_1')

reg n11 = 0;
// (3, 27, 'neigh_op_tnr_2')
// (3, 28, 'neigh_op_rgt_2')
// (3, 29, 'neigh_op_bnr_2')
// (4, 27, 'neigh_op_top_2')
// (4, 28, 'local_g0_2')
// (4, 28, 'lutff_2/in_2')
// (4, 28, 'lutff_2/out')
// (4, 29, 'neigh_op_bot_2')
// (5, 27, 'neigh_op_tnl_2')
// (5, 28, 'neigh_op_lft_2')
// (5, 29, 'neigh_op_bnl_2')

reg n12 = 0;
// (3, 27, 'neigh_op_tnr_3')
// (3, 28, 'neigh_op_rgt_3')
// (3, 29, 'neigh_op_bnr_3')
// (4, 27, 'neigh_op_top_3')
// (4, 28, 'local_g3_3')
// (4, 28, 'lutff_3/in_1')
// (4, 28, 'lutff_3/out')
// (4, 29, 'neigh_op_bot_3')
// (5, 27, 'neigh_op_tnl_3')
// (5, 28, 'neigh_op_lft_3')
// (5, 29, 'neigh_op_bnl_3')

reg n13 = 0;
// (3, 27, 'neigh_op_tnr_4')
// (3, 28, 'neigh_op_rgt_4')
// (3, 29, 'neigh_op_bnr_4')
// (4, 27, 'neigh_op_top_4')
// (4, 28, 'local_g2_4')
// (4, 28, 'lutff_4/in_2')
// (4, 28, 'lutff_4/out')
// (4, 29, 'neigh_op_bot_4')
// (5, 27, 'neigh_op_tnl_4')
// (5, 28, 'neigh_op_lft_4')
// (5, 29, 'neigh_op_bnl_4')

reg n14 = 0;
// (3, 27, 'neigh_op_tnr_5')
// (3, 28, 'neigh_op_rgt_5')
// (3, 29, 'neigh_op_bnr_5')
// (4, 27, 'neigh_op_top_5')
// (4, 28, 'local_g0_5')
// (4, 28, 'lutff_5/in_2')
// (4, 28, 'lutff_5/out')
// (4, 29, 'neigh_op_bot_5')
// (5, 27, 'neigh_op_tnl_5')
// (5, 28, 'neigh_op_lft_5')
// (5, 29, 'neigh_op_bnl_5')

reg n15 = 0;
// (3, 27, 'neigh_op_tnr_6')
// (3, 28, 'neigh_op_rgt_6')
// (3, 29, 'neigh_op_bnr_6')
// (4, 27, 'neigh_op_top_6')
// (4, 28, 'local_g0_6')
// (4, 28, 'lutff_6/in_2')
// (4, 28, 'lutff_6/out')
// (4, 29, 'neigh_op_bot_6')
// (5, 27, 'neigh_op_tnl_6')
// (5, 28, 'neigh_op_lft_6')
// (5, 29, 'neigh_op_bnl_6')

reg n16 = 0;
// (3, 27, 'neigh_op_tnr_7')
// (3, 28, 'neigh_op_rgt_7')
// (3, 29, 'neigh_op_bnr_7')
// (4, 27, 'neigh_op_top_7')
// (4, 28, 'local_g3_7')
// (4, 28, 'lutff_7/in_1')
// (4, 28, 'lutff_7/out')
// (4, 29, 'neigh_op_bot_7')
// (5, 27, 'neigh_op_tnl_7')
// (5, 28, 'neigh_op_lft_7')
// (5, 29, 'neigh_op_bnl_7')

reg n17 = 0;
// (3, 28, 'neigh_op_tnr_0')
// (3, 29, 'neigh_op_rgt_0')
// (3, 30, 'neigh_op_bnr_0')
// (4, 28, 'neigh_op_top_0')
// (4, 29, 'local_g2_0')
// (4, 29, 'lutff_0/in_2')
// (4, 29, 'lutff_0/out')
// (4, 30, 'neigh_op_bot_0')
// (5, 28, 'neigh_op_tnl_0')
// (5, 29, 'neigh_op_lft_0')
// (5, 30, 'neigh_op_bnl_0')

reg n18 = 0;
// (3, 28, 'neigh_op_tnr_1')
// (3, 29, 'neigh_op_rgt_1')
// (3, 30, 'neigh_op_bnr_1')
// (4, 28, 'neigh_op_top_1')
// (4, 29, 'local_g0_1')
// (4, 29, 'lutff_1/in_2')
// (4, 29, 'lutff_1/out')
// (4, 30, 'neigh_op_bot_1')
// (5, 28, 'neigh_op_tnl_1')
// (5, 29, 'neigh_op_lft_1')
// (5, 30, 'neigh_op_bnl_1')

reg n19 = 0;
// (3, 28, 'neigh_op_tnr_2')
// (3, 29, 'neigh_op_rgt_2')
// (3, 30, 'neigh_op_bnr_2')
// (4, 28, 'neigh_op_top_2')
// (4, 29, 'local_g2_2')
// (4, 29, 'lutff_2/in_2')
// (4, 29, 'lutff_2/out')
// (4, 30, 'neigh_op_bot_2')
// (5, 28, 'neigh_op_tnl_2')
// (5, 29, 'neigh_op_lft_2')
// (5, 30, 'neigh_op_bnl_2')

reg n20 = 0;
// (3, 28, 'neigh_op_tnr_3')
// (3, 29, 'neigh_op_rgt_3')
// (3, 30, 'neigh_op_bnr_3')
// (4, 28, 'neigh_op_top_3')
// (4, 29, 'local_g0_3')
// (4, 29, 'lutff_3/in_2')
// (4, 29, 'lutff_3/out')
// (4, 30, 'neigh_op_bot_3')
// (5, 28, 'neigh_op_tnl_3')
// (5, 29, 'neigh_op_lft_3')
// (5, 30, 'neigh_op_bnl_3')

reg n21 = 0;
// (3, 28, 'neigh_op_tnr_4')
// (3, 29, 'neigh_op_rgt_4')
// (3, 30, 'neigh_op_bnr_4')
// (4, 28, 'neigh_op_top_4')
// (4, 29, 'local_g3_4')
// (4, 29, 'lutff_4/in_1')
// (4, 29, 'lutff_4/out')
// (4, 30, 'neigh_op_bot_4')
// (5, 28, 'neigh_op_tnl_4')
// (5, 29, 'neigh_op_lft_4')
// (5, 30, 'neigh_op_bnl_4')

reg n22 = 0;
// (3, 28, 'neigh_op_tnr_5')
// (3, 29, 'neigh_op_rgt_5')
// (3, 30, 'neigh_op_bnr_5')
// (4, 28, 'neigh_op_top_5')
// (4, 29, 'local_g1_5')
// (4, 29, 'lutff_5/in_1')
// (4, 29, 'lutff_5/out')
// (4, 30, 'neigh_op_bot_5')
// (5, 28, 'neigh_op_tnl_5')
// (5, 29, 'neigh_op_lft_5')
// (5, 30, 'neigh_op_bnl_5')

reg n23 = 0;
// (3, 28, 'neigh_op_tnr_6')
// (3, 29, 'neigh_op_rgt_6')
// (3, 30, 'neigh_op_bnr_6')
// (4, 28, 'neigh_op_top_6')
// (4, 29, 'local_g1_6')
// (4, 29, 'lutff_6/in_1')
// (4, 29, 'lutff_6/out')
// (4, 30, 'neigh_op_bot_6')
// (5, 28, 'neigh_op_tnl_6')
// (5, 29, 'neigh_op_lft_6')
// (5, 30, 'neigh_op_bnl_6')

reg n24 = 0;
// (3, 28, 'neigh_op_tnr_7')
// (3, 29, 'neigh_op_rgt_7')
// (3, 30, 'neigh_op_bnr_7')
// (4, 28, 'neigh_op_top_7')
// (4, 29, 'local_g3_7')
// (4, 29, 'lutff_7/in_1')
// (4, 29, 'lutff_7/out')
// (4, 30, 'neigh_op_bot_7')
// (5, 28, 'neigh_op_tnl_7')
// (5, 29, 'local_g1_7')
// (5, 29, 'lutff_3/in_1')
// (5, 29, 'neigh_op_lft_7')
// (5, 30, 'neigh_op_bnl_7')

reg n25 = 0;
// (3, 29, 'neigh_op_tnr_0')
// (3, 30, 'neigh_op_rgt_0')
// (3, 31, 'logic_op_bnr_0')
// (4, 29, 'neigh_op_top_0')
// (4, 30, 'local_g3_0')
// (4, 30, 'lutff_0/in_1')
// (4, 30, 'lutff_0/out')
// (4, 31, 'logic_op_bot_0')
// (5, 29, 'neigh_op_tnl_0')
// (5, 30, 'local_g0_0')
// (5, 30, 'lutff_6/in_0')
// (5, 30, 'neigh_op_lft_0')
// (5, 31, 'logic_op_bnl_0')

reg n26 = 0;
// (3, 29, 'neigh_op_tnr_1')
// (3, 30, 'neigh_op_rgt_1')
// (3, 31, 'logic_op_bnr_1')
// (4, 29, 'neigh_op_top_1')
// (4, 30, 'local_g0_1')
// (4, 30, 'lutff_1/in_2')
// (4, 30, 'lutff_1/out')
// (4, 30, 'lutff_6/in_1')
// (4, 31, 'logic_op_bot_1')
// (5, 29, 'neigh_op_tnl_1')
// (5, 30, 'neigh_op_lft_1')
// (5, 31, 'logic_op_bnl_1')

wire io_4_31_0;
// (3, 29, 'neigh_op_tnr_6')
// (3, 30, 'neigh_op_rgt_6')
// (3, 31, 'logic_op_bnr_6')
// (4, 29, 'neigh_op_top_6')
// (4, 30, 'lutff_6/out')
// (4, 31, 'io_0/D_OUT_0')
// (4, 31, 'io_0/PAD')
// (4, 31, 'local_g0_6')
// (4, 31, 'logic_op_bot_6')
// (5, 29, 'neigh_op_tnl_6')
// (5, 30, 'neigh_op_lft_6')
// (5, 31, 'logic_op_bnl_6')

reg n28 = 0;
// (4, 26, 'neigh_op_tnr_5')
// (4, 27, 'local_g3_5')
// (4, 27, 'lutff_0/in_2')
// (4, 27, 'lutff_1/in_3')
// (4, 27, 'neigh_op_rgt_5')
// (4, 28, 'neigh_op_bnr_5')
// (5, 26, 'neigh_op_top_5')
// (5, 27, 'local_g1_5')
// (5, 27, 'lutff_5/in_3')
// (5, 27, 'lutff_5/out')
// (5, 28, 'neigh_op_bot_5')
// (6, 26, 'neigh_op_tnl_5')
// (6, 27, 'neigh_op_lft_5')
// (6, 28, 'neigh_op_bnl_5')

wire n29;
// (4, 27, 'lutff_1/cout')
// (4, 27, 'lutff_2/in_3')

wire n30;
// (4, 27, 'lutff_2/cout')
// (4, 27, 'lutff_3/in_3')

wire n31;
// (4, 27, 'lutff_3/cout')
// (4, 27, 'lutff_4/in_3')

wire n32;
// (4, 27, 'lutff_4/cout')
// (4, 27, 'lutff_5/in_3')

wire n33;
// (4, 27, 'lutff_5/cout')
// (4, 27, 'lutff_6/in_3')

wire n34;
// (4, 27, 'lutff_6/cout')
// (4, 27, 'lutff_7/in_3')

wire n35;
// (4, 27, 'lutff_7/cout')
// (4, 28, 'carry_in')
// (4, 28, 'carry_in_mux')
// (4, 28, 'lutff_0/in_3')

wire n36;
// (4, 28, 'lutff_0/cout')
// (4, 28, 'lutff_1/in_3')

wire n37;
// (4, 28, 'lutff_1/cout')
// (4, 28, 'lutff_2/in_3')

wire n38;
// (4, 28, 'lutff_2/cout')
// (4, 28, 'lutff_3/in_3')

wire n39;
// (4, 28, 'lutff_3/cout')
// (4, 28, 'lutff_4/in_3')

wire n40;
// (4, 28, 'lutff_4/cout')
// (4, 28, 'lutff_5/in_3')

wire n41;
// (4, 28, 'lutff_5/cout')
// (4, 28, 'lutff_6/in_3')

wire n42;
// (4, 28, 'lutff_6/cout')
// (4, 28, 'lutff_7/in_3')

wire n43;
// (4, 28, 'lutff_7/cout')
// (4, 29, 'carry_in')
// (4, 29, 'carry_in_mux')
// (4, 29, 'lutff_0/in_3')

wire io_5_31_0;
// (4, 28, 'neigh_op_tnr_3')
// (4, 29, 'neigh_op_rgt_3')
// (4, 29, 'sp4_r_v_b_38')
// (4, 30, 'neigh_op_bnr_3')
// (4, 30, 'sp4_r_v_b_27')
// (5, 28, 'neigh_op_top_3')
// (5, 28, 'sp4_v_t_38')
// (5, 29, 'lutff_3/out')
// (5, 29, 'sp4_v_b_38')
// (5, 30, 'neigh_op_bot_3')
// (5, 30, 'sp4_v_b_27')
// (5, 31, 'io_0/D_OUT_0')
// (5, 31, 'io_0/PAD')
// (5, 31, 'local_g0_6')
// (5, 31, 'span4_vert_14')
// (6, 28, 'neigh_op_tnl_3')
// (6, 29, 'neigh_op_lft_3')
// (6, 30, 'neigh_op_bnl_3')

wire n45;
// (4, 29, 'lutff_0/cout')
// (4, 29, 'lutff_1/in_3')

wire n46;
// (4, 29, 'lutff_1/cout')
// (4, 29, 'lutff_2/in_3')

wire n47;
// (4, 29, 'lutff_2/cout')
// (4, 29, 'lutff_3/in_3')

wire n48;
// (4, 29, 'lutff_3/cout')
// (4, 29, 'lutff_4/in_3')

wire n49;
// (4, 29, 'lutff_4/cout')
// (4, 29, 'lutff_5/in_3')

wire n50;
// (4, 29, 'lutff_5/cout')
// (4, 29, 'lutff_6/in_3')

wire n51;
// (4, 29, 'lutff_6/cout')
// (4, 29, 'lutff_7/in_3')

wire n52;
// (4, 29, 'lutff_7/cout')
// (4, 30, 'carry_in')
// (4, 30, 'carry_in_mux')
// (4, 30, 'lutff_0/in_3')

wire io_6_31_0;
// (4, 29, 'neigh_op_tnr_6')
// (4, 30, 'neigh_op_rgt_6')
// (4, 31, 'logic_op_bnr_6')
// (5, 29, 'neigh_op_top_6')
// (5, 30, 'lutff_6/out')
// (5, 31, 'logic_op_bot_6')
// (6, 29, 'neigh_op_tnl_6')
// (6, 30, 'neigh_op_lft_6')
// (6, 31, 'io_0/D_OUT_0')
// (6, 31, 'io_0/PAD')
// (6, 31, 'local_g0_6')
// (6, 31, 'logic_op_bnl_6')

wire n54;
// (4, 30, 'lutff_0/cout')
// (4, 30, 'lutff_1/in_3')

wire n55;
// (4, 27, 'lutff_0/cout')

wire n56;
// (4, 28, 'lutff_5/lout')

wire n57;
// (4, 29, 'lutff_0/lout')

wire n58;
// (4, 29, 'lutff_6/lout')

wire n59;
// (4, 29, 'lutff_3/lout')

wire n60;
// (5, 29, 'lutff_3/lout')

wire n61;
// (4, 28, 'lutff_4/lout')

wire n62;
// (4, 27, 'lutff_2/lout')

wire n63;
// (4, 30, 'lutff_1/lout')

wire n64;
// (4, 28, 'lutff_1/lout')

wire n65;
// (4, 28, 'lutff_7/lout')

wire n66;
// (4, 27, 'lutff_5/lout')

wire n67;
// (5, 27, 'lutff_5/lout')

wire n68;
// (4, 29, 'lutff_2/lout')

wire n69;
// (4, 29, 'lutff_5/lout')

wire n70;
// (4, 27, 'lutff_1/lout')

wire n71;
// (4, 28, 'lutff_0/lout')

wire n72;
// (4, 28, 'lutff_6/lout')

wire n73;
// (4, 27, 'lutff_4/lout')

wire n74;
// (4, 28, 'lutff_3/lout')

wire n75;
// (4, 27, 'lutff_7/lout')

wire n76;
// (4, 30, 'lutff_0/lout')

wire n77;
// (4, 30, 'lutff_6/lout')

wire n78;
// (4, 29, 'lutff_1/lout')

wire n79;
// (4, 29, 'lutff_4/lout')

wire n80;
// (4, 29, 'lutff_7/lout')

wire n81;
// (5, 30, 'lutff_6/lout')

wire n82;
// (4, 27, 'lutff_3/lout')

wire n83;
// (4, 28, 'lutff_2/lout')

wire n84;
// (4, 27, 'lutff_0/out')

wire n85;
// (4, 27, 'lutff_0/lout')

wire n86;
// (4, 27, 'carry_in_mux')

// Carry-In for (4 27)
assign n86 = 1;

wire n87;
// (4, 27, 'lutff_6/lout')

assign n85 = /* LUT    4 27  0 */ 1'b0;
assign n56 = /* LUT    4 28  5 */ (n40 ? !n14 : n14);
assign n57 = /* LUT    4 29  0 */ (n43 ? !n17 : n17);
assign n58 = /* LUT    4 29  6 */ (n50 ? !n23 : n23);
assign n59 = /* LUT    4 29  3 */ (n47 ? !n20 : n20);
assign n60 = /* LUT    5 29  3 */ n24;
assign n61 = /* LUT    4 28  4 */ (n39 ? !n13 : n13);
assign n62 = /* LUT    4 27  2 */ (n29 ? !n3 : n3);
assign n63 = /* LUT    4 30  1 */ (n54 ? !n26 : n26);
assign n64 = /* LUT    4 28  1 */ (n36 ? !n10 : n10);
assign n65 = /* LUT    4 28  7 */ (n42 ? !n16 : n16);
assign n66 = /* LUT    4 27  5 */ (n32 ? !n6 : n6);
assign n67 = /* LUT    5 27  5 */ !n28;
assign n68 = /* LUT    4 29  2 */ (n46 ? !n19 : n19);
assign n69 = /* LUT    4 29  5 */ (n49 ? !n22 : n22);
assign n70 = /* LUT    4 27  1 */ (n28 ? !n2 : n2);
assign n71 = /* LUT    4 28  0 */ (n35 ? !n9 : n9);
assign n72 = /* LUT    4 28  6 */ (n41 ? !n15 : n15);
assign n73 = /* LUT    4 27  4 */ (n31 ? !n5 : n5);
assign n74 = /* LUT    4 28  3 */ (n38 ? !n12 : n12);
assign n75 = /* LUT    4 27  7 */ (n34 ? !n8 : n8);
assign n76 = /* LUT    4 30  0 */ (n52 ? !n25 : n25);
assign n77 = /* LUT    4 30  6 */ !n26;
assign n78 = /* LUT    4 29  1 */ (n45 ? !n18 : n18);
assign n79 = /* LUT    4 29  4 */ (n48 ? !n21 : n21);
assign n80 = /* LUT    4 29  7 */ (n51 ? !n24 : n24);
assign n81 = /* LUT    5 30  6 */ !n25;
assign n82 = /* LUT    4 27  3 */ (n30 ? !n4 : n4);
assign n83 = /* LUT    4 28  2 */ (n37 ? !n11 : n11);
assign n87 = /* LUT    4 27  6 */ (n33 ? !n7 : n7);
assign n41 = /* CARRY  4 28  5 */ (1'b0 & n14) | ((1'b0 | n14) & n40);
assign n45 = /* CARRY  4 29  0 */ (1'b0 & n17) | ((1'b0 | n17) & n43);
assign n51 = /* CARRY  4 29  6 */ (n23 & 1'b0) | ((n23 | 1'b0) & n50);
assign n48 = /* CARRY  4 29  3 */ (1'b0 & n20) | ((1'b0 | n20) & n47);
assign n40 = /* CARRY  4 28  4 */ (1'b0 & n13) | ((1'b0 | n13) & n39);
assign n30 = /* CARRY  4 27  2 */ (n3 & 1'b0) | ((n3 | 1'b0) & n29);
assign n37 = /* CARRY  4 28  1 */ (n10 & 1'b0) | ((n10 | 1'b0) & n36);
assign n43 = /* CARRY  4 28  7 */ (n16 & 1'b0) | ((n16 | 1'b0) & n42);
assign n33 = /* CARRY  4 27  5 */ (1'b0 & n6) | ((1'b0 | n6) & n32);
assign n47 = /* CARRY  4 29  2 */ (1'b0 & n19) | ((1'b0 | n19) & n46);
assign n50 = /* CARRY  4 29  5 */ (n22 & 1'b0) | ((n22 | 1'b0) & n49);
assign n29 = /* CARRY  4 27  1 */ (1'b0 & n2) | ((1'b0 | n2) & n55);
assign n36 = /* CARRY  4 28  0 */ (n9 & 1'b0) | ((n9 | 1'b0) & n35);
assign n42 = /* CARRY  4 28  6 */ (1'b0 & n15) | ((1'b0 | n15) & n41);
assign n32 = /* CARRY  4 27  4 */ (1'b0 & n5) | ((1'b0 | n5) & n31);
assign n39 = /* CARRY  4 28  3 */ (n12 & 1'b0) | ((n12 | 1'b0) & n38);
assign n35 = /* CARRY  4 27  7 */ (1'b0 & n8) | ((1'b0 | n8) & n34);
assign n54 = /* CARRY  4 30  0 */ (n25 & 1'b0) | ((n25 | 1'b0) & n52);
assign n46 = /* CARRY  4 29  1 */ (1'b0 & n18) | ((1'b0 | n18) & n45);
assign n49 = /* CARRY  4 29  4 */ (n21 & 1'b0) | ((n21 | 1'b0) & n48);
assign n52 = /* CARRY  4 29  7 */ (n24 & 1'b0) | ((n24 | 1'b0) & n51);
assign n31 = /* CARRY  4 27  3 */ (n4 & 1'b0) | ((n4 | 1'b0) & n30);
assign n38 = /* CARRY  4 28  2 */ (1'b0 & n11) | ((1'b0 | n11) & n37);
assign n55 = /* CARRY  4 27  0 */ (1'b0 & n28) | ((1'b0 | n28) & n86);
assign n34 = /* CARRY  4 27  6 */ (1'b0 & n7) | ((1'b0 | n7) & n33);
/* FF  4 28  5 */ always @(posedge io_12_31_1) if (1'b1) n14 <= 1'b0 ? 1'b0 : n56;
/* FF  4 29  0 */ always @(posedge io_12_31_1) if (1'b1) n17 <= 1'b0 ? 1'b0 : n57;
/* FF  4 29  6 */ always @(posedge io_12_31_1) if (1'b1) n23 <= 1'b0 ? 1'b0 : n58;
/* FF  4 29  3 */ always @(posedge io_12_31_1) if (1'b1) n20 <= 1'b0 ? 1'b0 : n59;
/* FF  5 29  3 */ assign io_5_31_0 = n60;
/* FF  4 28  4 */ always @(posedge io_12_31_1) if (1'b1) n13 <= 1'b0 ? 1'b0 : n61;
/* FF  4 27  2 */ always @(posedge io_12_31_1) if (1'b1) n3 <= 1'b0 ? 1'b0 : n62;
/* FF  4 30  1 */ always @(posedge io_12_31_1) if (1'b1) n26 <= 1'b0 ? 1'b0 : n63;
/* FF  4 28  1 */ always @(posedge io_12_31_1) if (1'b1) n10 <= 1'b0 ? 1'b0 : n64;
/* FF  4 28  7 */ always @(posedge io_12_31_1) if (1'b1) n16 <= 1'b0 ? 1'b0 : n65;
/* FF  4 27  5 */ always @(posedge io_12_31_1) if (1'b1) n6 <= 1'b0 ? 1'b0 : n66;
/* FF  5 27  5 */ always @(posedge io_12_31_1) if (1'b1) n28 <= 1'b0 ? 1'b0 : n67;
/* FF  4 29  2 */ always @(posedge io_12_31_1) if (1'b1) n19 <= 1'b0 ? 1'b0 : n68;
/* FF  4 29  5 */ always @(posedge io_12_31_1) if (1'b1) n22 <= 1'b0 ? 1'b0 : n69;
/* FF  4 27  1 */ always @(posedge io_12_31_1) if (1'b1) n2 <= 1'b0 ? 1'b0 : n70;
/* FF  4 28  0 */ always @(posedge io_12_31_1) if (1'b1) n9 <= 1'b0 ? 1'b0 : n71;
/* FF  4 28  6 */ always @(posedge io_12_31_1) if (1'b1) n15 <= 1'b0 ? 1'b0 : n72;
/* FF  4 27  4 */ always @(posedge io_12_31_1) if (1'b1) n5 <= 1'b0 ? 1'b0 : n73;
/* FF  4 28  3 */ always @(posedge io_12_31_1) if (1'b1) n12 <= 1'b0 ? 1'b0 : n74;
/* FF  4 27  7 */ always @(posedge io_12_31_1) if (1'b1) n8 <= 1'b0 ? 1'b0 : n75;
/* FF  4 30  0 */ always @(posedge io_12_31_1) if (1'b1) n25 <= 1'b0 ? 1'b0 : n76;
/* FF  4 30  6 */ assign io_4_31_0 = n77;
/* FF  4 29  1 */ always @(posedge io_12_31_1) if (1'b1) n18 <= 1'b0 ? 1'b0 : n78;
/* FF  4 29  4 */ always @(posedge io_12_31_1) if (1'b1) n21 <= 1'b0 ? 1'b0 : n79;
/* FF  4 29  7 */ always @(posedge io_12_31_1) if (1'b1) n24 <= 1'b0 ? 1'b0 : n80;
/* FF  5 30  6 */ assign io_6_31_0 = n81;
/* FF  4 27  3 */ always @(posedge io_12_31_1) if (1'b1) n4 <= 1'b0 ? 1'b0 : n82;
/* FF  4 28  2 */ always @(posedge io_12_31_1) if (1'b1) n11 <= 1'b0 ? 1'b0 : n83;
/* FF  4 27  0 */ assign n84 = n85;
/* FF  4 27  6 */ always @(posedge io_12_31_1) if (1'b1) n7 <= 1'b0 ? 1'b0 : n87;

endmodule

