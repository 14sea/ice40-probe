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
export PYTHONPYCACHEPREFIX := $(abspath $(BUILD)/pycache)

.PHONY: all probes route-probe pll pll-check guarded guarded-test guarded-route-probe test analyze check-analysis oracle-leds oracle-leds-full oracle-leds-report oracle-dense-addrem verify-repro versions clean

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

# PLL fixture: the only fixture here that instantiates hard IP, so the only one
# that can exercise a source which is not a LUT, IO input, RAM read or DSP.
$(BUILD)/pll.json: $(WORK)/pll.v | $(BUILD)
	$(YOSYS) -q -l $(BUILD)/pll_yosys.log -p 'synth_ice40 -json $@' $<

$(BUILD)/pll.asc: $(BUILD)/pll.json $(WORK)/pll.pcf
	$(NEXTPNR) --up5k --package sg48 --json $< --pcf $(WORK)/pll.pcf --asc $@ --freq 48 --log $(BUILD)/pll_pnr.log

pll: $(BUILD)/pll.asc

pll-check: $(BUILD)/pll.asc $(WORK)/pll_check.py $(WORK)/exhaustive.py $(WORK)/oracle.py
	$(PYTHON) $(WORK)/pll_check.py $<

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

test: pll-check guarded-test $(BUILD)/test_baseline.vvp $(BUILD)/test_mut2.vvp $(BUILD)/test_mut3.vvp $(BUILD)/leds_rt.v check-analysis
	$(VVP) $(BUILD)/test_baseline.vvp
	$(VVP) $(BUILD)/test_mut2.vvp
	$(VVP) $(BUILD)/test_mut3.vvp
	! $(PYTHON) $(WORK)/mkprobe.py 4 30 6 $(BUILD)/negative_mut2 --source-asc $(BUILD)/leds.asc --baseline-vlog $(BUILD)/leds_rt.v
	$(PYTHON) -m py_compile $(WORK)/iceutil.py $(WORK)/bitclass.py $(WORK)/muxmodel.py $(WORK)/exhaustive.py $(WORK)/mkprobe.py $(WORK)/mkrouteprobe.py $(WORK)/decode_vlog.py $(WORK)/oracle.py $(WORK)/pll_check.py

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

oracle-dense-addrem: $(BUILD)/dense.asc
	$(PYTHON) $(WORK)/oracle.py $< --out $(RESULTS)/oracle_dense_addrem.jsonl \
		--flip-class addrem --workers $(ORACLE_WORKERS)

verify-repro: all pll-check
	cmp $(WORK)/leds.asc $(BUILD)/leds.asc
	cmp $(WORK)/dense.asc $(BUILD)/dense.asc
	cmp $(WORK)/leds.bin $(BUILD)/leds.bin
	cmp $(WORK)/leds_mut2.asc $(BUILD)/leds_mut2.asc
	cmp $(WORK)/leds_mut2.bin $(BUILD)/leds_mut2.bin
	cmp $(WORK)/leds_mut3.asc $(BUILD)/leds_mut3.asc
	cmp $(WORK)/leds_mut3.bin $(BUILD)/leds_mut3.bin
	cmp $(WORK)/pll.asc $(BUILD)/pll.asc
	cmp $(WORK)/pll_selector.asc $(BUILD)/pll_selector.asc

versions:
	$(YOSYS) -V
	$(NEXTPNR) --version
	$(PYTHON) --version
	$(IVERILOG) -V

clean:
	rm -rf $(BUILD)
	@echo "kept $(RESULTS)/ (sweep evidence)"
