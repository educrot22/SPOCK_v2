#!/anaconda3/bin/python3.6
from astropy.time import Time
from astropy.table import unique, Table, vstack
from astropy import units as u
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astroplan.utils import time_grid_from_range
from astroplan import FixedTarget, AltitudeConstraint, MoonSeparationConstraint, AtNightConstraint, AirmassConstraint, \
    TimeConstraint, observability_table
from astroplan.plots import dark_style_sheet, plot_airmass
from astroplan import Observer, moon_illumination, is_observable
from astroplan.periodic import EclipsingSystem
from astroplan.constraints import is_event_observable
from colorama import Fore
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import *
from datetime import date, timedelta, datetime
from eScheduler.spe_schedule import SPECULOOSScheduler, Schedule, ObservingBlock, Transitioner
import gspread
import matplotlib.pyplot as plt
import mphot
# path_mphot = mphot.__file__.replace('__init__.py', '')
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
import os
import pandas as pd
import requests
from .upload_night_plans import upload_np, upload_np_tn, upload_np_ts
from .make_night_plans import make_np, make_astra_schedule_file, offset_target_position
import subprocess
import sys
import shutil
import SPOCK.ETC as ETC
from SPOCK import user_portal, pwd_portal, pwd_appcs, path_spock, path_credential_json, path_credential_json_saint_ex, target_list_from_stargate_path, path_mphot
from requests.exceptions import ConnectionError

scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name(path_credential_json, scope)
client = gspread.authorize(creds)

# Autorisations
scope_saint_ex = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Connexion avec credentials
creds_saint_ex = ServiceAccountCredentials.from_json_keyfile_name(path_credential_json_saint_ex, scope_saint_ex
)

client_saint_ex = gspread.authorize(creds_saint_ex)

dt = Time('2018-01-02 00:00:00', scale='tcg') - Time('2018-01-01 00:00:00', scale='tcg')  # 1 day
constraints = [AltitudeConstraint(min=24 * u.deg), AtNightConstraint()]  # MoonSeparationConstraint(min=30*u.deg)


def charge_observatories(name):
    """

    Parameters
    ----------
    name: name of the observatory  "SSO" or "SNO" or "Saint-ex" or "TN_Oukaimeden or "TS_La_Silla"

    Returns
    -------
    astroplan.Observer object with name and coordinates of the observatory

    """
    observatories = []
    # Observatories
    if 'SSO' in str(name):
        location = \
            EarthLocation.from_geodetic(-70.40300000000002 * u.deg, -24.625199999999996 * u.deg,
                                        2635.0000000009704 * u.m)
        observatories.append(Observer(location=location, name="SSO", timezone="UTC"))

    if 'SNO' in str(name):
        location_SNO = EarthLocation.from_geodetic(-16.50583131 * u.deg, 28.2999988 * u.deg, 2390 * u.m)
        observatories.append(Observer(location=location_SNO, name="SNO", timezone="UTC"))

    if 'Saint-Ex' in str(name):
        location_saintex = EarthLocation.from_geodetic(-115.454764 * u.deg, 31.043417 * u.deg, #-115.48694444444445 * u.deg, 31.029166666666665 * u.deg values used before
                                                       2778.4 * u.m) # 2829.9999999997976 * u.m value used before
        observatories.append(Observer(location=location_saintex, name="Saint-Ex", timezone="UTC"))

    if 'TS_La_Silla' in str(name):
        location_TSlasilla = \
            EarthLocation.from_geodetic(-70.73000000000002 * u.deg, -29.25666666666666 * u.deg,
                                        2346.9999999988418 * u.m)
        observatories.append(Observer(location=location_TSlasilla, name="TS_La_Silla", timezone="UTC"))

    if 'TN_Oukaimeden' in str(name):
        location_TNOuka = EarthLocation.from_geodetic(-7.862263 * u.deg, 31.20516 * u.deg, 2751 * u.m)
        observatories.append(Observer(location=location_TNOuka, name="TN_Oukaimeden", timezone="UTC"))

    if 'Munich' in str(name):
        location_munich = EarthLocation.from_geodetic(48.2 * u.deg, -11.6 * u.deg, 600 * u.m)
        observatories.append(Observer(location=location_munich, name="Munich", timezone="UTC"))

    return observatories


def target_list_good_coord_format(df=None, path_target_list=None):
    """
    Give target corrdinates in ICRS format (used for astropy.coordinates SkyCoord function)

    Parameters
    ----------
    path_target_list: path on your computer toward the target list, by default take the one on the Cambridge server
    df: panda dataframe of the target list

    Returns
    -------
    targets: targets list with the following format : [<FixedTarget "Sp0002+0115" at SkyCoord (ICRS): (ra, dec) in deg (0.52591667, 1.26003889)>,


    """
    if df is None:
        df = pd.read_csv(path_target_list, delimiter=' ')
    target_table_spc = Table.from_pandas(df)
    targets = [FixedTarget(coord=SkyCoord(ra=target_table_spc['RA'][i] * u.degree,
                                          dec=target_table_spc['DEC'][i] * u.degree),
                           name=target_table_spc['Sp_ID'][i]) for i in range(len(target_table_spc['RA']))]
    return targets


