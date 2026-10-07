"""FORCE Python UDF for monthly median Normalized Burn Ratio (NBR).

The UDF calculates NBR for every quality-screened acquisition, groups the
observations by calendar month, and writes one Int16 band per month. Output
values are scaled by 1000 to match the Earth Engine workflow this UDF replaces.

The standalone FORCE UDF module supplies the complete BOA band stack. Sentinel-2
B8 is named ``BROADNIR`` by FORCE; ``NIR`` is the narrow B8A band.
"""

from datetime import date, timedelta
import warnings

import numpy as np


EPOCH = date(1970, 1, 1)
OUTPUT_SCALE = 1000


def _calendar_months(dates):
    """Return every calendar month for the years represented by ``dates``.

    FORCE calls the initializer independently for each tile. Some tiles do not
    contain an acquisition in every month, but all tiles in a mosaic must still
    expose the same output bands. Full-year jobs therefore always receive a
    January--December band set, with absent months left as nodata.
    """
    years = sorted(
        {
            (EPOCH + timedelta(days=int(value))).year
            for value in dates
        }
    )
    return [(year, month) for year in years for month in range(1, 13)]


def _band_index(bandnames, expected_name):
    """Find a FORCE band regardless of whether names are bytes or strings."""
    decoded_names = [
        name.decode("utf-8") if isinstance(name, bytes) else str(name)
        for name in bandnames
    ]
    try:
        return decoded_names.index(expected_name)
    except ValueError as error:
        raise ValueError(
            f"Required band {expected_name!r} is missing; got {decoded_names}. "
            "The UDF requires a full Sentinel-2 BOA input stack."
        ) from error


def forcepy_init(dates, sensors, bandnames):
    """Create one dated output band for every calendar month in the input."""
    return [
        f"{year:04d}{month:02d}_NBR_MEDIAN"
        for year, month in _calendar_months(dates)
    ]


def forcepy_pixel(inarray, outarray, dates, sensors, bandnames, nodata, nproc):
    """Calculate monthly median NBR for one pixel.

    ``inarray`` has shape [nDates, nBands, 1, 1]. FORCE has already applied
    the quality screening configured in the parameter file. Invalid inputs and
    zero denominators are excluded independently for every acquisition.
    """
    nir_index = _band_index(bandnames, "BROADNIR")
    swir2_index = _band_index(bandnames, "SWIR2")

    nir = inarray[:, nir_index, 0, 0].astype(np.float64)
    swir2 = inarray[:, swir2_index, 0, 0].astype(np.float64)

    invalid = (nir == nodata) | (swir2 == nodata)
    denominator = nir + swir2
    valid = (~invalid) & (denominator != 0)

    nbr = np.full(nir.shape, np.nan, dtype=np.float64)
    np.divide(nir - swir2, denominator, out=nbr, where=valid)

    acquisition_months = np.asarray(
        [
            (current.year, current.month)
            for current in (EPOCH + timedelta(days=int(value)) for value in dates)
        ]
    )

    outarray[:] = nodata
    for output_index, (year, month) in enumerate(_calendar_months(dates)):
        month_mask = (
            (acquisition_months[:, 0] == year)
            & (acquisition_months[:, 1] == month)
            & np.isfinite(nbr)
        )
        if not np.any(month_mask):
            continue

        median = np.median(nbr[month_mask])
        # Earth Engine's multiply(1000).toInt16() truncates toward zero.
        outarray[output_index] = np.int16(np.trunc(median * OUTPUT_SCALE))


def forcepy_chunk(inarray, outarray, dates, sensors, bandnames, nodata, nproc):
    """Calculate monthly median NBR for an entire FORCE processing chunk.

    This is the production entry point. It replaces millions of Python pixel
    calls with NumPy operations over [rows, columns]. Only one temporary stack
    for the currently processed month is allocated.
    """
    nir_index = _band_index(bandnames, "BROADNIR")
    swir2_index = _band_index(bandnames, "SWIR2")

    # These are zero-copy views into FORCE's input array.
    nir = inarray[:, nir_index, :, :]
    swir2 = inarray[:, swir2_index, :, :]
    months = _calendar_months(dates)
    acquisition_months = np.asarray(
        [
            (current.year, current.month)
            for current in (EPOCH + timedelta(days=int(value)) for value in dates)
        ]
    )

    outarray[:] = nodata
    for output_index, (year, month) in enumerate(months):
        date_indices = np.flatnonzero(
            (acquisition_months[:, 0] == year)
            & (acquisition_months[:, 1] == month)
        )
        if date_indices.size == 0:
            continue

        # Allocate only the observations needed for this month. With a 6000 m
        # chunk at 10 m resolution, each float32 observation is about 1.4 MiB.
        monthly_nbr = np.empty(
            (date_indices.size, inarray.shape[2], inarray.shape[3]),
            dtype=np.float32,
        )

        for month_position, date_index in enumerate(date_indices):
            nir_observation = nir[date_index]
            swir2_observation = swir2[date_index]
            nbr_observation = monthly_nbr[month_position]

            np.subtract(
                nir_observation,
                swir2_observation,
                out=nbr_observation,
                casting="unsafe",
            )
            denominator = np.add(
                nir_observation,
                swir2_observation,
                dtype=np.float32,
            )
            valid = (
                (nir_observation != nodata)
                & (swir2_observation != nodata)
                & (denominator != 0)
            )
            np.divide(
                nbr_observation,
                denominator,
                out=nbr_observation,
                where=valid,
            )
            nbr_observation[~valid] = np.nan

        # Suppress only the expected warning for pixels that have no valid
        # observation during this month; these remain nodata in the output.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="All-NaN slice encountered")
            median = np.nanmedian(monthly_nbr, axis=0)
        valid_output = np.isfinite(median)
        median *= OUTPUT_SCALE
        np.trunc(median, out=median)
        outarray[output_index, valid_output] = median[valid_output].astype(np.int16)
