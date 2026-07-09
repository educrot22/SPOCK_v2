#!/usr/bin/python
import subprocess
import os
from astropy.time import Time
from SPOCK import pwd_HUB, pwd_appcs, pwd_SNO_Reduc1, path_spock
import traceback
from colorama import Fore
import threading
import socket

import paramiko

# Load the private key for Cambridge archive
# private_key_path = os.path.expanduser("~/.ssh/id_rsa_cambridge")
# private_key = paramiko.RSAKey.from_private_key_file(private_key_path)

# Create the SSH clients for Cambridge archive, SSO hub, and SNO hub
ssh_client_cambridge = paramiko.SSHClient()
ssh_client_cambridge.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_client_cambridge.load_system_host_keys()

ssh_client_SSO_hub = paramiko.SSHClient()
ssh_client_SSO_hub.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh_client_SSO_hub.load_system_host_keys()

ssh_client_SNO_hub = paramiko.SSHClient()
ssh_client_SNO_hub.set_missing_host_key_policy(paramiko.AutoAddPolicy())
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


def test_connections():
    """
    Test SSH/SFTP connections to all servers. Use this to diagnose connectivity issues.
    Tests in phases: Ping → SSH → SFTP
    Returns a dict with connection status for each server.
    """
    import socket
    
    results = {
        'Cambridge': {'ping': False, 'ssh': False, 'sftp': False, 'client': None},
        'SSO_hub': {'ping': False, 'ssh': False, 'sftp': False, 'client': None},
        'SNO_hub': {'ping': False, 'ssh': False, 'sftp': False, 'client': None},
    }
    
    servers = {
        'Cambridge': ('appcs.ra.phy.cam.ac.uk', pwd_appcs),
        'SSO_hub': ('172.16.4.169', pwd_HUB),
        'SNO_hub': ('10.16.83.11', pwd_SNO_Reduc1),
    }
    
    print(Fore.CYAN + '=' * 70 + Fore.BLACK)
    print(Fore.CYAN + 'SPOCK Connection Diagnostic (3-Phase Test)' + Fore.BLACK)
    print(Fore.CYAN + '=' * 70 + Fore.BLACK)
    
    # ========== PHASE 1: PING ==========
    print(Fore.CYAN + '\n[PHASE 1] Testing Ping (Port 22 reachability)...' + Fore.BLACK)
    for server_name, (host, pwd) in servers.items():
        print(f'  Testing {server_name} ({host})...')
        try:
            sock = socket.create_connection((host, 22), timeout=5)
            sock.close()
            print(Fore.GREEN + f'    ✓ Ping: SUCCESS' + Fore.BLACK)
            results[server_name]['ping'] = True
        except socket.timeout:
            print(Fore.RED + f'    ✗ Ping: TIMEOUT (5s) - Network unreachable or blocked' + Fore.BLACK)
            results[server_name]['ping'] = False
        except socket.error as e:
            print(Fore.RED + f'    ✗ Ping: FAILED - {e}' + Fore.BLACK)
            results[server_name]['ping'] = False
    
    # ========== PHASE 2: SSH ==========
    print(Fore.CYAN + '\n[PHASE 2] Testing SSH Authentication...' + Fore.BLACK)
    for server_name, (host, pwd) in servers.items():
        if not results[server_name]['ping']:
            print(f'  {server_name}: Skipped (ping failed)')
            continue
        
        print(f'  Testing {server_name} ({host})...')
        test_client = paramiko.SSHClient()
        test_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        test_client.load_system_host_keys()
        try:
            test_client.connect(host, username="speculoos", password=pwd, timeout=10, banner_timeout=10)
            print(Fore.GREEN + f'    ✓ SSH: SUCCESS' + Fore.BLACK)
            results[server_name]['ssh'] = True
            results[server_name]['client'] = test_client  # Keep for SFTP phase
        except Exception as e:
            print(Fore.RED + f'    ✗ SSH: FAILED - {e}' + Fore.BLACK)
            results[server_name]['ssh'] = False
            test_client.close()
    
    # ========== PHASE 3: SFTP ==========
    print(Fore.CYAN + '\n[PHASE 3] Testing SFTP Session (with 5s timeout)...' + Fore.BLACK)
    for server_name in servers.keys():
        if not results[server_name]['ssh']:
            print(f'  {server_name}: Skipped (SSH failed)')
            continue
        
        print(f'  Testing {server_name} SFTP...')
        test_client = results[server_name]['client']
        
        # Use threading to enforce timeout on open_sftp
        sftp_result = {'sftp': None, 'error': None}
        
        def open_sftp_with_timeout():
            try:
                # Set socket timeout on transport before opening SFTP
                transport = test_client.get_transport()
                if transport and transport.sock:
                    transport.sock.settimeout(5)
                
                print(f'    Opening SFTP channel (5s timeout)...')
                sftp_result['sftp'] = test_client.open_sftp()
            except Exception as e:
                sftp_result['error'] = e
        
        sftp_thread = threading.Thread(target=open_sftp_with_timeout, daemon=True)
        sftp_thread.start()
        sftp_thread.join(timeout=7)  # Give it 7 seconds (5s + buffer)
        
        if sftp_thread.is_alive():
            print(Fore.RED + f'    ✗ SFTP: TIMEOUT (5s) - open_sftp() hanging, possible network issue' + Fore.BLACK)
            results[server_name]['sftp'] = False
            try:
                test_client.close()
            except:
                pass
            continue
        
        if sftp_result['error']:
            print(Fore.RED + f'    ✗ SFTP: FAILED - {sftp_result["error"]}' + Fore.BLACK)
            results[server_name]['sftp'] = False
            try:
                test_client.close()
            except:
                pass
            continue
        
        if not sftp_result['sftp']:
            print(Fore.RED + f'    ✗ SFTP: FAILED - Could not open SFTP session' + Fore.BLACK)
            results[server_name]['sftp'] = False
            try:
                test_client.close()
            except:
                pass
            continue
        
        # SFTP opened successfully, test with listdir
        try:
            test_sftp = sftp_result['sftp']
            test_sftp.get_channel().settimeout(5)
            
            print(f'    Testing SFTP listdir command...')
            test_sftp.listdir_attr('.')
            
            print(Fore.GREEN + f'    ✓ SFTP: SUCCESS' + Fore.BLACK)
            results[server_name]['sftp'] = True
            test_sftp.close()
        except socket.timeout:
            print(Fore.RED + f'    ✗ SFTP: TIMEOUT during listdir (5s)' + Fore.BLACK)
            results[server_name]['sftp'] = False
        except Exception as e:
            print(Fore.RED + f'    ✗ SFTP: FAILED during listdir - {e}' + Fore.BLACK)
            results[server_name]['sftp'] = False
        finally:
            try:
                test_client.close()
            except:
                pass
    
    # ========== SUMMARY ==========
    print(f'\n' + Fore.CYAN + '=' * 70 + Fore.BLACK)
    print(Fore.CYAN + 'Summary' + Fore.BLACK)
    print(Fore.CYAN + '=' * 70 + Fore.BLACK)
    
    for server_name in servers.keys():
        status = results[server_name]
        ping_ok = '✓' if status['ping'] else '✗'
        ssh_ok = '✓' if status['ssh'] else '✗'
        sftp_ok = '✓' if status['sftp'] else '✗'
        print(f'{server_name:12} | Ping: {ping_ok} | SSH: {ssh_ok} | SFTP: {sftp_ok}')
    
    all_ok = all(results[s]['ping'] and results[s]['ssh'] and results[s]['sftp'] for s in servers.keys())
    
    print(Fore.CYAN + '=' * 70 + Fore.BLACK)
    if all_ok:
        print(Fore.GREEN + '✓✓✓ All connections successful! Ready to upload.' + Fore.BLACK)
    else:
        print(Fore.RED + '✗✗✗ Some connections failed. Troubleshooting tips:' + Fore.BLACK)
        print(Fore.YELLOW + '  • Ping fails → Check VPN, firewall, or server IP address' + Fore.BLACK)
        print(Fore.YELLOW + '  • SSH fails → Check credentials in passwords.csv' + Fore.BLACK)
        print(Fore.YELLOW + '  • SFTP fails → Check network latency or remote permissions' + Fore.BLACK)
    
    return results


