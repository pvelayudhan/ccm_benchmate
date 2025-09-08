import platform
import sys
import time

import requests

# this is mostly aggregated from https://github.com/ebi-jdispatcher/webservice-clients/tree/master/python there were a lot
# of redundancies, they are just integrated into utils and a simple base runner
# Configuration
BASE_URL = "https://www.ebi.ac.uk/Tools/services/rest"
POLL_FREQ = 3  # Seconds between status checks
OUTPUT_LEVEL = 1
DEBUG_LEVEL = 0


def get_user_agent(script_name, version="2024-03-20"):
    """Generate a user-agent string for HTTP requests."""
    urllib_version = requests.__version__
    urllib_agent = f"Python-requests/{urllib_version}"
    try:
        python_version = platform.python_version()
        python_sys = platform.system()
    except ValueError:
        python_version, python_sys = "Unknown", "Unknown"
    user_agent = f"EBI-Sample-Client/{version} ({script_name}; Python {python_version}; {python_sys}) {urllib_agent}"
    print_debug_message("get_user_agent", f"user_agent: {user_agent}", 12)
    return user_agent


def print_debug_message(function_name, message, level):
    """Print debug messages based on debug level."""
    if level <= DEBUG_LEVEL:
        print(f"[{function_name}] {message}", file=sys.stderr)


def rest_request(url, headers=None, method="GET", data=None):
    """Make a REST request to the specified URL."""
    print_debug_message("rest_request", f"url: {url}", 11)
    if headers is None:
        headers = {"User-Agent": get_user_agent("utils.py")}
    try:
        if method == "POST":
            response = requests.post(url, headers=headers, data=data)
        else:
            response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        print_debug_message("rest_request", f"HTTP Error: {e}", 1)
        raise
    except Exception as e:
        print_debug_message("rest_request", f"Error: {e}", 1)
        raise


def read_file(file_path):
    """Read content from a file."""
    print_debug_message("read_file", f"Reading file: {file_path}", 11)
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        print_debug_message("read_file", f"Error reading file: {e}", 1)
        raise


def poll_job(job_id, tool_name, email):
    """Poll the status of an asynchronous job."""
    url = f"{BASE_URL}/{tool_name}/status/{job_id}"
    headers = {"User-Agent": get_user_agent(f"{tool_name}.py"), "Accept": "text/plain"}
    while True:
        response = rest_request(url, headers)
        status = response.text.strip()
        print_debug_message("poll_job", f"Job {job_id} status: {status}", 1)
        if status in ["RUNNING", "PENDING"]:
            time.sleep(POLL_FREQ)
        elif status == "FINISHED":
            return status
        else:
            raise Exception(f"Job {job_id} failed with status: {status}")


def retrieve_job_results(job_id, tool_name, outfile=None):
    """Retrieve results for a completed job."""
    url = f"{BASE_URL}/{tool_name}/result/{job_id}/out"
    headers = {"User-Agent": get_user_agent(f"{tool_name}.py"), "Accept": "text/plain"}
    response = rest_request(url, headers)
    result = response.text
    if outfile:
        with open(outfile, "w") as f:
            f.write(result)
    return result
