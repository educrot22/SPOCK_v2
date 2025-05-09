#!/usr/bin/python
import subprocess
import os
from astropy.time import Time
from SPOCK import pwd_HUB, pwd_appcs, pwd_SNO_Reduc1, path_spock

import paramiko

# Load the private key for Cambridge archive
#private_key_path = os.path.expanduser("~/.ssh/id_rsa_cambridge")
#private_key = paramiko.RSAKey.from_private_key_file(private_key_path)

# Create the SSH clients for Cambridge archive, SSO hub, and SNO hub
ssh_client_cambridge = paramiko.SSHClient()
#ssh_client_cambridge.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_client_cambridge.load_system_host_keys()

ssh_client_SSO_hub = paramiko.SSHClient()
ssh_client_SSO_hub.load_system_host_keys()

ssh_client_SNO_hub = paramiko.SSHClient()
ssh_client_SNO_hub.load_system_host_keys()


# Useful function to sftp folders
def upload_folder(sftp, local_folder, remote_folder):
    """
    Uploads a folder and its contents to the remote server using SFTP.

    :param sftp: The active SFTP connection.
    :param local_folder: The local folder path to upload.
    :param remote_folder: The remote folder path where the files should be uploaded.
    """
    # Ensure the remote folder exists
    try:
        sftp.stat(remote_folder)
    except FileNotFoundError:
        print(f"Creating remote folder: {remote_folder}")
        sftp.mkdir(remote_folder)

    # Walk through the local folder
    for root, dirs, files in os.walk(local_folder):
        # Calculate the relative path to maintain folder structure
        rel_path = os.path.relpath(root, local_folder)
        remote_path = os.path.join(remote_folder, rel_path).replace("\\", "/")

        # Ensure the remote path exists
        try:
            sftp.stat(remote_path)
        except FileNotFoundError:
            print(f"Creating remote folder: {remote_path}")
            sftp.mkdir(remote_path)

        # Upload files
        for file in files:
            local_file = os.path.join(root, file)
            remote_file = os.path.join(remote_path, file).replace("\\", "/")
            sftp.put(local_file, remote_file)

def upload_np_euro(t_now, nb_days):
    telescope = "Europa"
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    # Connect to the remote server
    try:
        #ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', pkey=private_key)
        ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', password=pwd_appcs)
        ssh_client_SSO_hub.connect('172.16.4.169', username='speculoos', password=pwd_HUB)
        print("Connected to the servers!")
        # Open SFTP sessions
        sftp_cambridge = ssh_client_cambridge.open_sftp()
        sftp_SSO_hub = ssh_client_SSO_hub.open_sftp()

        for nb_day in range(0, nb_days):
            t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

            # upload on Cambridge server
            # Plans by date
            path_database_plans = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/', telescope,
                                               'schedule', 'Plans_by_date', str(t_now))
            path_plans = os.path.join(path_spock + '/DATABASE/', telescope,
                                      'Plans_by_date/', str(t_now))
            # Upload the file
            upload_folder(sftp_cambridge, path_plans, path_database_plans)

            print('----->', t_now, 'Plans uploaded on the Cambridge server')

            # Archive_night_blocks
            night_block = 'night_blocks_Europa_'+str(t_now)+'.txt'
            path_database_nightb = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Archive_night_blocks', night_block)
            path_night_blocks = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Archive_night_blocks/', night_block)
            sftp_cambridge.put(path_night_blocks, path_database_nightb)
            print('----->', t_now, 'Night plans uploaded on the Cambridge server')

            # zip_files
            zip_file = str(t_now) + '.zip'
            path_database_zip_file = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                   telescope, 'schedule', 'Zip_files', zip_file)
            path_local_zip_file = os.path.join(path_spock + '/DATABASE/', telescope,
                                               'Zip_files/', zip_file)
            sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
            path_hub_zip_files = os.path.normpath(os.path.join("/home/speculoos/Plans_scheduler/", telescope, "Plans", zip_file))
            #print(f"Uploading from local: {path_local_zip_file} to remote: {path_hub_zip_files}")
            sftp_SSO_hub.put(path_local_zip_file, path_hub_zip_files)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the HUB for', telescope)

            # Astra
            csv_file = telescope + '_' + str(t_now) + '.csv'
            path_database_astra = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                               telescope,
                                               'schedule', 'Astra', csv_file)
            path_local_astra = os.path.join(path_spock + '/DATABASE/', telescope,
                                            'Astra/', csv_file)
            sftp_cambridge.put(path_local_astra, path_database_astra)
            print('----->', t_now, 'Astra folder updated on the Cambridge server')

            #path_hub_astra = os.path.normpath(
            #    os.path.join("/home/speculoos/Plans_scheduler/", telescope, 'Astra/', csv_file))
            #sftp_SSO_hub.put(path_local_astra, path_hub_astra)
            #print(f"Uploading from local: {path_local_astra} to remote: {path_hub_astra}")
            #print('----->', t_now, 'Astra folder updated on the HUB for', telescope)

        #    # upload on HUB
        #    # cam server to local
        #    path_database_zip_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Zip_files', str(t_now) + '.zip')
        #    path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Zip_files/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_zip_file,
        #                          path_local_zip_folder])
        #    # Astra cam server to local
        #    path_database_astra_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Astra', 'Europa_' + str(t_now) + '.csv')
        #    path_local_astra_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_astra_file,
        #                          path_local_astra_folder])

        #    # Astra Local to reduction computer
        #    path_local_astra_file = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/', 'Europa_'+str(t_now)+'.csv')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_local_astra_file,
        #                          'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Europa/Astra/'])
        #    print('----->', t_now, 'Astra folder updated on the HUB for Europa')

    except Exception as e:
        print(f"Failed to connect: {e}")

    finally:
        ssh_client_cambridge.close()
        ssh_client_SSO_hub.close()

