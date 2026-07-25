import argparse
from pathlib import Path

import numpy as np
import rasterio


def process_brickfield(year: str, input_path: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"brickfield_{year}_cog.tif"

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

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
                "nodata": 0,
            }
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            for _, window in src.block_windows(1):
                data = src.read(1, window=window)
                clean_data = np.where(data > 0, 1, 0).astype(np.uint8)
                dst.write(clean_data, 1, window=window)

            overviews = [2**j for j in range(1, 16)]
            dst.build_overviews(overviews, rasterio.enums.Resampling.nearest)
            dst.update_tags(ns="rio_overview", resampling="nearest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert brickfield masks to single-band COGs.")
    parser.add_argument("--input-2019", type=Path, required=True, help="Brickfield segmentation raster for 2019.")
    parser.add_argument("--input-2023", type=Path, required=True, help="Brickfield segmentation raster for 2023.")
    parser.add_argument("--output-dir", type=Path, default=Path("data/cogs"), help="Directory for generated COGs.")
    args = parser.parse_args()

    process_brickfield("2019", args.input_2019, args.output_dir)
    process_brickfield("2023", args.input_2023, args.output_dir)


if __name__ == "__main__":
    main()
