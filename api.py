import io
import os
from pathlib import Path
from typing import Any, Dict

import numpy as np
import rasterio
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from rasterio.enums import Resampling
from rasterio.features import bounds as feature_bounds, geometry_mask
from rasterio.transform import from_bounds as transform_from_bounds
from rasterio.windows import from_bounds
from rio_tiler.io import COGReader

app = FastAPI(title="LULC Bangladesh API")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

DATA_DIR = Path(os.getenv("LULC_DATA_DIR", "data/cogs")).resolve()

DATASETS = {
    "lulc2019": "2019_cog.tif",
    "lulc2023": "2023_cog.tif",
    "brickfield2019": "brickfield_2019_cog.tif",
    "brickfield2023": "brickfield_2023_cog.tif",
    "bing2019": "bing_satellite_2019_cog.tif",
    "bing2023": "bing_satellite_2023_cog.tif",
}

COLORS = {
    1: (0, 255, 255),  # Forest
    2: (255, 0, 0),  # Built-up
    3: (0, 0, 255),  # Water
    4: (0, 255, 0),  # Farmland
    5: (255, 255, 0),  # Meadow
}
BRICKFIELD_COLORS = {1: (255, 0, 0)}
GREY = (128, 128, 128)
FALLBACK_RED = (255, 0, 255)


def dataset_path(dataset_key: str) -> Path:
    filename = DATASETS.get(dataset_key)
    if not filename:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_key}")

    path = (DATA_DIR / filename).resolve()
    if DATA_DIR not in path.parents and path != DATA_DIR:
        raise HTTPException(status_code=400, detail="Dataset path is outside configured data directory")
    return path


