import argparse
import getpass
import logging
import paramiko
import subprocess
import traceback
import numpy as np
import xml.etree.ElementTree as et
from polling import poll


def parse_mem_str(mem_str):
    assert(mem_str[-4:] == ' MiB')
    return int(mem_str[:-4])


def alert(args):
    title = 'gpu-monitor <{}>'.format(args.addr)
    s = '' if args.min_gpus == 1 else 's'
    if args.min_ram is None:
        msg = '{} GPU{} are now available!'.format(args.min_gpus, s)
    else:
        msg = '{} GPU{} with {} MB RAM are now available!'.format(args.min_gpus, s, args.min_ram)

    subprocess.run(['notify-send', title, msg])
    if args.alert_sound is not None:
        subprocess.run(['ffplay', '-nodisp', '-loglevel', '8', '-autoexit', args.alert_sound])


def check_server(client, args):
    stdin, stdout, stderr = client.exec_command('nvidia-smi -q -x')
    status_tree = et.parse(stdout)
    root = status_tree.getroot()

    gpus = root.findall('gpu')
    used_mem = []
    free_mem = []
    for gpu in gpus:
        mem_usage = gpu.find('fb_memory_usage')
        used_mem.append(parse_mem_str(mem_usage.find('used').text))
        free_mem.append(parse_mem_str(mem_usage.find('free').text))

    used_mem = np.array(used_mem)
    free_mem = np.array(free_mem)
    used_gpus = np.sum(used_mem > 0)
    total_gpus = len(gpus)

    msg = '{} GPUs detected - {} idle, {} in use'.format(total_gpus, total_gpus - used_gpus, used_gpus)
    logging.info(msg)

    if args.min_ram is None:
        # Alert when there are at least <MIN_GPUS> completely idle gpus
        is_avail = (total_gpus - used_gpus) >= args.min_gpus
    else:
        # Alert when there are at least <MIN_GPUS> gpus with at least <MIN_RAM> free memory
        is_avail = np.sum(free_mem > args.min_ram) >= args.min_gpus

    if is_avail:
        logging.info('GPUs available now!')
        alert(args)

    return is_avail


def main():
    parser = argparse.ArgumentParser(description='GPU monitor for remote servers',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    ssh_grp = parser.add_argument_group('SSH options')
    ssh_grp.add_argument('--user', '-u', help='User name')
    ssh_grp.add_argument('--host', '-d', help='Host name')
    ssh_grp.add_argument('--port', '-p', default=22, type=int, help='Port number')
    ssh_grp.add_argument('--key', '-k', help='Path to public key')

    mon_grp = parser.add_argument_group('Monitor options')
    mon_grp.add_argument('--step', default=60, type=int, help='Period in seconds')
    mon_grp.add_argument('--min_gpus', default=1, type=int, help='Alert when at least this no. of GPUs is availble.')
    mon_grp.add_argument('--min_ram', type=int, help='Consider GPUs with at least this much free RAM (in MiB) as '
                                                     'available. If not specified, only look for fully idle GPUs.')
    mon_grp.add_argument('--alert_sound', help='Path to alert sound file')
    mon_grp.add_argument('--debug', action='store_true', help='Test if notification is working')

    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.WarningPolicy())

    if args.debug:
        args.addr = 'user@foo.bar.hk'
        alert(args)
        return

    user = args.user
    if args.host is not None:
        host = args.host
    else:
        assert '@' in args.user
        user, host = args.user.split('@')
    addr = '{}@{}'.format(user, host)
    port = args.port
    args.addr = addr

    logging.basicConfig(format='[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)

    try:
        if args.key is not None:
            client.connect(hostname=host, username=user, port=port, key_filename=args.key)
        else:
            password = getpass.getpass('Password for "{}": '.format(addr))
            client.connect(hostname=host, username=user, port=port, password=password)

        print('Connected to "{}"!'.format(addr))
        print('Listening for {} GPU(s) every {} seconds...'.format(args.min_gpus, args.step))

        try:
            poll(lambda: check_server(client, args), step=args.step, poll_forever=True)
        except KeyboardInterrupt:
            print('\nMonitor terminated by user.')

        client.close()

    except Exception as e:
        print('Connection error: {}: {}'.format(e.__class__, e))
        traceback.print_exc()
        try:
            client.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