class Schedules:
    """
    Class Schedules to make night plans
    """

    def __init__(self):
        self.altitude_constraint = 25
        self.airmass_constraint = None
        self.target_list = None
        self.telescopes = []
        self.telescope = []
        self.start_end_range = None  # date_range
        self.day_of_night = None
        self.constraints = [AtNightConstraint.twilight_civil()]
        self.moon_constraint = 30
        self.observatory = None
        self.observatory_name = None
        self.SS1_night_blocks = None
        self.scheduled_table = None
        self.SS1_night_blocks_old = None
        self.scheduled_table_sorted = None
        self.targets_follow_up = None
        self.target_table_spc_follow_up = None
        self.target_table_Saint_Ex = None
        self.target_list_follow_up = None
        self.target_list_special = None
        self.targets = None
        self.targets_Saint_Ex = None
        self.target_table_spc = []
        self.start_night = None
        self.end_night = None

    @property
    def start_of_observation(self):
        start_between_civil_nautical = Time((Time(
            self.observatory.twilight_evening_nautical(self.day_of_night, which='next')).value +
                                             Time(self.observatory.twilight_evening_civil(
                                                 self.day_of_night, which='next')).value) / 2, format='jd')
        return start_between_civil_nautical

    @property
    def end_of_observation(self):
        end_between_nautical_civil = Time((Time(
            self.observatory.twilight_morning_nautical(self.day_of_night + 1, which='nearest')).value +
                                           Time(self.observatory.twilight_morning_civil(
                                               self.day_of_night + 1, which='nearest')).value) / 2, format='jd')
        return end_between_nautical_civil

    def load_parameters(self, filename_list_special=None, filename_follow_up=None, mangos=None):
        """

        Parameters
        ----------
        filename_list_special: name of the file with special targets (stars not in SPECULOOS survey) to observe
        filename_follow_up: name of the file with follow up candidates targets (planets with ephemeris)
        set start and end of night 

        Returns
        -------

        """

        if (filename_list_special is None) or (filename_follow_up is None):
            try:
                sh = client.open('SPECULOOS WG6')
                # Read stars lists
                if mangos:
                    worksheet_follow_up = sh.worksheet("Annex_Targets_V1-MANGOs")
                else:
                    worksheet_follow_up = sh.worksheet("Annex_Targets_V1-PLANETS")
                dataframe = pd.DataFrame(worksheet_follow_up.get_all_records())
                self.target_table_spc_follow_up = dataframe.rename(columns={"sp_id": "Sp_ID", "gaia_dr2": "Gaia_ID",
                                                                            "period": "P", "period_e": "P_err",
                                                                            "duration": "W", "duration_e": "W_err",
                                                                            "dec": "DEC", "ra": "RA",
                                                                            "dec_err": "DEC_err", "ra_err": "RA_err",

                                                                            })
                self.targets_follow_up = target_list_good_coord_format(df=self.target_table_spc_follow_up)

                # Read follow up (planet candidates) list
                self.target_table_spc_follow_up['W'] /= 24
                self.target_table_spc_follow_up['W_err'] /= 24

                worksheet_special = sh.worksheet("Annex_Targets_V2-STARS")
                # Read follow up (planet candidates) list

                dataframe = pd.DataFrame(worksheet_special.get_all_records(expected_headers= [
                                "SPECULOOS", "Annex_Prog", "V_mag", "Alias", "Note", "Active", 
                                "Next Obs", "spc", "soi", "twomass", "gaia", "wise", "ra", "dec", 
                                "ra_err", "dec_err", "Filter_spc", "Filter_trap", "texp_spc", 
                                "texp_trap", "mag_j", "mag_j_err", "SpT", "e_Spt", "Teff", "distance"  ]))
                self.target_table_spc = dataframe.rename(columns={"spc": "Sp_ID", "gaia": "Gaia_ID", "dec": "DEC",
                                                                "ra": "RA", "dec_err": "DEC_err", "ra_err": "RA_err",
                                                                "mag_j": "J", "V_mag": "V"})
                self.targets = target_list_good_coord_format(df=self.target_table_spc)

                # Read Saint-Ex spreadsheet 
                # Ouvrir la spreadsheet
                sheet_saint_ex = client.open_by_url(
                    "https://docs.google.com/spreadsheets/d/1ITToBfgqTL5uRS5zWxZoClhPNVd1UpY0HdOCdJDG0_k/edit?gid=0#gid=0"
                ).sheet1

                # Récupérer les données
                data_saint_ex = sheet_saint_ex.get_all_records()

                # Convertir en DataFrame
                # df = pd.DataFrame(data_saint_ex)
                # worksheet_Saint_Ex = sh.worksheet("Annex_Targets_Saint-Ex")
                dataframe_Saint_Ex = pd.DataFrame(data_saint_ex) #pd.DataFrame(worksheet_Saint_Ex.get_all_records())
                self.target_table_Saint_Ex = dataframe_Saint_Ex.rename(columns={"Host star name": "Sp_ID", "gaia_dr2": "Gaia_ID",
                                                                            'FOV centre coordinates': "coord_hms_dms","Night (local start)":"night_start",
                                                                            "Start time (UT)": "start_time", "End time (UT)": "end_time",
                                                                            "Sp. Type": "SpT", 'Exposure time':"texp", "Filter":"Filter_spc", 

                                                                            })
                coords_saint_ex = self.target_table_Saint_Ex['coord_hms_dms'].apply(
                    lambda x: SkyCoord(x, unit=(u.hourangle, u.deg))
                )
                # change coord to deg and time to astropy Time format
                self.target_table_Saint_Ex['RA'] = coords_saint_ex.apply(lambda c: c.ra.deg)
                self.target_table_Saint_Ex['DEC'] = coords_saint_ex.apply(lambda c: c.dec.deg)
                self.target_table_Saint_Ex["night_start"] = pd.to_datetime(self.target_table_Saint_Ex["night_start"]) + pd.Timedelta(hours=15)
                self.target_table_Saint_Ex["night_start"] = self.target_table_Saint_Ex["night_start"].apply(Time)
                self.target_table_Saint_Ex[["start_hour", "start_minute", "start_second"]] = self.target_table_Saint_Ex["start_time"].str.split(":", expand=True)
                self.target_table_Saint_Ex[["end_hour", "end_minute", "end_second"]] = self.target_table_Saint_Ex["end_time"].str.split(":", expand=True)
                self.targets_Saint_Ex = target_list_good_coord_format(df=self.target_table_Saint_Ex)

            except ConnectionError:
                print(Fore.RED + 'ERROR: ' + Fore.BLACK +
                      ' there is a problem with your internet connection. ')

        if filename_list_special is not None:
            self.target_list_special = filename_list_special
            self.targets = target_list_good_coord_format(path_target_list=filename_list_special)
            self.target_table_spc = Table.from_pandas(pd.read_csv(filename_list_special, delimiter=' '))

        if filename_follow_up is not None:
            self.target_list_follow_up = filename_follow_up
            self.targets_follow_up = target_list_good_coord_format(path_target_list=filename_follow_up)
            self.target_table_spc_follow_up = Table.from_pandas(pd.read_csv(filename_follow_up, delimiter=' '))

    def night_duration(self):
        """

        Parameters
        ----------
        day: day str format '%y%m%d HH:MM:SS.sss'

        Returns
        -------
        duration of the day in astropy Time format
        """
        dt_1day = Time('2018-01-02 00:00:00', scale='tcg') - Time('2018-01-01 00:00:00', scale='tcg')
        return self.end_of_observation - self.start_of_observation

    def monitoring(self, input_name, airmass_max, time_monitoring):
        """
        Function to add a monitoring night block in  the plans
        Parameters
        ----------
        input_name: name of the target to monitor
        airmass_max: maximum airmass for the monitoring
        time_monitoring: time range of the monitoring in minutes

        Returns
        -------
        Create night block

        """
        idx_first_target = int(np.where((self.target_table_spc['Sp_ID'] == input_name))[0])
        dur_mon_target = time_monitoring * u.minute
        constraints_monitoring_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                         MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                         AirmassConstraint(max=airmass_max, boolean_constraint=True),
                                         TimeConstraint((
                                             Time(self.observatory.twilight_evening_nautical(self.day_of_night,
                                                                                             which='next'))),
                                             (Time(self.observatory.twilight_morning_nautical(self.day_of_night + 1,
                                                                                              which='nearest'))))]
        if self.target_table_spc['texp_spc'][idx_first_target] == 0:
            self.target_table_spc['texp_spc'][idx_first_target], self.target_table_spc['Filter_spc'][idx_first_target] = \
                self.exposure_time(input_name=self.target_table_spc['Sp_ID'][idx_first_target],
                                   target_list=self.target_table_spc)
        if self.telescope == 'Artemis':
            self.target_table_spc['Filter_spc'][idx_first_target] = \
                self.target_table_spc['Filter_spc'][idx_first_target].replace('\'', '')
        blocks = []
        a = ObservingBlock(self.targets[idx_first_target], dur_mon_target, -1,
                           constraints=constraints_monitoring_target,
                           configuration={"filt": str(self.target_table_spc['Filter_spc'][idx_first_target]),
                                          "texp": str(self.target_table_spc['texp_spc'][idx_first_target])})
        blocks.append(a)
        transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
        seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
        sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_monitoring_target,
                                                  observer=self.observatory, transitioner=transitioner)
        sequen_scheduler_ss1(blocks, seq_schedule_ss1)
        self.SS1_night_blocks = seq_schedule_ss1.to_table()
        return self.SS1_night_blocks

    def dome_rotation(self):
        """
        Function to add a dome rotation night block in the plans
        Returns
        -------
        Create a night block in between two targets or in the middle of  the night to ensure th dome is doing a full
        rotation

        """
        # not necessary
        dur_dome_rotation = 5 / 60 / 24 * u.day  # 5min

        sun_set = Time(self.observatory.twilight_evening_nautical(self.day_of_night, which='next'))
        sun_rise = Time(self.observatory.twilight_morning_nautical(self.day_of_night + 1, which='nearest'))

        time_resolution = 1 * u.hour
        time_grid = time_grid_from_range([sun_set, sun_rise], time_resolution=time_resolution)
        dom_rot_possible = False

        self.make_scheduled_table()
        end_times = Time(self.scheduled_table['end time (UTC)'][:]).iso

        for i in range(1, len(time_grid) - 1):

            start = time_grid[i]
            # print(start.iso)
            end = start + dur_dome_rotation
            idx = np.where((start < end_times[:]))[0]

            coords = SkyCoord(str(int(self.scheduled_table['ra (h)'][idx][0])) + 'h' +
                              str(int(self.scheduled_table['ra (m)'][idx][0])) + 'm' +
                              str(round(self.scheduled_table['ra (s)'][idx][0], 3)) + 's' + ' ' +
                              str(int(self.scheduled_table['dec (d)'][idx][0])) + 'd' +
                              str(abs(int(self.scheduled_table['dec (m)'][idx][0]))) + 'm' +
                              str(abs(round(self.scheduled_table['dec (s)'][idx][0], 3))) + 's').transform_to(
                AltAz(obstime=start, location=self.observatory.location))
            coords_dome_rotation = SkyCoord(alt=coords.alt, az=(coords.az.value - 180) * u.deg, obstime=start,
                                            frame='altaz', location=self.observatory.location)
            if (coords.alt.value > 60) or (coords.alt.value < 30):
                dom_rot_possible = False
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK +
                      ' dome rotation not possible at that time because of altitude constraint')

            else:
                target = FixedTarget(coord=SkyCoord(ra=coords_dome_rotation.icrs.ra.value * u.degree,
                                                    dec=coords_dome_rotation.icrs.dec.value * u.degree),
                                     name='dome_rot')
                dom_rot_possible = True

                df = pd.DataFrame({'target': target.name, 'start time (UTC)': start.iso, 'end time (UTC)': end.iso,
                                   'duration (minutes)': dur_dome_rotation.value * 24 * 60,
                                   'ra (h)': target.coord.ra.hms[0],
                                   'ra (m)': target.coord.ra.hms[1], 'ra (s)': target.coord.ra.hms[2],
                                   'dec (d)': target.coord.dec.dms[0], 'dec (m)': target.coord.dec.dms[1],
                                   'dec (s)': target.coord.dec.dms[2], 'configuration': "{\'filt=I+z\', \'texp=10\'}"},
                                  index=[0])
                self.SS1_night_blocks = Table.from_pandas(df)
                return self.SS1_night_blocks

                break

        if not dom_rot_possible:
            sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' No Dom rotation possible that night')

    def special_target_with_start_end(self, input_name, use_Saint_Ex_spreadsheet=False):
        """
        Function to add a special target night block in the plans with specific start/end times
        from self.start_end_range
        Parameters
        ----------
        input_name: name of the special target to schedule

        Returns
        -------
        Create a night block with special target observed in the given time range (self.start_end_range)

        """
        # IF TELESCOPE IS SAINT-EX WE USE THE SAINT-EX SPREADSHEET 
        if use_Saint_Ex_spreadsheet is True: 
            self.altitude_constraint = 27 
            self.moon_constraint = 25.5
            self.airmass_constraint = 2.4
            self.observatory = charge_observatories(self.observatory_name)[0]

            mask = (
                (self.target_table_Saint_Ex["night_start"] == self.day_of_night) &
                (self.target_table_Saint_Ex["Sp_ID"] == input_name)
            )

            try:
                row = self.target_table_Saint_Ex.loc[mask].iloc[0]
            except IndexError:
                sys.exit(
                            Fore.RED + "ERROR: " + Fore.RESET +
                            f"Target {input_name} not found in the Saint-Ex spreadsheet at this date {self.day_of_night}. "
                            "Please check the name and the date in the spreadsheet."
                        )

            base = Time(row["night_start"])
            t_start = Time(
                base.datetime.replace(
                    hour=int(row["start_hour"]),
                    minute=int(row["start_minute"]),
                    second=int(row["start_second"])
                ),
                scale="utc"
            )
            t_end = Time(
                base.datetime.replace(
                    hour=int(row["end_hour"]),
                    minute=int(row["end_minute"]),
                    second=int(row["end_second"])
                ),
                scale="utc"
            )
            
            if t_start.datetime.hour <12:
                t_start += 1*u.day
                t_end += 1*u.day
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + "Observation starts the day after the night start, adding a day")
            else:
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + "Observation starts the same day as the night start")
            start = t_start #self.start_end_range[0]
            end = t_end #self.start_end_range[1]

            dur_obs_both_target = (self.night_duration() / (2 * u.day)) * 2 * u.day
            constraints_Saint_Ex_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg, max=90 * u.deg),
                                        MoonSeparationConstraint(min=self.moon_constraint * u.deg), 
                                        AirmassConstraint(self.airmass_constraint),
                                        TimeConstraint(start, end)]
            idx_to_insert_target= self.target_table_Saint_Ex.loc[mask].index[0]
            ## WARNING with Next and Nearest, particularly for Saint-Ex
            rise_target = self.observatory.target_rise_time(self.start_of_observation, self.targets_Saint_Ex[idx_to_insert_target],  which='nearest', 
                                                            horizon= self.altitude_constraint * u.deg)
            set_target = self.observatory.target_set_time(self.start_of_observation, self.targets_Saint_Ex[idx_to_insert_target], which='next', 
                                                            horizon= self.altitude_constraint * u.deg)
            
            if (rise_target > start) or (set_target < end):   
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK
                        + " Observation impossible because the target is below the altitude constraint at some point during the given time range. If this is not the case this might be due to the setup of the \"which\" argument in the function target_rise_time(). Ask Elsa.")
                
            if (start < self.start_of_observation) or (end > self.end_of_observation):   
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK
                        + " Observation impossible because the given range is not fully within the night time. ")

            if self.target_table_Saint_Ex['texp'][idx_to_insert_target] == 0 \
                    or self.target_table_Saint_Ex['texp'][idx_to_insert_target] == "00":
                self.target_table_Saint_Ex['texp'][idx_to_insert_target], \
                self.target_table_Saint_Ex['Filter'][idx_to_insert_target] = \
                    self.exposure_time(input_name=self.target_table_Saint_Ex['Sp_ID'][idx_to_insert_target],
                                    target_list=self.target_table_Saint_Ex)

            observable = is_observable(constraints_Saint_Ex_target, self.observatory, self.targets_Saint_Ex[idx_to_insert_target],
                                    time_range=(start, end))
            
            if observable:
                blocks = []
                a = ObservingBlock(self.targets_Saint_Ex[idx_to_insert_target], dur_obs_both_target, -1,
                                constraints=constraints_Saint_Ex_target,
                                configuration={"filt": str(self.target_table_Saint_Ex['Filter_spc'][idx_to_insert_target]),
                                                "texp": str(self.target_table_Saint_Ex['texp'][idx_to_insert_target])})
                blocks.append(a)
                transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_Saint_Ex_target, observer=self.observatory,
                                                        transitioner=transitioner)
                sequen_scheduler_ss1(blocks, seq_schedule_ss1)
                self.SS1_night_blocks = seq_schedule_ss1.to_table()
                return self.SS1_night_blocks
            else:
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK
                        + " Observation on Saint-Ex impossible due to unrespected altitude and/or moon constraints. ")

        # if the telescope is not Saint-Ex
        else:
            self.observatory = charge_observatories(self.observatory_name)[0]
            start = self.start_end_range[0]
            end = self.start_end_range[1]


            if (start >= self.end_of_observation) or \
                    (end <= self.start_of_observation):
                sys.exit(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + 'Start time (or End time) is not on the same day.')

            dur_obs_both_target = (self.night_duration() / (2 * u.day)) * 2 * u.day
            constraints_special_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                        MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                        TimeConstraint(start, end)]
            idx_to_insert_target = int(np.where((self.target_table_spc['Sp_ID'] == input_name))[0])

            ## WARNING with Next and Nearest
            rise_target = self.observatory.target_rise_time(self.start_of_observation, self.targets[idx_to_insert_target],  which='nearest', 
                                                            horizon= self.altitude_constraint * u.deg)
            set_target = self.observatory.target_set_time(self.start_of_observation, self.targets[idx_to_insert_target], which='next', 
                                                            horizon= self.altitude_constraint * u.deg)

            if (rise_target > start) or (set_target < end):   
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK
                        + " Observation impossible because the target is not below the altitude constraint at some point during the given time range. If this is not the case this might be due to the setup of the \"which\" argument in the function target_rise_time(). Ask Elsa.")
                
            if (start < self.start_of_observation) or (end > self.end_of_observation):   
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK
                        + " Observation impossible because the given range is not fully within the night time. ")


            if self.target_table_spc['texp_spc'][idx_to_insert_target] == 0 \
                    or self.target_table_spc['texp_spc'][idx_to_insert_target] == "00":
                self.target_table_spc['texp_spc'][idx_to_insert_target], \
                self.target_table_spc['Filter_spc'][idx_to_insert_target] = \
                    self.exposure_time(input_name=self.target_table_spc['Sp_ID'][idx_to_insert_target],
                                    target_list=self.target_table_spc)
            if self.telescope == 'Artemis':
                self.target_table_spc['Filter_spc'][idx_to_insert_target] = \
                    self.target_table_spc['Filter_spc'][idx_to_insert_target].replace('\'', '')
            observable = is_observable(constraints_special_target, self.observatory, self.targets[idx_to_insert_target],
                                    time_range=(start, end))
            if observable:
                blocks = []
                a = ObservingBlock(self.targets[idx_to_insert_target], dur_obs_both_target, -1,
                                constraints=constraints_special_target,
                                configuration={"filt": str(self.target_table_spc['Filter_spc'][idx_to_insert_target]),
                                                "texp": str(self.target_table_spc['texp_spc'][idx_to_insert_target])})
                blocks.append(a)
                transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_special_target, observer=self.observatory,
                                                        transitioner=transitioner)
                sequen_scheduler_ss1(blocks, seq_schedule_ss1)
                self.SS1_night_blocks = seq_schedule_ss1.to_table()
                return self.SS1_night_blocks
            else:
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK
                        + " Observation impossible due to unrespected altitude and/or moon constraints. ")

    def special_target(self, input_name):
        """
        Function to add a special target night block in the plans
        Parameters
        ----------
        input_name: name of the special target to schedule

        Returns
        -------
        Create a night block with special target observed as much as possible given the constraints

        """
        self.observatory = charge_observatories(self.observatory_name)[0]
        dur_obs_both_target = (self.night_duration() / (2 * u.day)) * 2 * u.day
        constraints_special_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                      MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                      TimeConstraint(self.start_of_observation, self.end_of_observation)]
        idx_first_target = int(np.where((self.target_table_spc["Sp_ID"] == input_name))[0])
        if int(self.target_table_spc['texp_spc'][idx_first_target]) == 0:
            self.target_table_spc['texp_spc'][idx_first_target], \
            self.target_table_spc['Filter_spc'][idx_first_target] = \
                self.exposure_time(input_name=self.target_table_spc['Sp_ID'][idx_first_target],
                                   target_list=self.target_table_spc)
        if self.telescope == 'Artemis':
            self.target_table_spc['Filter_spc'][idx_first_target] = \
                self.target_table_spc['Filter_spc'][idx_first_target].replace('\'', '')
        blocks = []
        a = ObservingBlock(self.targets[idx_first_target], dur_obs_both_target, -1,
                           constraints=constraints_special_target,
                           configuration={"filt": str(self.target_table_spc['Filter_spc'][idx_first_target]),
                                          "texp": str(self.target_table_spc['texp_spc'][idx_first_target])})
        blocks.append(a)
        transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
        seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
        sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_special_target,
                                                  observer=self.observatory, transitioner=transitioner)
        sequen_scheduler_ss1(blocks, seq_schedule_ss1)
        self.SS1_night_blocks = seq_schedule_ss1.to_table()
        if len(self.SS1_night_blocks) == 0:
            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + 'Impossible to schedule target ' + input_name +
                  ' at this time range and/or with those constraints')
        return self.SS1_night_blocks

    def transit_follow_up(self, input_name):
        """
        Function to add a  night block with a transit of a follow candidate in the plans
        Parameters
        ----------
        input_name: name of the follow up candidate to schedule

        Returns
        -------
        Create a night block with transiting candidate observed for: transit duration * (1 + 1.5) centre on T0_predicted

        """
        self.observatory = charge_observatories(self.observatory_name)[0]

        constraints_follow_up = [AltitudeConstraint(min=self.altitude_constraint * u.deg), AtNightConstraint(),
                                 TimeConstraint(Time(self.day_of_night), Time(self.day_of_night + 1))]
        df = self.target_table_spc_follow_up

        if input_name is not None:
            i = int(np.where((df['Sp_ID'] == input_name))[0])
            blocks = []
            epoch = Time(df['T0'][i], format='jd')
            period = df['P'][i] * u.day
            duration = df['W'][i] * u.day
            oot_time = duration.value * 1. * u.day
            T0_err_transit = df['T0_err'][i]
            P_err_transit = df['P_err'][i]
            W_err_transit = df['W_err'][i]
            target_transit = EclipsingSystem(primary_eclipse_time=epoch, orbital_period=period, duration=duration,
                                             name=df['Sp_ID'][i])
            print(Fore.GREEN + Fore.GREEN + Fore.GREEN + 'INFO: ' + Fore.BLACK + ' ' + Fore.BLACK +
                  Fore.BLACK + str(df['Sp_ID'][i]) + ' next transit: ',
                  Time(target_transit.next_primary_eclipse_time(self.day_of_night, n_eclipses=1)).iso)
            timing_to_obs_jd = Time(target_transit.next_primary_eclipse_time(self.day_of_night, n_eclipses=1)).jd
            n_transits = 1
            try:
                ing_egr = target_transit.next_primary_ingress_egress_time(self.day_of_night, n_eclipses=n_transits)
            except ValueError:
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' No transit of ', df['Sp_ID'][i],
                      ' on the period chosen')

            observable = is_event_observable(constraints_follow_up, self.observatory, self.targets_follow_up,
                                             times_ingress_egress=ing_egr)
            if np.any(observable):
                err_T0_neg = T0_err_transit  # timing_to_obs_jd[0] -
                # (np.round((timing_to_obs_jd[0] - epoch.jd) / period.value, 1) *(period.value -
                # P_err_transit) + (epoch.jd - T0_err_transit))
                err_T0_pos = T0_err_transit  # (np.round((timing_to_obs_jd[0] - epoch.jd) / period.value, 1) *
                # (period.value + P_err_transit) + (epoch.jd + T0_err_transit)) - timing_to_obs_jd[0]
                start_transit = Time(ing_egr[0][0].value - err_T0_neg - oot_time.value - W_err_transit,
                                     format='jd')
                end_transit = Time(ing_egr[0][1].value + err_T0_pos + oot_time.value + W_err_transit,
                                   format='jd')
                dur_obs_transit_target = (end_transit - start_transit).value * 1. * u.day
                if (end_transit > self.end_of_observation) \
                        or (start_transit < self.start_of_observation):
                    if (Time(ing_egr[0][1]) < self.end_of_observation) \
                            and (Time(ing_egr[0][0]) > self.start_of_observation):
                        constraints_transit_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                                      TimeConstraint(start_transit, end_transit),
                                                      MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                                      AtNightConstraint(max_solar_altitude=-12 * u.deg)]
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' start_transit of ', str(df['Sp_ID'][i]),
                              ' : ', start_transit.iso)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' end_transit of ', str(df['Sp_ID'][i]),
                              ' : ', end_transit.iso)
                        print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Time out of transit not optimal.')
                        idx_first_target = int(np.where((df['Sp_ID'] == df['Sp_ID'][i]))[0])
                        if df['texp_spc'][idx_first_target] == 0:
                            df['texp_spc'][idx_first_target], df['Filter_spc'][idx_first_target] = self.exposure_time(
                                input_name=df['Sp_ID'][idx_first_target], target_list=self.target_table_spc_follow_up,
                                day=self.day_of_night)
                        if self.telescope == 'Artemis':
                            df['Filter_spc'][idx_first_target] = str(df['Filter_spc'][idx_first_target]).replace('\'', '')
                        a = ObservingBlock(self.targets_follow_up[idx_first_target], dur_obs_transit_target, -1,
                                           constraints=constraints_transit_target,
                                           configuration={"filt": str(df['Filter_spc'][idx_first_target]),
                                                          "texp": str(df['texp_spc'][idx_first_target])})
                        blocks.append(a)
                        transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                        seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                        sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_transit_target,
                                                                  observer=self.observatory,
                                                                  transitioner=transitioner)
                        sequen_scheduler_ss1(blocks, seq_schedule_ss1)

                    else:
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' start_transit of ', str(df['Sp_ID'][i]),
                              ' : ', Time(ing_egr[0][0]).iso)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' end_transit of ', str(df['Sp_ID'][i]),
                              ' : ', Time(ing_egr[0][1]).iso)
                        print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Transit not full.')
                        constraints_transit_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                                      MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                                      TimeConstraint(Time(ing_egr[0][0]), Time(ing_egr[0][1]))]
                        idx_first_target = int(np.where((df['Sp_ID'] == df['Sp_ID'][i]))[0])
                        if df['texp_spc'][idx_first_target] == 0:
                            df['texp_spc'][idx_first_target], df['Filter_spc'][idx_first_target] = self.exposure_time(
                                input_name=df['Sp_ID'][idx_first_target], target_list=self.target_table_spc_follow_up)
                        if self.telescope == 'Artemis':
                            df['Filter_spc'][idx_first_target] = str(df['Filter_spc'][idx_first_target]).replace('\'', '')
                        a = ObservingBlock(self.targets_follow_up[idx_first_target], dur_obs_transit_target, -1,
                                           constraints=constraints_transit_target,
                                           configuration={"filt": str(df['Filter_spc'][idx_first_target]),
                                                          "texp": str(df['texp_spc'][idx_first_target])})
                        blocks.append(a)
                        transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                        seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                        sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_transit_target,
                                                                  observer=self.observatory,
                                                                  transitioner=transitioner)
                        sequen_scheduler_ss1(blocks, seq_schedule_ss1)

                else:
                    constraints_transit_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                                  MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                                  TimeConstraint(start_transit, end_transit)]
                    idx_first_target = int(np.where((df['Sp_ID'] == df['Sp_ID'][i]))[0])
                    if df['texp_spc'][idx_first_target] == 0:
                        df['texp_spc'][idx_first_target], df['Filter_spc'][idx_first_target] = \
                            self.exposure_time(input_name=df['Sp_ID'][idx_first_target],
                                               target_list=self.target_table_spc_follow_up)
                    if self.telescope == 'Artemis':
                            df['Filter_spc'][idx_first_target] = str(df['Filter_spc'][idx_first_target]).replace('\'', '')
                    a = ObservingBlock(self.targets_follow_up[idx_first_target], dur_obs_transit_target, -1,
                                       constraints=constraints_transit_target,
                                       configuration={"filt": str(df['Filter_spc'][idx_first_target]),
                                                      "texp": str(df['texp_spc'][idx_first_target])})
                    blocks.append(a)
                    transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                    seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                    sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_transit_target,
                                                              observer=self.observatory,
                                                              transitioner=transitioner)
                    sequen_scheduler_ss1(blocks, seq_schedule_ss1)
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' start_transit of ', str(df['Sp_ID'][i]),
                          ' : ', Time(ing_egr[0][0]).iso)
                    print(Fore.GREEN + Fore.GREEN + 'INFO: ' + Fore.BLACK + ' ' + Fore.BLACK + ' end_transit of ',
                          str(df['Sp_ID'][i]), ' : ', Time(ing_egr[0][1]).iso)
                    print(Fore.GREEN + Fore.GREEN + 'INFO: ' + Fore.BLACK + ' ' + Fore.BLACK +
                          ' Transit is expected to be full.')
                    if len(seq_schedule_ss1.to_table()['target']) == 0:
                        print(Fore.RED + 'ERROR:  ' + Fore.BLACK +
                              ' The moon is too closed for the transit to be observed')

                if len(seq_schedule_ss1.to_table()['target']) != 0:
                    self.SS1_night_blocks = seq_schedule_ss1.to_table()
                    return self.SS1_night_blocks
            else:
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no transit of ', df['Sp_ID'][i], ' this day')

        else:
            for i in range(len(df['Sp_ID'])):
                blocks = []
                epoch = Time(df['T0'][i], format='jd')
                period = df['P'][i] * u.day
                duration = df['W'][i] * u.day
                oot_time = duration.value * 1. * u.day
                T0_err_transit = df['T0_err'][i]
                P_err_transit = df['P_err'][i]
                W_err_transit = df['W_err'][i]
                target_transit = EclipsingSystem(primary_eclipse_time=epoch, orbital_period=period,
                                                 duration=duration, name=df['Sp_ID'][i])
                print(Fore.GREEN + Fore.GREEN + Fore.GREEN + 'INFO: ' + Fore.BLACK + ' ' +
                      Fore.BLACK + Fore.BLACK + str(df['Sp_ID'][i]) + ' next transit: ',
                      Time(target_transit.next_primary_eclipse_time(self.day_of_night, n_eclipses=1)).iso)
                timing_to_obs_jd = Time(target_transit.next_primary_eclipse_time(self.day_of_night, n_eclipses=1)).jd
                n_transits = 1
                try:
                    ing_egr = target_transit.next_primary_ingress_egress_time(self.day_of_night, n_eclipses=n_transits)
                except ValueError:
                    print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' No transit of ',
                          df['Sp_ID'][i], ' on the period chosen')

                observable = is_event_observable(constraints, self.observatory,
                                                 self.targets_follow_up, times_ingress_egress=ing_egr)
                if np.any(observable):
                    err_T0_neg = timing_to_obs_jd[0] - (np.round((timing_to_obs_jd[0] - epoch.jd) / period.value, 1) *
                                                        (period.value - P_err_transit) + (epoch.jd - T0_err_transit))
                    err_T0_pos = (np.round((timing_to_obs_jd[0] - epoch.jd) / period.value, 1) *
                                  (period.value + P_err_transit) + (epoch.jd + T0_err_transit)) - timing_to_obs_jd[0]
                    start_transit = Time(ing_egr[0][0].value - err_T0_neg - oot_time.value - W_err_transit, format='jd')
                    end_transit = Time(ing_egr[0][1].value + err_T0_pos + oot_time.value + W_err_transit, format='jd')
                    dur_obs_transit_target = (end_transit - start_transit).value * 1. * u.day
                    if (end_transit > self.end_of_observation) \
                            or (start_transit < self.start_of_observation):

                        if (Time(ing_egr[0][1]) < self.end_of_observation) \
                                and (Time(ing_egr[0][0]) > self.start_of_observation):

                            constraints_transit_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                                          TimeConstraint(start_transit, end_transit),
                                                          MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                                          AtNightConstraint(max_solar_altitude=-12 * u.deg)]
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' start_transit of ',
                                  str(df['Sp_ID'][i]), ' : ', start_transit.iso)
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' end_transit of ',
                                  str(df['Sp_ID'][i]), ' : ', end_transit.iso)
                            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Time out of transit not optimal.')
                            idx_first_target = int(np.where((df['Sp_ID'] == df['Sp_ID'][i]))[0])
                            if df['texp_spc'][idx_first_target] == 0:
                                df['texp_spc'][idx_first_target], df['Filter_spc'][
                                    idx_first_target] = self.exposure_time(
                                    input_name=df['Sp_ID'][idx_first_target],
                                    target_list=self.target_table_spc_follow_up)
                            a = ObservingBlock(self.targets_follow_up[idx_first_target], dur_obs_transit_target, -1,
                                               constraints=constraints_transit_target,
                                               configuration={"filt": str(df['Filter_spc'][idx_first_target]),
                                                              "texp": str(df['texp_spc'][idx_first_target])})
                            blocks.append(a)
                            transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                            seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                            sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_transit_target,
                                                                      observer=self.observatory,
                                                                      transitioner=transitioner)
                            sequen_scheduler_ss1(blocks, seq_schedule_ss1)

                        else:
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' start_transit of ',
                                  str(df['Sp_ID'][i]), ' : ', Time(ing_egr[0][0]).iso)
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' end_transit of ',
                                  str(df['Sp_ID'][i]), ' : ', Time(ing_egr[0][1]).iso)
                            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Transit not full.')
                            constraints_transit_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                                          MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                                          TimeConstraint(Time(ing_egr[0][0]), Time(ing_egr[0][1]))]
                            # continue
                            idx_first_target = int(np.where((df['Sp_ID'] == df['Sp_ID'][i]))[0])
                            if df['texp_spc'][idx_first_target] == 0:
                                df['texp_spc'][idx_first_target], df['Filter_spc'][
                                    idx_first_target] = self.exposure_time(
                                    input_name=df['Sp_ID'][idx_first_target],
                                    target_list=self.target_table_spc_follow_up)
                            a = ObservingBlock(self.targets_follow_up[idx_first_target], dur_obs_transit_target, -1,
                                               constraints=constraints_transit_target,
                                               configuration={"filt": str(df['Filter_spc'][idx_first_target]),
                                                              "texp": str(df['texp_spc'][idx_first_target])})
                            blocks.append(a)
                            transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                            seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                            sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_transit_target,
                                                                      observer=self.observatory,
                                                                      transitioner=transitioner)
                            sequen_scheduler_ss1(blocks, seq_schedule_ss1)

                    else:
                        constraints_transit_target = [AltitudeConstraint(min=self.altitude_constraint * u.deg),
                                                      MoonSeparationConstraint(min=self.moon_constraint * u.deg),
                                                      TimeConstraint(start_transit, end_transit)]
                        idx_first_target = int(np.where((df['Sp_ID'] == df['Sp_ID'][i]))[0])
                        if df['texp_spc'][idx_first_target] == 0:
                            df['texp_spc'][idx_first_target], df['Filter_spc'][idx_first_target] = \
                                self.exposure_time(input_name=df['Sp_ID'][idx_first_target],
                                                   target_list=self.target_table_spc_follow_up)
                        a = ObservingBlock(self.targets_follow_up[idx_first_target], dur_obs_transit_target, -1,
                                           constraints=constraints_transit_target,
                                           configuration={"filt": str(df['Filter_spc'][idx_first_target]),
                                                          "texp": str(df['texp_spc'][idx_first_target])})
                        blocks.append(a)
                        transitioner = Transitioner(slew_rate=11 * u.deg / u.second)
                        seq_schedule_ss1 = Schedule(self.day_of_night, self.day_of_night + 1)
                        sequen_scheduler_ss1 = SPECULOOSScheduler(constraints=constraints_transit_target,
                                                                  observer=self.observatory,
                                                                  transitioner=transitioner)
                        sequen_scheduler_ss1(blocks, seq_schedule_ss1)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' start_transit of ', str(df['Sp_ID'][i]),
                              ' : ', Time(ing_egr[0][0]).iso)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' end_transit of ', str(df['Sp_ID'][i]),
                              ' : ', Time(ing_egr[0][1]).iso)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Transit is expected to be full.')
                        if len(seq_schedule_ss1.to_table()['target']) == 0:
                            print(Fore.RED + 'ERROR:  ' + Fore.BLACK +
                                  ' The moon is too closed for the transit to be observed')

                    if len(seq_schedule_ss1.to_table()['target']) != 0:
                        self.SS1_night_blocks = seq_schedule_ss1.to_table()
                        return self.SS1_night_blocks
                else:
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no transit of ', df['Sp_ID'][i], ' this day')


    def locking_observations(self):

        night_block = self.SS1_night_blocks.to_pandas()

        os.makedirs(path_spock + '/DATABASE/' + self.telescope + '/Locked_obs/', exist_ok=True)

        night_block.to_csv(path_spock + '/DATABASE/' + self.telescope + '/' +
                           'Locked_obs/' + 'lock_night_block_' + self.telescope + '_' +
                           Time(self.day_of_night, out_subfmt='date').iso + '.txt', index=None)

        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + 'Observation block saved as ' +
              path_spock + '/DATABASE/' + self.telescope + '/' +
              'Locked_obs/' + 'lock_night_block_' + self.telescope + '_' +
              Time(self.day_of_night, out_subfmt='date').iso + '.txt')

    def planification(self):

        self.make_scheduled_table()
        end_scheduled_table = pd.DataFrame(columns=['target', 'start time (UTC)', 'end time (UTC)',
                                                    'duration (minutes)', 'ra (h)', 'ra (m)', 'ra (s)',
                                                    'dec (d)', 'dec (m)', 'dec (s)', 'configuration'])
        try:
            self.SS1_night_blocks['target'][0]
        except TypeError:
            sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' No block to insert ')
        except IndexError:
            sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' No block to insert, it could be that the target is not visible or the moon is too close. ')
        if self.SS1_night_blocks['target'][0] in self.scheduled_table['target']:
            sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' This target is already scheduled this day')
        for i in range(len(self.scheduled_table['target'])):
            # print(i)
            try:
                self.SS1_night_blocks['target'][0]
            except IndexError:
                sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' No block to insert ')
            except TypeError:
                sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' No block to insert ')
            end_before_cut = self.scheduled_table['end time (UTC)'][i]
            start_before_cut = self.scheduled_table['start time (UTC)'][i]
            
            skip_scheduled_row = False
            if self.SS1_night_blocks is None:
                sys.exit('WARNING : No block to insert !')

            if not (self.scheduled_table_sorted is None):
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Several transits this night')
                if (np.any(str(self.SS1_night_blocks['target'][0]).find('Trappist-1')) == 0) and \
                        (np.any(str(self.scheduled_table_sorted['target'][0]).find('Trappist-1')) == 0):
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' two TRAPPIST-1 planets this night!')
                    self.SS1_night_blocks['start time (UTC)'][0] = \
                        min(self.SS1_night_blocks['start time (UTC)'][0],
                            self.scheduled_table_sorted['start time (UTC)'][0])
                    self.SS1_night_blocks['end time (UTC)'][0] = \
                        max(self.SS1_night_blocks['end time (UTC)'][0],
                            self.scheduled_table_sorted['end time (UTC)'][0])
                    self.SS1_night_blocks['duration (minutes)'][0] = \
                        (Time(self.SS1_night_blocks['end time (UTC)'][0]) -
                         Time(self.SS1_night_blocks['start time (UTC)'][0])).value * 24 * 60
                    new_row = pd.DataFrame([{'target': self.SS1_night_blocks['target'][0],
                                                'start time (UTC)': self.SS1_night_blocks['start time (UTC)'][0],
                                                'end time (UTC)': self.SS1_night_blocks['end time (UTC)'][0],
                                                'duration (minutes)': self.SS1_night_blocks['duration (minutes)'][0],
                                                'ra (h)': self.SS1_night_blocks['ra (h)'][0],
                                                'ra (m)': self.SS1_night_blocks['ra (m)'][0],
                                                'ra (s)': self.SS1_night_blocks['ra (s)'][0],
                                                'dec (d)': self.SS1_night_blocks['dec (d)'][0],
                                                'dec (m)': self.SS1_night_blocks['dec (m)'][0],
                                                'dec (s)': self.SS1_night_blocks['dec (s)'][0],
                                                'configuration': self.SS1_night_blocks['configuration'][0]}])
                    end_scheduled_table = pd.concat([end_scheduled_table, new_row], ignore_index=True)
            # situation 1
            if (self.SS1_night_blocks['start time (UTC)'][0] <=
                    self.start_of_observation.iso):
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 1')
                self.SS1_night_blocks['start time (UTC)'][0] = \
                    self.start_of_observation.iso

            if (self.SS1_night_blocks['start time (UTC)'][0] < start_before_cut) and \
                    (self.SS1_night_blocks['start time (UTC)'][0] < end_before_cut):

                # situation 2
                if (self.SS1_night_blocks['end time (UTC)'][0] > start_before_cut) and \
                        (self.SS1_night_blocks['end time (UTC)'][0] < end_before_cut):
                    # case 2 # if new_block ends beFore the end of existing block
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 2')
                    self.scheduled_table['start time (UTC)'][i] = self.SS1_night_blocks['end time (UTC)'][0]
                    self.scheduled_table['duration (minutes)'][i] = \
                        (Time(self.scheduled_table['end time (UTC)'][i]) -
                         Time(self.scheduled_table['start time (UTC)'][i])).value * 24 * 60

                # situation 3
                if self.SS1_night_blocks['end time (UTC)'][0] <= start_before_cut:
                    self.scheduled_table['duration (minutes)'][i] = \
                        (Time(self.scheduled_table['end time (UTC)'][i]) -
                         Time(self.scheduled_table['start time (UTC)'][i])).value * 24 * 60
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 3, no change made to initial schedule')

                # situation 4
                elif (self.SS1_night_blocks['end time (UTC)'][0] >= end_before_cut) and \
                        (self.SS1_night_blocks['end time (UTC)'][0] <=
                         self.end_of_observation.iso):
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 4')
                    skip_scheduled_row = True
                    # self.scheduled_table[i] = self.SS1_night_blocks[0]  # a way to erase self.scheduled_table block
                    

                # situation 5
                elif (self.SS1_night_blocks['end time (UTC)'][0] >=
                      self.end_of_observation.iso):
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 5')
                    self.SS1_night_blocks['end time (UTC)'][0] = \
                        self.end_of_observation.iso
                    skip_scheduled_row = True
                    #self.scheduled_table[i] = self.SS1_night_blocks[0]  # a way to erase self.scheduled_table block

            if self.SS1_night_blocks['start time (UTC)'][0] >= start_before_cut:

                # situation 6
                if (self.SS1_night_blocks['start time (UTC)'][0] <= end_before_cut) and \
                        (self.SS1_night_blocks['end time (UTC)'][0] <= end_before_cut):
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 6')
                    self.scheduled_table['end time (UTC)'][i] = self.SS1_night_blocks['start time (UTC)'][0]
                    self.scheduled_table['duration (minutes)'][i] = \
                        (Time(self.scheduled_table['end time (UTC)'][i]) -
                         Time(self.scheduled_table['start time (UTC)'][i])).value * 24 * 60
                    
                    new_row = pd.DataFrame([{'target': self.scheduled_table['target'][i] + '_2',
                         'start time (UTC)':
                             self.SS1_night_blocks['end time (UTC)'][0],
                         'end time (UTC)': end_before_cut,
                         'duration (minutes)': (Time(end_before_cut) - Time(
                             self.SS1_night_blocks['end time (UTC)'][
                                 0])).value * 24 * 60,
                         'ra (h)': self.scheduled_table['ra (h)'][i],
                         'ra (m)': self.scheduled_table['ra (m)'][i],
                         'ra (s)': self.scheduled_table['ra (s)'][i],
                         'dec (d)': self.scheduled_table['dec (d)'][i],
                         'dec (m)': self.scheduled_table['dec (m)'][i],
                         'dec (s)': self.scheduled_table['dec (s)'][i],
                         'configuration':
                             self.scheduled_table['configuration'][i]}])
                    end_scheduled_table = pd.concat([end_scheduled_table, new_row], ignore_index=True)


                if self.SS1_night_blocks['end time (UTC)'][0] >= end_before_cut:

                    # situation 7
                    if (self.SS1_night_blocks['end time (UTC)'][0] >=
                            self.end_of_observation.iso):

                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 7')

                        if self.SS1_night_blocks['start time (UTC)'][0] > self.scheduled_table['end time (UTC)'][i]:
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK +
                                  ' situation 7a, no change made to initial schedule')
                        else:
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 7b')
                            self.scheduled_table['end time (UTC)'][i] = self.SS1_night_blocks['start time (UTC)'][0]
                            self.scheduled_table['duration (minutes)'][i] = \
                                (Time(self.scheduled_table['end time (UTC)'][i])
                                 - Time(self.scheduled_table['start time (UTC)'][i])).value * 24 * 60

                            self.SS1_night_blocks['end time (UTC)'][0] = \
                                self.end_of_observation.iso
                            self.SS1_night_blocks['duration (minutes)'][0] = \
                                (Time(self.SS1_night_blocks['end time (UTC)'][0]) -
                                 Time(self.SS1_night_blocks['start time (UTC)'][0])).value * 24 * 60

                    elif (self.SS1_night_blocks['end time (UTC)'][0] <=
                          self.end_of_observation.iso):

                        # situation 8
                        if self.SS1_night_blocks['start time (UTC)'][0] >= end_before_cut:
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK +
                                  ' situation 8, no change made to initial schedule')
                        # situation 9
                        else:
                            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 9')
                            self.scheduled_table['end time (UTC)'][i] = self.SS1_night_blocks['start time (UTC)'][0]
                            self.scheduled_table['duration (minutes)'][i] = \
                                (Time(self.scheduled_table['end time (UTC)'][i]) -
                                 Time(self.scheduled_table['start time (UTC)'][i])).value * 24 * 60

                # situation 10
                if self.SS1_night_blocks['start time (UTC)'][0] >= end_before_cut:
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' situation 10, no change made to initial schedule')

            new_row = pd.DataFrame([{'target': self.SS1_night_blocks['target'][0],
                                                              'start time (UTC)':
                                                                  self.SS1_night_blocks['start time (UTC)'][0],
                                                              'end time (UTC)':
                                                                  self.SS1_night_blocks['end time (UTC)'][0],
                                                              'duration (minutes)':
                                                                  self.SS1_night_blocks['duration (minutes)'][0],
                                                              'ra (h)': self.SS1_night_blocks['ra (h)'][0],
                                                              'ra (m)': self.SS1_night_blocks['ra (m)'][0],
                                                              'ra (s)': self.SS1_night_blocks['ra (s)'][0],
                                                              'dec (d)': self.SS1_night_blocks['dec (d)'][0],
                                                              'dec (m)': self.SS1_night_blocks['dec (m)'][0],
                                                              'dec (s)': self.SS1_night_blocks['dec (s)'][0],
                                                              'configuration':
                                                                  self.SS1_night_blocks['configuration'][0]}])
            end_scheduled_table = pd.concat([end_scheduled_table, new_row], ignore_index=True)
            if not skip_scheduled_row:
                new_row = pd.DataFrame([{'target': self.scheduled_table['target'][i],
                                                                'start time (UTC)':
                                                                    self.scheduled_table['start time (UTC)'][i],
                                                                'end time (UTC)':
                                                                    self.scheduled_table['end time (UTC)'][i],
                                                                'duration (minutes)':
                                                                    self.scheduled_table['duration (minutes)'][i],
                                                                'ra (h)': self.scheduled_table['ra (h)'][i],
                                                                'ra (m)': self.scheduled_table['ra (m)'][i],
                                                                'ra (s)': self.scheduled_table['ra (s)'][i],
                                                                'dec (d)': self.scheduled_table['dec (d)'][i],
                                                                'dec (m)': self.scheduled_table['dec (m)'][i],
                                                                'dec (s)': self.scheduled_table['dec (s)'][i],
                                                                'configuration':
                                                                    self.scheduled_table['configuration'][i]}])
                end_scheduled_table = pd.concat([end_scheduled_table, new_row], ignore_index=True)

        end_scheduled_table = Table.from_pandas(end_scheduled_table)
        end_scheduled_table = unique(end_scheduled_table, keys='target')
        end_scheduled_table.sort(keys='start time (UTC)')
        idx_too_short_block = np.where((end_scheduled_table['duration (minutes)'] <= 3))

        if idx_too_short_block:
            for i in list(idx_too_short_block[0]):
                idx_for_target_2 = \
                    np.where((end_scheduled_table['target'] == end_scheduled_table['target'][i] + '_2'))[0]
                if idx_for_target_2.size != 0:
                    end_scheduled_table['target'][idx_for_target_2[0]] = end_scheduled_table['target'][i]

            list_too_short_reverse = list(idx_too_short_block[0])
            list_too_short_reverse.reverse()  # important to reverse if you want to delete lines correctly
            for i in list_too_short_reverse:
                end_scheduled_table.remove_row(i)

        self.scheduled_table_sorted = end_scheduled_table
        # ***** Update target lists on server *****
        # subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp", path_spock + '/target_lists/target_list_special.txt',
        #                   'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/spock_files/target_lists/'])
        # subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp", path_spock + '/target_lists/target_transit_follow_up.txt',
        #                   'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/spock_files/target_lists/'])

        return self.scheduled_table_sorted

    def make_scheduled_table(self):
        path = path_spock + '/DATABASE'
        try:
            os.path.exists(os.path.join(path, self.telescope, '/Archive_night_blocks/night_blocks_' + str(self.telescope) + '_' +
                                        self.day_of_night.tt.strftime("%Y-%m-%d") + '.txt'))
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Local path exists and is: ',
                  os.path.join(path, self.telescope, '/Archive_night_blocks/night_blocks_' + str(self.telescope) + '_' +
                               self.day_of_night.tt.strftime("%Y-%m-%d") + '.txt'))
        except TypeError:
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Local path does not exist yet ')
        except NameError:
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no input night_block for this day')
        except FileNotFoundError:
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no input night_block for this day')

        if not (self.scheduled_table is None):
            return self.scheduled_table
        else:
            try:
                self.scheduled_table = read_night_block(telescope=self.telescope,
                                                        day=self.day_of_night.tt.datetime.strftime("%Y-%m-%d"))
                return self.scheduled_table
            except TypeError:
                self.scheduled_table = read_night_block(telescope=self.telescope,
                                                        day=self.day_of_night.tt.datetime.strftime("%Y-%m-%d"))
                return self.scheduled_table

    def make_night_block(self):

        path = path_spock + '/night_blocks_propositions/'
        if not (self.scheduled_table_sorted is None):
            if isinstance(self.scheduled_table_sorted, pd.DataFrame):
                self.scheduled_table_sorted = self.scheduled_table_sorted.set_index('target')
                try:
                    self.scheduled_table_sorted.drop('TransitionBlock', inplace=True)
                except KeyError:
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no transition block')
                panda_table = self.scheduled_table_sorted
                try:
                    panda_table.to_csv(os.path.join(path, 'night_blocks_' + str(self.telescope) + '_' +
                                                    self.day_of_night.tt.datetime[0].strftime("%Y-%m-%d") +
                                                    '.txt'), sep=' ')
                except TypeError:
                    panda_table.to_csv(os.path.join(path, 'night_blocks_' + str(self.telescope) + '_' +
                                                    self.day_of_night.tt.datetime.strftime("%Y-%m-%d") +
                                                    '.txt'), sep=' ')
            else:
                try:
                    self.scheduled_table_sorted.add_index('target')
                    index_to_delete = self.scheduled_table_sorted.loc['TransitionBlock'].index
                    self.scheduled_table_sorted.remove_row(index_to_delete)
                except KeyError:
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' no transition block')
                panda_table = self.scheduled_table_sorted.to_pandas()
                try:
                    panda_table.to_csv(os.path.join(path, 'night_blocks_' + str(self.telescope) + '_' +
                                                    self.day_of_night.tt.datetime[0].strftime("%Y-%m-%d") +
                                                    '.txt'), sep=' ',index_label='target')
                except TypeError:
                    panda_table.to_csv(os.path.join(path, 'night_blocks_' + str(self.telescope) + '_' +
                                                    self.day_of_night.tt.datetime.strftime("%Y-%m-%d") +
                                                    '.txt'), sep=' ',index_label='target')

    def exposure_time(self, input_name, target_list, day=None):
        """

        Parameters
        ----------
        input_name
        target_list
        day

        Returns
        -------

        """
        i = np.where((target_list['Sp_ID'] == input_name))[0]
        if day is None:
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Not using moon phase in ETC')


        if self.telescope == 'Callisto':
            #filters list
            possible_filters = ['zYJ','SPC_J','SPC_H'] # We're not looping here
            filt_ = target_list['Filter_spc'][i].values[0]

            #mphot computation
            efficiencyFile_SPIRIT = path_mphot + '/resources/systems/speculoos_PIRT_1280SciCam_-60.csv'
            if filt_ == 'J':
                filt_ = 'SPC_J'
            elif filt_ == 'H':
                filt_ = 'SPC_H'

            filterFile_SPIRIT = path_mphot + '/resources/filters/'+filt_+'.csv'
            # name to refer to the generated file
            name_SPIRIT, system_response_SPIRIT = mphot.generate_system_response(
                efficiencyFile_SPIRIT, filterFile_SPIRIT
            )

            props_sky = {
                "pwv": 2.5,  # PWV [mm]
                "airmass": 1.1,  # airmass
                "seeing": 1.,  # seeing (==FWHM) ["]
            }
            props_callisto = {
                "name": name_SPIRIT,
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

            try:
                spirit = mphot.get_precision(props_callisto, props_sky, 
                                             Teff=float(target_list["Teff"][i].values[0]), 
                                             distance=float(target_list["distance"][i].values[0]))
            except FileNotFoundError:
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Re-running the grid for mphot, can take 30s')
                spirit = mphot.get_precision(props_callisto, props_sky, Teff=float(target_list["Teff"][i].values[0]),
                                              distance=float(target_list["distance"][i].values[0]), override_grid=True)
                raise
            # extract exposure time
            image_precision, binned_precision, components = spirit
            texp = int(components["t [s]"])

            # change the naming of filter SPC_H and SPC_J back to H and J for the astra output night block
            if filt_ == 'SPC_J':
                filt_ = 'J'
            elif filt_ == 'SPC_H':
                filt_ = 'H'

        else:
            #filters list
            filt_ = target_list['Filter_spc'][i].values[0]
            if (filt_ == 'z\'') or (filt_ == 'r\'') or (filt_ == 'i\'') or (filt_ == 'g\'') or (filt_ == 'u\''):
                filt_ = filt_.replace('\'', '')
            if filt_ == 'zcut':
                filt_ = 'z'
            if filt_ == 'zYJ':
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + f' Filter zYJ is only available on Callisto, not {self.telescope}. Defaulting to I+z.')
                filt_ = 'I+z'
            if filt_ != 'I+z':
                filters = [filt_] + ['I+z', 'z', 'i', 'r', 'g']
            else:
                filters = ['I+z', 'z', 'i', 'r', 'g']
            filt_idx = 0
            filt_ = filters[filt_idx]
            #texp = 0
            filt_ = filters[filt_idx]

            #mphot computation
            efficiencyFile_ANDOR = path_mphot + '/resources/systems/speculoos_Andor_iKon-L-936_-60.csv'
            filterFile_ANDOR = path_mphot + '/resources/filters/'+str(filt_)+'.csv'
            # name to refer to the generated file
            name_ANDOR, system_response_ANDOR = mphot.generate_system_response(
                efficiencyFile_ANDOR, filterFile_ANDOR
            )

            props_sky = {
                "pwv": 2.5,  # PWV [mm]
                "airmass": 1.1,  # airmass
                "seeing": 1.,  # seeing (==FWHM) ["]
            }
            # instrument properties
            props_telescope_ANDOR = {
                "name": name_ANDOR,  # name to get SR/precision grid from file
                "plate_scale": 0.35,  # pixel plate scale ["]
                "N_dc": 0.2,  # dark current [e/pix/s]
                "N_rn": 6.328,  # read noise [e_rms/pix]
                "well_depth": 64000,  # well depth [e/pix]
                "well_fill": 0.7,  # fractional value to fill central target pixel, assuming gaussian (width function of seeing^)
                "read_time": 10.5,  # read time between images [s]
                "r0": 0.5,  # radius of telescope's primary mirror [m]
                "r1": 0.14,  # radius of telescope's secondary mirror [m]
                # "min_exp" : 0,          # optional, minimum exposure time [s]
                # "max_exp" : 120,        # optional, maximum exposure time [s]
                # "ap_rad" : 3            # optional, aperture radius [FWHM, seeing] for photometry -- 3 default == 7 sigma of Gaussian
            }

            # get the precision and components used to calculate it (generates grid if not already present)
            try:
                andor = mphot.get_precision(props_telescope_ANDOR, props_sky, #source_id=target_list["Gaia_ID"][i].values[0],
                                            Teff=float(target_list["Teff"][i].values[0]),distance=float(target_list["distance"][i].values[0]))
            except FileNotFoundError:
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Re-running the grid for mphot, can take 30s')
                andor = mphot.get_precision(props_telescope_ANDOR, props_sky, #source_id=target_list["Gaia_ID"][i].values[0],
                                            Teff=float(target_list["Teff"][i].values[0]), distance=float(target_list["distance"][i].values[0]), override_grid=True)
            except TypeError as e:
                sys.exit(Fore.RED + 'ERROR: ' + Fore.BLACK + f' Please make sure the Teff and distance are provided in the WG6 spreadsheet. Got Teff={target_list["Teff"][i].values[0]!r}, distance={target_list["distance"][i].values[0]!r}. Original error: {e}')
            # extract exposure time
            image_precision, binned_precision, components = andor
            texp = int(components["t [s]"])
            
            while texp < 10 and filt_idx < len(filters) - 1:

                filt_idx += 1
                filt_ = filters[filt_idx]
                efficiencyFile_ANDOR = path_mphot + '/resources/systems/speculoos_Andor_iKon-L-936_-60.csv'
                filterFile_ANDOR = path_mphot+ '/resources/filters/'+str(filt_)+'.csv'
                # name to refer to the generated file
                name_ANDOR, system_response_ANDOR = mphot.generate_system_response(
                    efficiencyFile_ANDOR, filterFile_ANDOR
                )
                # instrument properties
                props_telescope_ANDOR = {
                "name": name_ANDOR,  # name to get SR/precision grid from file
                "plate_scale": 0.35,  # pixel plate scale ["]
                "N_dc": 0.2,  # dark current [e/pix/s]
                "N_rn": 6.328,  # read noise [e_rms/pix]
                "well_depth": 64000,  # well depth [e/pix]
                "well_fill": 0.7,  # fractional value to fill central target pixel, assuming gaussian (width function of seeing^)
                "read_time": 10.5,  # read time between images [s]
                "r0": 0.5,  # radius of telescope's primary mirror [m]
                "r1": 0.14,  # radius of telescope's secondary mirror [m]
                # "min_exp" : 0,          # optional, minimum exposure time [s]
                # "max_exp" : 120,        # optional, maximum exposure time [s]
                # "ap_rad" : 3            # optional, aperture radius [FWHM, seeing] for photometry -- 3 default == 7 sigma of Gaussian
                }
                if target_list['Teff'][i].values[0] is not None and target_list['distance'][i].values[0] is not None:
                    try:
                        andor = mphot.get_precision(props_telescope_ANDOR, props_sky, #source_id=target_list["Gaia_ID"][i].values[0],
                                                    Teff=float(target_list["Teff"][i].values[0]),distance=float(target_list["distance"][i].values[0]))
                    except FileNotFoundError:
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Re-running the grid for mphot, can take 30s')
                        andor = mphot.get_precision(props_telescope_ANDOR, props_sky, #source_id=target_list["Gaia_ID"][i].values[0],
                                                    Teff=float(target_list["Teff"][i].values[0]), distance=float(target_list["distance"][i].values[0]), override_grid=True)
                else:
                    try:
                        andor = mphot.get_precision_gaia(props_telescope_ANDOR, props_sky, source_id=target_list["Gaia_ID"][i].values[0], 
                                                     Teff=target_list["Teff"][i].values[0])
                    except FileNotFoundError:
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Re-running the grid for mphot, can take 30s')
                        andor = mphot.get_precision_gaia(props_telescope_ANDOR, props_sky, source_id=target_list["Gaia_ID"][i].values[0], 
                                                     Teff=target_list["Teff"][i].values[0], override_grid=True)
    
                # extract exposure time
                image_precision, binned_precision, components = andor                
                texp = int(components["t [s]"])
                if self.telescope == 'Artemis': # Artemis plans do not want '
                    filt_ = filt_.replace('\'', '')
            if texp < 10:
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + f'No filter found with exposure_time >= 10s for this target, it needs defocusing. Setting the filter to {filt_} with exposure_time fixed to 10s.')
                texp = 10

        target_list['Filter_spc'][i] = filt_

        return int(texp), filt_

    def visibility_plot(self):
        day = self.day_of_night
        delta_midnight = Time(np.linspace(self.start_of_observation.jd,
                                          self.end_of_observation.jd, 100),
                              format='jd')
        for i in range(len(self.scheduled_table_sorted)):
            idx = np.where((self.target_table_spc['Sp_ID'] == self.scheduled_table_sorted['target'][i]))[0]
            plot_airmass(self.targets[int(idx)], self.observatory, delta_midnight, style_sheet=dark_style_sheet)
            t = Time(self.scheduled_table_sorted['start time (UTC)'][i])
            plt.vlines(t.iso, 3, 1, color='r')
        plt.legend(shadow=True, loc=2)


