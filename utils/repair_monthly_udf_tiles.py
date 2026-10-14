"""Normalize monthly FORCE UDF tiles to a fixed calendar-month band schema."""

import argparse
import os
from pathlib import Path

import numpy as np
import rasterio


NODATA = -9999


def expected_descriptions(year):
    return tuple(f"{year}{month:02d}_NBR_MEDIAN" for month in range(1, 13))


def inspect_tile(path, descriptions):
    with rasterio.open(path) as src:
        actual = tuple(src.descriptions)
        if len(actual) == len(descriptions) and actual == descriptions:
            return "complete"
        if any(description is None for description in actual):
            raise ValueError(f"{path}: one or more bands have no description")
        if len(set(actual)) != len(actual):
            raise ValueError(f"{path}: duplicate band descriptions")
        unexpected = sorted(set(actual) - set(descriptions))
        if unexpected:
            raise ValueError(f"{path}: unexpected bands: {unexpected}")
        return "incomplete"


def normalize_tile(path, descriptions):
    """Pad/reorder one tile atomically, retaining the original as a backup."""
    path = Path(path)
    backup = path.with_suffix(path.suffix + ".pre_month_padding")
    temporary = path.with_suffix(path.suffix + ".month_padding_tmp")

    if backup.exists():
        raise FileExistsError(f"Backup already exists: {backup}")
    if temporary.exists():
        temporary.unlink()

    with rasterio.open(path) as src:
        source_descriptions = tuple(src.descriptions)
        source_bands = {
            description: index
            for index, description in enumerate(source_descriptions, start=1)
        }
        profile = src.profile.copy()
        profile.update(count=len(descriptions), nodata=NODATA, BIGTIFF="IF_SAFER")
        dataset_tags = src.tags()
        band_tags = {
            description: src.tags(source_bands[description])
            for description in source_descriptions
        }

        with rasterio.open(temporary, "w", **profile) as dst:
            dst.update_tags(**dataset_tags)
            for destination_band, description in enumerate(descriptions, start=1):
                dst.set_band_description(destination_band, description)
                source_band = source_bands.get(description)
                if source_band is not None:
                    dst.update_tags(destination_band, **band_tags[description])

                for _, window in dst.block_windows(destination_band):
                    if source_band is None:
                        data = np.full(
                            (window.height, window.width),
                            NODATA,
                            dtype=profile["dtype"],
                        )
                    else:
                        data = src.read(source_band, window=window)
                    dst.write(data, destination_band, window=window)

    try:
        os.replace(path, backup)
        os.replace(temporary, path)
    except Exception:
        if backup.exists() and not path.exists():
            os.replace(backup, path)
        raise


def normalize_directory(root, year):
    descriptions = expected_descriptions(year)
    paths = sorted(Path(root).glob("X*/PYP/*.tif"))
    if not paths:
        raise ValueError(f"No PYP tiles found below {root}")

    complete = []
    incomplete = []
    for path in paths:
        status = inspect_tile(path, descriptions)
        (complete if status == "complete" else incomplete).append(path)

    print(f"Validated {len(paths)} tiles: {len(complete)} complete, {len(incomplete)} incomplete")
    for number, path in enumerate(incomplete, start=1):
        print(f"Normalizing {number}/{len(incomplete)}: {path}", flush=True)
        normalize_tile(path, descriptions)

    for path in paths:
        if inspect_tile(path, descriptions) != "complete":
            raise ValueError(f"Normalization verification failed: {path}")
    print(f"All {len(paths)} tiles now have the expected 12-band schema")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", help="tiles_tss directory containing X*/PYP/*.tif")
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()
    normalize_directory(args.root, args.year)


if __name__ == "__main__":
    main()