def upload_np_calli(t_now, nb_days):
    telescope = 'Callisto'
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    # Connect to the remote server
    try:
        #ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', pkey=private_key)
        ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', password=pwd_appcs)
        ssh_client_SSO_hub.connect('172.16.4.169', username='speculoos', password=pwd_HUB)
        print("Connected to the servers!")
        # Open SFTP sessions
        sftp_cambridge = ssh_client_cambridge.open_sftp()
        sftp_SSO_hub = ssh_client_SSO_hub.open_sftp()

        for nb_day in range(0, nb_days):
            t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

            # upload on Cambridge server
            # Plans by date
            path_database_plans = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/', telescope,
                                               'schedule', 'Plans_by_date', str(t_now))
            path_plans = os.path.join(path_spock + '/DATABASE/', telescope,
                                      'Plans_by_date/', str(t_now))
            # Upload the file
            upload_folder(sftp_cambridge, path_plans, path_database_plans)

            print('----->', t_now, 'Plans uploaded on the Cambridge server')

            # Archive_night_blocks
            night_block = 'night_blocks_'+telescope+'_'+str(t_now)+'.txt'
            path_database_nightb = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Archive_night_blocks', night_block)
            path_night_blocks = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Archive_night_blocks/', night_block)
            sftp_cambridge.put(path_night_blocks, path_database_nightb)
            print('----->', t_now, 'Night plans uploaded on the Cambridge server')

            # zip_files
            zip_file = str(t_now) + '.zip'
            path_database_zip_file = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                   telescope, 'schedule', 'Zip_files', zip_file)
            path_local_zip_file = os.path.join(path_spock + '/DATABASE/', telescope,
                                               'Zip_files/', zip_file)
            sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')

            # Astra
            csv_file = telescope+'_'+str(t_now)+'.csv'
            path_database_astra = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Astra', csv_file)
            path_local_astra = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Astra/', csv_file)
            sftp_cambridge.put(path_local_astra, path_database_astra)
            print('----->', t_now, 'Astra folder updated on the Cambridge server')

            path_hub_astra = os.path.normpath(os.path.join("/home/speculoos/Plans_scheduler/", telescope, 'Astra/', csv_file))
            sftp_SSO_hub.put(path_local_astra, path_hub_astra)
            #print(f"Uploading from local: {path_local_astra} to remote: {path_hub_astra}")
            print('----->', t_now, 'Astra folder updated on the HUB for Callisto')

        #    # upload on HUB
        #    # cam server to local
        #    path_database_zip_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Zip_files', str(t_now) + '.zip')
        #    path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Zip_files/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_zip_file,
        #                          path_local_zip_folder])
        #    # Astra cam server to local
        #    path_database_astra_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Astra', 'Europa_' + str(t_now) + '.csv')
        #    path_local_astra_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_astra_file,
        #                          path_local_astra_folder])

        #    # Astra Local to reduction computer
        #    path_local_astra_file = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/', 'Europa_'+str(t_now)+'.csv')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_local_astra_file,
        #                          'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Europa/Astra/'])
        #    print('----->', t_now, 'Astra folder updated on the HUB for Europa')

    except Exception as e:
        print(f"Failed to connect: {e}")

    finally:
        ssh_client_cambridge.close()
        ssh_client_SSO_hub.close()




