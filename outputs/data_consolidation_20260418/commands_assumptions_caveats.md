# Commands, assumptions, caveats

## Command run
- `python scripts/build_data_consolidation_bundle.py --output-dir outputs/data_consolidation_20260418`

## Assumptions
- Uses current repository registries and output folders as source of truth.
- Treats finalized dataset set as fixed; no new dataset hunting.

## Caveats
- Inventory uses lightweight folder scans and selected row-count probes, not full artifact replay.
- Some older exploratory outputs remain in-place and are classified by role rather than deleted.
