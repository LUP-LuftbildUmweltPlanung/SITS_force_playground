"""Benchmark lossless GeoTIFF layouts on representative raster windows.

This script never runs FORCE and never rewrites the source mosaic. It extracts
small north, center, and south windows and compares their aggregate compressed
sizes and write times. The results can then be copied into ``mosaic_output`` in
``config.yaml`` before producing one full-resolution mosaic.
"""

import argparse
import csv
import json
from pathlib import Path
import subprocess
import time


BASELINE = {
    "name": "baseline_zstd9_pixel_512",
    "compression": "ZSTD",
    "interleave": "PIXEL",
    "level": 9,
    "block_size": 512,
}


def variants():
    yield BASELINE
    for compression in ("ZSTD", "LERC_ZSTD"):
        for level in (15, 19):
            for block_size in (512, 1024):
                yield {
                    "name": (
                        f"{compression.lower()}_{level}_band_{block_size}"
                    ),
                    "compression": compression,
                    "interleave": "BAND",
                    "level": level,
                    "block_size": block_size,
                }


def raster_info(path):
    result = subprocess.run(
        ["gdalinfo", "-json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    info = json.loads(result.stdout)
    band_types = {band["type"] for band in info["bands"]}
    if band_types != {"Int8"}:
        raise ValueError(
            f"Expected an Int8 source, found {sorted(band_types)} in {path}"
        )
    return info


def sample_windows(width, height, sample_size):
    size = min(sample_size, width, height)
    x_offset = (width - size) // 2
    windows = []
    for name, vertical_fraction in (
        ("north", 0.20),
        ("center", 0.50),
        ("south", 0.80),
    ):
        center_y = round(height * vertical_fraction)
        y_offset = max(0, min(height - size, center_y - size // 2))
        windows.append((name, x_offset, y_offset, size, size))
    return windows


def creation_options(variant):
    options = [
        "-co", f"COMPRESS={variant['compression']}",
        "-co", f"INTERLEAVE={variant['interleave']}",
        "-co", f"ZSTD_LEVEL={variant['level']}",
        "-co", "TILED=YES",
        "-co", f"BLOCKXSIZE={variant['block_size']}",
        "-co", f"BLOCKYSIZE={variant['block_size']}",
        "-co", "BIGTIFF=IF_SAFER",
        "-co", "NUM_THREADS=ALL_CPUS",
    ]
    if variant["compression"] == "ZSTD":
        options.extend(["-co", "PREDICTOR=2"])
    else:
        options.extend(["-co", "MAX_Z_ERROR=0"])
    return options


def benchmark(source, output_dir, sample_size):
    info = raster_info(source)
    width, height = info["size"]
    band_count = len(info["bands"])
    windows = sample_windows(width, height, sample_size)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for variant in variants():
        total_bytes = 0
        total_seconds = 0.0
        for sample_name, xoff, yoff, xsize, ysize in windows:
            destination = output_dir / f"{sample_name}_{variant['name']}.tif"
            if destination.exists():
                raise FileExistsError(
                    f"Benchmark output already exists: {destination}. "
                    "Use a new --output-dir or remove the old benchmark directory."
                )

            command = [
                "gdal_translate",
                "-q",
                "-of", "GTiff",
                "-ot", "Int8",
                "-srcwin", str(xoff), str(yoff), str(xsize), str(ysize),
                *creation_options(variant),
                str(source),
                str(destination),
            ]
            print(f"Writing {destination.name}", flush=True)
            started = time.monotonic()
            subprocess.run(command, check=True)
            total_seconds += time.monotonic() - started
            total_bytes += destination.stat().st_size

        raw_bytes = sum(
            xsize * ysize * band_count
            for _, _, _, xsize, ysize in windows
        )
        rows.append({
            **variant,
            "samples": len(windows),
            "compressed_bytes": total_bytes,
            "compressed_mib": total_bytes / 1024**2,
            "compression_ratio": raw_bytes / total_bytes,
            "seconds": total_seconds,
        })

    baseline_bytes = rows[0]["compressed_bytes"]
    for row in rows:
        row["size_change_percent"] = (
            (row["compressed_bytes"] / baseline_bytes) - 1
        ) * 100

    results_path = output_dir / "results.csv"
    with results_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print("\nAggregate results (smaller is better):")
    print(f"{'variant':38} {'MiB':>10} {'vs baseline':>12} {'seconds':>10}")
    for row in sorted(rows, key=lambda item: item["compressed_bytes"]):
        print(
            f"{row['name']:38} "
            f"{row['compressed_mib']:10.1f} "
            f"{row['size_change_percent']:+11.1f}% "
            f"{row['seconds']:10.1f}"
        )

    winner = min(rows, key=lambda item: item["compressed_bytes"])
    print(f"\nSmallest lossless variant: {winner['name']}")
    print(f"Detailed results: {results_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark lossless compression without rebuilding the mosaic."
    )
    parser.add_argument("source", type=Path, help="Existing Int8 NBR mosaic")
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="New directory in which benchmark samples and results are written",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=2048,
        help="Width and height of each of three sample windows (default: 2048)",
    )
    args = parser.parse_args()
    if args.sample_size <= 0:
        parser.error("--sample-size must be positive")
    benchmark(args.source, args.output_dir, args.sample_size)


if __name__ == "__main__":
    main()