def upload_np_io(t_now, nb_days):
    telescope = 'Io'
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    # Connect to the remote server
    try:
        #ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', pkey=private_key)
        ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', password=pwd_appcs)
        ssh_client_SSO_hub.connect('172.16.4.169', username='speculoos', password=pwd_HUB)
        print("Connected to the servers!")
        # Open SFTP sessions
        sftp_cambridge = ssh_client_cambridge.open_sftp()
        sftp_SSO_hub = ssh_client_SSO_hub.open_sftp()

        for nb_day in range(0, nb_days):
            t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

            # upload on Cambridge server
            # Plans by date
            path_database_plans = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/', telescope,
                                               'schedule', 'Plans_by_date', str(t_now))
            path_plans = os.path.join(path_spock + '/DATABASE/', telescope,
                                      'Plans_by_date/', str(t_now))
            # Upload the file
            upload_folder(sftp_cambridge, path_plans, path_database_plans)

            print('----->', t_now, 'Plans uploaded on the Cambridge server')

            # Archive_night_blocks
            night_block = 'night_blocks_'+telescope+'_'+str(t_now)+'.txt'
            path_database_nightb = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Archive_night_blocks', night_block)
            path_night_blocks = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Archive_night_blocks/', night_block)
            sftp_cambridge.put(path_night_blocks, path_database_nightb)
            print('----->', t_now, 'Night plans uploaded on the Cambridge server')

            # zip_files
            zip_file = str(t_now) + '.zip'
            path_database_zip_file = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                   telescope, 'schedule', 'Zip_files', zip_file)
            path_local_zip_file = os.path.join(path_spock + '/DATABASE/', telescope,
                                               'Zip_files/', zip_file)
            sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
            path_hub_zip_files = os.path.normpath(os.path.join("/home/speculoos/Plans_scheduler/", telescope, "Plans", zip_file))
            #print(f"Uploading from local: {path_local_zip_file} to remote: {path_hub_zip_files}")
            sftp_SSO_hub.put(path_local_zip_file, path_hub_zip_files)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the HUB for', telescope)

            # Astra
            csv_file = telescope + '_' + str(t_now) + '.csv'
            path_database_astra = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                               telescope,
                                               'schedule', 'Astra', csv_file)
            path_local_astra = os.path.join(path_spock + '/DATABASE/', telescope,
                                            'Astra/', csv_file)
            sftp_cambridge.put(path_local_astra, path_database_astra)
            print('----->', t_now, 'Astra folder updated on the Cambridge server')

            #path_hub_astra = os.path.normpath(
            #    os.path.join("/home/speculoos/Plans_scheduler/", telescope, 'Astra/', csv_file))
            #sftp_SSO_hub.put(path_local_astra, path_hub_astra)
            #print(f"Uploading from local: {path_local_astra} to remote: {path_hub_astra}")
            #print('----->', t_now, 'Astra folder updated on the HUB for', telescope)

        #    # upload on HUB
        #    # cam server to local
        #    path_database_zip_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Zip_files', str(t_now) + '.zip')
        #    path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Zip_files/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_zip_file,
        #                          path_local_zip_folder])
        #    # Astra cam server to local
        #    path_database_astra_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Astra', 'Europa_' + str(t_now) + '.csv')
        #    path_local_astra_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_astra_file,
        #                          path_local_astra_folder])

        #    # Astra Local to reduction computer
        #    path_local_astra_file = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/', 'Europa_'+str(t_now)+'.csv')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_local_astra_file,
        #                          'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Europa/Astra/'])
        #    print('----->', t_now, 'Astra folder updated on the HUB for Europa')

    except Exception as e:
        print(f"Failed to connect: {e}")

    finally:
        ssh_client_cambridge.close()
        ssh_client_SSO_hub.close()


