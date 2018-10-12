#!/usr/bin/env python
# Copyright 2018 ARC Centre of Excellence for Climate Extremes
# author: Scott Wales <scott.wales@unimelb.edu.au>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import print_function

from coecms.dimension import identify_lat_lon, identify_time
from coecms.grid import LonLatGrid

import dask.array
import mule
import numpy
import re
import xarray


def global_grid(resolution, field='T', endgame=None):
    """Get a global UM grid

    Args:
        resolution (str): Grid resolution (e.g. 'N96e')
        field (str): Field type ('T', 'U' or 'V')
        endgame (bool): Endgame grid (by default true if resolution ends with 'e')

    Returns:
        :obj:`coecms.grid.Grid` describing the given grid
    """

    if field not in ['T','U','V']:
        raise Exception("Invalid field type '%s'"%field)

    m = re.match(r'n(?P<res>\d+)(?P<end>e)?', resolution)
    if not m:
        raise Exception("Invalid resolution '%s'"%resolution)

    n = int(m.group('res'))

    if m.group('end'):
        endgame = True

    if endgame:
        nx = n * 2
        ny = n / 2 * 3

        dx = 360.0 / (nx)
        dy = 180.0 / (ny)

        # Default is 'T' field
        x0 = dx/2.0
        y0 = -90.0+dy/2.0
        
        if field == 'U':
            x0 = 0.0

        if field == 'V':
            ny += 1
            y0 = -90.0

        lon = x0 + numpy.arange(nx) * dx
        lat = y0 + numpy.arange(ny) * dy

    else:
        raise NotImplemented("ND Grids not implemented")

    return LonLatGrid(lats=lat, lons=lon)


def create_surface_ancillary(input_ds, stash_map):
    """Create a surface-level UM ancillary file

    Args:
        input_ds: Source dataset/dataarray
        output_filename: UM ancillary file to create
        stash_map: Mapping of variable name from `input_ds` to STASH code

    Returns:
        :obj:`mule.AncilFile` containing ancillary file data, write out with
        ``.to_file()``

    Example:
        ::

            input_ds = xarray.open_mfdataset(files, engine='pynio')
            stash_map = {'CI_GDS0_SFC': 31, 'SSTK_GDS0_SFC': 507,}

            ancil = create_um_surface_ancillary(input_ds, stash_map)
            ancil.to_file('sstice.ancil')

    Todo:
        * Assumes Gregorian calendar
        * Assumes sub-daily frequency
        * Does not compress output
    """

    time = identify_time(input_ds)
    lat, lon = identify_lat_lon(input_ds)

    tstep = (time[1] - time[0]) / numpy.timedelta64(1, 's')

    template = {
        'fixed_length_header': {
            'sub_model': 1,         # Atmosphere
            'dataset_type': 4,      # Ancillary
            'horiz_grid_type': 0,   # Global
            'calendar': 1,          # Gregorian
            'grid_staggering': 6,   # EndGame
            'time_type': 1,         # Time series
            'model_version': 1006,  # UM 10.6
            # Start time
            't1_year': time.dt.year.values[0],
            't1_month': time.dt.month.values[0],
            't1_day': time.dt.day.values[0],
            't1_hour': time.dt.hour.values[0],
            't1_minute': time.dt.minute.values[0],
            't1_second': time.dt.second.values[0],
            # End time
            't2_year': time.dt.year.values[-1],
            't2_month': time.dt.month.values[-1],
            't2_day': time.dt.day.values[-1],
            't2_hour': time.dt.hour.values[-1],
            't2_minute': time.dt.minute.values[-1],
            't2_second': time.dt.second.values[-1],
            # Frequency (must be sub-daily)
            't3_year': 0,
            't3_month': 0,
            't3_day': 0,
            't3_hour': tstep / 3600,
            't3_minute': tstep % 3600 / 60,
            't3_second': tstep % 60,
        },
        'integer_constants': {
            'num_times': time.size,
            'num_cols': lon.size,
            'num_rows': lat.size,
            'num_levels': 1,
            'num_field_types': len(stash_map),
        },
        'real_constants': {
            'start_lat': lat.values[0],# + (lat.values[1] - lat.values[0])/2.0,
            'row_spacing': lat.values[1] - lat.values[0],
            'start_lon': lon.values[0],# + (lon.values[1] - lon.values[0])/2.0,
            'col_spacing': lon.values[1] - lon.values[0],
            'north_pole_lat': 90,
            'north_pole_lon': 0,
        },
    }

    ancil = mule.AncilFile.from_template(template)

    # UM Missing data magic value
    MDI = -1073741824.0

    for var, stash in stash_map.items():
        # Mask out with MDI
        #var_data = input_ds[var].filled(MDI)

        for t in input_ds[var][time.name]:
            print(var, t.data)
            field = mule.Field3.empty()

            field.lbyr = t.dt.year.values
            field.lbmon = t.dt.month.values
            field.lbdat = t.dt.day.values
            field.lbhr = t.dt.hour.values
            field.lbmin = t.dt.minute.values
            field.lbsec = t.dt.second.values

            field.lbtime = 1        # Instantaneous Gregorian calendar
            field.lbcode = 1        # Regular Lat-Lon grid
            field.lbhem = 0         # Global

            field.lbrow = ancil.integer_constants.num_rows
            field.lbnpt = ancil.integer_constants.num_cols

            field.lbpack = 0        # No packing
            field.lbrel = 3         # UM 8.1 or later
            field.lbvc = 129        # Surface field

            field.lbuser1 = 1       # Real data
            field.lbuser4 = stash   # STASH code
            field.lbuser7 = 1       # Atmosphere model

            field.bplat = ancil.real_constants.north_pole_lat
            field.bplon = ancil.real_constants.north_pole_lon

            field.bdx = ancil.real_constants.col_spacing
            field.bdy = ancil.real_constants.row_spacing
            field.bzx = ancil.real_constants.start_lon - field.bdx
            field.bzy = ancil.real_constants.start_lat - field.bdy

            field.bmdi = MDI
            field.bmks = 1.0

            data = input_ds[var].sel({time.name: t}).data
            masked_data = dask.array.ma.filled(input_ds[var].sel({time.name: t}).data, MDI)

            field.set_data_provider(FastDataProvider(masked_data))

            ancil.fields.append(field)

    return ancil


