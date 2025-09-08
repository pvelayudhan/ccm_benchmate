import warnings
import requests

def warn_for_status(response, message):
    """
    Check the status of a response and issue a warning if the status code is not 200. I should not be holding hands but i might as well
    """
    if response.status_code != 200:
        warnings.warn("Response status code: {}, status message {}".format(response.status_code, message))
        return None
    else:
        return response.content.decode().strip()