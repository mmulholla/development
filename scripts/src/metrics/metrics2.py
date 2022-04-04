import analytics
import argparse
import re
from github import Github
import dateutil.parser
import os
import json

verbose=True
metricsLog = "metrics_log.json"
metrics_log_content = {}
iteration = 1

def init(force):
    global metrics_log_content,iteration
    write_out(f"Current directory: {os.getcwd()}")
    write_out(f"Read metrics file {metricsLog}")
    with open(metricsLog) as f:
        metrics_log_content = json.load(f)
        write_out(f'metrics previously processed pr numbers:\n{metrics_log_content.get("pr_numbers")}')
    if force:
        write_out("Ignore previous numbers, start afresh")
        metrics_log_content["iteration"] += 1
        metrics_log_content["pr_numbers"] = []
    iteration = metrics_log_content.get("iteration")

def write_out(msg,force=False):
    if verbose or force:
        print(msg)

def on_error(error,items):
    write_out(f"An error occurred creating metrics: {error}",True)
    write_out(f"error with items:{items}",True)
    sys.exit(1)

def check_pr(pr_number):
    write_out(f'    PR {pr_number} already processed: {pr_number in metrics_log_content.get("pr_numbers")}' )
    return pr_number not in metrics_log_content.get("pr_numbers")

def log_pr(pr_number):
    metrics_log_content.get("pr_numbers").append(pr_number)
    write_out(f'    log processing of pr {pr_number}, log content now: {metrics_log_content.get("pr_numbers")}')
    with open(metricsLog,'w') as f:
        json.dump(metrics_log_content,f,indent=4, sort_keys=True)


def send_event_metric(id,event,properties,timestamp):
    metrics_id = f'{iteration}-{id}'
    write_out(f'----> Add event metric:  user: {metrics_id},  event:{event},  properties:{properties}, timestamp:{timestamp}',True)
    analytics.track(metrics_id, event, properties, timestamp=timestamp)

def process_report_fails(body,type,created_at,pr_number):

    fails = ""
    num_error_messages = 0
    error_messages = []
    checks_failed = []
    body_lines = body.split("\n")
    for body_line in body_lines:
        body_line = body_line.strip()
        if fails:
            if "Error message(s)" in body_line:
                num_error_messages = 1
            elif num_error_messages <= int(fails):
                write_out(f"add error message: {body_line.strip()}" )
                error_messages.append(body_line.strip())
                num_error_messages +=1
            else:
                break
        elif "Number of checks failed" in body_line:
            body_line_parts = body_line.split(":")
            fails = body_line_parts[1].strip()
            write_out(f"Number of failures in report {fails}")

    for error_message in error_messages:
        if ("Missing required annotations" in error_message
            or
            "Empty metadata in chart" in error_messages
        ):
            checks_failed.append("required-annotations-present")
        elif "Chart test files do not exist" in error_message:
            checks_failed.append("required-annotations-present")
        elif "Chart test files do not exist" in error_message:
            checks_failed.append("contains-test")
        elif "API version is not V2, used in Helm 3" in error_message:
            checks_failed.append("is-helm-v3")
        elif "Values file does not exist" in error_message:
            checks_failed.append("contains-values")
        elif "Values schema file does not exist" in error_message:
            checks_failed.append("contains-values-schema")
        elif ("Kubernetes version is not specified" in error_message
              or
              "Error converting kubeVersion to an OCP range" in error_message
        ):
            checks_failed.append("has-kubeversion")
        elif "Helm lint has failed" in error_message:
            checks_failed.append("helm_lint")
        elif ( "Failed to certify images" in error_message
              or
               "Image is not Red Hat certified" in error_message
        ):
            if "images-are-certified" not in checks_failed:
                checks_failed.append("images-are-certified")
        elif "Chart does not have a README" in error_message:
            checks_failed.append("has-readme")
        elif "Missing mandatory check" in error_messages:
            checks_failed.append("missing-mandatory-check")
        elif "Chart contains CRDs" in error_messages:
            checks_failed.append("not-contains-crds")
        elif "CSI objects exist" in error_message:
            checks_failed.append("not-contain-csi-objects")
        else:
            checks_failed.append("chart-testing")


    for check in checks_failed:
        check_properties ={ "type": type, "check" : check, "pr" : pr_number}
        send_event_metric("metrics-report","check_failed",check_properties,created_at)

    return int(fails)



def process_comments(repo,pr,type):

    issue = repo.get_issue(number=pr.number)

    comments = issue.get_comments()

    num_builds = 0
    for comment in comments:
        num_fails = 0
        report_result = ""
        if (
            f"Thank you for submitting PR #{pr.number} for Helm Chart Certification!" in comment.body
            or
            f"Thank you for submitting pull request #{pr.number} for Helm Chart Certification!" in comment.body
        ):
            if "[ERROR] Chart verifier report includes failures:" in comment.body:
                num_fails = process_report_fails(comment.body,type,comment.created_at,pr.number)
                report_result = "report-failure"
            elif (
                "There were one or more errors while building and verifying your pull request." in comment.body
                or
                "One or more errors were found with the pull request" in comment.body
                or
                "An error was found with the Pull Request:" in comment.body
            ):
                num_fails = 1
                report_result = "content-failure"
            elif "Congratulations! Your chart has been certified and will be published shortly" in comment.body:
                report_result = "report-pass"
            elif "Community charts require maintainer review and approval" in comment.body:
                report_result = "community_review"
            num_builds +=1

        if report_result:
            check_properties ={ "type" : type, "result" : report_result, "failures" : num_fails, "pr" : pr.number}
            send_event_metric("metrics-report","report_run",check_properties,comment.created_at)

    return num_builds

