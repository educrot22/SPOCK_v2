#!/usr/bin/python
import os
import shutil
from astropy.table import Table
from astroplan import Observer, FixedTarget
#from astropy.time import Time
from astropy.time import Time, TimeDelta
from astroplan import Observer, FixedTarget, AltitudeConstraint, AtNightConstraint, AirmassConstraint, MoonSeparationConstraint, ObservingBlock, TimeConstraint, is_always_observable, is_observable  


from colorama import Fore
from .txt_files import startup, startup_no_flats, Path_txt_files, flatexo_gany, flatexo_io, \
    flatexo_euro, first_target_offset, flatexo_artemis_morning, flatexo_artemis_evening, startup_artemis, \
    flatexo_saintex
from .txt_files import first_target, target, flatdawn, biasdark, shutdown, flatexo_calli, \
    flatdawn_no_flats, target_no_DONUTS, target_offset, biasdark_comete, flatdawn_artemis, haumea
from astropy.coordinates import SkyCoord, get_sun, AltAz, EarthLocation, Angle, Latitude, Longitude 
from astropy import units as u
import pandas as pd
import numpy as np
import ast
from SPOCK import path_spock

pd.set_option('display.max_columns', 50)

# initialisation
index = {}
ra1 = {}
dec1 = {}
ra2 = {}
dec2 = {}
ra3 = {}
dec3 = {}


def offset_target_position(day_start, nb_days, telescope, ra_offset, dec_offset):
    """
    date = "YYYY-MM-DD"
    """
    dt = Time('2018-01-02 00:00:00', scale='tcg') - Time('2018-01-01 00:00:00', scale='tcg')  # 1 day
    day_start = Time(day_start)
    for nb_day in range(0, nb_days):
        date = Time(day_start + nb_day*dt, scale='utc', out_subfmt='date').tt.datetime.strftime("%Y-%m-%d")
        scheduler_table = Table.read(path_spock + '/DATABASE/' + str(telescope) + '/Archive_night_blocks' +
                                        '/night_blocks_' + str(telescope) + '_' + str(date) + '.txt', format='ascii')
        for i in range(len(scheduler_table)):
            coord = SkyCoord(
                str(int(scheduler_table['ra (h)'][i])) + ":" + str(int(scheduler_table['ra (m)'][i])) + ":" + str(
                    int(scheduler_table['ra (s)'][i]))
                             + " " +
                             str(int(scheduler_table['dec (d)'][i])) + ":" + str(abs(int(scheduler_table['dec (m)'][i]))) + ":" + str(
                    abs(int(scheduler_table['dec (s)'][i])))
                            , unit=(u.hourangle, u.deg))
            
            new_c = SkyCoord(ra=coord.ra.to(u.deg) + ra_offset/3600*u.deg,
                             dec=coord.dec.to(u.deg) + dec_offset/3600*u.deg, unit="deg")
            scheduler_table['ra (h)'][i] = new_c.ra.hms[0]
            scheduler_table['ra (m)'][i] = new_c.ra.hms[1]
            scheduler_table['ra (s)'][i] = new_c.ra.hms[2]
            scheduler_table['dec (d)'][i] = new_c.dec.dms[0]
            scheduler_table['dec (m)'][i] = new_c.dec.dms[1]
            scheduler_table['dec (s)'][i] = new_c.dec.dms[2]

        scheduler_table.write(path_spock + '/DATABASE/'+ telescope + '/Archive_night_blocks/' + 'night_blocks_' + telescope + '_' + str(date) + '.txt', format='ascii', overwrite=True)  
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + "Offset has been applied to targets on " + str(telescope)+ " on the "+ str(date)) 

def make_scheduled_table(telescope, day_of_night):
    Path = path_spock + '/DATABASE'
    scheduled_table = None
    day_of_night = Time(day_of_night)
    try:
        os.path.exists(os.path.join(Path, telescope, 'Archive_night_blocks',
                                    'night_blocks_' + telescope + '_' + day_of_night.tt.datetime[0].strftime(
                                        "%Y-%m-%d") + '.txt'))
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Path exists and is: ',
              os.path.join(Path, telescope, 'night_blocks_' + telescope + '_' +
                           day_of_night.tt.datetime[0].strftime("%Y-%m-%d") + '.txt'))
    except TypeError:
        os.path.exists(os.path.join(Path, telescope, 'Archive_night_blocks',
                                    'night_blocks_' + telescope + '_' + day_of_night.tt.datetime.strftime(
                                        "%Y-%m-%d") + '.txt'))
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Path exists and is: ', os.path.join(Path, telescope,
                                                                                         'night_blocks_' + telescope + '_' + day_of_night.tt.datetime.strftime(
                                                                                             "%Y-%m-%d") + '.txt'))
    except NameError:
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no input night_block for this day')
    except FileNotFoundError:
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no input night_block for this day')

    if not (scheduled_table is None):
        return scheduled_table
    else:
        try:
            scheduled_table = Table.read(os.path.join(Path, telescope, 'Archive_night_blocks',
                                                      'night_blocks_' + telescope + '_' +
                                                      day_of_night.tt.datetime[0].strftime(
                                                          "%Y-%m-%d") + '.txt'), format='ascii')
            return scheduled_table
        except TypeError:
            scheduled_table = Table.read(os.path.join(Path, telescope, 'Archive_night_blocks',
                                                      'night_blocks_' + telescope + '_' +
                                                      day_of_night.tt.datetime.strftime("%Y-%m-%d") + '.txt'),
                                         format='ascii')
            return scheduled_table


