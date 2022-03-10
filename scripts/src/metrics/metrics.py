
import argparse
import itertools
import logging
import requests
import sys
import analytics
import os

logging.basicConfig(level=logging.INFO)

def parse_response(response):
    result = []
    for obj in response:
        if 'name' in obj and len(obj.get('assets', [])) > 0:
            release = {
                'name': obj['name'],
                'assets': list(map(lambda asset: (asset.get('name', 'unknown'), asset.get('download_count', 0)), obj['assets']))
            }
            result.append(release)
    return result


def get_release_metrics():
    result = []
    for i in itertools.count(start=1):
        response = requests.get(
            f'https://api.github.com/repos/openshift-helm-charts/charts/releases?per_page=100&page={i}')
        if not 200 <= response.status_code < 300:
            logging.error(f"unexpected response getting release data : {response.status_code} : {response.reason}")
            sys.exit(1)
        response_json = response.json()
        if len(response_json) == 0:
            break
        result.extend(response_json)
    return parse_response(result)


def send_release_metrics(metrics: dict):
    for release in metrics:
        send_metric(release['name'],"Chart downloads", dict(release['assets']))


def send_fail_metric(partner,chart,message):

    properties = { "chart" : chart, "message" : message }

    send_metric(partner,"PR run Failed",properties)

def send_pass_metric(partner,chart):

    properties = { "chart" : chart }

    send_metric(partner,"PR Success",properties)


def on_error(error,items):
    print("An error occurred creating metrics:", error)
    print("error with items:",items)
    sys.exit(1)


def send_metric(user,event,properties):

    analytics.write_key = os.getenv('SEGMENT_WRITE_KEY')
    analytics.on_error = on_error

    analytics.track(user, event, properties)

    logging.info(f'Add track:\nuser: {user}\nevent:{event}\nproperties:{properties}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--metric-type", dest="type", type=str, required=True,
                        help="metric type, releases or pull_request")
    parser.add_argument("-c", "--chart", dest="chart", type=str, required=False,
                        help="chart name for metric")
    parser.add_argument("-p", "--partner", dest="partner", type=str, required=False,
                        help="name of partner")
    parser.add_argument("-m", "--message", dest="message", type=str, required=False,
                        help="message for metric")
    args = parser.parse_args()

    if not os.getenv('SEGMENT_WRITE_KEY'):
        print("Error SEGMENT_WRITE_KEY not found")
        sys.exit(1)

    if args.type == "pull_request":
        if args.message:
            send_fail_metric(args.partner,args.chart,args.message)
        else:
            send_pass_metric(args.partner,args.chart)
    else:
        send_release_metrics(get_release_metrics())


if __name__ == '__main__':
    main()