def upload_np_gany(t_now, nb_days):
    telescope = 'Ganymede'
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    # Connect to the remote server
    try:
        #ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', pkey=private_key)
        ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', password=pwd_appcs)
        ssh_client_SSO_hub.connect('172.16.4.169', username='speculoos', password=pwd_HUB)
        print("Connected to the servers!")
        # Open SFTP sessions
        sftp_cambridge = ssh_client_cambridge.open_sftp()
        sftp_SSO_hub = ssh_client_SSO_hub.open_sftp()

        for nb_day in range(0, nb_days):
            t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

            # upload on Cambridge server
            # Plans by date
            path_database_plans = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/', telescope,
                                               'schedule', 'Plans_by_date', str(t_now))
            path_plans = os.path.join(path_spock + '/DATABASE/', telescope,
                                      'Plans_by_date/', str(t_now))
            # Upload the file
            upload_folder(sftp_cambridge, path_plans, path_database_plans)

            print('----->', t_now, 'Plans uploaded on the Cambridge server')

            # Archive_night_blocks
            night_block = 'night_blocks_'+telescope+'_'+str(t_now)+'.txt'
            path_database_nightb = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Archive_night_blocks', night_block)
            path_night_blocks = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Archive_night_blocks/', night_block)
            sftp_cambridge.put(path_night_blocks, path_database_nightb)
            print('----->', t_now, 'Night plans uploaded on the Cambridge server')

            # zip_files
            zip_file = str(t_now) + '.zip'
            path_database_zip_file = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                   telescope, 'schedule', 'Zip_files', zip_file)
            path_local_zip_file = os.path.join(path_spock + '/DATABASE/', telescope,
                                               'Zip_files/', zip_file)
            sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
            path_hub_zip_files = os.path.normpath(os.path.join("/home/speculoos/Plans_scheduler/", telescope, "Plans", zip_file))
            #print(f"Uploading from local: {path_local_zip_file} to remote: {path_hub_zip_files}")
            sftp_SSO_hub.put(path_local_zip_file, path_hub_zip_files)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the HUB for', telescope)

            # Astra
            csv_file = telescope + '_' + str(t_now) + '.csv'
            path_database_astra = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                               telescope,
                                               'schedule', 'Astra', csv_file)
            path_local_astra = os.path.join(path_spock + '/DATABASE/', telescope,
                                            'Astra/', csv_file)
            sftp_cambridge.put(path_local_astra, path_database_astra)
            print('----->', t_now, 'Astra folder updated on the Cambridge server')

            path_hub_astra = os.path.normpath(
                os.path.join("/home/speculoos/Plans_scheduler/", telescope, 'Astra/', csv_file))
            sftp_SSO_hub.put(path_local_astra, path_hub_astra)
            #print(f"Uploading from local: {path_local_astra} to remote: {path_hub_astra}")
            print('----->', t_now, 'Astra folder updated on the HUB for', telescope)

        #    # upload on HUB
        #    # cam server to local
        #    path_database_zip_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Zip_files', str(t_now) + '.zip')
        #    path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Zip_files/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_zip_file,
        #                          path_local_zip_folder])
        #    # Astra cam server to local
        #    path_database_astra_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Astra', 'Europa_' + str(t_now) + '.csv')
        #    path_local_astra_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_astra_file,
        #                          path_local_astra_folder])

        #    # Astra Local to reduction computer
        #    path_local_astra_file = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/', 'Europa_'+str(t_now)+'.csv')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_local_astra_file,
        #                          'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Europa/Astra/'])
        #    print('----->', t_now, 'Astra folder updated on the HUB for Europa')

    except Exception as e:
        print(f"Failed to connect: {e}")

    finally:
        ssh_client_cambridge.close()
        ssh_client_SSO_hub.close()

