import os
from argparse import ArgumentParser
from datetime import timedelta, datetime, timezone
import delete_stack
import create_stack
import create_dashboard
from dotenv import load_dotenv
from aws_secrets import get_secret_value
from threading import Thread
from time import sleep

# Stacks are deleted duration + offset seconds after creation; should be set to 900.
DELETE_TIME_OFFSET = 900

# Interval for how often "time elapsed" messages are displayed for delete stack process
MESSAGE_INTERVAL = 600


class Config(object):
    # Load configuration
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    load_dotenv(os.path.join(BASEDIR, 'config.env'), override=True)
    try:
        # these field names should not be changed as they correspond exactly to the names of create_stack's params.
        aws_profile_name = os.getenv("AWS_PROFILE_NAME")
        region = os.getenv("REGION")
        total_users = int(os.getenv("TOTAL_USERS"))
        users_per_instance = int(os.getenv("USERS_PER_INSTANCE"))
        duration = os.getenv("DURATION")
        list = os.getenv("TEST_DATA_FILE")
        minio_url = os.getenv("MINIO_URL")
        minio_external_url = os.getenv("MINIO_EXTERNAL_URL")
        minio_access_key = os.getenv("MINIO_ACCESS_KEY")
        minio_secret_key = os.getenv("MINIO_SECRET_KEY")
        minio_input_bucket = os.getenv("MINIO_INPUT_BUCKET")
        minio_output_bucket = os.getenv("MINIO_OUTPUT_BUCKET")
        influxdb_url = os.getenv("INFLUXDB_URL")
        prefix = os.getenv("PREFIX")
        icap_server = os.getenv("ICAP_SERVER_URL")
        grafana_url = os.getenv("GRAFANA_URL")
        grafana_api_key = os.getenv("GRAFANA_API_KEY")
        grafana_file = os.getenv("GRAFANA_FILE")
        grafana_secret = os.getenv("GRAFANA_SECRET")
        exclude_dashboard = os.getenv("EXCLUDE_DASHBOARD")
        preserve_stack = os.getenv("PRESERVE_STACK")
        icap_server_port = os.getenv("ICAP_SERVER_PORT")
        enable_tls = os.getenv("ENABLE_TLS")
        jmx_file_path = os.getenv("JMX_FILE_PATH")
        tls_verification_method = os.getenv("TLS_VERIFICATION_METHOD")
        proxy_static_ip = os.getenv("PROXY_STATIC_IP")
        load_type = os.getenv("LOAD_TYPE")
        grafana_username = os.getenv("GRAFANA_USERNAME")
        grafana_password = os.getenv("GRAFANA_PASSWORD")
    except Exception as e:
        print(
            "Please create config.env file similar to config.env.sample or set environment variables for all variables in config.env.sample file")
        print(str(e))
        raise


# set all possible arguments/options that can be input into the script
def __get_commandline_args():
    parser = ArgumentParser(fromfile_prefix_chars='@',
                            description='Creates k8 stack, generates Grafana Dashboard, deletes stack when complete')

    parser.add_argument('--total_users', '-t', default=Config.total_users,
                        help='total number of users in the test (default: 100)')

    parser.add_argument('--users_per_instance', '-u', default=Config.users_per_instance,
                        help='number of users per instance (default: 25)')

    parser.add_argument('--duration', '-d', default=Config.duration,
                        help='duration of test (default: 60)')

    parser.add_argument('--test_data_file', '-l', default=Config.list,
                        help='Path to file list')

    parser.add_argument('--minio_url', '-m', default=Config.minio_url,
                        help='Minio URL (default: "http://minio.minio.svc.cluster.local:9000")')

    parser.add_argument('--minio_external_url', '-me', default=Config.minio_external_url,
                        help='Minio URL (default: "http://localhost:9000")')

    parser.add_argument('--minio_access_key', '-a', default=Config.minio_access_key,
                        help='Minio access key')

    parser.add_argument('--minio_secret_key', '-s', default=Config.minio_secret_key,
                        help='Minio secret key')

    parser.add_argument('--minio_input_bucket', '-i', default=Config.minio_input_bucket,
                        help='Minio input bucket name (default: "input")')

    parser.add_argument('--minio_output_bucket', '-o', default=Config.minio_output_bucket,
                        help='Minio output bucket name (default: "output")')

    parser.add_argument('--influxdb_url', '-x', default=Config.influxdb_url,
                        help='Influx DB URL (default: "influxdb.influxdb.svc.cluster.local")')

    parser.add_argument('--prefix', '-p', default=Config.prefix,
                        help='Prefix for stack name (default: "")')

    parser.add_argument('--icap_server_url', '-v', default=Config.icap_server,
                        help='ICAP server endpoint URL (default: icap02.glasswall-icap.com)')

    parser.add_argument('--grafana_url', '-gu',
                        type=str,
                        help='URL to Grafana instance',
                        default=Config.grafana_url)

    parser.add_argument('--grafana_api_key', '-k',
                        type=str,
                        help='API key to be used for dashboard creation in grafana database',
                        default=Config.grafana_api_key)

    parser.add_argument('--grafana_file', '-f',
                        type=str,
                        help='path to grafana template used for dashboard creation',
                        default=Config.grafana_file)

    parser.add_argument('--grafana_secret', '-gs', default=Config.grafana_secret,
                        help='The secret ID for the Grafana API Key stored in AWS Secrets')

    parser.add_argument('--exclude_dashboard', '-ed', action='store_true',
                        help='Setting this option will prevent the creation of a new dashboard for this stack')

    parser.add_argument('--preserve_stack', '-ps', action='store_true',
                        help='Setting this option will prevent the created stack from being automatically deleted.')

    parser.add_argument('--icap_server_port', '-port', default=Config.icap_server_port,
                        help='Port of ICAP server used for testing')

    parser.add_argument('--tls_verification_method', '-tls', default=Config.tls_verification_method,
                        help='Verification method used with TLS')

    parser.add_argument('--enable_tls', '-et', default=Config.enable_tls,
                        help='Whether or not to enable TLS')

    parser.add_argument('--jmx_file_path', '-jmx', default=Config.jmx_file_path,
                        help='The file path of the JMX file under the test')

    parser.add_argument('--proxy_static_ip', '-proxy', default=Config.proxy_static_ip,
                        help='Static IP for when proxy is used')

    parser.add_argument('--load_type', '-load', default=Config.load_type,
                        help='Load type: Direct or Proxy')

    parser.add_argument('--grafana_username', '-un', default=Config.grafana_username,
                        help='Load type: Direct or Proxy')

    parser.add_argument('--grafana_password', '-pw', default=Config.grafana_password,
                        help='Load type: Direct or Proxy')

    return parser.parse_args()


