# Context

Terms used across this repo's code and docs.

## SAR data

**Sample**: one value of one metric at one time, for one host and device. The long-format table holds one row per sample: `host, timestamp, section, device, metric, value`.

**Section**: a block of related columns in sar output, under one header (`cpu`, `mem`, `net`, ...). Short names come from the header signature (`model.SECTION_NAMES`). A section not in that table still loads, named `x-<first column>`. *Avoid*: "report", "activity".

**Metric**: one column of a section, named exactly as text `sar` prints it (`%usr`, `rxkB/s`).

**Device**: the row key within a section that has one: CPU id, interface, block device, tty. Sections without one use the empty device. *Avoid*: "instance", "unit".

**Selector**: `SECTION.COLUMN[@DEVICE]`, the thing `-m` takes. Each part may be a glob. No device means every device. `sargraph list` prints the selectors a file offers.

**Series**: one plotted line: one host, section, metric and device.

**Restart**: a `LINUX RESTART` marker. Plotted lines break there instead of joining across it.

## Input

**Text input**: output of `sar -A` (or similar) saved to a file. Parsed by `parse_text`.

**Binary input**: a sysstat `saDD` file. Never parsed directly: `sar -A -f` (with `LC_ALL=C S_TIME_FORMAT=ISO`) renders it to text and the text parser reads that. See `docs/adr/0001-binary-files-are-rendered-by-sar.md`.

**Section clock**: the per-section date counter. Each section runs through the whole day in `sar -A` output, so time going backwards inside a section means midnight passed, and a new section starts its own clock.

## Output

**Layout**: how selectors map to images. `stacked` is one subplot per `-m`, `combined` is every series on one axes, `separate` is one file per `-m`.
