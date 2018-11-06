#!/usr/bin/env python

from __future__ import print_function

import sys
import xarray as xr
import netCDF4 as nc
from coecms.split_var import splitbyvar

testfile = 'test/data/ocean_scalar.nc'

verbose = True

def setup_module(module):
    if verbose: print ("setup_module      module:%s" % module.__name__)
    if verbose: print ("Python version: {}".format(sys.version))
    # Put any setup code in here, like making temporary files
    # Make 5 years of a noleap calendar on the first of each month
 
def teardown_module(module):
    if verbose: print ("teardown_module   module:%s" % module.__name__)
    # Put any taerdown code in here, like deleting temporary files


def test_splitbyvariable():

    # ds = xr.open_dataset(testfile,decode_times=False)
    ds = xr.open_dataset(testfile)
    # ds['time'] = nc.num2date(ds.time, 'days since 1678-01-01 00:00:00', 'noleap')

    # ds2 = ds['temp_global_ave']

    i = 0
    for var in splitbyvar(ds):
        print(var.name)

    for var in splitbyvar(ds,['salt_global_ave','temp_global_ave']):
        print(var)
        var.to_netcdf(path=var.name+'.nc',format="NETCDF4_CLASSIC")
        # for varbytime in splitbytime(var,'24MS'):
        #     i += 1
        #     fname = "{}_{}.nc".format(var.name,i)
        #     print(varbytime.shape,fname)
        #     writevar(var,fname)