# Starts the process of calling delete_stack after duration. Starts timer and displays messages updating users on status
def __start_delete_stack(additional_delay, prefix, duration):
    delete_stack_args = ["--prefix", prefix]
    total_wait_time = additional_delay + int(duration)
    minutes = total_wait_time / 60
    finish_time = datetime.now(timezone.utc) + timedelta(seconds=total_wait_time)
    start_time = datetime.now(timezone.utc)

    print("Stack will be deleted after {0:.1f} minutes".format(minutes))

    while datetime.now(timezone.utc) < finish_time:
        if datetime.now(timezone.utc) != start_time and datetime.now(timezone.utc) + timedelta(seconds=MESSAGE_INTERVAL) < finish_time:
            diff = datetime.now(timezone.utc) - start_time
            print("{0:.1f} minutes have elapsed, stack will be deleted in {1:.1f} minutes".format(diff.seconds / 60, (
                    total_wait_time - diff.seconds) / 60))
            sleep(MESSAGE_INTERVAL)

    print("Deleting stack with prefix: {0}".format(prefix))
    delete_stack.Main.main(argv=delete_stack_args)


# creates a list of args to be passed to create_stack from Config (i.e. config.env or command line args)
def get_args_list(config, options):
    # go through Config object, compile list of relevant arguments
    args_list = []
    for key in config.__dict__:
        if not key.startswith('__') and key in options:
            if config.__dict__[key]:
                args_list.append('--{0}'.format(key))
                args_list.append(str(config.__dict__[key]))

    return args_list


def run_using_ui(ui_json_params):
    additional_delay = 0
    prefix = ''
    duration = ''
    # Set Config values gotten from front end
    if ui_json_params['total_users']:
        Config.total_users = ui_json_params['total_users']
    if ui_json_params['ramp_up_time']:
        Config.ramp_up_time = ui_json_params['ramp_up_time']
    if ui_json_params['duration']:
        Config.duration = ui_json_params['duration']
        duration = ui_json_params['duration']
    if ui_json_params['prefix']:
        Config.prefix = ui_json_params['prefix']
        prefix = ui_json_params['prefix']
    if ui_json_params['icap_endpoint_url']:
        Config.load_type = ui_json_params['load_type']
        if ui_json_params['load_type'] == "Direct":
            Config.icap_server = ui_json_params['icap_endpoint_url']
        elif ui_json_params['load_type'] == "Proxy":
            # this comes as "icap_endpoint_url" from front end, but may also represent proxy IP if proxy load selected
            Config.proxy_static_ip = ui_json_params['icap_endpoint_url']

    __ui_set_files_for_load_type(ui_json_params['load_type'])

    # If Grafana API key provided, that takes precedence. Otherwise get key from AWS. If neither method provided, error output.
    if not Config.grafana_api_key:
        print("Must include a Grafana API key in config.env")
        exit(0)

    # ensure that preserve stack and create_dashboard are at default values
    Config.preserve_stack = False
    Config.exclude_dashboard = False

    __ui_set_tls_and_port_params(ui_json_params['load_type'], ui_json_params['enable_tls'],
                                 ui_json_params['tls_ignore_error'], ui_json_params['port'])

    dashboard_url = main(Config, additional_delay, prefix, duration)

    return dashboard_url


def stop_tests_using_ui(prefix=''):

    if prefix == '':
        delete_stack.Main.main(argv=[])
    else:
        delete_stack_options = ["--prefix", prefix]
        delete_stack.Main.main(argv=delete_stack_options)


