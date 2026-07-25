import argparse
import json
from pathlib import Path

import numpy as np
import rasterio

COLOR_MAP = {
    (0, 0, 0): 0,  # Background / no data
    (0, 255, 0): 4,  # Farmland
    (0, 0, 255): 3,  # Water
    (0, 255, 255): 1,  # Forest
    (255, 0, 0): 2,  # Built-up
    (255, 255, 0): 5,  # Meadow
}
DEFAULT_CLASS = 0


def process_year(year: str, input_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{year}_cog.tif"
    stats_path = output_dir / f"{year}_stats.json"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    global_stats = {class_id: 0 for class_id in COLOR_MAP.values()}
    global_stats[DEFAULT_CLASS] = 0

    with rasterio.open(input_path) as src:
        profile = src.profile.copy()
        profile.update(
            {
                "count": 1,
                "dtype": "uint8",
                "driver": "GTiff",
                "compress": "deflate",
                "tiled": True,
                "blockxsize": 512,
                "blockysize": 512,
                "photometric": "MINISBLACK",
                "nodata": 0,
            }
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            windows = list(src.block_windows(1))
            total_windows = len(windows)

            for index, (_, window) in enumerate(windows):
                r = src.read(1, window=window)
                g = src.read(2, window=window)
                b = src.read(3, window=window)

                out_block = np.full(r.shape, DEFAULT_CLASS, dtype=np.uint8)

                for rgb, class_id in COLOR_MAP.items():
                    r_t, g_t, b_t = rgb
                    mask = (r == r_t) & (g == g_t) & (b == b_t)
                    out_block[mask] = class_id
                    global_stats[class_id] += int(np.count_nonzero(mask))

                dst.write(out_block, 1, window=window)

                if index % 100 == 0:
                    percent = (index / total_windows) * 100
                    print(f"{year}: {percent:.2f}%", end="\r")

            print(f"{year}: 100.00%")

            overviews = [2**j for j in range(1, 16)]
            dst.build_overviews(overviews, rasterio.enums.Resampling.nearest)
            dst.update_tags(ns="rio_overview", resampling="nearest")

    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(global_stats, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert RGB LULC segmentation rasters to single-band COGs.")
    parser.add_argument("--input-2019", type=Path, required=True, help="RGB LULC segmentation raster for 2019.")
    parser.add_argument("--input-2023", type=Path, required=True, help="RGB LULC segmentation raster for 2023.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/cogs"), help="Directory for generated COGs.")
    args = parser.parse_args()

    process_year("2019", args.input_2019, args.output_dir)
    process_year("2023", args.input_2023, args.output_dir)


if __name__ == "__main__":
    main()