def upload_np_artemis(t_now, nb_days):
    telescope = 'Artemis'
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    # Connect to the remote server
    try:
        #ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', pkey=private_key)
        ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', password=pwd_appcs)
        ssh_client_SNO_hub.connect('172.16.3.11', username='speculoos', password=pwd_SNO_Reduc1)
        print("Connected to the servers!")
        # Open SFTP sessions
        sftp_cambridge = ssh_client_cambridge.open_sftp()
        sftp_SNO_hub = ssh_client_SNO_hub.open_sftp()

        for nb_day in range(0, nb_days):
            t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

            # upload on Cambridge server
            # Plans by date
            path_database_plans = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/', telescope,
                                               'schedule', 'Plans_by_date', str(t_now))
            path_plans = os.path.join(path_spock + '/DATABASE/', telescope,
                                      'Plans_by_date/', str(t_now))
            # Upload the file
            upload_folder(sftp_cambridge, path_plans, path_database_plans)

            print('----->', t_now, 'Plans uploaded on the Cambridge server')

            # Archive_night_blocks
            night_block = 'night_blocks_'+telescope+'_'+str(t_now)+'.txt'
            path_database_nightb = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Archive_night_blocks', night_block)
            path_night_blocks = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Archive_night_blocks/', night_block)
            sftp_cambridge.put(path_night_blocks, path_database_nightb)
            print('----->', t_now, 'Night plans uploaded on the Cambridge server')

            # zip_files
            zip_file = str(t_now) + '.zip'
            path_database_zip_file = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                   telescope, 'schedule', 'Zip_files', zip_file)
            path_local_zip_file = os.path.join(path_spock + '/DATABASE/', telescope,
                                               'Zip_files/', zip_file)
            sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
            path_hub_zip_files = os.path.join("/home/speculoos/Desktop/Plans/", zip_file)
            sftp_SNO_hub.put(path_local_zip_file, path_hub_zip_files)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the HUB for', telescope)

        #    # upload on HUB
        #    # cam server to local
        #    path_database_zip_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Zip_files', str(t_now) + '.zip')
        #    path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Zip_files/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_zip_file,
        #                          path_local_zip_folder])
        #    # Astra cam server to local
        #    path_database_astra_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Astra', 'Europa_' + str(t_now) + '.csv')
        #    path_local_astra_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_astra_file,
        #                          path_local_astra_folder])

        #    # Astra Local to reduction computer
        #    path_local_astra_file = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/', 'Europa_'+str(t_now)+'.csv')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_local_astra_file,
        #                          'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Europa/Astra/'])
        #    print('----->', t_now, 'Astra folder updated on the HUB for Europa')

    except Exception as e:
        print(f"Failed to connect: {e}")

    finally:
        ssh_client_cambridge.close()
        ssh_client_SNO_hub.close()


def upload_np_ts(t_now, nb_days):
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    for nb_day in range(0, nb_days):
        t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

        # upload on Cam server
        path_database = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
                                     'TS_La_Silla', 'schedule')
        # Plans
        path_database_plans = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
                                           'TS_La_Silla', 'schedule', 'Plans_by_date')
        path_plans = os.path.join(path_spock + '/DATABASE/', 'TS_La_Silla',
                                  'Plans_by_date/',str(t_now))
        subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_plans,path_database_plans])
        print('----->', t_now, 'Plans uploaded on the Cambridge server')

        # Archive night blocks
        path_database_nightb = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
                                            'TS_La_Silla', 'schedule', 'Archive_night_blocks')
        path_night_blocks = os.path.join(path_spock + '/DATABASE/', 'TS_La_Silla',
                                         'Archive_night_blocks/','night_blocks_TS_La_Silla_'+str(t_now)+'.txt')
        subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp", path_night_blocks, path_database_nightb])
        print('----->', t_now, 'Night plans uploaded on the Cambridge server')


