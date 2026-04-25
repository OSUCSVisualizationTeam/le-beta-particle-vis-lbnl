"""Inspect a Historical export `.h5` file (issue #56).

Prints:
  * `/clusters` schema (column order + dtypes) and row count, via pandas DataFrame
  * `/images/*` count and a sample shape
  * `/export_info` attrs (provenance)
  * Optional preview of the first N rows as a DataFrame

Usage::

    uv run python tools/h5_export_dump.py path/to/export.h5
    uv run python tools/h5_export_dump.py path/to/export.h5 --rows 5

Loading /clusters into a DataFrame in your own analysis scripts
(``pd.read_hdf()`` is NOT compatible — this file is written with h5py,
not PyTables)::

    import h5py
    import pandas as pd

    with h5py.File("export.h5", "r") as f:
        df = pd.DataFrame(f["clusters"][:])

This is the manual smoke-test companion to the automated
``test_H5ExportStorageService.py`` suite.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import h5py
import pandas as pd


def _print_header(title: str) -> None:
    print()
    print(f"=== {title} ===")


def dump(path: Path, rows: int) -> None:
    with h5py.File(path, "r") as f:
        _print_clusters(f, rows)
        _print_images(f)
        _print_export_info(f)


def _decode_bytes_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Decode object columns that contain bytes (h5py < 3 variable-length string behaviour)."""
    for col in df.select_dtypes(include="object").columns:
        if df[col].size and isinstance(df[col].iloc[0], bytes):
            df[col] = df[col].str.decode("utf-8", errors="replace")
    return df


def _print_clusters(f: h5py.File, rows: int) -> None:
    _print_header("/clusters")
    df = _decode_bytes_columns(pd.DataFrame(f["clusters"][:]))
    print(f"rows: {len(df)}")
    print("\nschema (column order locked — see H5ExportStorageService.CLUSTER_COLUMNS):")
    for col, dtype in df.dtypes.items():
        print(f"  {col}: {dtype}")
    if rows > 0 and len(df) > 0:
        _print_header(f"first {min(rows, len(df))} rows")
        with pd.option_context(
            "display.max_columns", None,
            "display.max_rows", rows,
            "display.width", None,
            "display.max_colwidth", 40,
        ):
            print(df.head(rows).to_string(index=True))


def _print_images(f: h5py.File) -> None:
    _print_header("/images")
    if "images" not in f:
        print("(missing)")
        return
    keys = list(f["images"].keys())
    print(f"count: {len(keys)}")
    if keys:
        sample = f["images"][keys[0]]
        print(f"sample key: {keys[0]}  shape: {sample.shape}  dtype: {sample.dtype}")


def _print_export_info(f: h5py.File) -> None:
    _print_header("/export_info")
    if "export_info" not in f:
        print("(missing)")
        return
    attrs = f["export_info"].attrs
    for name in attrs:
        value = attrs[name]
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        print(f"  {name}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Path to export .h5")
    parser.add_argument(
        "--rows",
        type=int,
        default=0,
        help="Print the first N rows of /clusters as a DataFrame (default: 0)",
    )
    args = parser.parse_args()
    dump(args.path, args.rows)


if __name__ == "__main__":
    main()
