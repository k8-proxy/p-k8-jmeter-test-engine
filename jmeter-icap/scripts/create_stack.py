import os
import logging
import sys, getopt
import time
import uuid
import platform
import subprocess
import shutil
import fileinput
import math
import boto3
import requests
import botocore
from botocore.exceptions import ClientError
from ipaddress import ip_address, IPv4Address
import proxy_sites
from config_params import Config

logger = logging.getLogger('create_stack')

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

class Main():

    #total_users = '100'
    #users_per_instance = '25'
    #duration = '60'
    #filelist = ''
    #minio_url = 'http://minio-service.common:80'
    #minio_external_url = 'http://localhost:9000'
    minio_access_key = ''
    minio_secret_key = ''
    #minio_input_bucket = 'input'
    #minio_output_bucket = 'output'
    #influxdb_url = 'http://influxdb-service.common:80'
    influxHost = ''
    #prefix = 'test'
    #icap_server = 'icap02.glasswall-icap.com'
    requests_memory = '768'
    requests_cpu = '300'
    limits_memory = '768'
    limits_cpu = '500'
    Xms_value = '512'
    Xmx_value = '512'
    parallelism = 1
    microk8s = False
    #icap_server_port = '1344'
    #enable_tls = False
    #tls_verification_method = 'no-verify'
    #jmx_file_path = 'none'
    filelist_bucket = 'filelist'
    kubectl_string = ''
    #proxy_static_ip = ''
    #load_type = 'Direct'

    @staticmethod
    def get_microk8s():
        try:
            var = subprocess.Popen(["microk8s", "kubectl", "version"], stdout=subprocess.PIPE)
            Main.microk8s = True
            Main.kubectl_string = "microk8s kubectl "
        except:
            Main.microk8s = False    
            Main.kubectl_string = "kubectl "    

    @staticmethod
    def log_level(level):
        logging.basicConfig(level=getattr(logging, level))

    @staticmethod
    def verify_url(service_name, url):
        try:
            if not (url.startswith('http://') or url.startswith('https://')):
                print("ERROR: {} url must srart with \'http://\' or \'https://\'".format(service_name))
                exit(1)
            port = int(url.split(':', 2)[2])
            if not (port > 0 and port < 0xffff):
                print("ERROR: {} url must contain a valid port number".format(service_name))
                exit(1)
        except Exception as e:
            print("ERROR: {} URL vertification failed {}".format(service_name, e))
            exit(1)

    @staticmethod
    def sanity_checks():
        try:
            if not Main.microk8s:
                var = subprocess.Popen(["kubectl", "version"], stdout=subprocess.PIPE)
        except Exception as e:
            print("ERROR: failed to run kubectl: {}".format(e))
            exit(1)
        if int(Config.total_users) <= 0:
            print("ERROR: Total users must be positive number")
            exit(1)
        if int(Config.users_per_instance) <= 0:
            print("ERROR: Users per instance must be positive number")
            exit(1)
        if int(Config.users_per_instance) > 200:
            print("ERROR: Users per instance cannot be greater than 200")
            exit(1)
        if int(Config.duration) <= 0:
            print("ERROR: Test duration must be positive number")
            exit(1)
        if not os.path.exists(Config.list):
            print("ERROR: File {} does not exist".format(Config.list))
            exit(1)
        Main.verify_url('minio', Config.minio_url)
        Main.verify_url('minio external', Config.minio_external_url)
        Main.verify_url('influxdb', Config.influxdb_url)
        if not (int(Config.icap_server_port) > 0 and int(Config.icap_server_port) < 0xffff):
            print("ERROR: Wrong icap server port value {}".format(Config.icap_server_port))
            exit(1)
        if not os.path.exists(Config.jmx_file_path):
            print("ERROR: File {} does not exist".format(Config.jmx_file_path))
            exit(1)

        load_type_values = ['Direct','Proxy']
        if not Config.load_type in load_type_values:
            print("ERROR: Unsupported load type: {}".format(Config.load_type))
            exit(1)
        elif Config.load_type == 'Proxy':
            try: 
                if not type(ip_address(Config.proxy_static_ip)) is IPv4Address:
                    print("ERROR: Invalid Proxy IP address {}".format(Config.proxy_static_ip))
                    exit(1)
            except ValueError: 
                print("ERROR: Invalid Proxy IP address {}".format(Config.proxy_static_ip))
                exit(1)

    @staticmethod
    def stop_jmeter_jobs():
        try:
            os.system(Main.kubectl_string + "-n jmeterjobs delete --ignore-not-found jobs -l jobgroup=" + Config.prefix + "-jmeter")
            os.system(Main.kubectl_string +" -n jmeterjobs delete --ignore-not-found secret jmeterconf")
        except Exception as e:
            print(e)
            exit(1)

    @staticmethod
    def replace_in_file(filename, prev_str, new_str):
        try:
            with fileinput.FileInput(filename, inplace=True, backup='.bak') as file:
                for line in file:
                    print(line.replace(prev_str, new_str), end='')
            os.remove(filename + '.bak')
        except Exception as e:
            print(e)
            exit(1)

    @staticmethod
    def get_jmx_file():
        try:
            a = uuid.uuid4()
            jmeter_script_name = str(a)
            shutil.copyfile(Config.jmx_file_path,jmeter_script_name)
            Main.replace_in_file(jmeter_script_name,"$number_of_threads$", str(Config.users_per_instance))
            Main.replace_in_file(jmeter_script_name,"$duration_in_seconds$", str(Config.duration))
            Main.replace_in_file(jmeter_script_name,"$minio_endpoint$", Config.minio_url)
            Main.replace_in_file(jmeter_script_name,"$minio_access_key$", Main.minio_access_key)
            Main.replace_in_file(jmeter_script_name,"$minio_secret_key$", Main.minio_secret_key)
            Main.replace_in_file(jmeter_script_name,"$minio_input_bucket$", Config.minio_input_bucket)
            Main.replace_in_file(jmeter_script_name,"$minio_output_bucket$", Config.minio_output_bucket)
            Main.replace_in_file(jmeter_script_name,"$influxdb_url$", Config.influxdb_url)
            Main.replace_in_file(jmeter_script_name,"$influxHost$", Main.influxHost)
            Main.replace_in_file(jmeter_script_name,"$prefix$", Config.prefix)
            Main.replace_in_file(jmeter_script_name,"$icap_server$", Config.icap_server)
            Main.replace_in_file(jmeter_script_name,"$icap_server_port$", Config.icap_server_port)

            if Config.enable_tls:
                Main.replace_in_file(jmeter_script_name,"$use_tls$", "true")
            else:
                Main.replace_in_file(jmeter_script_name,"$use_tls$", "false")
            Main.replace_in_file(jmeter_script_name,"$tls_verification_method$", Config.tls_verification_method)
            return jmeter_script_name
        except Exception as e:
            print(e)
            exit(1)

    @staticmethod
    def apply_resource_table():
        try:
            if int(Config.users_per_instance) <= 50:
                Main.requests_memory = '768'
                Main.requests_cpu = '300'
                Main.limits_memory = '768'
                Main.limits_cpu = '500'
                Main.Xms_value = '512'
                Main.Xmx_value = '512'
                return
            if int(Config.users_per_instance) <= 100:
                Main.requests_memory = '1280'
                Main.requests_cpu = '600'
                Main.limits_memory = '1280'
                Main.limits_cpu = '1000'
                Main.Xms_value = '1024'
                Main.Xmx_value = '1024'
                return
            if int(Config.users_per_instance) <= 200:
                Main.requests_memory = '2304'
                Main.requests_cpu = '1200'
                Main.limits_memory = '2304'
                Main.limits_cpu = '2000'
                Main.Xms_value = '2048'
                Main.Xmx_value = '2048'
                return
        except Exception as e:
            print(e)
            exit(1)

    @staticmethod
    def start_jmeter_job():
        try:
            if os.path.exists('jmeter-conf.jmx'):
                os.remove('jmeter-conf.jmx')

            jmeter_script_name = Main.get_jmx_file()
            shutil.copyfile(jmeter_script_name,'jmeter-conf.jmx')
            os.remove(jmeter_script_name)
            os.system(Main.kubectl_string + "create namespace jmeterjobs")
            os.system(Main.kubectl_string + "-n jmeterjobs create secret generic jmeterconf --from-file=jmeter-conf.jmx")

            if os.path.exists('job-0.yaml'):
                os.remove('job-0.yaml')

            if Config.load_type == 'Direct':
                shutil.copyfile('jmeter-job-tmpl.yaml','job-0.yaml')
            elif Config.load_type == 'Proxy':
                shutil.copyfile('jmeter-proxy-job-tmpl.yaml','job-0.yaml')
                Main.replace_in_file('job-0.yaml','$proxy-static-ip$', Main.proxy_static_ip)
                proxy_sites.Main.file_path = Config.list
                proxy_sites.Main.yaml_file = 'job-0.yaml'
                proxy_sites.Main.get_domains()
                proxy_sites.Main.update_yaml()

            Main.parallelism = math.ceil(Config.total_users / Config.users_per_instance)
            print("Number of pods to be created: {}".format(Main.parallelism))
            Main.replace_in_file('job-0.yaml','$parallelism-number', str(Main.parallelism))

            Main.apply_resource_table()
            Main.replace_in_file('job-0.yaml','$requests_memory$', Main.requests_memory)
            Main.replace_in_file('job-0.yaml','$requests_cpu$', Main.requests_cpu)
            Main.replace_in_file('job-0.yaml','$limits_memory$', Main.limits_memory)
            Main.replace_in_file('job-0.yaml','$limits_cpu$', Main.limits_cpu)
            Main.replace_in_file('job-0.yaml','$Xms_value$', Main.Xms_value)
            Main.replace_in_file('job-0.yaml','$Xmx_value$', Main.Xmx_value)
            Main.replace_in_file('job-0.yaml','$prefix$', Config.prefix)

            os.system(Main.kubectl_string + "create -f job-0.yaml")

            os.remove('jmeter-conf.jmx')
            os.remove('job-0.yaml')

        except Exception as e:
            print(e)
            exit(1)

    @staticmethod
    def upload_to_minio(file_path):
        try:
            logger.info('Uploading file {}.'.format(file_path))
            s3 = boto3.resource('s3', endpoint_url=Config.minio_external_url, aws_access_key_id=Config.minio_access_key,
                                aws_secret_access_key=Config.minio_secret_key, config=botocore.client.Config(signature_version='s3v4'))
            logger.debug('Checking if the Bucket to upload files exists or not.')
            if (s3.Bucket(Main.filelist_bucket) in s3.buckets.all()) == False:
                logger.info('Bucket not Found. Creating Bucket.')
                s3.create_bucket(Bucket=Main.filelist_bucket)
            logger.debug('Uploading file to bucket {} minio {}'.format(Main.filelist_bucket, Config.minio_external_url))
            s3.Bucket(Main.filelist_bucket).upload_file(file_path, 'files')
            #s3.Bucket(Main.filelist_bucket).download_file('files', 'files')
        except Exception as e:
            print("ERROR: Cannot upload the file list to minio {}".format(e))
            exit(1)

    @staticmethod
    def main(argv):
        help_string = 'python3 create_stack.py --total_users <number of users> --users_per_instance <number of users> --duration <test duaration> --list <file list> --minio_url <url> --minio_external_url <url> --minio_access_key <access key> --minio_secret_key <secret key> --minio_input_bucket <bucket name> --minio_output_bucket <bucket name> --influxdb_url <url> --prefix <prefix> --icap_server <url>'
        try:
            opts, args = getopt.getopt(argv,"htudl:ma:s:ibxpv",["total_users=","users_per_instance=","duration=","list=","minio_url=","minio_external_url=","minio_access_key=","minio_secret_key=", "minio_input_bucket=", "minio_output_bucket=","influxdb_url=","prefix=","icap_server=","icap_server_port=","enable_tls=","tls_verification_method=","jmx_file_path=","proxy_static_ip=", "load_type="])
        except getopt.GetoptError:
            print (help_string)
            sys.exit(2)
        for opt, arg in opts:
            if opt == '-h':
                print (help_string)
                sys.exit()
            #elif opt in ("-t", "--total_users"):
            #    Config.total_users = arg
            #elif opt in ("-u", "--users_per_instance"):
            #    Config.users_per_instance = arg
            #elif opt in ("-d", "--duration"):
            #    Config.duration = arg
            #elif opt in ("-l", "--list"):
            #    Config.list = arg
            #elif opt in ("-m", "--minio_url"):
            #    Config.minio_url = arg
            #elif opt in ("-me", "--minio_external_url"):
            #    Config.minio_external_url = arg
            #elif opt in ("-a", "--minio_access_key"):
            #    Config.minio_access_key = arg
            #elif opt in ("-s", "--minio_secret_key"):
            #    Main.minio_secret_key = arg
            #elif opt in ("-i", "--minio_input_bucket"):
            #    Config.minio_input_bucket = arg
            #elif opt in ("-o", "--minio_output_bucket"):
            #    Config.minio_output_bucket = arg
            #elif opt in ("-x", "--influxdb_url"):
            #    Config.influxdb_url = arg
            #elif opt in ("-p", "--prefix"):
            #    Config.prefix = arg
            #elif opt in ("-v", "--icap_server"):
            #    Config.icap_server = arg
            #elif opt in ("-port", "--icap_server_port"):
            #    Config.icap_server_port = arg
            #elif opt in ("-et", "--enable_tls"):
            #    Config.enable_tls = arg
            #elif opt in ("-tls", "--tls_verification_method"):
            #    Config.tls_verification_method = arg
            #elif opt in ("-jmx", "--jmx_file_path"):
            #    Config.jmx_file_path = arg
            #elif opt in ("-proxy", "--proxy_static_ip"):
            #    Config.proxy_static_ip = arg
            #elif opt in ("-load", "--load_type"):
            #    Config.load_type = arg

        Main.log_level(LOG_LEVEL)
        print("LOAD TYPE           {}".format(Config.load_type))

        print("TOTAL USERS         {}".format(Config.total_users))
        print("USERS PER INSTANCE  {}".format(Config.users_per_instance))
        print("TEST DURATION       {}".format(Config.duration))
        print("FILE LIST           {}".format(Config.list))


        print("MINIO URL           {}".format(Config.minio_url))
        print("MINIO EXTERNAL URL  {}".format(Config.minio_external_url))
        
        #print("MINIO ACCESS KEY    {}".format(Config.minio_access_key))
        #print("MINIO SECRET KEY    {}".format(Config.minio_secret_key))
        print("MINIO INPUT BUCKET  {}".format(Config.minio_input_bucket))
        print("MINIO OUTPUT BUCKET {}".format(Config.minio_output_bucket))

        Main.influxHost = Config.influxdb_url.replace('http://', '')
        Main.influxHost = Main.influxHost.split(':', 1)[0]
        print("INFLUXDB URL        {}".format(Config.influxdb_url))
        print("INFLUX HOST         {}".format(Main.influxHost))
        print("PREFIX              {}".format(Config.prefix))

        print("ICAP SERVER         {}".format(Config.icap_server))
        print("ICAP SERVER PORT    {}".format(Config.icap_server_port))

        print("ENABLE TLS          {}".format(Config.enable_tls))
        print("TLS VERIFICATION    {}".format(Config.tls_verification_method))


        Main.get_microk8s()
        print("Micro k8s           {}".format(Main.microk8s))

        print("JMX FILE PATH       {}".format(Config.jmx_file_path))
        print("PROXY STATIC IP     {}".format(Config.proxy_static_ip))

        Main.sanity_checks()
        Main.upload_to_minio(Config.list)
        Main.minio_access_key = Config.minio_access_key.replace('&','&amp;')
        Main.minio_secret_key = Config.minio_secret_key.replace('&','&amp;')
        Main.stop_jmeter_jobs()
        Main.start_jmeter_job()

if __name__ == "__main__":
    Main.main(sys.argv[1:])