def visibility_plot(day, observatory, night_block):
    delta_midnight = Time(np.linspace(observatory.twilight_evening_nautical(day, which='next').jd,
                                      observatory.twilight_morning_nautical(day + 1, which='nearest').jd, 100),
                          format='jd')
    dec = str(int(float(night_block['dec (d)'][0]))) + 'd' + str(int(float(night_block['dec (m)'][0]))) + 'm' + \
          str(int(float(night_block['dec (s)'][0]))) + 's'
    ra = str(int(float(night_block['ra (h)'][0]))) + 'h' + str(int(float(night_block['ra (m)'][0]))) + 'm' + \
         str(int(float(night_block['ra (s)'][0]))) + 's'
    for i in range(len(night_block)):
        plot_airmass(SkyCoord(ra=ra, dec=dec, frame='icrs'), observatory, delta_midnight, style_sheet=dark_style_sheet)
        t = Time(night_block['start time (UTC)'][i])
        plt.vlines(t.iso, 3, 1, linestyle='-', color='r', alpha=0.7)
        plt.legend(shadow=True, loc=2)


def save_schedule(save, over_write, day, telescope):
    if save:
        source = path_spock + '/night_blocks_propositions/' + 'night_blocks_' + telescope + '_' + \
                 day.tt.datetime.strftime("%Y-%m-%d") + '.txt'
        #destination = path_spock + '/DATABASE/' + telescope + '/'
        destination_2 = path_spock + '/DATABASE/' + telescope + '/' + 'Archive_night_blocks/'
        if over_write:
            #dest = shutil.copy(source, destination)
            dest2 = shutil.copy(source, destination_2)
            print(Fore.GREEN + 'INFO:  ' + Fore.BLACK + '\"' + source + '\"' + ' has been over-written to ' +
                  '\"' + destination_2 + '\"')
            #make_astra_schedule_file(day, 1, telescope)
        if not over_write:
            try:
                dest = shutil.move(source, destination_2)
                shutil.move(source, destination_2)
                print(Fore.GREEN + 'INFO:  ' + Fore.BLACK + '\"' + source + '\"' + ' has been copied to ' +
                      '\"' + destination_2 + '\"')
                #make_astra_schedule_file(day, 1, telescope)
            except shutil.Error:
                print(Fore.GREEN + 'INFO:  ' + Fore.BLACK + '\"' + destination_2 + 'night_blocks_' +
                      telescope + '_' + day.tt.datetime.strftime("%Y-%m-%d") + '.txt' + '\"' + ' already exists')
    if not save:
        print(Fore.GREEN + 'INFO:  ' + Fore.BLACK + ' Those plans have not been saved')