def safe_convert(arr):
    try:
        if np.ma.is_masked(arr):
            arr = arr.filled(0)
        arr_float = np.array(arr, dtype=np.float32)
        np.nan_to_num(arr_float, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        np.clip(arr_float, 0, 255, out=arr_float)
        return arr_float.astype(np.uint8)
    except Exception as exc:
        print(f"Sanitization failed: {exc}")
        return np.zeros((256, 256), dtype=np.uint8)


def png_response(img: np.ndarray) -> Response:
    image = Image.fromarray(img)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


def empty_tile() -> Response:
    return png_response(np.zeros((256, 256, 4), dtype=np.uint8))


def read_tile(dataset_key: str, x: int, y: int, z: int) -> np.ndarray:
    with COGReader(str(dataset_path(dataset_key))) as src:
        return src.tile(x, y, z).data


def parse_classes(classes: str | None, default_classes: set[int]) -> set[int]:
    if not classes:
        return default_classes
    try:
        return {int(cls.strip()) for cls in classes.split(",") if cls.strip()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="classes must be comma-separated integers") from exc


def render_class_tile(data: np.ndarray, palette: Dict[int, tuple[int, int, int]], active_classes: set[int]) -> Response:
    band = safe_convert(data[0] if data.ndim == 3 else data)
    height, width = band.shape
    img = np.zeros((height, width, 4), dtype=np.uint8)
    for cls_id, rgb in palette.items():
        if cls_id in active_classes:
            img[band == cls_id] = (*rgb, 255)
    return png_response(img)


def render_rgb_tile(data: np.ndarray, nodata: int | None = None) -> Response:
    if data.ndim != 3 or data.shape[0] < 3:
        return empty_tile()

    rgb = np.stack([safe_convert(data[i]) for i in range(3)], axis=-1)
    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    if nodata is not None:
        alpha[np.all(rgb == nodata, axis=-1)] = 0
    return png_response(np.dstack([rgb, alpha]))


def render_change_tile_internal(b19, b23, l19, l23) -> bytes:
    b19 = safe_convert(b19)
    b23 = safe_convert(b23)
    l19 = safe_convert(l19)
    l23 = safe_convert(l23)

    height, width = b19.shape
    img = np.zeros((height, width, 4), dtype=np.uint8)

    is_brick_19 = b19 > 0
    is_brick_23 = b23 > 0

    mask_unchanged = is_brick_19 & is_brick_23
    img[mask_unchanged] = (*GREY, 255)

    mask_lost = is_brick_19 & (~is_brick_23)
    img[mask_lost] = (*FALLBACK_RED, 255)

    for cls_id, rgb in COLORS.items():
        class_mask = mask_lost & (l23 == cls_id)
        img[class_mask] = (*rgb, 255)

    mask_gained = (~is_brick_19) & is_brick_23
    img[mask_gained] = (*FALLBACK_RED, 255)

    y_indices, x_indices = np.indices((int(height), int(width)))
    stripe_mask = (x_indices + y_indices) % 8 < 3

    for cls_id, rgb in COLORS.items():
        class_mask = mask_gained & (l19 == cls_id)
        img[class_mask] = (*rgb, 255)
        img[class_mask & stripe_mask] = (255, 255, 255, 255)

    fallback_gained = mask_gained & (img[..., 0] == 255) & (img[..., 1] == 0) & (img[..., 2] == 255)
    img[fallback_gained & stripe_mask] = (255, 255, 255, 255)

    buffer = io.BytesIO()
    Image.fromarray(img).save(buffer, format="PNG")
    return buffer.getvalue()


def render_lulc_change_tile_internal(target_id, l19, l23) -> bytes:
    l19 = safe_convert(l19)
    l23 = safe_convert(l23)

    height, width = l19.shape
    img = np.zeros((height, width, 4), dtype=np.uint8)

    is_target_19 = l19 == target_id
    is_target_23 = l23 == target_id

    img[is_target_19 & is_target_23] = (*GREY, 255)
    mask_lost = is_target_19 & (~is_target_23)

    for cls_id, rgb in COLORS.items():
        if cls_id != target_id:
            img[mask_lost & (l23 == cls_id)] = (*rgb, 255)

    mask_gained = (~is_target_19) & is_target_23
    y_indices, x_indices = np.indices((int(height), int(width)))
    stripe_mask = (x_indices + y_indices) % 8 < 3

    for cls_id, rgb in COLORS.items():
        if cls_id != target_id:
            class_mask = mask_gained & (l19 == cls_id)
            img[class_mask] = (*rgb, 255)
            img[class_mask & stripe_mask] = (255, 255, 255, 255)

    buffer = io.BytesIO()
    Image.fromarray(img).save(buffer, format="PNG")
    return buffer.getvalue()


@app.get("/health")
def health():
    return {"status": "ok", "data_dir": str(DATA_DIR)}


@app.get("/tiles/{dataset_key}/{z}/{x}/{y}.png")
def classified_tile(
    dataset_key: str,
    z: int,
    x: int,
    y: int,
    classes: str | None = Query(default=None),
    nodata: int | None = Query(default=None),
):
    try:
        data = read_tile(dataset_key, x, y, z)
        if dataset_key.startswith("lulc"):
            active_classes = parse_classes(classes, set(COLORS))
            return render_class_tile(data, COLORS, active_classes)
        if dataset_key.startswith("brickfield"):
            active_classes = parse_classes(classes, set(BRICKFIELD_COLORS))
            return render_class_tile(data, BRICKFIELD_COLORS, active_classes)
        if dataset_key.startswith("bing"):
            return render_rgb_tile(data, nodata=nodata)
        raise HTTPException(status_code=404, detail=f"Unknown dataset type: {dataset_key}")
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Tile read failed for {dataset_key}/{z}/{x}/{y}: {exc}")
        return empty_tile()


@app.get("/brickfield_change/{z}/{x}/{y}.png")
def brickfield_change(z: int, x: int, y: int):
    try:
        b19 = read_tile("brickfield2019", x, y, z)[0]
        b23 = read_tile("brickfield2023", x, y, z)[0]
        if np.max(safe_convert(b19)) == 0 and np.max(safe_convert(b23)) == 0:
            return empty_tile()
        l19 = read_tile("lulc2019", x, y, z)[0]
        l23 = read_tile("lulc2023", x, y, z)[0]
        return Response(content=render_change_tile_internal(b19, b23, l19, l23), media_type="image/png")
    except Exception as exc:
        print(f"Brickfield change tile failed for {z}/{x}/{y}: {exc}")
        return empty_tile()


@app.get("/lulc_change/{target_id}/{z}/{x}/{y}.png")
def lulc_change(target_id: int, z: int, x: int, y: int):
    if target_id not in COLORS:
        raise HTTPException(status_code=400, detail="Unknown LULC class")
    try:
        l19 = read_tile("lulc2019", x, y, z)[0]
        l23 = read_tile("lulc2023", x, y, z)[0]
        if np.max(safe_convert(l19)) == 0 and np.max(safe_convert(l23)) == 0:
            return empty_tile()
        return Response(content=render_lulc_change_tile_internal(target_id, l19, l23), media_type="image/png")
    except Exception as exc:
        print(f"LULC change tile failed for {z}/{x}/{y}: {exc}")
        return empty_tile()


class GeoStatsRequest(BaseModel):
    dataset: str
    geojson: Dict[str, Any]


@app.get("/exact_stats")
def exact_stats(dataset: str, bbox: str):
    try:
        minx, miny, maxx, maxy = map(float, bbox.split(","))
        with rasterio.open(dataset_path(dataset)) as src:
            window = from_bounds(minx, miny, maxx, maxy, src.transform)
            data = src.read(1, window=window, out_shape=(512, 512), resampling=Resampling.nearest, boundless=True, fill_value=0)
            unique, counts = np.unique(data, return_counts=True)
            result = dict(zip(unique.tolist(), counts.tolist()))
            result.pop(0, None)
            return {"counts": result}
    except HTTPException:
        raise
    except Exception:
        return {"counts": {}}


@app.post("/exact_stats_geojson")
def exact_stats_geojson(item: GeoStatsRequest):
    try:
        geom = item.geojson
        if "geometry" in geom:
            geom = geom["geometry"]
        with rasterio.open(dataset_path(item.dataset)) as src:
            minx, miny, maxx, maxy = feature_bounds(geom)
            window = from_bounds(minx, miny, maxx, maxy, src.transform)
            max_size = 2048
            width, height = int(window.width), int(window.height)
            if width > max_size or height > max_size:
                scale = min(max_size / width, max_size / height)
                width, height = max(1, int(width * scale)), max(1, int(height * scale))
            data = src.read(1, window=window, out_shape=(height, width), resampling=Resampling.nearest, boundless=True, fill_value=0)
            out_transform = transform_from_bounds(minx, miny, maxx, maxy, width, height)
            poly_mask = geometry_mask([geom], transform=out_transform, invert=True, out_shape=(height, width), all_touched=True)
            unique, counts = np.unique(data[poly_mask], return_counts=True)
            result = dict(zip(unique.tolist(), counts.tolist()))
            result.pop(0, None)
            return {"counts": result}
    except HTTPException:
        raise
    except Exception:
        return {"counts": {}}