class FastDataProvider():
    """Faster version of mule.ArrayDataProvider
    
    Doesn't convert to a numpy array, so works with dask fields
    """
    def __init__(self, array):
        if len(array.shape) != 2:
            raise Exception

        self._array = array

    def _data_array(self):
        return self._array.compute()


def sstice_erai(begindate, enddate, frequency, um_grid):
    """Returns a :obj:`mule.AncilFile` with ERA-Interim SST and ice fields

    Args:
        begindate (:obj:`datetime.date`): Initial date
        enddate (:obj:`datetime.date`): Final date
        frequency (:obj:`datetime.timedelta`): Update frequency
        um_grid (:obj:`coecms.grid.LonLatGrid`): UM Grid

    Returns:
        :obj:`mule.AncilFile` containing the ERA-Interim fields for the time period interpolated to `grid`

    Example:
        ::
        
            import coecms.um as um
            ancil = um.sstice_erai('20110906', '20110908', '12H', um.global_grid('n96e'))
            ancil.to_file('sstice.ancil')
    """
    from coecms.datasets import erai
    from coecms.regrid import Regridder, esmf_generate_weights

    # Grab the data at the correct times from ERA-Interim 
    data = erai('oper_an_sfc').sel(time=slice(begindate, enddate)).resample(time=frequency).asfreq()

    # Regrid to the target UM resolution
    data['tos'].encoding['_FillValue'] = -9999
    w = esmf_generate_weights(data, um_grid, source_mask='tos')
    r = Regridder(weights=w)

    ds_um = xarray.Dataset()
    ds_um['sic'] = r.regrid(data.sic)
    ds_um['tos'] = r.regrid(data.tos)

    # Convert to UM format
    ancil = create_surface_ancillary(ds_um, {'tos': 507, 'sic': 31})

    return ancil


def sstice_era5(begindate, enddate, frequency, grid):
    """Returns a :obj:`mule.AncilFile` with ERA5 SST and ice fields

    Args:
        begindate (:obj:`datetime.date`): Initial date
        enddate (:obj:`datetime.date`): Final date
        frequency (:obj:`datetime.timedelta`): Update frequency
        grid (:obj:`coecms.grid.LonLatGrid`): UM Grid

    Returns:
        :obj:`mule.AncilFile` containing the ERA5 fields for the time period interpolated to `grid`
    """
    raise NotImplemented