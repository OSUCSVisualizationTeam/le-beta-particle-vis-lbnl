"""Inspect a Historical export `.h5` file (issue #56).

Prints:
  * `/clusters` schema (column order + dtypes) and row count
  * `/images/*` count and a sample shape
  * `/export_info` attrs (provenance)
  * Optional preview of the first N rows

Usage::

    uv run python tools/h5_export_dump.py path/to/export.h5
    uv run python tools/h5_export_dump.py path/to/export.h5 --rows 5

This is the manual smoke-test companion to the automated
`test_H5ExportStorageService.py` suite.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import h5py


def _print_header(title: str) -> None:
    print()
    print(f"=== {title} ===")


def dump(path: Path, rows: int) -> None:
    with h5py.File(path, "r") as f:
        _print_clusters(f, rows)
        _print_images(f)
        _print_export_info(f)


def _print_clusters(f: h5py.File, rows: int) -> None:
    _print_header("/clusters")
    ds = f["clusters"]
    print(f"rows: {ds.shape[0]}")
    print("columns:")
    for name in ds.dtype.names:
        print(f"  - {name}: {ds.dtype[name]}")
    if rows > 0 and ds.shape[0] > 0:
        _print_header(f"first {min(rows, ds.shape[0])} rows")
        for i in range(min(rows, ds.shape[0])):
            row = ds[i]
            print(f"row {i}:")
            for name in ds.dtype.names:
                value = row[name]
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                print(f"  {name}: {value}")


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
        help="Print the first N rows of /clusters (default: 0)",
    )
    args = parser.parse_args()
    dump(args.path, args.rows)


if __name__ == "__main__":
    main()
