#!/usr/bin/env python3

import sys
import yaml
import ipaddress
import urllib.parse
import subprocess
import socket
import requests
import re
import logging
import os

FAIL = "\033[1;91m" + "FAIL" + "\033[0m"
PASS = "\033[1;92m" + "PASS" + "\033[0m"

def microk8s_verification():
    retcode = 0

    try:
        var = subprocess.Popen(["microk8s", "kubectl", "version"], stdout=subprocess.PIPE)
    except:
        print('ERROR: no microk8s running in the system')
        return 1

    not_runnig = os.popen('microk8s kubectl get pods -A | grep -v STATUS | grep -v Running').read()

    if not not_runnig :
        print('All PODs are running')
    else:
        print(not_runnig)
        retcode = len(not_runnig.split('\n')) - 1
        print('ERROR: {} PODs are not running'.format(retcode))
        return retcode

    minio = os.popen('microk8s kubectl get pods -A | grep minio').read()
    if not minio:
        print('minio pod not found')
        return 1

    grafana = os.popen('microk8s kubectl get pods -A | grep grafana').read()
    if not grafana:
        print('grafana pod not found')
        return 1

    influxdb = os.popen('microk8s kubectl get pods -A | grep influxdb').read()
    if not influxdb:
        print('influxdb pod not found')
        return 1


    return retcode

def connection_verification():
    retcode = 0

    print('Connection Verification Test')

    SSLVerify = False
    logging.captureWarnings(True)

    script_path = os.path.dirname(os.path.realpath(__file__))
    with open('{}/config.yml'.format(script_path)) as file:
        config = yaml.load(file, Loader=yaml.Loader)

    for i in config['hosts']:
        try:
            addr = i['address']
            try:
                addr = ipaddress.ip_address(addr)
            except ValueError:
                url = urllib.parse.urlparse(addr,scheme='http')
                if url.netloc=='' and url.path != '':
                    url = urllib.parse.urlparse(f'{url.scheme}://{url.path}')
                addr =  url.hostname
        except KeyError:
            continue

        if i['prot'] == 'icmp':
            print(f'ping       {str(addr):30}: ', end='', flush=True)
            cp = subprocess.run(['ping','-c1','-w2',f'{addr}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            print(f'{FAIL if cp.returncode else PASS}')
            retcode = retcode + cp.returncode
        elif i['prot'] == "tcp":
            print(f'tcp/{i["tcpport"]:<6} {str(addr):30}: ', end='', flush=True)
            s = None
            for res in socket.getaddrinfo(str(addr), i['tcpport'], socket.AF_UNSPEC, socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    s = socket.socket(af, socktype, proto)
                    s.settimeout(5)
                except socket.error:
                    s = None
                    continue
                try:
                    s.connect(sa)
                except socket.error:
                    s.close()
                    s = None
                    continue
                break
            print(f'{PASS if s else FAIL}')
            retcode = retcode + (0 if s else  1)
            if s: s.close()
        elif i['prot'] == 'httpstatus':
            print(f'httpstatus {url.geturl():30}: ', end='', flush=True)
            r = requests.get(url.geturl(), verify=SSLVerify)
            print(f'{PASS if r.status_code==i["httpstatus"] else FAIL}')
            retcode = retcode + (0 if r.status_code==i["httpstatus"] else 1)
        elif i['prot'] == 'httpstring':
            print(f'httpstring {url.geturl():30}: ', end='', flush=True)
            r = requests.get(url.geturl(), verify=SSLVerify)
            print(f'{PASS if re.search(i["httpstring"],r.text) else FAIL}')
            retcode = retcode + (0 if re.search(i["httpstring"],r.text) else 1)

    return retcode


def main(args):
    retcode = 0

    retcode = microk8s_verification()
    if retcode != 0:
        return retcode

    retcode = connection_verification()
    if retcode != 0:
        print ("Connection verification {} test(s) failed".format(retcode))
        return retcode

    return retcode

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