def make_plans(day, nb_days, telescope):
    make_np(day, nb_days, telescope)
    make_astra_schedule_file(day, nb_days, telescope)


def upload_plans(day, nb_days, telescope):
    """ upload plans to DATABASE

    Parameters
    ----------
    day : date
        date in fmt 'yyyy-mm-dd'
    nb_days : int
        number of days
    telescope : str
        name of telescope

    Returns
    -------

    """
    if (telescope == 'Io') or telescope == ('Europa') or (telescope == 'Ganymede') or (telescope == 'Callisto') or (telescope =='Artemis') or (telescope == 'Saint-Ex'):
        upload_np(day,nb_days,telescope)
    if telescope.find('TS_La_Silla') is not -1:
        upload_np_ts(day, nb_days)
    if telescope.find('TN_Oukaimeden') is not -1:
        upload_np_tn(day, nb_days)
    # ------------------- update archive date by date plans folder  ------------------

    # path_gant_chart = os.path.join(path_spock + '/SPOCK_Figures/Preview_schedule.html')
    # path_database_home = \
    #     os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Preview_schedule.html')
    # print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Path local \'Gant chart\' = ', path_gant_chart)
    # print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Path database = \'Gant chart\' = ', path_database_home)
    #subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp", "-r", path_gant_chart, path_database_home])
    # path_gant_chart_masterfile = \
    #     os.path.join('/Users/elsaducrot/spock_2/SPOCK_Figures/spock_stats_masterfile.csv')
    # path_database_home_masterfile = \
    #     os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/spock_stats_masterfile.csv')
    #subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp", "-r", path_gant_chart_masterfile,
 #                     path_database_home_masterfile])