def __ui_set_tls_and_port_params(input_load_type, input_enable_tls, input_tls_ignore_verification, input_port):
    if input_load_type == "Direct":

        # enable/disable tls based on user input
        Config.enable_tls = str(input_enable_tls)

        # if user entered a port, use that. Otherwise port will be set depending on tls_enabled below.
        if input_port:
            Config.icap_server_port = input_port

        # if user did not provide port, set one depending on whether or not tls is enabled
        if not input_port:
            if input_enable_tls:
                Config.icap_server_port = "443"
            else:
                Config.icap_server_port = "1344"

        # If TLS is enabled, get the user preference as to whether or not TLS verification should be used
        if input_enable_tls:
            Config.tls_verification_method = "tls-no-verify" if input_tls_ignore_verification else ""


def __ui_set_files_for_load_type(load: str):
    if load == "Direct":
        Config.jmx_file_path = './ICAP-Direct-File-Processing/ICAP_Direct_FileProcessing_k8_v3.jmx'
        Config.grafana_file = './ICAP-Direct-File-Processing/k8-test-engine-dashboard.json'
        Config.list = './ICAP-Direct-File-Processing/gov_uk_files.csv'

    elif load == "Proxy":
        Config.jmx_file_path = './ICAP-Proxy-Site/ProxySite_Processing_v1.jmx'
        Config.grafana_file = './ICAP-Proxy-Site/ProxySite_Dashboard_Template.json'
        Config.list = './ICAP-Proxy-Site/proxyfiles.csv'


def main(config, additional_delay, prefix, duration):
    dashboard_url = ''

    if config.exclude_dashboard:
        print("Dashboard will not be created")
    else:
        print("Creating dashboard...")
        dashboard_url = create_dashboard.main(config)

    # options to look out for when using create_stack, used to exclude all other unrelated options in config
    create_stack_options = ["total_users", "users_per_instance", "duration", "list", "minio_url", "minio_external_url", "minio_access_key",
               "minio_secret_key", "minio_input_bucket", "minio_output_bucket", "influxdb_url", "prefix", "icap_server",
               "icap_server_port", "enable_tls", "tls_verification_method", "jmx_file_path", "proxy_static_ip"]

    create_stack_args = get_args_list(config, create_stack_options)

    print("Creating Load Generators...")
    create_stack.Main.main(create_stack_args)

    if config.preserve_stack:
        print("Stack will not be automatically deleted.")
    else:
        delete_stack_thread = Thread(target=__start_delete_stack, args=(additional_delay, prefix, duration))
        delete_stack_thread.start()

    return dashboard_url


if __name__ == "__main__":
    args = __get_commandline_args()

    # Get all argument values from Config.env file. Any command line args input manually will override config.env args.
    Config.total_users = int(args.total_users)
    Config.users_per_instance = args.users_per_instance
    Config.duration = args.duration
    Config.list = args.test_data_file
    Config.minio_url = args.minio_url
    Config.minio_access_key = args.minio_access_key
    Config.minio_input_bucket = args.minio_input_bucket
    Config.minio_output_bucket = args.minio_output_bucket
    Config.influxdb_url = args.influxdb_url
    Config.prefix = args.prefix
    Config.icap_server = args.icap_server_url
    Config.grafana_url = args.grafana_url
    Config.grafana_file = args.grafana_file
    Config.grafana_api_key = args.grafana_api_key
    Config.grafana_secret = args.grafana_secret
    Config.icap_server_port = args.icap_server_port
    Config.tls_verification_method = args.tls_verification_method
    Config.proxy_static_ip = args.proxy_static_ip
    Config.load_type = args.load_type
    Config.grafana_username = args.grafana_username
    Config.grafana_password = args.grafana_password
    # these are flag/boolean arguments
    if args.exclude_dashboard:
        Config.exclude_dashboard = True
    elif Config.exclude_dashboard:
        Config.exclude_dashboard = int(Config.exclude_dashboard) == 1

    if args.preserve_stack:
        Config.preserve_stack = True
    elif Config.preserve_stack:
        Config.preserve_stack = int(Config.preserve_stack) == 1

    Config.enable_tls = (int(args.enable_tls) == 1)

    Config.jmx_file_path = args.jmx_file_path

    # Use Grafana key obtained either from config.env or from AWS secrets. Key from config.env gets priority.
    if not Config.grafana_api_key and not Config.grafana_secret and not (Config.grafana_username and Config.grafana_password):
        print("Must input either grafana_api_key, grafana_secret, or username/password in config.env or using args")
        exit(0)
    elif not Config.grafana_api_key and not Config.exclude_dashboard and not (Config.grafana_username and Config.grafana_password):
        secret_response = get_secret_value(config=Config, secret_id=Config.grafana_secret)
        secret_val = next(iter(secret_response.values()))
        Config.grafana_api_key = secret_val
        if secret_val:
            print("Grafana secret key retrieved.")

    main(Config, DELETE_TIME_OFFSET, Config.prefix, Config.duration)
