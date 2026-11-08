# sargraph

CLI that graphs [sysstat](https://github.com/sysstat/sysstat) SAR data to **png**, **svg** or **jpg**.

It reads SAR data you already have, as text `sar` output or binary `saDD` files. Collecting the data is not its job. Pick a time range and one or more metrics, and it draws them.

## Install

```sh
uv tool install git+https://github.com/pgmac-net/sargraph
```

Binary `saDD` files need the `sar` command (the `sysstat` package). Text files need nothing else.

## Use

```sh
# What can I graph?
sargraph list sar-2026-09-02.txt

# CPU and memory, 06:00 to 18:00, three formats at once
sargraph sar-2026-09-02.txt \
  -m 'cpu.%usr@all' -m 'cpu.%sys@all' -m 'mem.%memused' \
  --from 06:00 --to 18:00 \
  -o out.png -o out.svg -o out.jpg

# Binary files, several days, a glob of columns
sargraph /var/log/sysstat/sa0[1-3] -m 'cpu.%*@all' --layout combined -o cpu.png
```

`sargraph graph ...` and `sargraph ...` are the same.

### Metrics: `-m SECTION.COLUMN[@DEVICE]`

Repeatable. Each part may be a glob. No `@DEVICE` means every device.

| Example | Selects |
|---|---|
| `cpu.%usr@all` | total CPU user time |
| `cpu.%*@all` | every CPU percentage |
| `net.rxkB/s@eth0` | receive rate on `eth0` |
| `mem.%memused` | memory used |
| `disk.tps@sda` | transfers per second on `sda` |

Sections: `cpu`, `mem`, `swap`, `paging`, `io`, `disk`, `net`, `net-err`, `load`, `sock`, `nfs`, `nfsd`, `task`, `swapping`, `hugepages`, `inode`, `tty`, `softnet`. Any other section loads as `x-<first column>`. Columns are named exactly as `sar` prints them. `sargraph list FILE...` prints every selector a file offers.

### Time range

`--from` and `--to`, both optional and inclusive.

- ISO datetime: `2026-09-02T09:00`.
- A date alone is the whole day: its start for `--from`, its end for `--to`.
- A bare time (`09:00`) works only when the data covers a single day.

Times are the host's local time as sar prints them. Nothing is converted between timezones. In text input, a time that goes backwards inside a section means midnight passed and the date advances. A `--from` or `--to` that leaves nothing to plot is an error.

### Several files and hosts

All files load into one timeline. If two files hold the same sample, the first one given wins. With more than one host, series are labelled `host:metric`.

### Layout: `--layout`

| Value | Result |
|---|---|
| `stacked` (default) | one image, one subplot per `-m`, shared time axis |
| `combined` | every series on one set of axes |
| `separate` | one image per `-m`; put `{n}` or `{metric}` in the `-o` name |

### Output

- `-o FILE`: format comes from the extension (`.png`, `.svg`, `.jpg`, `.jpeg`). Repeat `-o` to write several; the data is read once.
- `-o -` writes to stdout and needs `--format png|svg|jpg`.
- `--width`, `--height` in pixels (default 1600x900), `--dpi` (default 100).
- jpg has a white background, quality 90.
- `--title` replaces the automatic title.
- No `-o` is an error: there is no interactive window.

`LINUX RESTART` markers break the plotted line instead of joining across the restart.

## Development

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run pylint src tests
uv run pytest
```

Terms are defined in [CONTEXT.md](CONTEXT.md). Decisions are in [docs/adr](docs/adr).

## Releases

A signed tag `vX.Y.Z` runs the release workflow: it builds the wheel and sdist with `uv build` and attaches them, plus `checksums.txt`, to a GitHub Release.

## Licence

MIT.
