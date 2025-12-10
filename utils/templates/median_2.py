import numpy as np

def forcepy_init(dates, sensors, bandnames):
    return [bn.decode("utf-8") + "_median" for bn in bandnames]


def forcepy_pixel(inarray, outarray, dates, sensors, bandnames, nodata, nproc):
    """
    This UDF calculates the median for every Band over the period defined in the parameter file.
    Output is one raster image per tile.
    inarray shape: [nDates, nBands, 1, 1]
    outarray shape: [nBands]
    """

    # auf Form [nDates, nBands] reduzieren
    vals = inarray[:, :, 0, 0].astype(np.float32)

    # nodata → NaN
    vals[vals == nodata] = np.nan

    # median je band
    med = np.nanmedian(vals, axis=0)   # → [nBands]

    # schreiben
    outarray[:] = np.round(med)
    outarray[np.isnan(med)] = nodata
