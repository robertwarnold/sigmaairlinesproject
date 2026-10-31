# Public-source conversion candidate

Source: NASA/CR-2019-220217, June 2019, Table B-1, printed B-1 (PDF page 109),
rows 1A1 and 1B1. Definitions: section 8.1, printed 52–53 (PDF pages 66–67).

- Catalog: https://ntrs.nasa.gov/citations/20190026443
- Original PDF: https://ntrs.nasa.gov/api/citations/20190026443/downloads/20190026443.pdf
- Rights: catalog states Public Use Permitted. Only a limited attributed derivative
  fixture is proposed for repository review. The original PDF/render stays ignored.

The two selected rows were compared visually with the rendered source page during
development. Wrapped words/line breaks were joined. The worksheet has a function column,
not a separate item column: this candidate uses that function as the functional item
label and retains an explicit review flag. Hardware scope is not inferred.

Source rates retain scientific-notation strings and failures-per-flight-hour units.
Severity codes, alpha, beta and criticality numbers retain source meanings. Source
criticality is a probability over its stated default one-hour mission, not a generic
FMEA RPN. No target rating is assigned. Beta explanation text remains referenced by
column locator rather than represented as a complete copied worksheet.

Detection and compensating provisions are separated. Section 8.1 describes compensating
provisions as mitigation of effects rather than occurrence prevention. The report is
conceptual design evidence; the candidate does not assert controls are implemented.
Both kinds therefore retain unknown implementation status and source evidence.

Tests verify supported engineering-field mappings, original risk values/units, retained
unmapped fields, unknown ratings/actions/implemented controls, report hashes, and export
bundle verification. They do not independently establish that the source engineering
judgments are correct or complete. The source-page manifest records the original PDF
hash and review/normalization boundaries; it does not claim independent approval.

This is **candidate conversion evidence**, not reviewed benchmark ground truth. It lives
only under tests/fixtures and is never imported by generation/provider code. Do not use
these answers as context for evaluating the same system. Independent engineering review
must check item interpretation, propagation levels, source ratings, controls and all
selected source cells before freezing a benchmark. Owners remain Unassigned.