def dome_rotation(day_of_night, telescope):
    scheduled_table = make_scheduled_table(telescope, day_of_night)
    location = EarthLocation.from_geodetic(-70.40300000000002 * u.deg, -24.625199999999996 * u.deg,
                                           2635.0000000009704 * u.m)
    paranal = Observer(location=location, name="paranal", timezone="UTC")
    dur_dome_rotation = 2 / 60 / 24  # 5min
    number_of_targets = len(scheduled_table['target'])

    if number_of_targets == 1:
        old_end_time = scheduled_table['end time (UTC)'][0]

        start_dome_rot = Time((Time(scheduled_table['start time (UTC)'][0], format='iso').jd +
                               Time(scheduled_table['end time (UTC)'][0], format='iso').jd) / 2, format='jd')

        end_dome_rot = Time(start_dome_rot.jd + dur_dome_rotation, format='jd')

        dur_first_block = Time(start_dome_rot.jd - Time(scheduled_table['start time (UTC)'][0],
                                                        format='iso').jd, format='jd').jd
        dur_second_block = Time(Time(old_end_time).jd - end_dome_rot.jd, format='jd').jd

        coords = SkyCoord(str(int(scheduled_table['ra (h)'][0])) + 'h' + str(
            int(scheduled_table['ra (m)'][0])) + 'm' + str(
            round(scheduled_table['ra (s)'][0], 3)) + 's' + \
                          ' ' + str(int(scheduled_table['dec (d)'][0])) + 'd' + str(
            abs(int(scheduled_table['dec (m)'][0]))) + \
                          'm' + str(abs(round(scheduled_table['dec (s)'][0], 3))) + 's').transform_to(
            AltAz(obstime=start_dome_rot, location=paranal.location))
        coords_dome_rotation = SkyCoord(alt=coords.alt, az=(coords.az.value - 180) * u.deg, obstime=start_dome_rot,
                                        frame='altaz', location=paranal.location)
        if coords.alt.value < 50:
            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK +
                  'dome rotation not possible at that time because of altitude constraint, adding 20 degrees altitude')
            coords_dome_rotation = SkyCoord(alt=coords.alt + 20 * u.deg, az=(coords.az.value - 180) * u.deg,
                                            obstime=start_dome_rot, frame='altaz', location=paranal.location)

        target = FixedTarget(coord=SkyCoord(ra=coords_dome_rotation.icrs.ra.value * u.degree,
                                            dec=coords_dome_rotation.icrs.dec.value * u.degree),
                             name='dome_rot')

        if (telescope == "Callisto"):
            scheduled_table.add_row([target.name, start_dome_rot.iso, end_dome_rot.iso,
                                     dur_dome_rotation * 24 * 60,
                                     target.coord.ra.hms[0],
                                     target.coord.ra.hms[1], target.coord.ra.hms[2],
                                     target.coord.dec.dms[0], target.coord.dec.dms[1],
                                     target.coord.dec.dms[2], "{'filt':'zYJ', 'texp':'10'}"])
        else:
            scheduled_table.add_row([target.name, start_dome_rot.iso, end_dome_rot.iso,
                                     dur_dome_rotation * 24 * 60,
                                     target.coord.ra.hms[0],
                                     target.coord.ra.hms[1], target.coord.ra.hms[2],
                                     target.coord.dec.dms[0], target.coord.dec.dms[1],
                                     target.coord.dec.dms[2], "{'filt':'I+z', 'texp':'10'}"])

        scheduled_table['end time (UTC)'][0] = start_dome_rot.iso
        scheduled_table['duration (minutes)'][0] = dur_first_block * 24 * 60

        scheduled_table.add_row([scheduled_table['target'][0], end_dome_rot.iso, old_end_time,
                                 dur_second_block * 24 * 60,
                                 scheduled_table['ra (h)'][0],
                                 scheduled_table['ra (m)'][0], scheduled_table['ra (s)'][0],
                                 scheduled_table['dec (d)'][0], scheduled_table['dec (m)'][0],
                                 scheduled_table['dec (s)'][0], scheduled_table['configuration'][0]])

        df = scheduled_table.to_pandas()
        df['target'][2] = df['target'][2] + '_2'

        scheduled_table = Table.from_pandas(df)
        scheduled_table.sort('start time (UTC)')

    if number_of_targets > 1:
        start_dome_rot = Time(scheduled_table['end time (UTC)'][0], format='iso')

        end_dome_rot = Time(start_dome_rot.jd + dur_dome_rotation, format='jd')

        coords = SkyCoord(str(int(scheduled_table['ra (h)'][0])) + 'h' + str(
            int(scheduled_table['ra (m)'][0])) + 'm' + str(
            round(scheduled_table['ra (s)'][0], 3)) + 's' + \
                          ' ' + str(int(scheduled_table['dec (d)'][0])) + 'd' + str(
            abs(int(scheduled_table['dec (m)'][0]))) + \
                          'm' + str(abs(round(scheduled_table['dec (s)'][0], 3))) + 's').transform_to(
            AltAz(obstime=start_dome_rot, location=paranal.location))
        coords_dome_rotation = SkyCoord(alt=coords.alt, az=(coords.az.value - 180) * u.deg, obstime=start_dome_rot,
                                        frame='altaz', location=paranal.location)
        if coords.alt.value < 50:
            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK +
                  ' not possible at that time because of altitude constraint, adding 20 degrees altitude')
            coords_dome_rotation = SkyCoord(alt=coords.alt + 20 * u.deg, az=(coords.az.value - 180) * u.deg,
                                            obstime=start_dome_rot, frame='altaz', location=paranal.location)

        target = FixedTarget(coord=SkyCoord(ra=coords_dome_rotation.icrs.ra.value * u.degree,
                                            dec=coords_dome_rotation.icrs.dec.value * u.degree),
                             name='dome_rot')

        if (telescope == "Callisto"):
            scheduled_table.add_row([target.name, start_dome_rot.iso, end_dome_rot.iso,
                                     dur_dome_rotation * 24 * 60,
                                     target.coord.ra.hms[0],
                                     target.coord.ra.hms[1], target.coord.ra.hms[2],
                                     target.coord.dec.dms[0], target.coord.dec.dms[1],
                                     target.coord.dec.dms[2], "{'filt':'zYJ', 'texp':'10'}"])
        else:
            scheduled_table.add_row([target.name, start_dome_rot.iso, end_dome_rot.iso,
                                     dur_dome_rotation * 24 * 60,
                                     target.coord.ra.hms[0],
                                     target.coord.ra.hms[1], target.coord.ra.hms[2],
                                     target.coord.dec.dms[0], target.coord.dec.dms[1],
                                     target.coord.dec.dms[2], "{'filt':'I+z', 'texp':'10'}"])

        scheduled_table['start time (UTC)'][1] = end_dome_rot.iso

        scheduled_table.sort('start time (UTC)')

    return scheduled_table


