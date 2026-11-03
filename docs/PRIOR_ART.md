# Prior art

Added 2026-11-03 after a full-text literature review. This file does not change any
finding, hash or manifest entry.

**Bottom line:** classifying single-bit configuration flips of iCE40 (and Artix-7)
against the open database's routing model, and restricting mutation to a safe subset of
bits, have both been published. What this repo adds is an exhaustive, hash-bound,
host-only consistency check of the IceStorm/nextpnr model (including hard-IP driver
coverage) with its limits stated; it makes no silicon claim.

| What this repo does | Closest prior work | Relation |
|---|---|---|
| Classify single-bit flips by their effect in the open database's routing model | Fibich, Horauer, Obermaisser, "Bitstream-level interconnect fault characterization for SRAM-based FPGAs", DATE 2023: uses prjxray-db / IceStorm to map each single-bit flip of a routing resource to a fault model (Open / Conflict / Input Antenna / Output Antenna / Bridge), then measures criticality **on silicon** (4× xc7a35t, 10× ice40up5k — the same part as here) | **Close precedent.** Fibich adds silicon measurements; we add exhaustive enumeration over two fixtures and hard-IP driver modelling. **The numbers are not comparable**: our 39–41 % is a structural event rate per coordinate of a design; Fibich reports per-fault-class criticality in a characterization design (iCE40 Conflict 98.5 % any-device / 86.3 % all-devices; Input Antenna 22.1 % / 4.95 %) |
| "Global multi-driver candidate" | Corresponds conceptually to Fibich's **Conflict** class | Fibich's silicon rates can serve as a prior that such candidates are mostly critical; not a conversion factor |
| A mutation operator more conservative than raw bit flipping | Fritzsch, Hoffmann, Bogdan, CEC 2022 (iCE40: routing fixed, every gene a LUT truth table); BitstreamEvolution (github.com/evolvablehardware/BitstreamEvolution, GPL-3.0: mutates an 18-bit-per-tile hand-made allowlist of buffer-mux and LC bits, no routing); Levi & Guccione 1999 (XC4000 single-driver local lines) | **Same idea**; we derive the safe set from the database model rather than by hand |
| Open iCE40 bitstream model | Project IceStorm, nextpnr | Inherited; this repo checks their self-consistency |

References:
- Fibich, Horauer, Obermaisser. DATE 2023 (2 pp., "preliminary results").
- Fritzsch, Hoffmann, Bogdan. Evolving hardware by direct bitstream manipulation of a modern FPGA. CEC 2022.
- Levi, Guccione. GeneticFPGA. EH 1999, doi:10.1109/EH.1999.785430.
- BitstreamEvolution, github.com/evolvablehardware/BitstreamEvolution.
