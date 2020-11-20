import requests
import json


# If the grafana file passed does not contain the appropriate elements with appropriate values, modify it
def __convert_grafana_json_to_template(grafana_json):

    # file must be enclosed in a dashboard tag
    if not 'dashboard' in grafana_json:
        grafana_json = {'dashboard': grafana_json}

    # ids must be set to null to prevent duplicate id errors. Grafana generates these automatically.
    grafana_json['dashboard']['id'] = None
    grafana_json['dashboard']['uid'] = None

    grafana_json['folderId'] = 0
    grafana_json['overwrite'] = True

    return grafana_json


#  Appends prefix to title and all occurrences of "measurement" value in the Grafana JSON file
def __add_prefix_to_grafana_json(grafana_json, prefix):
    grafana_json["dashboard"]["title"] = prefix + ' ' + grafana_json["dashboard"]["title"]
    if 'panels' in grafana_json["dashboard"]:
        for i in grafana_json["dashboard"]['panels']:
            for j in i:
                if 'targets' in j:
                    for k in i['targets']:
                        if 'measurement' in k:
                            k['measurement'] = prefix + '_' + k['measurement']


def __add_prefix_to_grafana_loki_source_job(grafana_json, prefix):
    if 'panels' in grafana_json["dashboard"]:
        for i in grafana_json["dashboard"]['panels']:
            if i['datasource'] == 'Loki':
                for j in i['targets']:
                    j['expr'] = '{job="' + prefix + '_' + 'jmeter"}'


# Modifies green info bar at the top of dashboard to display info on current test run
def __modify_dashboard_info_bar(grafana_json, total_users, duration, endpoint_url):
    if "options" in grafana_json["dashboard"]['panels'][0]:
        if "content" in grafana_json["dashboard"]['panels'][0]["options"]:
            grafana_json["dashboard"]['panels'][0]["options"][
                "content"] = "<p style=\"background-color:green;\" style=\"text-align:left;\">The endpoint for this run is: \n%s. Total users are %s. Duration of test is %s seconds  </p>    " \
                             % (endpoint_url, total_users, duration)


# responsible for posting the dashboard to Grafana and returning the URL to it
def __post_grafana_dash(config):
    grafana_api_key = config.grafana_api_key
    grafana_template = config.grafana_file
    prefix = config.prefix
    grafana_url = config.grafana_url
    total_users = config.total_users
    duration = config.duration
    icap_server = config.icap_server

    if not grafana_url.startswith("http"):
        grafana_url = "http://" + grafana_url

    grafana_api_url = grafana_url

    if grafana_url[len(grafana_url) - 1] != '/':
        grafana_api_url += '/'

    grafana_api_url = grafana_api_url + 'api/dashboards/db'

    headers = {
        "Authorization": "Bearer " + grafana_api_key,
        "Content-Type": "application/json"}

    # Modify grafana JSON to display current run's info
    with open(grafana_template) as json_file:
        grafana_json = json.load(json_file)
        grafana_json = __convert_grafana_json_to_template(grafana_json)
        __add_prefix_to_grafana_json(grafana_json, prefix)
        __add_prefix_to_grafana_loki_source_job(grafana_json, prefix)
        __modify_dashboard_info_bar(grafana_json, total_users, duration, icap_server)
    # post Grafana request to kubernetes pod
    resp = requests.post(grafana_api_url, json=grafana_json, headers=headers)
    d = eval(resp.text)
    # if the response contains a URL, use it to build a url that links directly to the newly created dashboard
    if "url" in d:
        if grafana_url[len(grafana_url) - 1] == '/':
            grafana_url = grafana_url[:-1]
        return grafana_url + d.get('url')
    else:
        print("Dashboard creation failed: {0}".format(resp.text))


def main(config):

    created_dashboard_url = __post_grafana_dash(config)

    if created_dashboard_url:
        print("Dashboard created at: ")
        print(created_dashboard_url)