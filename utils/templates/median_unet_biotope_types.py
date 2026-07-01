import numpy as np
from datetime import date

SEASON_ORDER = ["spring", "summer", "autumn", "winter"]
_EPOCH       = date(1970, 1, 1)

IDX_RED   = 2   # B04
IDX_NIR   = 6   # B08
IDX_GREEN = 1   # B03

BAND_NAMES_BASE = ["B02","B03","B04","B05","B06","B07","B08","B8A","B11","B12"]
INDEX_NAMES     = ["NDVI", "NDWI"]
NODATA_OUT      = -9999


def forcepy_init(dates, sensors, bandnames):
    out = []
    for season in SEASON_ORDER:
        for bn in BAND_NAMES_BASE:
            out.append(f"{bn}_{season}_median")
        for idx in INDEX_NAMES:
            out.append(f"{idx}_{season}_median")
    return out  # 4 × 12 = 48 Bänder


def forcepy_pixel(inarray, outarray, dates, sensors, bandnames, nodata, nproc):
    """
    This UDF calculates the median for every band/index over each season for the period defined in the parameter file.
    inarray shape:  [nDates, 10, 1, 1]   int16
    outarray shape: [48]                  int16
    Layout:         4 Saisons × (10 Bänder + NDVI + NDWI)
    NDVI/NDWI werden ×10000 skaliert gespeichert (int16-kompatibel)
    """
    nBands = inarray.shape[1]           # 10
    nOut   = nBands + len(INDEX_NAMES)  # 12

    if np.all(inarray[:, :, 0, 0] == nodata):
        outarray[:] = NODATA_OUT
        return

    # ── Reflektanzen: int16 → float32, nodata → NaN ─────────────────────
    vals = inarray[:, :, 0, 0].astype(np.float32)
    vals[vals == float(nodata)] = np.nan

    # ── DOY aus Unix-Tagen ───────────────────────────────────────────────
    doys = np.array([
        date.fromordinal(_EPOCH.toordinal() + int(d)).timetuple().tm_yday
        for d in dates
    ], dtype=np.int32)

    # ── Saison-Masken ────────────────────────────────────────────────────
    season_masks = {
        "spring": (doys >= 60)  & (doys <= 151),
        "summer": (doys >= 152) & (doys <= 243),
        "autumn": (doys >= 244) & (doys <= 334),
        "winter": ((doys >= 1)  & (doys <= 59)) | (doys >= 335),
    }

    # ── NDVI / NDWI berechnen, ×10000 skalieren → int16-kompatibel ──────
    red   = vals[:, IDX_RED]
    nir   = vals[:, IDX_NIR]
    green = vals[:, IDX_GREEN]

    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir   - red)   / (nir   + red)   * 10000.0
        ndwi = (green - nir)   / (green + nir)   * 10000.0

    ndvi[~np.isfinite(ndvi)] = np.nan
    ndwi[~np.isfinite(ndwi)] = np.nan

    # Indizes anhängen → [nDates, 12]
    vals_ext = np.concatenate(
        [vals, ndvi[:, np.newaxis], ndwi[:, np.newaxis]], axis=1
    )

    # ── Median je Saison ─────────────────────────────────────────────────
    for s_idx, season in enumerate(SEASON_ORDER):
        mask  = season_masks[season]
        start = s_idx * nOut

        if mask.sum() == 0:
            outarray[start:start + nOut] = NODATA_OUT
            continue

        med = np.nanmedian(vals_ext[mask, :], axis=0)  # [12]

        result = np.round(med).astype(np.int16)
        result[np.isnan(med)] = NODATA_OUT
        outarray[start:start + nOut] = result