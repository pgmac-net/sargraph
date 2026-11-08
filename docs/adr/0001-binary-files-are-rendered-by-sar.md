# Binary sa files are rendered by `sar -A -f`, not parsed or read as JSON

Status: accepted (pgmac-net/homelabia#230)

The first design read binary `saDD` files with `sadf -j` (JSON). Measured on sysstat 12.7.7, that is the wrong source:

- JSON keys differ from the text headers (`user`, `system` against `%usr`, `%sys`), so every section needs a hand-kept key map that drifts between sysstat versions.
- JSON timestamps are converted to UTC, while text sar prints host-local time.

`LC_ALL=C S_TIME_FORMAT=ISO sar -A -f FILE` prints the same text format as a text input, in local 24h time with ISO dates. Binary input is therefore rendered to text and handed to the one text parser, so column names match by construction and there is a single code path.

Consequences: binary input needs `sar` (sysstat) installed, as `sadf` would have. Files from another sysstat version fail with sar's own error, and the message points at `sadf -c` to convert them.