def make_np(t_now, nb_jours, tel):
    telescope = tel
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg') - Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    for nb_day in range(0, nb_jours):
        t_now = Time(t0 + nb_day * dt, scale='utc', out_subfmt='date').tt.datetime.strftime("%Y-%m-%d")
        Path = path_spock + '/DATABASE'
        p = os.path.join(Path, str(telescope), 'Plans_by_date', str(t_now))
        if not os.path.exists(p):
            os.makedirs(p)

        scheduler_table = Table.read(path_spock + '/DATABASE/' + str(telescope) + '/Archive_night_blocks' +
                                     '/night_blocks_' + str(telescope) + '_' + str(t_now) + '.txt', format='ascii')

        if (tel == 'Io') or tel == ('Europa') or (tel == 'Ganymede') or (tel == 'Callisto'):
            scheduler_table = dome_rotation(telescope=tel, day_of_night=t_now)  # Intentional dome rotation to
            # avoid technical pb on Callisto with dome

        name = scheduler_table['target']
        date_start = scheduler_table['start time (UTC)']
        date_end = scheduler_table['end time (UTC)']
        ra1 = scheduler_table['ra (h)']
        ra2 = scheduler_table['ra (m)']
        ra3 = scheduler_table['ra (s)']
        dec1 = scheduler_table['dec (d)']
        dec2 = scheduler_table['dec (m)']
        dec3 = scheduler_table['dec (s)']
        config = scheduler_table['configuration']
        filt = []
        texp = []

        scheduler_table.add_index('target')
        try:
            index_to_delete = scheduler_table.loc['TransitionBlock'].index
            scheduler_table.remove_row(index_to_delete)
        except KeyError:
            print()

        for i in range(0, len(scheduler_table)):
            if name[i] != 'TransitionBlock':
                conf = ast.literal_eval(config[i])
                filt.append(conf['filt'])
                texp.append(conf['texp'])
                if telescope != 'Artemis':
                    if filt[i] == 'z' or filt[i] == 'g' or filt[i] == 'g' or filt[i] == 'i' or filt[i] == 'r':
                        a = filt[i]
                        filt[i] = a + '\''

        if telescope == 'Artemis':
            autofocus = True
        else:
            autofocus = False
        waitlimit = 600
        afinterval = 60
        count = '5000'

        location = EarthLocation.from_geodetic(-70.40300000000002 * u.deg, -24.625199999999996 * u.deg,
                                               2635.0000000009704 * u.m)
        paranal = Observer(location=location, name="paranal", timezone="UTC")
        t = Time(t_now)
        sun_set = paranal.sun_set_time(t, which='next',horizon=-1*u.deg)
        sun_rise = paranal.sun_rise_time(t, which='next', horizon=-1*u.deg)
        location_SNO = EarthLocation.from_geodetic(-16.50583131 * u.deg, 28.2999988 * u.deg, 2390 * u.m)
        teide = Observer(location=location_SNO, name="SNO", timezone="UTC")
        sun_set_teide = teide.sun_set_time(t, which='next', horizon=-1*u.deg)
        sun_rise_teide = teide.sun_rise_time(t + 1, which='next', horizon=-1*u.deg)
        location_saintex = EarthLocation.from_geodetic(-115.48694444444445 * u.deg, 31.029166666666665 * u.deg,
                                                       2829.9999999997976 * u.m)
        san_pedro = Observer(location=location_saintex, name="saintex", timezone="UTC")
        sun_set_san_pedro = san_pedro.sun_set_time(t + 1, which='next', horizon=-1*u.deg)
        sun_rise_san_pedro = san_pedro.sun_rise_time(t + 1, which='next', horizon=-1*u.deg)

        Path = Path_txt_files(telescope)
        if telescope.find('Europa') != -1:
            startup(t_now, name[0], sun_set.iso, date_start[0], Path, telescope)
        if telescope.find('Ganymede') != -1:
            startup(t_now, name[0], sun_set.iso, date_start[0], Path, telescope)
        if telescope.find('Io') != -1:
            startup(t_now, name[0], sun_set.iso, date_start[0], Path, telescope)
        if telescope.find('Callisto') != -1:
            startup(t_now, name[0], sun_set.iso, date_start[0], Path, telescope)
        if telescope.find('Artemis') != -1:
            startup_artemis(t_now, name[0], sun_set_teide.iso, date_start[0], Path)
        if telescope.find('Saint-Ex') != -1:
            startup(t_now, name[0], sun_set_san_pedro.iso, date_start[0], Path, telescope)
        for i, nam in enumerate(name):
            if nam != 'TransitionBlock':
                if len(name) >= 2:
                    if i == 0:
                        first_target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                                     filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], name[i + 1],
                                     Path, telescope)
                    if i == 0 and telescope.find('Ganymede') != -1:
                        first_target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                                     filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], name[i + 1],
                                     Path, telescope)
                    if i == 0 and telescope.find('Artemis') != -1:
                        filt[i] = filt[i].replace('\'', '')
                        if nam == 'haumea':
                            haumea(t_now, date_start[i], date_end[i], count, filt='Exo', exptime=240,
                                   name_2=name[i + 1], binning=1, Path=Path, telescope='Artemis')
                        else:
                            first_target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus,
                                         count,
                                         filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i],
                                         name[i + 1],
                                         Path, telescope='Artemis')
                    if i == 0 and telescope.find('Saint-Ex') != -1:
                        first_target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                                     filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], name[i + 1],
                                     Path, telescope='Saint-Ex')

                    if i == (len(name) - 1) and telescope.find('Europa') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)
                    if i == (len(name) - 1) and telescope.find('Callisto') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)
                    if i == (len(name) - 1) and telescope.find('Io') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)
                    if i == (len(name) - 1) and telescope.find('Ganymede') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)

                    if i == (len(name) - 1) and telescope.find('Artemis') != -1:
                        filt[i] = filt[i].replace('\'', '')
                        if nam == 'haumea':
                            haumea(t_now, date_start[i], date_end[i], count, filt='Exo', exptime=240,
                                   name_2=None, binning=1, Path=Path, telescope='Artemis')
                        else:
                            target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                                   filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None,
                                   Path, telescope='Artemis')
                        flatdawn_artemis(t_now, date_end[i], sun_rise_teide.iso, Path)

                    if i == (len(name) - 1) and telescope.find('Saint-Ex') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path,
                               telescope='Saint-Ex')
                        flatdawn(t_now, date_end[i], sun_rise_san_pedro.iso, Path, telescope)

                    if (i > 0) and (i < (len(name) - 1)):
                        if nam == 'haumea':
                            haumea(t_now, date_start[i], date_end[i], count, filt='Exo', exptime=240,
                                   name_2=name[i + 1], binning=1, Path=Path, telescope='Artemis')
                        if telescope == "Artemis":
                            if filt[i] == "z\'":
                                filt[i] = filt[i].replace('\'', '')
                        else:
                            filt[i] = filt[i]

                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], name[i + 1], Path,
                               telescope=telescope)

                else:
                    if i == (len(name) - 1) and telescope.find('Europa') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)
                    if i == (len(name) - 1) and telescope.find('Callisto') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)
                    if i == (len(name) - 1) and telescope.find('Io') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)
                    if i == (len(name) - 1) and telescope.find('Ganymede') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count, filt[i],
                               texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], None, Path, telescope)
                        flatdawn(t_now, date_end[i], sun_rise.iso, Path, telescope)

                    if i == (len(name) - 1) and telescope.find('Artemis') != -1:
                        filt[i] = filt[i].replace('\'', '')
                        if nam == 'haumea':
                            haumea(t_now, date_start[i], date_end[i], count, filt='Exo', exptime=240,
                                   name_2=None, binning=1, Path=Path, telescope='Artemis')
                        else:
                            target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                                   filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i],
                                   None, Path, telescope=telescope)
                            flatdawn_artemis(t_now, date_end[i], sun_rise_teide.iso, Path)

                    if i == (len(name) - 1) and telescope.find('Saint-Ex') != -1:
                        target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                               filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i],
                               None, Path, telescope=telescope)
                        flatdawn(t_now, date_end[i], sun_rise_san_pedro.iso, Path, telescope)

                    if (i > 0) and (i < (len(name) - 1)):
                        if telescope == "Artemis":
                            filt[i] = filt[i].replace('\'', '')
                        else:
                            filt[i] = filt[i]
                        if nam == 'haumea':
                            haumea(t_now, date_start[i], date_end[i], count, filt='Exo', exptime=240,
                                   name_2=name[i + 1], binning=1, Path=Path, telescope='Artemis')
                        else:
                            target(t_now, nam, date_start[i], date_end[i], waitlimit, afinterval, autofocus, count,
                                   filt[i], texp[i], ra1[i], ra2[i], ra3[i], dec1[i], dec2[i], dec3[i], name[i + 1],
                                   Path, telescope=telescope)

        if telescope.find('Callisto') != -1:
            #filt.append("Clear")
            flatexo_calli(Path, t_now, filt)
        if telescope.find('Ganymede') != -1:
            flatexo_gany(Path, t_now, filt)
        if telescope.find('Io') != -1:
            flatexo_io(Path, t_now, filt)
        if telescope.find('Europa') != -1:
            flatexo_euro(Path, t_now, filt)
        if telescope.find('Artemis') != -1:
            flatexo_artemis_evening(Path, t_now, filt)
            flatexo_artemis_morning(Path, t_now, filt)
        if telescope.find('Saint-Ex') != -1:
            flatexo_saintex(Path, t_now, filt)

        if telescope.find('Saint-Ex') != -1:
            list_texps = [texp[i] for i in range(len(texp))]
            list_texps = list(dict.fromkeys(list_texps))
            biasdark(t_now, Path, telescope, texps=list_texps)

        elif telescope.find('Callisto') != -1 or telescope.find('Ganymede') != -1 or (
                telescope.find('Europa') != -1) or (telescope.find('Io') != -1) or \
                (telescope.find('Artemis') != -1):
            list_texps = [15., 30., 60., 120.] + [float(x) for x in texp]
            list_texps = np.unique(np.sort(list_texps))
            list_texps = [str(int(x)) for x in list_texps]
            list_texps = list(dict.fromkeys(list_texps))
            biasdark(t_now, Path, telescope, texps=list_texps)
            # if np.any(name == 'haumea'):
            #     biasdark(t_now, Path, telescope)

        p2 = os.path.join(path_spock + '/DATABASE', str(telescope), 'Zip_files', str(t_now))
        shutil.make_archive(p2, 'zip', p)


