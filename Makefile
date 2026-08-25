WORK := work
BUILD := build
# Sweep results are evidence, not build output: they cost hours to produce and
# must survive `make clean` and any rm -rf of the build directory.
RESULTS := results
YOSYS ?= yosys
NEXTPNR ?= nextpnr-ice40
ICEPACK ?= icepack
IVERILOG ?= iverilog
VVP ?= vvp
PYTHON ?= python3
ORACLE_WORKERS ?= 16
# Enumerated, never hand-listed: a hand-written list is how this project twice
# lost track of something it should have covered.
PY_SOURCES := $(wildcard $(WORK)/*.py)
export PYTHONPYCACHEPREFIX := $(abspath $(BUILD)/pycache)

.PHONY: all probes route-probe pll pll-check spram spram-check osc osc-check osc-evidence i2c i2c-check spi spi-check spi-evidence rgba rgba-check tile-coverage carry-check hard-ip-inventory guarded guarded-test guarded-route-probe test analyze check-analysis oracle-leds oracle-leds-full oracle-leds-report oracle-leds-addrem oracle-dense-full oracle-dense-addrem manifest manifest-check archive verify-repro versions clean

all: $(BUILD)/leds.bin $(BUILD)/dense.asc probes

$(BUILD):
	mkdir -p $@

$(BUILD)/leds.json: $(WORK)/leds.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/leds_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/dense.json: $(WORK)/dense.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/dense_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/leds.asc: $(BUILD)/leds.json $(WORK)/top.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/top.pcf --asc $@ --freq 12 --log $(BUILD)/leds_pnr.log

$(BUILD)/dense.asc: $(BUILD)/dense.json $(WORK)/top.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/top.pcf --asc $@ --freq 12 --log $(BUILD)/dense_pnr.log

$(BUILD)/%.bin: $(BUILD)/%.asc
	$(ICEPACK) $< $@

$(BUILD)/leds_rt.v: $(BUILD)/leds.asc $(WORK)/decode_vlog.py
	$(PYTHON) $(WORK)/decode_vlog.py $< $@

$(BUILD)/leds_rt_sim.v: $(BUILD)/leds.asc $(WORK)/decode_vlog.py
	$(PYTHON) $(WORK)/decode_vlog.py --simulation $< $@

$(BUILD)/leds_mut3.asc $(BUILD)/leds_mut3.bin $(BUILD)/leds_mut3.v &: $(BUILD)/leds.asc $(BUILD)/leds_rt.v $(WORK)/mkprobe.py $(WORK)/iceutil.py
	$(PYTHON) $(WORK)/mkprobe.py 5 29 3 $(BUILD)/leds_mut3 --source-asc $(BUILD)/leds.asc --baseline-vlog $(BUILD)/leds_rt.v

$(BUILD)/leds_mut3_sim.v: $(BUILD)/leds_mut3.asc $(WORK)/decode_vlog.py
	$(PYTHON) $(WORK)/decode_vlog.py --simulation $< $@

$(BUILD)/leds_mut2.asc $(BUILD)/leds_mut2.bin $(BUILD)/leds_mut2.v &: $(BUILD)/leds.asc $(BUILD)/leds_rt.v $(WORK)/mkprobe.py $(WORK)/iceutil.py
	$(PYTHON) $(WORK)/mkprobe.py 4 30 6 $(BUILD)/leds_mut2 --allow-indistinguishable --source-asc $(BUILD)/leds.asc --baseline-vlog $(BUILD)/leds_rt.v

$(BUILD)/leds_mut2_sim.v: $(BUILD)/leds_mut2.asc $(WORK)/decode_vlog.py
	$(PYTHON) $(WORK)/decode_vlog.py --simulation $< $@

probes: $(BUILD)/leds_mut3.bin

route-probe: $(BUILD)/physical/route_candidate_1.bin

$(BUILD)/physical/route_candidate_1.asc $(BUILD)/physical/route_candidate_1.bin $(BUILD)/physical/route_candidate_1.v &: $(BUILD)/leds.asc $(WORK)/mkrouteprobe.py $(WORK)/exhaustive.py $(WORK)/iceutil.py
	$(PYTHON) $(WORK)/mkrouteprobe.py 4 27 2 50 $(BUILD)/physical/route_candidate_1 --source-asc $(BUILD)/leds.asc

# PLL fixture: the first of the hard-IP fixtures, and the one that established
# the shape the others follow -- a source which is not a LUT, IO input, RAM
# read or DSP, decoded from configuration rather than from a net name.
# SPRAM, the oscillators, SB_I2C and SB_SPI have their own fixtures below.
$(BUILD)/pll.json: $(WORK)/pll.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/pll_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/pll.asc: $(BUILD)/pll.json $(WORK)/pll.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/pll.pcf --asc $@ --freq 48 --log $(BUILD)/pll_pnr.log

pll: $(BUILD)/pll.asc

pll-check: $(BUILD)/pll.asc $(WORK)/pll_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/pll_check.py $<

# SPRAM fixture: the second hard-IP fixture.  UP5K read data leaves the IP
# through ipcon-tile slf_op_* segments, a name absent from any design without
# hard IP, so neither leds nor dense can exercise it.
$(BUILD)/spram.json: $(WORK)/spram.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/spram_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/spram.asc: $(BUILD)/spram.json $(WORK)/spram.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/spram.pcf --asc $@ --freq 12 --log $(BUILD)/spram_pnr.log

spram: $(BUILD)/spram.asc

spram-check: $(BUILD)/spram.asc $(BUILD)/leds.asc $(WORK)/spram_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/spram_check.py $<

# Oscillator fixture: third hard-IP fixture.  HFOSC and LFOSC reach the global
# networks with no source segment of their own, the same shape as a PLL global.
$(BUILD)/osc.json: $(WORK)/osc.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/osc_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/osc.asc: $(BUILD)/osc.json $(WORK)/osc.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/osc.pcf --asc $@ --freq 12 --log $(BUILD)/osc_pnr.log

osc: $(BUILD)/osc.asc

carry-check: $(BUILD)/leds.asc $(BUILD)/dense.asc $(WORK)/carry_check.py $(WORK)/exhaustive.py
	$(PYTHON) $(WORK)/carry_check.py

# Survey step for the hard-IP milestone: decides whether a fixture is warranted
# before any identity is written.  Host-only; builds four designs.
hard-ip-inventory: $(WORK)/hard_ip_inventory.py $(WORK)/exhaustive.py
	$(PYTHON) $(WORK)/hard_ip_inventory.py

tile-coverage: $(BUILD)/leds.asc $(BUILD)/dense.asc $(BUILD)/pll.asc $(BUILD)/spram.asc $(BUILD)/osc.asc $(BUILD)/i2c.asc $(BUILD)/spi.asc $(BUILD)/rgba.asc $(WORK)/tile_coverage_check.py $(WORK)/carry_check.py $(WORK)/hard_ip_inventory.py $(WORK)/iceutil.py
	$(PYTHON) $(WORK)/tile_coverage_check.py

osc-evidence: $(WORK)/osc_evidence.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/osc_evidence.py

osc-check: $(BUILD)/osc.asc $(BUILD)/leds.asc $(BUILD)/pll.asc $(WORK)/osc_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/osc_check.py $<

# I2C fixture: fourth hard-IP fixture, and the first written after the hard-IP
# inventory.  Fifteen fabric outputs per instance leave through ipcon-tile
# slf_op_* segments; both instances are placed because their enabling bits are
# laid out differently.
$(BUILD)/i2c.json: $(WORK)/i2c.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/i2c_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/i2c.asc: $(BUILD)/i2c.json $(WORK)/i2c.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/i2c.pcf --asc $@ --freq 12 --log $(BUILD)/i2c_pnr.log

i2c: $(BUILD)/i2c.asc

i2c-check: $(BUILD)/i2c.asc $(BUILD)/leds.asc $(BUILD)/osc.asc $(WORK)/i2c_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/i2c_check.py $<

# SPI fixture: fifth hard-IP fixture.  Twenty-five fabric outputs per instance
# -- the inventory's first figure of nineteen was a property of its own Verilog
# -- and both instances are placed because their four enable bits are split
# across different IO tiles.
$(BUILD)/spi.json: $(WORK)/spi.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/spi_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/spi.asc: $(BUILD)/spi.json $(WORK)/spi.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/spi.pcf --asc $@ --freq 12 --log $(BUILD)/spi_pnr.log

spi: $(BUILD)/spi.asc

# BUS_ADDR74 mapping and the enable vector, rebuilt over all sixteen values.
spi-evidence: $(BUILD)/leds.asc $(WORK)/spi_evidence.py $(WORK)/exhaustive.py
	$(PYTHON) $(WORK)/spi_evidence.py

spi-check: $(BUILD)/spi.asc $(BUILD)/leds.asc $(BUILD)/osc.asc $(BUILD)/i2c.asc $(WORK)/spi_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/spi_check.py $<

# RGBA: the negative case.  No fixture identity is built for it -- the block
# has no output that enters the fabric -- so what is regression-tested is that
# negative, on an exhaustive count of the block's database ports.
$(BUILD)/rgba.json: $(WORK)/rgba.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/rgba_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/rgba.asc: $(BUILD)/rgba.json $(WORK)/rgba.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/rgba.pcf --asc $@ --freq 12 --log $(BUILD)/rgba_pnr.log

rgba: $(BUILD)/rgba.asc

rgba-check: $(BUILD)/rgba.asc $(BUILD)/leds.asc $(BUILD)/i2c.asc $(BUILD)/spi.asc $(WORK)/rgba_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/rgba_check.py $<

guarded: $(BUILD)/guarded.bin $(BUILD)/guarded_rt.v

guarded-test: $(BUILD)/test_guarded.vvp
	$(VVP) $<

guarded-route-probe: $(BUILD)/physical/guarded_route_candidate.bin

$(BUILD)/guarded.json: $(WORK)/guarded.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/guarded_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/guarded.asc: $(BUILD)/guarded.json $(WORK)/guarded.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/guarded.pcf --asc $@ --freq 12 --log $(BUILD)/guarded_pnr.log

$(BUILD)/guarded_rt.v: $(BUILD)/guarded.asc $(WORK)/decode_vlog.py
	$(PYTHON) $(WORK)/decode_vlog.py $< $@

$(BUILD)/guarded_rt_sim.v: $(BUILD)/guarded.asc $(WORK)/decode_vlog.py
	$(PYTHON) $(WORK)/decode_vlog.py --simulation $< $@

$(BUILD)/test_guarded.vvp: $(BUILD)/guarded_rt_sim.v $(WORK)/guarded_tb.v
	$(IVERILOG) -g2012 -Wall -o $@ $^

$(BUILD)/physical/guarded_route_candidate.asc $(BUILD)/physical/guarded_route_candidate.bin $(BUILD)/physical/guarded_route_candidate.v &: $(BUILD)/guarded.asc $(WORK)/mkrouteprobe.py $(WORK)/exhaustive.py $(WORK)/iceutil.py
	$(PYTHON) $(WORK)/mkrouteprobe.py 5 27 10 50 $(BUILD)/physical/guarded_route_candidate --source-asc $(BUILD)/guarded.asc

$(BUILD)/test_baseline.vvp: $(BUILD)/leds_rt_sim.v $(WORK)/tb.v
	$(IVERILOG) -g2012 -Wall -o $@ $^

$(BUILD)/test_mut2.vvp: $(BUILD)/leds_mut2_sim.v $(WORK)/tb.v
	$(IVERILOG) -g2012 -Wall -DEXPECT_MUT2 -o $@ $^

$(BUILD)/test_mut3.vvp: $(BUILD)/leds_mut3_sim.v $(WORK)/tb.v
	$(IVERILOG) -g2012 -Wall -DEXPECT_MUT3 -o $@ $^

test: tile-coverage carry-check pll-check spram-check osc-check i2c-check spi-check rgba-check osc-evidence spi-evidence manifest-check guarded-test $(BUILD)/test_baseline.vvp $(BUILD)/test_mut2.vvp $(BUILD)/test_mut3.vvp $(BUILD)/leds_rt.v check-analysis
	$(VVP) $(BUILD)/test_baseline.vvp
	$(VVP) $(BUILD)/test_mut2.vvp
	$(VVP) $(BUILD)/test_mut3.vvp
	! $(PYTHON) $(WORK)/mkprobe.py 4 30 6 $(BUILD)/negative_mut2 --source-asc $(BUILD)/leds.asc --baseline-vlog $(BUILD)/leds_rt.v
	$(PYTHON) -m py_compile $(PY_SOURCES)

analyze: $(BUILD)/leds.asc $(BUILD)/dense.asc
	$(PYTHON) $(WORK)/bitclass.py $(BUILD)/leds.asc 20000 > $(BUILD)/bitclass.txt
	$(PYTHON) $(WORK)/muxmodel.py $(BUILD)/leds.asc 20000 > $(BUILD)/muxmodel.txt
	$(PYTHON) $(WORK)/exhaustive.py --details $(BUILD)/leds.asc > $(BUILD)/exhaustive_leds.txt
	$(PYTHON) $(WORK)/exhaustive.py $(BUILD)/dense.asc > $(BUILD)/exhaustive_dense.txt

check-analysis: analyze
	grep -F 'LUT-INIT coordinates                      17536' $(BUILD)/exhaustive_leds.txt
	grep -F 'global multi-driver net candidate            14' $(BUILD)/exhaustive_leds.txt
	grep -F 'of which found after component split        0' $(BUILD)/exhaustive_leds.txt
	grep -F 'of which locally clean (global-only)        1' $(BUILD)/exhaustive_leds.txt
	grep -F 'of which cross-tile                       1' $(BUILD)/exhaustive_leds.txt
	grep -F 'split-aware add+remove checks               351' $(BUILD)/exhaustive_leds.txt
	grep -F 'tile=(4,30) bit=B10[53]' $(BUILD)/exhaustive_leds.txt
	grep -F "post-mutation drivers: ((4, 30, 'lutff_5/out'), (5, 29, 'lutff_3/out'))" $(BUILD)/exhaustive_leds.txt
	grep -F 'LUT-INIT coordinates                      76288' $(BUILD)/exhaustive_dense.txt
	grep -F 'local dual-route candidate                 1287' $(BUILD)/exhaustive_dense.txt
	grep -F 'global multi-driver net candidate          2471' $(BUILD)/exhaustive_dense.txt
	grep -F 'of which found after component split        0' $(BUILD)/exhaustive_dense.txt
	grep -F 'of which locally clean (global-only)     1474' $(BUILD)/exhaustive_dense.txt
	grep -F 'of which cross-tile                    1473' $(BUILD)/exhaustive_dense.txt
	grep -F 'split-aware add+remove checks             36343' $(BUILD)/exhaustive_dense.txt

# Independent cross-check of exhaustive.py's verdicts.  Opt-in only: the full
# sweep is ~105 min on 16 workers, so it is deliberately NOT part of `test`.
# Runs are resumable -- re-run the same target to continue an interrupted sweep.
oracle-leds: $(BUILD)/leds.asc
	$(PYTHON) $(WORK)/oracle.py $< --out $(RESULTS)/oracle_leds_sample.jsonl \
		--sample 500 --workers $(ORACLE_WORKERS)

oracle-leds-full: $(BUILD)/leds.asc
	$(PYTHON) $(WORK)/oracle.py $< --out $(RESULTS)/oracle_leds_full.jsonl \
		--workers $(ORACLE_WORKERS)

# Acceptance gate for a finished sweep: coordinate completeness and uniqueness,
# +1 conflict delta on every positive, exactly 14 positives, no disagreement.
oracle-leds-report:
	$(PYTHON) $(WORK)/oracle.py $(BUILD)/leds.asc \
		--out $(RESULTS)/oracle_leds_full.jsonl --report --expect-positives 14

oracle-leds-addrem: $(BUILD)/leds.asc
	$(PYTHON) $(WORK)/oracle.py $< --out $(RESULTS)/oracle_leds_addrem.jsonl \
		--flip-class addrem --workers $(ORACLE_WORKERS)

oracle-dense-full: $(BUILD)/dense.asc
	$(PYTHON) $(WORK)/oracle.py $< --out $(RESULTS)/oracle_dense_full.jsonl \
		--workers $(ORACLE_WORKERS)

oracle-dense-addrem: $(BUILD)/dense.asc
	$(PYTHON) $(WORK)/oracle.py $< --out $(RESULTS)/oracle_dense_addrem.jsonl \
		--flip-class addrem --workers $(ORACLE_WORKERS)

# Evidence bookkeeping.  `manifest` re-runs the fixture checks and records the
# hashes and counts of every sweep result; `archive` compresses the completed
# sweeps so the evidence is not stored on one machine only.
manifest:
	$(PYTHON) $(WORK)/manifest.py

# Freshness gate.  Without it a stale manifest is invisible: `make test` stays
# green while the manifest describes model sources that no longer exist.  Only
# the tracked-tree sections are checkable -- the sweep results are untracked.
manifest-check: $(WORK)/manifest.py
	$(PYTHON) $(WORK)/manifest.py --self-test
	$(PYTHON) $(WORK)/manifest.py --check

archive:
	mkdir -p $(RESULTS)/archive
	for f in $(RESULTS)/*.jsonl; do gzip -9 -c "$$f" > $(RESULTS)/archive/$$(basename $$f).gz; done
	cd $(RESULTS)/archive && sha256sum *.gz > SHA256SUMS

verify-repro: all pll-check spram-check osc-check i2c-check spi-check rgba-check
	cmp $(WORK)/leds.asc $(BUILD)/leds.asc
	cmp $(WORK)/dense.asc $(BUILD)/dense.asc
	cmp $(WORK)/leds.bin $(BUILD)/leds.bin
	cmp $(WORK)/leds_mut2.asc $(BUILD)/leds_mut2.asc
	cmp $(WORK)/leds_mut2.bin $(BUILD)/leds_mut2.bin
	cmp $(WORK)/leds_mut3.asc $(BUILD)/leds_mut3.asc
	cmp $(WORK)/leds_mut3.bin $(BUILD)/leds_mut3.bin
	cmp $(WORK)/pll.asc $(BUILD)/pll.asc
	cmp $(WORK)/pll_selector.asc $(BUILD)/pll_selector.asc
	cmp $(WORK)/spram.asc $(BUILD)/spram.asc
	cmp $(WORK)/osc.asc $(BUILD)/osc.asc
	cmp $(WORK)/osc_selector.asc $(BUILD)/osc_selector.asc
	cmp $(WORK)/osc_fabric_selector.asc $(BUILD)/osc_fabric_selector.asc
	cmp $(WORK)/i2c.asc $(BUILD)/i2c.asc
	cmp $(WORK)/spi.asc $(BUILD)/spi.asc
	cmp $(WORK)/rgba.asc $(BUILD)/rgba.asc

versions:
	$(YOSYS) -V
	$(NEXTPNR) --version
	$(PYTHON) --version
	$(IVERILOG) -V

clean:
	rm -rf $(BUILD)
	@echo "kept $(RESULTS)/ (sweep evidence)"
