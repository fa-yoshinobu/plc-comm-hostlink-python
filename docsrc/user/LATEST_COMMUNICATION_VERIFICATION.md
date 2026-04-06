# Latest Communication Verification

This page keeps the current public summary only. Older detailed notes are not kept in the public documentation set.

## Current Retained Summary

- latest retained hardware check date: `2026-03-19`
- verified PLC model: `KV-7500`
- verified Ethernet paths: built-in Ethernet port and `KV-XLE02`
- verified transports: `TCP`, `UDP`
- verified public surface: typed reads/writes, mixed snapshots, bit-in-word updates, single-request reads, chunked reads, polling

## Practical Public Conclusions

- `DM` remains the safest first-run path
- typed views `:S`, `:D`, `:L`, and `:F` are part of the current public helper surface
- bit-in-word updates remain public through `write_bit_in_word`

## Current Cautions

- keep large chunked reads out of the first smoke test
- use only the families in the current public register table

## Where Older Evidence Went

Public historical validation clutter was removed. Maintainer-only retained evidence now belongs under `internal_docs/`.