def getfullcloseSaintEx(day,num_filters = 1):
    longitude = "-115d27m17.15s"
    latitude = "+31d02m36.3s"
    elevation = 2778.4*u.meter
    location = EarthLocation.from_geodetic(longitude, latitude, elevation)
    observer = Observer(name="SAINT-EX",location=location)
        
    at_astro = observer.twilight_evening_astronomical(Time(day), which='nearest')    
    at_nau = observer.twilight_evening_nautical(time=day, which='nearest')    
    at_civil = observer.twilight_evening_civil(time=day, which='nearest')
    
    am_astro = observer.twilight_morning_astronomical(time=day, which='next')    
    am_nau = observer.twilight_morning_nautical(time=day, which='next')    
    am_civil = observer.twilight_morning_civil(time=day, which='next') 

    tleve_nau = observer.twilight_evening_nautical(time=day, which='nearest')
    tlmor_nau = observer.twilight_morning_nautical(day, which='next')
    sun_rise = observer.sun_rise_time(tlmor_nau, which="next") # Salida del Sol en días julianos /Sunrise in Julian days
    am_sun_rise = Time(sun_rise, format='datetime') # Salida del Sol en yy-mm-dd hr:min:seg / Sunrise in yy-mm-dd hr:min:sec



    sun_set = observer.sun_set_time(tlmor_nau, which="previous") # Puesta del Sol en días julianos /Sunset in Julian days
    at_sun_set = Time(sun_set, format='datetime') # Puesta del Sol en yy-mm-dd hr:min:seg /Sunset in yy-mm-dd hr:min:sec


    dif_begin_open = (at_civil - at_sun_set)/2
    at_begin_open = sun_set + dif_begin_open
    full_open = Time(at_begin_open, format='datetime')
    #print(full_open)
    if num_filters > 1:
        #print('Multiple filters are being used. Moving start from %s'%full_open)
        full_open = full_open - TimeDelta(7*60, format='sec')
        #full_open = full_open - TimeDelta((num_filters-1)*7*60, format='sec')
        #print('to %s'%full_open)
    
    
    dif_begin_close = (am_sun_rise - am_civil)/2
    at_begin_open = am_civil + dif_begin_close
    full_close = Time(at_begin_open, format='datetime')
    #print(full_close)
    
    if num_filters > 1:
        #print('Multiple filters are being used. Moving start from %s'%full_close)
        full_close = full_close + TimeDelta(7*60, format='sec')
        #full_open = full_open - TimeDelta((num_filters-1)*7*60, format='sec')
        #print('to %s'%full_close) 

    return full_open.iso, full_close.iso


