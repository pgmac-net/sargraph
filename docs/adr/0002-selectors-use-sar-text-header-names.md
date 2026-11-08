# Selectors name columns exactly as text sar prints them

Status: accepted (pgmac-net/homelabia#230)

A selector is `SECTION.COLUMN[@DEVICE]`. The column is the header text sar prints (`%usr`, `rxkB/s`), not an invented name. People already read those headers in sar output, and ADR 0001 means both input kinds share them.

Section names are short and fixed (`cpu`, `mem`, `net`, ...) because the headers repeat across sections (`IFACE` heads both `net` and `net-err`) and are not unique. An unrecognised section gets `x-<first column>`, so new sysstat sections load without a code change.

A device is recognised from the header's first column (`CPU`, `IFACE`, `DEV`, ...) and not from the row's first value, because CPU ids are numeric (`0`, `1`).