def read_night_block(telescope, day):
    day_fmt = Time(day, scale='utc', out_subfmt='date').tt.datetime.strftime("%Y-%m-%d")
    path_local = path_spock + '/DATABASE/' + telescope + '/Archive_night_blocks/night_blocks_' + telescope + '_' + \
                 day_fmt + '.txt'

    if os.path.exists(path_local):
        day_fmt = Time(day, scale='utc', out_subfmt='date').tt.datetime.strftime("%Y-%m-%d")
        scheduler_table = Table.read(
            path_spock + '/DATABASE/' + str(telescope) + '/Archive_night_blocks' + '/night_blocks_' +
            str(telescope) + '_' + str(day_fmt) + '.txt',
            format='ascii')
    else:
        nightb_url = "https://www.mrao.cam.ac.uk/SPECULOOS/Observations/" + telescope + '/schedule/Archive_night_blocks/night_blocks_' + \
                     telescope + '_' + day_fmt + '.txt'
        nightb = requests.get(nightb_url, auth=(user_portal, pwd_portal))

        if nightb.status_code == 404:
            sys.exit(Fore.RED + 'ERROR:  ' + Fore.BLACK + ' No plans on the server for this date')
        else:
            open(path_local, 'wb').write(nightb.content)
            scheduler_table = pd.read_csv(path_local, delimiter=' ', skipinitialspace=True,)
    return scheduler_table