def getnewstarttimefirstobjectSaint(day,coords,starttime,endtime):

    longitude = "-115d27m17.15s"
    latitude = "+31d02m36.3s"
    elevation = 2778.4*u.meter
    location = EarthLocation.from_geodetic(longitude, latitude, elevation)
    observer = Observer(name="SAINT-EX",location=location)
    
    angsol_eve=observer.sun_set_time(day, which='nearest', horizon=-8.19*u.degree)
    angsol_mor=observer.sun_rise_time(day, which='next', horizon=-8.19*u.degree)

    starttime = Time(starttime, scale='utc')
    endtime = Time(endtime,scale='utc')

    #print('days',starttime, angsol_eve.iso, endtime)

    constraints = [AltitudeConstraint(min = 27. * u.deg, max = 90 * u.deg), AirmassConstraint(2.4), MoonSeparationConstraint(min=25.5*u.deg), AtNightConstraint.twilight_civil()]

    target = FixedTarget(coord=coords, name='primer')  
    
    if starttime > angsol_eve:
        print('starttime > angsol_eve')
        jd1 = angsol_eve
        jd2 = endtime
        rango_tiempo=Time([jd1, jd2])
        always_observable = is_always_observable(constraints, observer, target, time_range=rango_tiempo)
        print('always',always_observable,jd1.iso,endtime)
        if always_observable:
            jd1 = angsol_eve
        else:
            jd1 = starttime
        
        rango_tiempo=Time([jd1, jd2])
        always_observable = is_always_observable(constraints, observer, target, time_range=rango_tiempo)
    print('How about now:',jd1,endtime, always_observable)
    return jd1, endtime

def getnewendtimelastobjectSaint(day,coords,starttime,endtime):

    longitude = "-115d27m17.15s"
    latitude = "+31d02m36.3s"
    elevation = 2778.4*u.meter
    location = EarthLocation.from_geodetic(longitude, latitude, elevation)
    observer = Observer(name="SAINT-EX",location=location)
    
    angsol_eve=observer.sun_set_time(day, which='nearest', horizon=-8.19*u.degree)
    angsol_mor=observer.sun_rise_time(day, which='next', horizon=-8.19*u.degree)

    starttime = Time(starttime, scale='utc')
    endtime = Time(endtime,scale='utc')

    constraints = [AltitudeConstraint(min = 27. * u.deg, max = 90 * u.deg), AirmassConstraint(2.4), MoonSeparationConstraint(min=25.5*u.deg), AtNightConstraint.twilight_civil()]
    target = FixedTarget(coord=coords, name='primer')  
    #print('end,mor',endtime.iso,angsol_mor.iso)
    if endtime < angsol_mor:
        print('endtime < angsol_mor')
        jd1 = starttime
        jd2 = angsol_mor
        rango_tiempo=Time([jd1, jd2])
        always_observable = is_always_observable(constraints, observer, target, time_range=rango_tiempo)
        print('always',always_observable,starttime,jd2.iso)
        if always_observable:
            jd2 = angsol_mor
        else:
            jd2 = endtime
        rango_tiempo=Time([jd1, jd2])
        print('How about now',starttime,jd2.iso,always_observable)
    return starttime, jd2



