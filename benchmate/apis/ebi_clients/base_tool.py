from urllib.parse import urlencode

from .utils import BASE_URL
from .utils import get_user_agent, rest_request, poll_job, retrieve_job_results


class BaseTool:
    """Base class for EBI Job Dispatcher tools."""

    def __init__(self, email, tool_name):
        self.email = email
        self.tool_name = tool_name
        self.base_url = f"{BASE_URL}/{self.tool_name}"

    def run_async(self, params):
        """Submit an asynchronous job."""
        params["email"] = self.email
        url = f"{self.base_url}/run"
        headers = {"User-Agent": get_user_agent(f"{self.tool_name}.py"),
                   "Content-Type": "application/x-www-form-urlencoded"}
        data = urlencode(params)
        response = rest_request(url, headers, method="POST", data=data)
        return response.text.strip()

    def run_sync(self, params, outfile=None):
        """Run a synchronous job."""
        job_id = self.run_async(params)
        status = poll_job(job_id, self.tool_name, self.email)
        if status == "FINISHED":
            return retrieve_job_results(job_id, self.tool_name, outfile)
        else:
            raise Exception(f"Job {job_id} failed.")


class Dbfetch:
    """Client for Dbfetch database entry retrieval."""

    def __init__(self, email):
        self.email = email
        self.base_url = "https://www.ebi.ac.uk/Tools/dbfetch/dbfetch"

    def run_async(self, params):
        """Dbfetch does not support asynchronous jobs."""
        raise NotImplementedError("Dbfetch does not support asynchronous jobs.")

    def run_sync(self, params, outfile=None):
        """Fetch database entries synchronously."""
        method = params.get("method", "fetchData")
        db_id = params.get("db_id")
        format = params.get("format", "default")
        style = params.get("style", "raw")

        url = f"{self.base_url}/{db_id}/{format}/{style}" if method == "fetchData" else f"{self.base_url}/{method}"
        headers = {"User-Agent": get_user_agent("dbfetch.py"), "Accept": "text/plain"}
        response = rest_request(url, headers)
        result = response.text
        if outfile:
            with open(outfile, "w") as f:
                f.write(result)
        return result