def upload_np_tn(t_now, nb_days):
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    for nb_day in range(0, nb_days):
        t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

        # upload on Cam server
        path_database = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
                                     'TN_Oukaimeden', 'schedule')
        # Plans
        path_database_plans = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
                                           'TN_Oukaimeden', 'schedule', 'Plans_by_date')
        path_plans = os.path.join(path_spock + '/DATABASE/', 'TN_Oukaimeden',
                                  'Plans_by_date/',str(t_now))
        subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_plans,path_database_plans])
        print('----->', t_now, 'Plans uploaded on the Cambridge server')

        # Archive night blocks
        path_database_nightb = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
                                            'TN_Oukaimeden', 'schedule', 'Archive_night_blocks')
        path_night_blocks = os.path.join(path_spock + '/DATABASE/', 'TN_Oukaimeden',
                                         'Archive_night_blocks/','night_blocks_TN_Oukaimeden_'+str(t_now)+'.txt')
        subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp", path_night_blocks, path_database_nightb])
        print('----->', t_now, 'Night plans uploaded on the Cambridge server')

def upload_np_saint_ex(t_now, nb_days):
    telescope = 'Saint-Ex'
    t0 = Time(t_now)
    dt = Time('2018-01-02 00:00:00', scale='tcg')-Time('2018-01-01 00:00:00', scale='tcg')  # 1 day

    # Connect to the remote server
    try:
        #ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', pkey=private_key)
        ssh_client_cambridge.connect('appcs.ra.phy.cam.ac.uk', username='speculoos', password=pwd_appcs)
        print("Connected to the servers!")
        # Open SFTP sessions
        sftp_cambridge = ssh_client_cambridge.open_sftp()

        for nb_day in range(0, nb_days):
            t_now = Time(t0+nb_day*dt, scale='utc', out_subfmt='date').iso

            # upload on Cambridge server
            # Plans by date
            path_database_plans = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/', telescope,
                                               'schedule', 'Plans_by_date', str(t_now))
            path_plans = os.path.join(path_spock + '/DATABASE/', telescope,
                                      'Plans_by_date/', str(t_now))
            # Upload the file
            upload_folder(sftp_cambridge, path_plans, path_database_plans)

            print('----->', t_now, 'Plans uploaded on the Cambridge server')

            # Archive_night_blocks
            night_block = 'night_blocks_'+telescope+'_'+str(t_now)+'.txt'
            path_database_nightb = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                telescope,
                                                'schedule', 'Archive_night_blocks', night_block)
            path_night_blocks = os.path.join(path_spock + '/DATABASE/', telescope,
                                             'Archive_night_blocks/', night_block)
            sftp_cambridge.put(path_night_blocks, path_database_nightb)
            print('----->', t_now, 'Night plans uploaded on the Cambridge server')

            # zip_files
            zip_file = str(t_now) + '.zip'
            path_database_zip_file = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                                   telescope, 'schedule', 'Zip_files', zip_file)
            path_local_zip_file = os.path.join(path_spock + '/DATABASE/', telescope,
                                               'Zip_files/', zip_file)
            sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
            print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')

            # Astra
            csv_file = telescope + '_' + str(t_now) + '.csv'
            path_database_astra = os.path.join('../../appct/data/SPECULOOSPipeline/Observations/',
                                               telescope,
                                               'schedule', 'Astra', csv_file)
            path_local_astra = os.path.join(path_spock + '/DATABASE/', telescope,
                                            'Astra/', csv_file)
            sftp_cambridge.put(path_local_astra, path_database_astra)
            print('----->', t_now, 'Astra folder updated on the Cambridge server')

        #    # upload on HUB
        #    # cam server to local
        #    path_database_zip_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Zip_files', str(t_now) + '.zip')
        #    path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Zip_files/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_zip_file,
        #                          path_local_zip_folder])
        #    # Astra cam server to local
        #    path_database_astra_file = os.path.join(
        #        'speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
        #        'Europa', 'schedule', 'Astra', 'Europa_' + str(t_now) + '.csv')
        #    path_local_astra_folder = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_database_astra_file,
        #                          path_local_astra_folder])

        #    # Astra Local to reduction computer
        #    path_local_astra_file = os.path.join(path_spock + '/DATABASE/', 'Europa', 'Astra/', 'Europa_'+str(t_now)+'.csv')
        #    p = subprocess.Popen(["sshpass", "-p", pwd_HUB, "scp", path_local_astra_file,
        #                          'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Europa/Astra/'])
        #    print('----->', t_now, 'Astra folder updated on the HUB for Europa')

    except Exception as e:
        print(f"Failed to connect: {e}")

    finally:
        ssh_client_cambridge.close()