def date_range_in_days(date_range):
    date_format = "%Y-%m-%d %H:%M:%S.%f"
    date_start = datetime.strptime(date_range[0].value, date_format)
    date_end = datetime.strptime(date_range[1].value, date_format)
    return (date_end - date_start).days


def get_info_follow_up_target(name, target_list_follow_up):
    """

    Parameters
    ----------
    name: name of the target  you wish to the next transit windows of
    target_list_follow_up: dataframe

    Returns
    -------

    """
    idx_target = np.where((target_list_follow_up['Sp_ID'] == name))[0]
    if idx_target.size == 0:
        sys.exit('ERROR: This target name is not in the list.')
    else:
        return float(target_list_follow_up['RA'][idx_target]), float(target_list_follow_up['DEC'][idx_target]), \
               float(target_list_follow_up['T0'][idx_target]), float(target_list_follow_up['P'][idx_target]), \
               float(target_list_follow_up['W'][idx_target])


def prediction(name, ra, dec, timing, period, duration, start_date, ntr):
    altitude_constraint = 25
    altitude_constraint_stx = 27

    start_date = Time(start_date)

    constraints_predictions = [AltitudeConstraint(min=altitude_constraint * u.deg),
                               AtNightConstraint.twilight_nautical()]
    constraints_predictions_stx = [AltitudeConstraint(min=altitude_constraint_stx * u.deg),
                                   AtNightConstraint.twilight_nautical()]

    target_transit = EclipsingSystem(primary_eclipse_time=Time(timing, format='jd'),
                                     orbital_period=period * u.day, duration=duration * u.day,
                                     name=name)
    target = [FixedTarget(coord=SkyCoord(ra=ra * u.degree, dec=dec * u.degree), name=name)]

    target_set_time_sso = charge_observatories('SSO')[0].target_set_time(start_date,
                                                                         target,
                                                                         which='next',
                                                                         horizon=altitude_constraint * u.deg)

    mid_transit_timing = Time(target_transit.next_primary_eclipse_time(start_date, n_eclipses=ntr)).iso
    mid_transit_timing_jd = Time(target_transit.next_primary_eclipse_time(start_date, n_eclipses=ntr)).jd

    ing_egr = target_transit.next_primary_ingress_egress_time(start_date, n_eclipses=ntr)

    target = [FixedTarget(coord=SkyCoord(ra=ra * u.degree, dec=dec * u.degree), name=name)]
    # observatory = charge_observatories(obs_name)[0]

    observable_sso = is_event_observable(constraints_predictions, charge_observatories('SSO')[0], target,
                                         times_ingress_egress=ing_egr)
    observable_sno = is_event_observable(constraints_predictions, charge_observatories('SNO')[0], target,
                                         times_ingress_egress=ing_egr)
    observable_saintex = is_event_observable(constraints_predictions_stx, charge_observatories('Saint-Ex')[0], target,
                                             times_ingress_egress=ing_egr)
    observable_tn_oukaimeden = is_event_observable(constraints_predictions, charge_observatories('TN_Oukaimeden')[0],
                                                   target, times_ingress_egress=ing_egr)
    observable_ts_la_silla = is_event_observable(constraints_predictions, charge_observatories('TS_La_Silla')[0],
                                                 target, times_ingress_egress=ing_egr)

    dates = [Time(Time(ing_egr[i][0]).iso, out_subfmt='date').iso for i in range(len(ing_egr))]

    observable_sso_tables = []
    observable_sno_tables = []
    observable_saint_ex_tables = []

    for i in range(len(ing_egr)):
        date = Time(Time(Time(Time(ing_egr[i][0]).iso, out_subfmt='date').iso).jd + 0.625, format='jd')
        observable_sso_tables.append(observability_table(constraints_predictions, charge_observatories('SSO')[0],
                                                         target, time_range=Time([date, date + 1]),
                                                         time_grid_resolution=0.5 * u.hour))

        observable_sno_tables.append(observability_table(constraints_predictions, charge_observatories('SNO')[0],
                                                         target, time_range=Time([date, date + 1]),
                                                         time_grid_resolution=0.5 * u.hour))

        observable_saint_ex_tables.append(observability_table(constraints_predictions_stx,
                                                              charge_observatories('Saint-Ex')[0],
                                                              target, time_range=Time([date, date + 1]),
                                                              time_grid_resolution=0.5 * u.hour))

    observable_sso_table = vstack(observable_sso_tables)
    observable_sno_table = vstack(observable_sno_tables)
    observable_saint_ex_table = vstack(observable_saint_ex_tables)

    df = pd.DataFrame(data=ing_egr.sort().iso, index=[name] * len(ing_egr), columns=["Ingress", "Egress"])

    df['mid transit'] = mid_transit_timing

    df['mid transit JD'] = np.round(mid_transit_timing_jd, 3)

    df['Observable SSO'] = observable_sso[0]

    df['Hours observable SSO (h)'] = observable_sso_table['fraction of time observable'] * 24  # *u.hour

    df['Observable SNO'] = observable_sno[0]

    df['Hours observable SNO (h)'] = observable_sno_table['fraction of time observable'] * 24  # *u.hour

    df['Observable Saint-Ex'] = observable_saintex[0]

    df['Hours observable Saint-Ex (h)'] = observable_saint_ex_table['fraction of time observable'] * 24  # *u.hour

    df['Observable TN Oukaimeden'] = observable_tn_oukaimeden[0]

    df['Observable TS La Silla'] = observable_ts_la_silla[0]

    return df