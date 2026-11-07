# Elyon — recovered change evidence

This ZIP was extracted **locally** from a user-provided ChatGPT shared-thread JSON network capture.
The original HTTP request headers, bearer token, account identifiers, chat messages,
and network-response wrapper were deliberately **excluded**.

## Contents

- `initial_sources/` — 23 initial full-file additions as reported by the webpage,
  plus the README content captured in its replacement hunk. These are **not the final files**.
- `changes/` — all **60 fileChange entries** (including additions and later updates),
  numbered in the order they appeared. Each uses source paths inferred from the
  final `docs/RESULTS.md` file map.
- `MANIFEST.json` — evidence count, path map and SHA-256 for each change text.

## Known limitation

The webpage recorded 31 completed change batches containing 60 change entries
across 24 distinct basenames. Some later patches reference line numbers or contexts
absent in the initial file additions, so a complete final tree **cannot be proved**
by blindly applying these patches. They preserve valuable source fragments and
full patch evidence but do not guarantee a buildable project.

`docs/RESULTS.md` itself lists `tests/__init__.py`, which has no corresponding
source-creation event in this capture. Generated `artifacts/` outputs are also
not included in this response.

To restore the project correctly, supply this archive to a Codex workspace and
ask it to replay/reconcile the source edits, identify unaccounted-for fragments,
then rerun tests. Keep the recovered evidence separately until verification passes.