def upload_np(t_now, nb_day, telescope):
    t0 = Time(t_now)
    dt = Time("2018-01-02 00:00:00", scale="tcg") - Time(
        "2018-01-01 00:00:00", scale="tcg"
    )  # 1 day

    # Initialize SFTP clients
    sftp_cambridge = None
    sftp_SSO_hub = None
    sftp_SNO_hub = None
    cambridge_available = False
    
    try:
        # ========== CAMBRIDGE (optional - non-critical) ==========
        try:
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Connecting to Cambridge archive (non-critical)...')
            ssh_client_cambridge.connect(
                "appcs.ra.phy.cam.ac.uk", username="speculoos", password=pwd_appcs, timeout=10
            )
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Connected to Cambridge SSH!')
            
            # Open SFTP with timeout using threading
            sftp_result = {'sftp': None, 'error': None}
            
            def open_cambridge_sftp():
                try:
                    print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Opening Cambridge SFTP channel (10s timeout)...')
                    transport = ssh_client_cambridge.get_transport()
                    if transport and transport.sock:
                        transport.sock.settimeout(10)
                    sftp_result['sftp'] = ssh_client_cambridge.open_sftp()
                except Exception as e:
                    sftp_result['error'] = e
            
            sftp_thread = threading.Thread(target=open_cambridge_sftp, daemon=True)
            sftp_thread.start()
            sftp_thread.join(timeout=12)  # Give 12 seconds (10s + buffer)
            
            if sftp_thread.is_alive():
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Cambridge SFTP timeout (10s) - skipping archive upload')
                cambridge_available = False
            elif sftp_result['error']:
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + f' Cambridge SFTP failed - {sftp_result["error"]}')
                cambridge_available = False
            elif sftp_result['sftp']:
                sftp_cambridge = sftp_result['sftp']
                sftp_cambridge.get_channel().settimeout(10)
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' SFTP Cambridge ready')
                cambridge_available = True
            else:
                print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Cambridge SFTP could not open')
                cambridge_available = False
                
        except Exception as e:
            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + f' Cambridge archive connection failed (non-critical) - {e}')
            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Continuing with SSO/SNO hub uploads...')
            cambridge_available = False
        
        # ========== HUB SERVERS (critical) ==========
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Connecting to SSO hub (172.16.4.169)...')
        ssh_client_SSO_hub.connect(
            "172.16.4.169", username="speculoos", password=pwd_HUB, timeout=30
        )
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Connected to SSO hub!')
        sftp_SSO_hub = ssh_client_SSO_hub.open_sftp()
        sftp_SSO_hub.get_channel().settimeout(30)
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' SFTP SSO hub ready')
        
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Connecting to SNO hub (10.16.83.11)...')
        ssh_client_SNO_hub.connect(
            "10.16.83.11", username="speculoos", password=pwd_SNO_Reduc1, timeout=30
        )
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Connected to SNO hub!')
        sftp_SNO_hub = ssh_client_SNO_hub.open_sftp()
        sftp_SNO_hub.get_channel().settimeout(30)
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' SFTP SNO hub ready')
        
        if cambridge_available:
            print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' All servers connected!')
        else:
            print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Hub servers ready (Cambridge unavailable)')

        for nb_day in range(0, nb_day):
            t_now = Time(t0 + nb_day * dt, scale="utc", out_subfmt="date").iso

            # Cambridge server paths
            path_database_plans = os.path.join(
                "../../appct/data/SPECULOOSPipeline/Observations/",
                telescope,
                "schedule",
                "Plans_by_date",
                str(t_now),
            )
            path_plans = os.path.join(
                path_spock + "/DATABASE/", telescope, "Plans_by_date/", str(t_now)
            )
            # Archive_night_blocks
            night_block = "night_blocks_" + telescope + "_" + str(t_now) + ".txt"
            path_database_nightb = os.path.join(
                "../../appct/data/SPECULOOSPipeline/Observations/",
                telescope,
                "schedule",
                "Archive_night_blocks",
                night_block,
            )
            path_night_blocks = os.path.join(
                path_spock + "/DATABASE/",
                telescope,
                "Archive_night_blocks/",
                night_block,
            )
            # zip_files
            zip_file = str(t_now) + ".zip"
            path_database_zip_file = os.path.join(
                "../../appct/data/SPECULOOSPipeline/Observations/",
                telescope,
                "schedule",
                "Zip_files",
                zip_file,
            )
            path_local_zip_file = os.path.join(
                path_spock + "/DATABASE/", telescope, "Zip_files/", zip_file
            )
            path_hub_zip_files = os.path.normpath(
                os.path.join(
                    "/home/speculoos/Plans_scheduler/", telescope, "Plans", zip_file
                )
            )

            path_hub_SNO_zip_files = os.path.join(
                "/home/speculoos/Desktop/Plans/", zip_file
            )

            # Astra
            csv_file = telescope + "_" + str(t_now) + ".csv"
            jsonl_file = telescope + "_" + str(t_now) + ".jsonl"
            path_database_astra = os.path.join(
                "../../appct/data/SPECULOOSPipeline/Observations/",
                telescope,
                "schedule",
                "Astra",
                jsonl_file,
            )
            path_local_astra_csv = os.path.join(
                path_spock + "/DATABASE/", telescope, "Astra/", csv_file
            )
            path_local_astra_jsonl = os.path.join(
                path_spock + "/DATABASE/", telescope, "Astra/", jsonl_file
            )

            if (
                (telescope == "Io")
                or (telescope == "Europa")
                or (telescope == "Ganymede")
                or (telescope == "Callisto")
            ):

                # ========== CAMBRIDGE UPLOADS (optional) ==========
                if cambridge_available:
                    try:
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + f' Uploading to Cambridge for {telescope}...')
                        upload_folder(sftp_cambridge, path_plans, path_database_plans)
                        sftp_cambridge.put(path_night_blocks, path_database_nightb)
                        sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
                        sftp_cambridge.put(path_local_astra_jsonl, path_database_astra)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + f' All files uploaded to Cambridge for {telescope}')
                    except Exception as e:
                        print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + f' Cambridge upload failed (continuing): {e}')
                else:
                    print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Skipping Cambridge upload (not available)')
                
                # ========== HUB UPLOADS (critical) ==========
                print(Fore.GREEN + 'INFO: ' + Fore.BLACK + f' Uploading to HUB servers for {telescope}...')
                try:
                    sftp_SSO_hub.put(path_local_zip_file, path_hub_zip_files)
                    print(Fore.GREEN + '----->' + Fore.BLACK + f' {t_now} Zip Plans uploaded to SSO hub for {telescope}')
                except OSError as e:
                    print(Fore.RED + 'ERROR: ' + Fore.BLACK + f' SSO hub upload failed: {e}')
                
                path_hub_astra = os.path.normpath(
                    os.path.join(
                        "/home/speculoos/Plans_scheduler/",
                        telescope,
                        "Astra/",
                        jsonl_file,
                    )
                )
                try:
                    sftp_SSO_hub.put(path_local_astra_jsonl, path_hub_astra)
                    print(Fore.GREEN + '----->' + Fore.BLACK + f' {t_now} Astra plans uploaded to SSO hub for {telescope}')
                except OSError as e:
                    print(Fore.RED + 'ERROR: ' + Fore.BLACK + f' SSO hub astra upload failed: {e}')
                # else:
                #     sftp_cambridge.put(path_local_astra_csv, path_database_astra)
                #     print(
                #     "----->",
                #     t_now,
                #     "Astra folder updated on the Cambridge server for",
                #     telescope,
                #     )
                #     path_hub_astra = os.path.normpath(
                #     os.path.join(
                #         "/home/speculoos/Plans_scheduler/",
                #         telescope,
                #         "Astra/",
                #         csv_file,
                #     )
                #     )
                    # sftp_SSO_hub.put(path_local_astra_csv, path_hub_astra)
                    # print(
                    #     "----->",
                    #     t_now,
                    #     "Astra folder updated on the HUB for",
                    #     telescope,
                    # )

            if (telescope == "Artemis") or (telescope == "Saint-Ex"):
                # ========== CAMBRIDGE UPLOADS (optional) ==========
                if cambridge_available:
                    try:
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + f' Uploading to Cambridge for {telescope}...')
                        upload_folder(sftp_cambridge, path_plans, path_database_plans)
                        sftp_cambridge.put(path_night_blocks, path_database_nightb)
                        sftp_cambridge.put(path_local_zip_file, path_database_zip_file)
                        if telescope == "Saint-Ex":
                            sftp_cambridge.put(path_local_astra_csv, path_database_astra)
                        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + f' All files uploaded to Cambridge for {telescope}')
                    except Exception as e:
                        print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + f' Cambridge upload failed (continuing): {e}')
                else:
                    print(Fore.YELLOW + 'WARNING: ' + Fore.BLACK + ' Skipping Cambridge upload (not available)')
                
                # ========== HUB UPLOADS (critical) ==========
                if telescope == "Artemis":
                    try:
                        sftp_SNO_hub.put(path_local_zip_file, path_hub_SNO_zip_files)
                        print(Fore.GREEN + '----->' + Fore.BLACK + f' {t_now} Zip Plans uploaded to SNO hub for {telescope}')
                    except OSError as e:
                        print(Fore.RED + 'ERROR: ' + Fore.BLACK + f' SNO hub upload failed: {e}')

    except paramiko.ssh_exception.SSHException as e:
        print(Fore.RED + f'ERROR: SSH connection failed - {e}' + Fore.BLACK)
        print(Fore.RED + 'ERROR: ' + Fore.BLACK + ' Hub servers are critical. Check your VPN connection.' + Fore.BLACK)
        traceback.print_exc()
    except TimeoutError as e:
        print(Fore.RED + f'ERROR: Connection timed out - {e}' + Fore.BLACK)
        print(Fore.RED + 'ERROR: ' + Fore.BLACK + ' Network unreachable. Verify VPN connection.' + Fore.BLACK)
        traceback.print_exc()
    except OSError as e:
        print(Fore.RED + f'ERROR: Connection or file error - {e}' + Fore.BLACK)
        print(Fore.RED + 'ERROR: ' + Fore.BLACK + ' Check network and file paths.' + Fore.BLACK)
        traceback.print_exc()
    except Exception as e:
        print(Fore.RED + f'ERROR: Unexpected error - {e}' + Fore.BLACK)
        traceback.print_exc()

    finally:
        print(Fore.GREEN + 'INFO: ' + Fore.BLACK + ' Closing connections...')
        try:
            if sftp_cambridge:
                sftp_cambridge.close()
        except:
            pass
        try:
            if sftp_SSO_hub:
                sftp_SSO_hub.close()
        except:
            pass
        try:
            if sftp_SNO_hub:
                sftp_SNO_hub.close()
        except:
            pass
        try:
            ssh_client_cambridge.close()
        except:
            pass
        try:
            ssh_client_SSO_hub.close()
        except:
            pass
        try:
            ssh_client_SNO_hub.close()
        except:
            pass

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


