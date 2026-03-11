import numpy as np

def forcepy_init(dates, sensors, bandnames):
    # calculate for all bands or specified bands only
    #desired_bands = [0, 1, 2, 7]  # Beispiel: Band 1, 3 und 5 auswählen (0-indexiert)
    #return [bandnames[i].decode("utf-8") + "_median" for i in desired_bands]
    return [bn.decode("utf-8") + "_median" for bn in bandnames]


def forcepy_pixel(inarray, outarray, dates, sensors, bandnames, nodata, nproc):
    """
    This UDF calculates the median for every Band over the period defined in the parameter file.
    Output is one raster image per tile.
    inarray shape: [nDates, nBands, 1, 1]
    outarray shape: [nBands]
    """

    # calculate for all bands or specified bands only
    #desired_bands = [0, 1, 2, 7]
    #vals = inarray[:, desired_bands, 0, 0].astype(np.float32)
    vals = inarray[:, :, 0, 0].astype(np.float32)

    # nodata → NaN
    vals[vals == nodata] = np.nan

    # calculate median
    med = np.nanmedian(vals, axis=0)   # → [nBands]

    # wrie output array
    outarray[:] = np.round(med)
    outarray[np.isnan(med)] = nodata