# def upload_np_calli_old(t_now,nb_days):
#     t0=Time(t_now)
#     dt=Time('2018-01-02 00:00:00',scale='tcg')-Time('2018-01-01 00:00:00',scale='tcg') #1 day
#
#     for nb_day in range(0,nb_days):
#         t_now=Time(t0+ nb_day*dt, scale='utc', out_subfmt='date').iso
#
#         # upload on Cambridge server
#         ## Plans by date
#         path_database_plans = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Callisto',
#                                      'schedule','Plans_by_date')
#         path_plans = os.path.join(path_spock + '/DATABASE/', 'Callisto',
#                                   'Plans_by_date/',str(t_now))
#         subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_plans,path_database_plans])
#         print('----->', t_now, 'Plans uploaded on the Cambridge server')
#
#         ## Archive_night_blocks
#         path_database_nightb = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
#                                            'Callisto',
#                                            'schedule', 'Archive_night_blocks')
#         path_night_blocks = os.path.join(path_spock + '/DATABASE/', 'Callisto',
#                                          'Archive_night_blocks/','night_blocks_Callisto_'+str(t_now)+'.txt')
#         subprocess.Popen(["sshpass", "-p", pwd_appcs , "scp", path_night_blocks, path_database_nightb])
#         print('----->', t_now, 'Night plans uploaded on the Cambridge server')
#
#         ## zip_files
#         path_database_zip_files = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Callisto',
#                                      'schedule','Zip_files')
#         path_local_zip_file = os.path.join(path_spock + '/DATABASE/', 'Callisto',
#                                            'Zip_files/', str(t_now) + '.zip')
#         subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_local_zip_file,path_database_zip_files])
#         print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
#
#         #upload on data reduction computer
#         ## cam server to local
#         path_database_zip_file = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Callisto',
#                                      'schedule','Zip_files',str(t_now)+'.zip')
#         path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Callisto',
#                                   'Zip_files/')
#         p = subprocess.Popen(["sshpass", "-p", pwd_HUB,"scp", path_database_zip_file,path_local_zip_folder])
#         ## Local to reduction computer
#         p = subprocess.Popen(["sshpass", "-p", pwd_HUB,"scp", path_local_zip_file, 'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Callisto/Plans/'])
#         print('----->',t_now,'Zip Plans_by_dates folder uploaded on the HUB for Callisto')