def process_pull_requests(token):

    pattern = re.compile(r"charts/([\w-]+)/([\w-]+)/([\w\.-]+)/([\w\.-]+)/.*")

    ignore_users=["zonggen","mmulholla","dperaza4dustbit","openshift-helm-charts-bot","baijum","tisutisu"]
    g = Github(token)
    repo = g.get_repo("openshift-helm-charts/charts")
    pull_requests = repo.get_pulls(state="open,closed")
    for pr in pull_requests:
        write_out(f"PR number: {pr.number}")
        write_out(f"    state: {pr.state}")
        write_out(f"    user: {pr.user.login}")
        write_out(f"    created: {pr.created_at}")
        write_out(f"    merged: {pr.merged_at}")
        if not check_pr(pr.number):
            write_out(f"XXX ignore pr - already processed")
        elif pr.closed_at and not pr.merged_at:
            write_out("     ignore, closed but not merged!")
            write_out(f"         closed: {pr.closed_at}")
            write_out(f"         merged: {pr.merged_at}")
        elif pr.user.login in ignore_users:
            write_out("      ignore user")
            write_out(f"         user: {pr.user.login}")
        elif pr.draft or pr.base.ref != "main":
            write_out("      ignore draft pr or main branch os not targetted")
            write_out(f"         draft: {pr.draft}")
            write_out(f"         base ref: {pr.base.ref}")
        elif pr.merged_at:
            write_out(f"    user: {pr.user.login}")
            commits=pr.get_commits()
            pr_chart_submission_files = []
            for commit  in commits:
                write_out(f"    commit: {commit.url}")
                write_out(f"    commit parents: {len(commit.parents)}")
                if len(commit.parents) < 2:
                    files = commit.files
                    for file in files:
                        write_out(f"      file: {file.filename}")
                        write_out(f"      file status: {file.status}")
                        if pattern.match(file.filename):
                            if file.status != "removed" and not file.filename in pr_chart_submission_files:
                                pr_chart_submission_files.append(file.filename)
                            elif file.status == "removed" and file.filename in pr_chart_submission_files:
                                pr_chart_submission_files.remove(file.filename)
                        else:
                            write_out(f'ignore non chart file : {file.filename}')

            if len(pr_chart_submission_files) > 0:
                write_out(f"    Found unique files: {len(pr_chart_submission_files)}")
                match = pattern.match(pr_chart_submission_files[0])
                type,org,chart,version = match.groups()
                write_out(f"    type: {type},org: {org},chart: {chart},version: {version}")
                tgz_found = False
                report_found = False
                src_found = False
                for file in pr_chart_submission_files:
                    filename = os.path.basename(file)
                    if filename == "report.yaml":
                        report_found = True
                    elif filename.endswith(".tgz"):
                        tgz_found = True
                    elif filename == "Chart.yaml" and len(pr_chart_submission_files) > 2:
                        src_found = True

                pr_content = "undetermined"
                if report_found:
                    if tgz_found:
                        pr_content = "report and tgz"
                    elif src_found:
                        pr_content = "src and report"
                    else:
                        pr_content = "report only"
                elif tgz_found:
                    pr_content = "tgz only"
                elif src_found:
                    pr_content = "src only"

                builds =  process_comments(repo,pr,type)
                write_out(f"    PR  build cycles : {builds}")

                submission_properties ={ "type" : type, "pr content" : pr_content, "pr" : pr.number}
                send_event_metric(f"metrics-PR{pr.number}","pr_submission",submission_properties,pr.created_at)

                elapsed_time = pr.merged_at - pr.created_at
                # round up to an hour to avoid 0 time
                elapsed_hours = elapsed_time.total_seconds()//3600
                duration = "0-1 hours"
                if 24 > elapsed_hours > 1:
                    duration = "1-24 hours"
                elif 168 > elapsed_hours > 24:
                    duration = "1-7 days"
                elif elapsed_hours > 168:
                    duration= "> 7 days"

                build_out = str(builds)
                if builds > 5:
                    build_out = "> 5"

                merged_properties = { "type" : type, "builds" : build_out, "duration(hrs)" : duration, "pr" : pr.number}
                send_event_metric(f"metrics-PR{pr.number}","pr_merged",merged_properties,pr.merged_at)

            log_pr(pr.number)
        else:
            write_out(f"Ignore irrelevant/active PR{pr.number}")




def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--force-all", dest="force_all", action=argparse.BooleanOptionalAction,
                        help="Force recreate of all metrics",default=False)
    args = parser.parse_args()

    write_out(f'force-all arg: {args.force_all}')

    init(args.force_all)

    analytics.write_key = "Blah"
    analytics.on_error = on_error

    process_pull_requests("BlahBlah")


if __name__ == '__main__':
    main()
