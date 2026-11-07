# Preserved uploads

These files are evidence, not the active application. The original repository
upload flattened source snapshots, patches, documentation, and a recovery ZIP
into the root. Every uploaded file is preserved byte-for-byte here.

- `changes/`: all 60 ordered change records; filenames retain their sequence.
- `initial-upload/`: flattened initial source and historical documents.
- `bundles/`: the complete recovery ZIP originally uploaded to GitHub.
- `UPLOAD-MAP.json`: old paths, preserved paths, and SHA-256 digests.

The runnable source is `../elyon/`, tests are `../tests/`, and current documentation
is `../docs/`. Do not blindly apply these historical patches to the active tree.
Run `python tools/check_recovery.py` to verify the original upload is intact.