# def upload_np_io_old(t_now,nb_days):
#     t0=Time(t_now)
#     dt=Time('2018-01-02 00:00:00',scale='tcg')-Time('2018-01-01 00:00:00',scale='tcg') #1 day
#
#     for nb_day in range(0,nb_days):
#         t_now=Time(t0+ nb_day*dt, scale='utc', out_subfmt='date').iso
#
#         # upload on Cambridge server
#         ## Plans by date
#         path_database_plans = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Io',
#                                      'schedule','Plans_by_date')
#         path_plans = os.path.join(path_spock + '/DATABASE/', 'Io',
#                                   'Plans_by_date/',str(t_now))
#         subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_plans,path_database_plans])
#         print('----->', t_now, 'Plans uploaded on the Cambridge server')
#
#         ## Archive_night_blocks
#         path_database_nightb = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
#                                            'Io',
#                                            'schedule', 'Archive_night_blocks')
#         path_night_blocks = os.path.join(path_spock + '/DATABASE/', 'Io',
#                                          'Archive_night_blocks/','night_blocks_Io_'+str(t_now)+'.txt')
#         subprocess.Popen(["sshpass", "-p", pwd_appcs , "scp", path_night_blocks, path_database_nightb])
#         print('----->', t_now, 'Night plans uploaded on the Cambridge server')
#
#         ## zip_files
#         path_database_zip_files = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Io',
#                                      'schedule','Zip_files')
#         path_local_zip_file = os.path.join(path_spock + '/DATABASE/', 'Io',
#                                            'Zip_files/', str(t_now) + '.zip')
#         subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_local_zip_file,path_database_zip_files])
#         print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
#
#         #upload on data reduction computer
#         ## cam server to local
#         path_database_zip_file = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Io',
#                                      'schedule','Zip_files',str(t_now)+'.zip')
#         path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Io',
#                                   'Zip_files/')
#         p = subprocess.Popen(["sshpass", "-p", pwd_HUB,"scp", path_database_zip_file,path_local_zip_folder])
#         ## Local to reduction computer
#         p = subprocess.Popen(["sshpass", "-p", pwd_HUB,"scp", path_local_zip_file, 'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Io/Plans/'])
#         print('----->',t_now,'Zip Plans_by_dates folder uploaded on the HUB for Io')
# def upload_np_gany(t_now,nb_days):
#     t0=Time(t_now)
#     dt=Time('2018-01-02 00:00:00',scale='tcg')-Time('2018-01-01 00:00:00',scale='tcg') #1 day
#
#     for nb_day in range(0,nb_days):
#         t_now=Time(t0+ nb_day*dt, scale='utc', out_subfmt='date').iso
#
#         # upload on Cambridge server
#         ## Plans by date
#         path_database_plans = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Ganymede',
#                                      'schedule','Plans_by_date')
#         path_plans = os.path.join(path_spock + '/DATABASE/', 'Ganymede',
#                                   'Plans_by_date/',str(t_now))
#         subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_plans,path_database_plans])
#         print('----->', t_now, 'Plans uploaded on the Cambridge server')
#
#         ## Archive_night_blocks
#         path_database_nightb = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/',
#                                            'Ganymede',
#                                            'schedule', 'Archive_night_blocks')
#         path_night_blocks = os.path.join(path_spock + '/DATABASE/', 'Ganymede',
#                                          'Archive_night_blocks/','night_blocks_Ganymede_'+str(t_now)+'.txt')
#         subprocess.Popen(["sshpass", "-p", pwd_appcs , "scp", path_night_blocks, path_database_nightb])
#         print('----->', t_now, 'Night plans uploaded on the Cambridge server')
#
#         ## zip_files
#         path_database_zip_files = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Ganymede',
#                                      'schedule','Zip_files')
#         path_local_zip_file = os.path.join(path_spock + '/DATABASE/', 'Ganymede',
#                                            'Zip_files/', str(t_now) + '.zip')
#         subprocess.Popen(["sshpass", "-p", pwd_appcs, "scp","-r",path_local_zip_file,path_database_zip_files])
#         print('----->', t_now, 'Zip Plans_by_dates folder uploaded on the Cambridge server')
#
#         #upload on data reduction computer
#         ## cam server to local
#         path_database_zip_file = os.path.join('speculoos@appcs.ra.phy.cam.ac.uk:/appct/data/SPECULOOSPipeline/Observations/', 'Ganymede',
#                                      'schedule','Zip_files',str(t_now)+'.zip')
#         path_local_zip_folder = os.path.join(path_spock + '/DATABASE/', 'Ganymede',
#                                   'Zip_files/')
#         p = subprocess.Popen(["sshpass", "-p", pwd_HUB,"scp", path_database_zip_file,path_local_zip_folder])
#         ## Local to reduction computer
#         p = subprocess.Popen(["sshpass", "-p", pwd_HUB,"scp", path_local_zip_file, 'speculoos@172.16.4.169:/home/speculoos/Plans_scheduler/Ganymede/Plans/'])
#         print('----->',t_now,'Zip Plans_by_dates folder uploaded on the HUB for Ganymede')