def make_astra_schedule_file(day, nb_days, telescope):
    t0 = Time(day)
    #print(day,t0)
    dt = Time('2018-01-02 00:00:00', scale='tcg') - Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    for nb_day in range(0, nb_days):
        t = Time(t0 + nb_day * dt)
        t_now = Time(t0 + nb_day * dt, scale='utc', out_subfmt='date').tt.datetime.strftime("%Y-%m-%d")
        Path = path_spock + '/DATABASE'
        p = os.path.join(Path, str(telescope), 'Plans_by_date', str(t_now))
        if not os.path.exists(p):
            os.makedirs(p)
        scheduler_table = Table.read(path_spock + '/DATABASE/' + str(telescope) + '/Archive_night_blocks' +
                                     '/night_blocks_' + str(telescope) + '_' + str(t_now) + '.txt', format='ascii')
        if (telescope == 'Io') or telescope == ('Europa') or (telescope == 'Ganymede') or (telescope == 'Callisto'):
            scheduler_table = dome_rotation(telescope=telescope, day_of_night=t_now)  # Intentional dome rotation to
            # avoid technical pb on Callisto with dome
        name = scheduler_table['target']
        config = scheduler_table['configuration']
        filt = []
        texp = []
        scheduler_table.add_index('target')
        try:
            index_to_delete = scheduler_table.loc['TransitionBlock'].index
            scheduler_table.remove_row(index_to_delete)
        except KeyError:
            print()
        for i in range(0, len(scheduler_table)):
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + "Target " + name[i] + " has been scheduled on the " + t_now + " on " + telescope)
            if name[i] != 'TransitionBlock':
                conf = ast.literal_eval(config[i])
                filt.append(conf['filt'])
                texp.append(conf['texp'])
                if telescope != 'Artemis':
                    if filt[i] == 'z' or filt[i] == 'g' or filt[i] == 'g' or filt[i] == 'i' or filt[i] == 'r':
                        a = filt[i]
                        filt[i] = a + '\''

        #Paranal
        location_paranal = EarthLocation.from_geodetic(-70.40300000000002 * u.deg, -24.625199999999996 * u.deg,
                                               2635.0000000009704 * u.m)
        paranal = Observer(location=location_paranal, name="paranal", timezone="UTC")

        #Tenerife
        location_SNO = EarthLocation.from_geodetic(-16.50583131 * u.deg, 28.2999988 * u.deg, 2390 * u.m)
        teide = Observer(location=location_SNO, name="SNO", timezone="UTC")

        #San Pedro de Martir
        location_saintex = EarthLocation.from_geodetic(-115.48694444444445 * u.deg, 31.029166666666665 * u.deg,
                                                       2829.9999999997976 * u.m)
        san_pedro = Observer(location=location_saintex, name="saintex", timezone="UTC")

        if telescope == "Saint-Ex":
            location = san_pedro

        elif (telescope == "Io") or (telescope == "Europa") or (telescope == "Ganymede") or (telescope == "Callisto"):
            location = paranal

        elif (telescope == "Artemis"):
            location = teide


        ## Built Schedule for ASTRA
        # Open
        open_row = [[	"camera_"+str(telescope).replace("-",""),	"open",	 "{}",
                     (location.sun_set_time(t, which='next', horizon=-1*u.deg)+15*u.min).iso,
                     (location.sun_rise_time(t, which='next',horizon=-1*u.deg)-15*u.min).iso]]
        if telescope == "Saint-Ex": 
            numfil = len(list(set(filt)))
            #print('filters',list(set(filt)),numfil)
            open_row = [[	"camera_"+str(telescope).replace("-",""),	"open",	 "{}",
            getfullcloseSaintEx(day=day,num_filters=numfil)[0],
            getfullcloseSaintEx(day=day,num_filters=numfil)[1]]]

        #print(t)

        df = pd.DataFrame(open_row, columns=["device_name",	"action_type",	"action_value",
                                             "start_time",	"end_time"])

        # # Dome
        # dome_row = pd.Series({	"device_name": "dome_"+str(telescope).replace("-",""),
        #                      "action_type": "SlewToAzimuth",	"action_value": 230,
        #                      "start_time": location.sun_set_time(t, which='next').iso,
        #                       "end_time": location.sun_rise_time(t, which='next').iso})
        # df = pd.concat([df, pd.DataFrame([dome_row])], ignore_index=True)
        # Flats
        def custom_sort(arr, custom_order):
            # Create a dictionary to store the index of each element in the custom order
            order_dict = {val: idx for idx, val in enumerate(custom_order)}
            # Define a custom sorting key function that uses the order_dict to get the index of each element
            def custom_key(element):
                return order_dict.get(element, float('inf'))

            # Sort the array using the custom sorting key
            sorted_arr = sorted(arr, key=custom_key)
            return sorted_arr

        my_array = list(set(filt)) # + ["z\'", "i\'"]))
        my_custom_order_evening = ["B", "z\'", "V", "r\'", "i\'", "g\'", "I+z", "Exo", "zYJ", "Clear"]
        filt_evening = custom_sort(my_array, my_custom_order_evening)
        if len(filt_evening) == 1:
            nb_flats = 30
        else:
            nb_flats = 15
        if len(filt_evening) == 1:
            nb_flats = 20
        else:
            nb_flats = 10

        if (telescope == "Callisto"):
            try:
                filt_evening.remove('I+z')
            except ValueError:
                (Fore.GREEN + 'INFO: ' + Fore.BLACK + " No I+z to discard for Callisto's Astra plans ")
                pass
        flats_row_evening = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                             "action_type": "flats",
                             "action_value": {"filter": filt_evening, 'n': [nb_flats]*len(filt_evening)},
                             "start_time": (location.sun_set_time(t, which='next', horizon=-1*u.deg)+15*u.min + 1*u.min).iso,
                                       "end_time": scheduler_table["start time (UTC)"][0]})

        if telescope == "Saint-Ex":
            i = 0
            my_custom_order_morning = my_custom_order_evening[::-1]# temporaty fix for Callisto 

            filt_morning = custom_sort(my_array, my_custom_order_morning)

            coords = SkyCoord(str(int(scheduler_table['ra (h)'][i])) + 'h' +
                              str(int(scheduler_table['ra (m)'][i])) + 'm' +
                              str(round(scheduler_table['ra (s)'][i], 3)) + 's' + ' ' +
                              str(int(scheduler_table['dec (d)'][i])) + 'd' +
                              str(abs(int(scheduler_table['dec (m)'][i]))) + 'm' +
                              str(abs(round(scheduler_table['dec (s)'][i], 3))) + 's')

            #print('call of getnewstarttimefirstobjectSaint',day,coords,Time(scheduler_table["start time (UTC)"][i] ).iso,
            #scheduler_table["end time (UTC)"][i])
            tiemposp = getnewstarttimefirstobjectSaint(day,coords,Time(scheduler_table["start time (UTC)"][i] ).iso,
            scheduler_table["end time (UTC)"][i])
        
            ultimoi = len(scheduler_table)
            #print('ultimo i',ultimoi)
            coords0 = SkyCoord(str(int(scheduler_table['ra (h)'][ultimoi-1])) + 'h' +
                    str(int(scheduler_table['ra (m)'][ultimoi-1])) + 'm' +
                    str(round(scheduler_table['ra (s)'][ultimoi-1], 3)) + 's' + ' ' +
                    str(int(scheduler_table['dec (d)'][ultimoi-1])) + 'd' +
                    str(abs(int(scheduler_table['dec (m)'][ultimoi-1]))) + 'm' +
                    str(abs(round(scheduler_table['dec (s)'][ultimoi-1], 3))) + 's')

            tiemposEnd = getnewendtimelastobjectSaint(day,coords0,Time(scheduler_table["start time (UTC)"][ultimoi-1] ).iso,
            scheduler_table["end time (UTC)"][ultimoi-1])
            #print('ultimo es',tiemposEnd[0].iso,tiemposEnd[1].iso )


            #print('flats antes', i,scheduler_table["start time (UTC)"][i],scheduler_table["end time (UTC)"][i], )
            #print('flats tiempos',tiemposp[0].iso,tiemposp[1].iso)

            flats_row_evening = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                        "action_type": "flats",
                                "action_value": {"filter": filt_morning, 'n': [nb_flats]*len(filt_morning)},
                        "start_time": (Time(getfullcloseSaintEx(day=day,num_filters=numfil)[0]) + 1*u.min).iso,
                                "end_time": tiemposp[0].iso})
            #print('flats',(Time(getfullcloseSaintEx(day=day,num_filters=numfil)[0]) + 1*u.min).iso,tiemposp[0].iso )
            #print(flats_row_evening['start_time'])

            #print(flats_row_evening['start_time'])
            #print(pd.DataFrame([flats_row_evening]))


        df = pd.concat([df, pd.DataFrame([flats_row_evening])], ignore_index=True)
        #Targets
        for i in range(len(scheduler_table)):
            #print('Comenzo',i)
        #    if scheduler_table['target'][i] == "dome_rot":
        #        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + " Not adding dom_rot to the targets ")
        #    else:
            coords = SkyCoord(str(int(scheduler_table['ra (h)'][i])) + 'h' +
                              str(int(scheduler_table['ra (m)'][i])) + 'm' +
                              str(round(scheduler_table['ra (s)'][i], 3)) + 's' + ' ' +
                              str(int(scheduler_table['dec (d)'][i])) + 'd' +
                              str(abs(int(scheduler_table['dec (m)'][i]))) + 'm' +
                              str(abs(round(scheduler_table['dec (s)'][i], 3))) + 's')

            if i == 0:
                tiemposp = getnewstarttimefirstobjectSaint(day,coords,Time(scheduler_table["start time (UTC)"][i] ).iso,
                scheduler_table["end time (UTC)"][i])
                #print('antes', i,scheduler_table["start time (UTC)"][i],scheduler_table["end time (UTC)"][i], )
                #print('tiempos',tiemposp[0].iso,tiemposp[1].iso)

                # Check if all filters are the same
                if len(list(set(filt))) == 1:
                    autofocus_end_time = tiemposEnd[1].iso
                    #print('autofocus uno',autofocus_end_time)
                else:
                    autofocus_end_time = tiemposp[1].iso
                #print('cual es autofocus',len(list(set(filt))),autofocus_end_time)

                deltaf = np.abs((Time(getfullcloseSaintEx(day=day,num_filters=numfil)[0]) + 1*u.min) -tiemposp[0])
                #print(deltaf.min,0.4*deltaf,(tiemposp[0]-0.4*deltaf).iso)
                #print('diff auto',tiemposp[0].iso,(tiemposp[0]-0.4*deltaf).iso)
                #print('autofocus',(tiemposp[0]).iso,autofocus_end_time )
                autofocus_row1 = pd.Series({"device_name": "camera_"+str(telescope).replace("-", ""), "action_type": "autofocus",
                                    "action_value": {"exptime": 1.0, "filter": filt[0], "focus_measure_operator": "hfr", "g_mag_range": (5, 10),
                                            "j_mag_range": (5, 10), "search_range": (10200, 10550), "n_steps": (20,), "n_exposures": [1],
                                            "airmass_threshold": 1.1, "selection_method": "maximal", "star_find_threshold": 6},
                                    "start_time": (tiemposp[0]-0.4*deltaf).iso,
                                    "end_time": autofocus_end_time})

                df = pd.concat([df, pd.DataFrame([autofocus_row1])], ignore_index=True)

            #print('Este es otro autofocus antes',i,filt[i],filt[i-1])
            if i > 0 and filt[i] != filt[i-1] and (i != ultimoi-1):
                #print('Este es otro autofocus',i,'filti',filt[i],'filt i-1',filt[i-1])
                #print(filt,ultimoi-1)
                #print('name',i,name[i])
                autofocus_rowmore = pd.Series({"device_name": "camera_"+str(telescope).replace("-", ""), "action_type": "autofocus",
                                    "action_value": {"exptime": 1.0, "filter": filt[i], "focus_measure_operator": "hfr", "g_mag_range": (5, 10),
                                            "j_mag_range": (5, 10), "search_range": (10200, 10550), "n_steps": (20,), "n_exposures": [1],
                                            "airmass_threshold": 1.1, "selection_method": "maximal", "star_find_threshold": 6},
                                    "start_time": (Time(scheduler_table["start time (UTC)"][i] ) + 0.5*u.min).iso,
                                    "end_time": scheduler_table["end time (UTC)"][i]})
                df = pd.concat([df, pd.DataFrame([autofocus_rowmore])], ignore_index=True)

            if (i > 0) and (filt[i] != filt[i-1]) and (i == ultimoi-1) and (i!= 0):
                #print('ultimo autofocus needed',i,ultimoi-1 )
                autofocus_rowmore = pd.Series({"device_name": "camera_"+str(telescope).replace("-", ""), "action_type": "autofocus",
                                    "action_value": {"exptime": 1.0, "filter": filt[i], "focus_measure_operator": "hfr", "g_mag_range": (5, 10),
                                            "j_mag_range": (5, 10), "search_range": (10200, 10550), "n_steps": (20,), "n_exposures": [1],
                                            "airmass_threshold": 1.1, "selection_method": "maximal", "star_find_threshold": 6},
                                    "start_time": (Time(scheduler_table["start time (UTC)"][i] ) + 0.5*u.min).iso,
                                    "end_time": tiemposEnd[1].iso})
            

                df = pd.concat([df, pd.DataFrame([autofocus_rowmore])], ignore_index=True)





            if scheduler_table['target'][i] == "dome_rot":
                action_values_target = {'object': name[i], 'filter': filt[i], 'ra': coords.ra.value,
                                    'dec': coords.dec.value,
                                    'exptime': int(texp[i]), 'n':int(0)}
            elif 'ch_' in scheduler_table['target'][i] or 'Ch_' in scheduler_table['target'][i]:
                action_values_target = {'object': name[i], 'filter': filt[i], 'ra': coords.ra.value, 'dec': coords.dec.value,
                            'exptime': int(texp[i]), 'guiding': True, 'pointing': True, 
                            'dir': 'C:/Users/speculoos/Documents/astra/images/Chilean'}
            else:
                action_values_target = {'object': name[i], 'filter': filt[i], 'ra': coords.ra.value, 'dec': coords.dec.value,
                            'exptime': int(texp[i]), 'guiding': True, 'pointing': True}
            target_row = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                             "action_type": "object",	"action_value": action_values_target,
                             "start_time": (Time(scheduler_table["start time (UTC)"][i] ) + 1*u.min).iso,
                                    "end_time": scheduler_table["end time (UTC)"][i]})
            if (i == 0) and (ultimoi > 1):
                #print('target0',filt[i])
                #print('target0',action_values_target)
                target_row = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                                "action_type": "object",	"action_value": action_values_target,
                                "start_time": (tiemposp[0] + 1*u.min).iso,
                                        "end_time": scheduler_table["end time (UTC)"][i]})
                #print('start',tiemposp[0],(tiemposp[0] + 1*u.min).iso,scheduler_table["end time (UTC)"][i])
                #print(target_row)

            if (i == 0) and (ultimoi == 1):
                #print('target1 of 1',filt[i])
                target_row = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                                "action_type": "object",	"action_value": action_values_target,
                                "start_time": (tiemposp[0] + 1*u.min).iso,
                                        "end_time": (tiemposEnd[1]+0*u.min).iso})
                #print('startt1',tiemposp[0],(tiemposp[0] + 1*u.min).iso,scheduler_table["end time (UTC)"][i])
                #print(target_row)


            if (i == ultimoi-1) and (i!= 0):
                #print('targetultimo', i)
                target_row = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                                "action_type": "object",	"action_value": action_values_target,
                                "start_time":  (Time(scheduler_table["start time (UTC)"][i] ) + 1*u.min).iso,
                                        "end_time": tiemposEnd[1].iso})
                #print('start',(Time(scheduler_table["start time (UTC)"][i] ) + 1*u.min).iso,tiemposEnd[1].iso)
                #print(target_row)
            

            df = pd.concat([df, pd.DataFrame([target_row])], ignore_index=True)
        # Flats
        my_custom_order_morning = my_custom_order_evening[::-1]# temporaty fix for Callisto 

        filt_morning = custom_sort(my_array, my_custom_order_morning)
        if (telescope == "Callisto"):
            try:
                filt_evening.remove('I+z')
            except ValueError:
                (Fore.GREEN + 'INFO: ' + Fore.BLACK + " No I+z to discard for Callisto's Astra plans ")
                pass
        flats_row_morning = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                             "action_type": "flats",
                                       "action_value": {"filter": filt_morning, 'n': [nb_flats]*len(filt_morning)},
                             "start_time": (Time(scheduler_table["end time (UTC)"][-1]) + 1*u.min).iso,
                                       "end_time": (location.sun_rise_time(t, which='next',horizon=-1*u.deg)-15*u.min).iso})

        if (telescope == 'Saint-Ex'):
            flats_row_morning = pd.Series({"device_name": "camera_"+str(telescope).replace("-",""),
                        "action_type": "flats",
                                "action_value": {"filter": filt_morning, 'n': [nb_flats]*len(filt_morning)},
                        "start_time": (tiemposEnd[1]+1*u.min).iso,
                                "end_time": getfullcloseSaintEx(day=day,num_filters=numfil)[1]})



        df = pd.concat([df, pd.DataFrame([flats_row_morning])], ignore_index=True)
        # Close
        close_row = pd.Series({	"device_name": "camera_"+str(telescope).replace("-",""),
                             "action_type": "close",	"action_value": {},
                             "start_time": (location.sun_rise_time(t, which='next', horizon=-1*u.deg)-15*u.min).iso,
                               "end_time": (location.sun_rise_time(t, which='next', horizon=-1*u.deg)+45*u.min).iso})
        if (telescope == 'Saint-Ex'):
            close_row = pd.Series({	"device_name": "camera_"+str(telescope).replace("-",""),
                                "action_type": "close",	"action_value": {},
                                "start_time": (Time(getfullcloseSaintEx(day=day,num_filters=numfil)[1],scale='utc')+1*u.min).iso,
                                "end_time": (Time(getfullcloseSaintEx(day=day,num_filters=numfil)[1],scale='utc')+6*u.min).iso})


        df = pd.concat([df, pd.DataFrame([close_row])], ignore_index=True)
        # Calibration
        texp = [int(x) for x in texp]
        texp += [0, 15, 30, 60, 120]
        texp = list(np.sort(np.unique(texp)))
        texp1_m = np.sum(texp)*10/60+10

        if (telescope == "Callisto"):
            calibration_row = pd.DataFrame([{	"device_name": "camera_"+str(telescope).replace("-",""),
                                 "action_type": "calibration",	"action_value": {"exptime":texp, 'n': [10]*len(texp), 'filter':'Dark'},
                                 "start_time": (location.sun_rise_time(t, which='next', horizon=-1*u.deg)-10*u.min+ 1*u.min).iso,
                                         "end_time": (location.sun_rise_time(t, which='next', horizon=-1*u.deg)+45*u.min).iso}])
        else:
            calibration_row = pd.DataFrame([
                {"device_name": "camera_" + str(telescope).replace("-", ""),
                 "action_type": "calibration",
                 "action_value": {"exptime": texp, 'n': [10] * len(texp), 'filter': 'I+z'},
                 "start_time": (location.sun_rise_time(t, which='next', horizon=-1*u.deg) - 10 * u.min + 1 * u.min).iso,
                 "end_time": (location.sun_rise_time(t, which='next', horizon=-1*u.deg) + 45 * u.min).iso}])

        if (telescope == 'Saint-Ex'):
            calibration_row = pd.DataFrame([
                {"device_name": "camera_" + str(telescope).replace("-", ""),
                 "action_type": "calibration",
                 "action_value": {"exptime": texp, 'n': [10] * len(texp), 'filter': 'I+z'},
                 "start_time": (Time(getfullcloseSaintEx(day=day,num_filters=numfil)[1],scale='utc')+7*u.min).iso,
                 "end_time": (Time(getfullcloseSaintEx(day=day,num_filters=numfil)[1],scale='utc')+7*u.min+texp1_m*u.min).iso}])



        # Add calibration row to the dataframe
        df = pd.concat([df, calibration_row], ignore_index=True)
        #df = df.append(calibration_row, ignore_index=True)
        df.sort_values('start_time', inplace=True)

        #To .csv file

        if (telescope == 'Saint-Ex') or  (telescope == "Callisto") or (telescope=="Ganymede") or (telescope=="Io") or (telescope=="Europa"):
            df.to_json(path_spock + '/DATABASE/' + str(telescope) + "/Astra/" +
                  str(telescope) + '_' + str(t_now) + '.jsonl', orient="records", lines=True)
            df.to_csv(path_spock + '/DATABASE/' + str(telescope) + "/Astra/" + str(telescope) + '_' + str(t_now) + '.csv', index=None)
        else:
            df.to_csv(path_spock + '/DATABASE/' + str(telescope) + "/Astra/" +
                  str(telescope) + '_' + str(t_now) + '.csv', index=None)
