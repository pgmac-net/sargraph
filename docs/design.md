# sargraph: design notes

Built for pgmac-net/homelabia#230: a CLI that graphs existing SAR data to png, svg and jpg, filtered by time range and metric. Getting the SAR data is out of scope.

## Shape

```
files -> load (text | binary via sar) -> parse_text -> long table
      -> filter_time -> select(-m) -> plot.render -> save (png|svg|jpg)
```

Long table columns: `host, timestamp, section, device, metric, value`. Restart markers travel in the same table under the `_restart` section and are split out by the loader.

| Module | Job |
|---|---|
| `model.py` | table schema, section names, `Selector` parse and glob match |
| `parse_text.py` | generic text parser (state machine, no per-section code) |
| `load.py` | type detection, `sar -f` for binary, merge and dedup, time range |
| `plot.py` | layouts, restart gaps, export |
| `cli.py` | `graph` (default) and `list` |

## Decisions

The grilling session settled these before any code:

1. Input is text and binary, auto-detected.
2. Python, uv, matplotlib, pandas, typer. ruff, pylint and pytest check it.
3. New public repo `pgmac-net/sargraph`, declared in terraform-github (PR #69).
4. Metrics are `SECTION.COLUMN[@DEVICE]`, repeatable, globs allowed, columns named as sar prints them. `list` shows what exists.
5. Times are naive host-local. Bare `HH:MM` needs a single-day dataset. Files merge, first duplicate wins. Hosts become `host:metric` series.
6. Layouts: `stacked` (default), `combined`, `separate`.
7. `-o` picks the format from the extension and repeats. `-o -` needs `--format`. No `-o` is an error.
8. The text parser is generic and tolerates 12h/24h times and comma decimals.
9. Install with `uv tool install git+...`. CI runs ruff, pylint, pytest. A signed tag builds the release.

Decisions 1 and 4 have ADRs in `docs/adr`.

## Deviations from the approved plan

- **Binary input** goes through `sar -A -f` (with `LC_ALL=C S_TIME_FORMAT=ISO`), not `sadf -j`. `sadf -j` uses different keys and UTC timestamps, so it would need a fragile per-version key map. See ADR 0001.
- **Device detection** uses the header's first column rather than "first field non-numeric", since CPU ids are numeric. See ADR 0002.
- **Per-section clocks.** `sar -A` prints each section across the whole day, so a single midnight-rollover counter would misfire at every section boundary. Each section keeps its own.
- **Date-only bounds** (`--to 2026-09-02`) mean the whole day. Not in the plan; it avoids `--to` silently stopping at midnight.

## Testing

- `tests/data/sample_12h.sar` is a trim of a real `sar -A` capture (three samples per section, hostname scrubbed). It covers 12-hour times and all 18 standard sections.
- `tests/data/edge_24h.sar` is hand-written: 24-hour times, comma decimals, midnight rollover, `LINUX RESTART`, an `Average:` line and an unknown section.
- Binary input is tested with `sar` mocked, plus a manual run against real `/var/log/sysstat/saDD` files (all standard sections, the newer PSI sections via the `x-` fallback). There is no committed binary fixture: it would carry host data and is sysstat-version specific.
- Exports are checked by magic bytes for all three formats. A test asserts a restart puts a gap in the plotted line.
