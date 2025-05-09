# Useful tools

## 1- Transit observability predictions

In this section we present a tool to predict whether the next transits of your favorite exoplanet will be observable from ome of the SPECULOOS site

Only a few basic information are needed:

* Site name, ex: `obs_name = 'SSO'`

* Planet name, ex: `name = TRAPPIST-1b`

* Right ascension, ex: `ra = 346.622384`  

* Declinaison, ex: `dec = -5.041398`

* Timing (in BJD_TDB), ex: `timing = 2457322.51505`

* Period (in days), ex: `period = 1.51088212`

* Transit duration (in days), ex: `duration = 0.02511108`

* Date to start prediction, ex start_date = `'2020-06-01 00:00:00'`

* Number of next transits from this atart date, ex: `ntr = 4`


Note that this tools is not suposed to be very precise as errors on timing, period and duration are **NOT** taken into account. 


```python
import SPOCK.short_term_scheduler as SPOCKST

SPOCKST.prediction(name='TRAPPIST-1b',ra=346.,dec=-5.05,
                   timing=2457322.51505,
                   period=1.51088212,duration=0.02511108,
                   start_date='2020-10-01 00:00:00',ntr=4)
```

## 2- Get info on a target from SPECULOOS target list

If you want to check rapidly the stellar properties, GAIA ID, its priority, its completion etc of a SPECULOOS `target`, you can use the following function:


```python
import SPOCK.stats as SPOCKstats

SPOCKstats.info_on_Sp_target(target = 'Sp0439-3235')
```

## 3- Get info on scheduled night blocks

Here we propose a function to check which targets have been scheduled on the SPECULOOS telescopes by displaying its corresponding <span style="background-color:lightyellow"><font color='orangered'> **night_blocks** </font></span>. The user will onyly have to precise the `date` and the `telescope`.


```python
import SPOCK.stats as SPOCKstats

SPOCKstats.read_night_plans_server(telescope = 'Io',date = '2020-10-12')


```

## 4- Compute exposure time 


```python
import SPOCK.ETC as ETC

# ------- test  ETC

a = (ETC.etc(mag_val= 11.89 , mag_band='J', spt='M2',filt='z',  airmass=1.3, moonphase=0.5, irtf=0.8, num_tel=1, seeing=1.5, gain=1.1))#airmass=1.1, moonphase=0.5, irtf=0.8, num_tel=1, seeing=2., gain=1.1))
texp = a.exp_time_calculator(ADUpeak=50000)[0]

print(texp)

```

    [32mINFO: [30m Please add password.csv file in: /Users/ed268546/elsenv/lib/python3.8/site-packages/SPOCK/credentials/
    [32mINFO: [30m OK Password file exists
    [32mINFO: [30mLatest target list already updated.
    [32mINFO: [30mTarget list already in good format
    121.84420605637354



```python
import SPOCK.mphot as mphot
from SPOCK import path_spock
import numpy as np

Teff_target = 3072 #K
dist_target = 100 #pc
filt_andor = 'I+z'

# example files used to generate SR
efficiencyFile2 = path_spock + '/SPOCK/files_ETC/SPIRIT/datafiles/systems/pirtSPC_-60.csv'
filterFile2 = path_spock + '/SPOCK/files_ETC/SPIRIT/datafiles/filters/zYJ.csv'

# name to refer to the generated file
name2 = efficiencyFile2.split('/')[-1][:-4] + '_' + filterFile2.split('/')[-1][:-4]

# generates a SR, saved locally as 'name1_instrumentSR.csv'
SRFile2 = path_spock + '/SPOCK/files_ETC/SPIRIT/datafiles/SRs/' + name2 + '_instrumentSR.csv'
mphot.generateSR(efficiencyFile2, filterFile2, SRFile2)
props_sky = {
    "pwv": 2.5,  # PWV [mm]
    "airmass": 1.1,  # Airmass
    "seeing": 1.2  # Seeing/FWHM ["]
}
props_callisto = {
    "name": name2,
    "plate_scale": 0.35 * (12 / 13.5),
    "N_dc": 230,
    "N_rn": 80,
    "well_depth": 55000,
    "bias_level": 0,
    "well_fill": 0.7,
    "read_time": 0.1,
    "r0": 0.5,
    "r1": 0.14,
    "ap_rad": 3
}

# example files used to generate spectral response (SR)
efficiencyFile1 = path_spock + '/SPOCK/files_ETC/SPIRIT/datafiles/systems/andorSPC_-60.csv' # in microns, fractional efficiency
filterFile1 = path_spock + '/SPOCK/files_ETC/SPIRIT/datafiles/filters/'+filt_andor+'.csv'

# name to refer to the generated file
name1 = efficiencyFile1.split('/')[-1][:-4] + '_' + filterFile1.split('/')[-1][:-4]

# generates a SR, saved locally as 'name1_instrumentSR.csv'
SRFile1 = path_spock + '/SPOCK/files_ETC/SPIRIT/datafiles/SRs/' + name1 + '_instrumentSR.csv'
mphot.generateSR(efficiencyFile1, filterFile1, SRFile1)

props_telescope1 = {
    "name" : name1, # name to get SR/precision grid from file
    "plate_scale" : 0.35, # pixel plate scale ["]
    "N_dc" : 0.2, # dark current [e/pix/s]
    "N_rn" : 6.328, # read noise [e_rms/pix]
    "well_depth" : 64000, # well depth [e/pix]
    "bias_level" : 0, # bias level [e/pix] - not really needed if well depth ignores bias level
    "well_fill" : 0.7, # fractional value to fill central target pixel, assuming gaussian (width function of seeing^)
    "read_time" : 10.5, # read time between images [s]
    "r0" : 0.5, # radius of telescope's primary mirror [m]
    "r1" : 0.14, # radius of telescope's secondary mirror [m]
    "ap_rad" : 3 # aperture radius [FWHM] -- 3 default == 7 sigma of Gaussian ~ aperture 6 on Cambridge pipeline/Portal
}

andor = mphot.get_precision(props_telescope1, props_sky, Teff=Teff_target, distance=dist_target, override=False, mapping=True)


#--- SPIRIT------

props_telescope2 = {
    "name" : name2,
    "plate_scale" : 0.35 * (12/13.5),
    "N_dc" : 230,
    "N_rn" : 80,
    "well_depth" : 55000,
    "bias_level" : 0,
    "well_fill" : 0.7,
    "read_time" : 0.1,
    "r0" : 0.5,
    "r1" : 0.14,
    "ap_rad" : 3
}

spirit = mphot.get_precision(props_telescope2, props_sky, Teff_target, dist_target, override=False, mapping=True)


print("texp ANDOR : ", andor['components']['t [s]'][0])
print("texp SPIRIT : ", spirit['components']['t [s]'][0])
```

    /Users/ed268546/Documents/codes/SPOCK/SPOCK/files_ETC/SPIRIT/datafiles/SRs/pirtSPC_-60_zYJ_instrumentSR.csv has been saved!
    /Users/ed268546/Documents/codes/SPOCK/SPOCK/files_ETC/SPIRIT/datafiles/SRs/andorSPC_-60_I+z_instrumentSR.csv has been saved!
    texp ANDOR :  120
    texp SPIRIT :  46.49716726740656



```python

```
