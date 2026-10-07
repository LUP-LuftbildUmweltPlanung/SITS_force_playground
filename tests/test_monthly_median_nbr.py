from datetime import date
import unittest

import numpy as np

from utils.templates.monthly_median_nbr import (
    forcepy_chunk,
    forcepy_init,
    forcepy_pixel,
)


EPOCH = date(1970, 1, 1)
NODATA = -9999


def _days(value):
    return (date.fromisoformat(value) - EPOCH).days


class MonthlyMedianNbrTest(unittest.TestCase):
    def test_groups_dates_and_ignores_nodata(self):
        dates = np.array(
            [_days("2025-01-05"), _days("2025-01-20"), _days("2025-02-10")]
        )
        bandnames = np.array([b"BROADNIR", b"SWIR2"])
        inarray = np.array(
            [
                [[[8000]], [[2000]]],  # NBR = 0.6
                [[[6000]], [[4000]]],  # NBR = 0.2
                [[[NODATA]], [[3000]]],
            ],
            dtype=np.int16,
        )
        outarray = np.full(12, NODATA, dtype=np.int16)

        self.assertEqual(
            forcepy_init(dates, np.array([b"SEN2A"] * 3), bandnames),
            [f"2025{month:02d}_NBR_MEDIAN" for month in range(1, 13)],
        )

        forcepy_pixel(
            inarray,
            outarray,
            dates,
            np.array([b"SEN2A"] * 3),
            bandnames,
            NODATA,
            1,
        )

        self.assertEqual(outarray.tolist(), [400, NODATA] + [NODATA] * 10)

    def test_chunk_matches_pixel_results(self):
        dates = np.array(
            [_days("2025-01-05"), _days("2025-01-20"), _days("2025-02-10")]
        )
        bandnames = np.array([b"BROADNIR", b"SWIR2"])
        # Two pixels: January has medians 0.4 and -0.4; February is valid only
        # for the second pixel.
        inarray = np.array(
            [
                [[[8000, 2000]], [[2000, 8000]]],
                [[[6000, 4000]], [[4000, 6000]]],
                [[[NODATA, 9000]], [[3000, 1000]]],
            ],
            dtype=np.int16,
        )
        outarray = np.full((12, 1, 2), NODATA, dtype=np.int16)

        forcepy_chunk(
            inarray,
            outarray,
            dates,
            np.array([b"SEN2A"] * 3),
            bandnames,
            NODATA,
            1,
        )

        self.assertEqual(
            outarray.tolist(),
            [[[400, -400]], [[NODATA, 800]]] + [[[NODATA, NODATA]]] * 10,
        )

    def test_missing_january_keeps_february_in_second_band(self):
        dates = np.array([_days("2025-02-10"), _days("2025-03-10")])
        bandnames = np.array([b"BROADNIR", b"SWIR2"])
        inarray = np.array(
            [
                [[[8000]], [[2000]]],
                [[[6000]], [[4000]]],
            ],
            dtype=np.int16,
        )
        outarray = np.full((12, 1, 1), NODATA, dtype=np.int16)

        forcepy_chunk(inarray, outarray, dates, None, bandnames, NODATA, 1)

        self.assertEqual(outarray[:, 0, 0].tolist(), [NODATA, 600, 200] + [NODATA] * 9)

    def test_rejects_missing_required_band(self):
        dates = np.array([_days("2025-01-05")])
        inarray = np.array([[[[8000]]]], dtype=np.int16)
        outarray = np.full(1, NODATA, dtype=np.int16)

        with self.assertRaisesRegex(ValueError, "SWIR2"):
            forcepy_pixel(
                inarray,
                outarray,
                dates,
                np.array([b"SEN2A"]),
                np.array([b"BROADNIR"]),
                NODATA,
                1,
            )


if __name__ == "__main__":
    unittest.main()
