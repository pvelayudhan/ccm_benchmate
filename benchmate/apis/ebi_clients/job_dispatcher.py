from benchmate.apis.ebi_clients.base_tool import Dbfetch
from benchmate.apis.ebi_clients.tools import (
    ClustalOmega,
    EMBOSS_Pepinfo,
    EMBOSS_Backtranseq,
    InterProScan5,
    Lalign,
    Muscle,
    NCBIBlast,
    TCoffee,
    Wise
)
from benchmate.apis.ebi_clients.utils import poll_job, retrieve_job_results


class JobDispatcher:
    """Main interface to interact with EBI Job Dispatcher tools."""

    TOOLS = {
        "clustalo": ClustalOmega,
        "emboss_pepinfo": EMBOSS_Pepinfo,
        "dbfetch": Dbfetch,
        "emboss_backtranseq": EMBOSS_Backtranseq,
        "iprscan5": InterProScan5,
        "lalign": Lalign,
        "muscle": Muscle,
        "ncbiblast": NCBIBlast,
        "tcoffee": TCoffee,
        "wise": Wise
    }

    def __init__(self, email):
        """Initialize with a user email for API access."""
        if not email or "@" not in email:
            raise ValueError("A valid email address is required.")
        self.email = email

    def list_tools(self):
        """Return a list of available tools."""
        return list(self.TOOLS.keys())

    def run_tool(self, tool_name, params, async_job=False, outfile=None):
        """Run a specified tool with given parameters."""
        if tool_name not in self.TOOLS:
            raise ValueError(f"Tool {tool_name} not supported. Available tools: {self.list_tools()}")

        tool_class = self.TOOLS[tool_name]
        tool_instance = tool_class(self.email)

        if async_job:
            job_id = tool_instance.run_async(params)
            return {"job_id": job_id}
        else:
            result = tool_instance.run_sync(params, outfile)
            return result

    def check_status(self, tool_name, job_id):
        """Check the status of an asynchronous job."""
        if tool_name not in self.TOOLS:
            raise ValueError(f"Tool {tool_name} not supported.")
        return poll_job(job_id, tool_name, self.email)

    def retrieve_results(self, tool_name, job_id, outfile=None):
        """Retrieve results for a completed job."""
        if tool_name not in self.TOOLS:
            raise ValueError(f"Tool {tool_name} not supported.")
        return retrieve_job_results(job_id, tool_name, outfile)
