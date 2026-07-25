import argparse
import os
import subprocess
import sys
from pathlib import Path


def process_image(
    input_path: Path,
    boundary_geojson: Path,
    output_path: Path,
    memory_limit_mb: str,
    gdal_cachemax_mb: str,
    num_threads: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    vrt_path = output_path.with_suffix(".vrt")

    os.environ["CPL_TMPDIR"] = str(output_path.parent)
    os.environ["TMPDIR"] = str(output_path.parent)

    cmd_vrt = [
        "gdalwarp",
        "-of",
        "VRT",
        "-cutline",
        str(boundary_geojson),
        "-crop_to_cutline",
        "-dstalpha",
        "-wm",
        memory_limit_mb,
        str(input_path),
        str(vrt_path),
    ]

    cmd_cog = [
        "gdal_translate",
        "-of",
        "COG",
        "--config",
        "GDAL_CACHEMAX",
        gdal_cachemax_mb,
        "--config",
        "GTIFF_IGNORE_READ_ERRORS",
        "YES",
        "-co",
        "COMPRESS=DEFLATE",
        "-co",
        "PREDICTOR=2",
        "-co",
        f"NUM_THREADS={num_threads}",
        "-co",
        "BIGTIFF=YES",
        str(vrt_path),
        str(output_path),
    ]

    try:
        subprocess.run(cmd_vrt, check=True)
        subprocess.run(cmd_cog, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit status {exc.returncode}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("GDAL tools were not found in PATH.", file=sys.stderr)
        sys.exit(1)
    finally:
        if vrt_path.exists():
            vrt_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert Bangladesh satellite imagery to a clipped COG.")
    parser.add_argument("--year", choices=["2019", "2023"], required=True, help="Imagery year.")
    parser.add_argument("--input", type=Path, required=True, help="Source satellite GeoTIFF.")
    parser.add_argument(
        "--boundary",
        type=Path,
        default=Path("bgd_admbnda_adm0_bbs_20201113.json"),
        help="Boundary GeoJSON used as the cutline.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/cogs"), help="Directory for generated COGs.")
    parser.add_argument("--warp-memory-mb", default="2048", help="GDAL warp memory limit in MB.")
    parser.add_argument("--gdal-cachemax-mb", default="20000", help="GDAL cache size in MB.")
    parser.add_argument("--threads", default="16", help="GDAL COG compression thread count.")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found: {args.input}")
    if not args.boundary.exists():
        raise FileNotFoundError(f"Boundary file not found: {args.boundary}")

    output_path = args.output_dir / f"bing_satellite_{args.year}_cog.tif"
    process_image(
        args.input,
        args.boundary,
        output_path,
        args.warp_memory_mb,
        args.gdal_cachemax_mb,
        args.threads,
    )


if __name__ == "__main__":
    main()
