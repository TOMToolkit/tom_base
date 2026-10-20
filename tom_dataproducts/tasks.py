import requests
import time
import logging
import re
from astropy.time import Time
from urllib.parse import urlparse
from django.conf import settings
from django.utils import timezone
from django_tasks import task

from tom_targets.models import Target
from tom_dataproducts.models import DataProduct
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.data_processor import run_data_processor
from tom_dataproducts.api_views import ATLASProcessorView

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

@task
def atlas_query(*args, **kwargs):
    """just a wrapper on trigger_atlas_fp for backwards compatability"""
    return trigger_atlas_fp(*args, **kwargs)

def trigger_atlas_fp(min_date_mjd, max_date_mjd, target_id, data_product_type, use_reduced=False, use_callback=True):
    logger.debug('Calling atlas query!')
    target = Target.objects.get(pk=target_id)
    headers = {"Authorization": f"Token {settings.SINGLE_TARGET_DATA_SERVICES.get('ATLAS', {}).get('api_key')}",
               "Accept": "application/json"}
    base_url = settings.SINGLE_TARGET_DATA_SERVICES.get('ATLAS', {}).get('url')

    task_url = None
    while not task_url:
        with requests.Session() as s:
            task_data = {"ra": target.ra, "dec": target.dec, "mjd_min": min_date_mjd, "send_email": False,
                         "use_reduced": use_reduced}

            ran_with_callback = False
            if use_callback:
                if not getattr(settings, "ATLAS_CALLBACK_URL", None):
                    logger.error("ATLAS_CALLBACK_URL is not set in settings, defaulting to waiting for ATLAS FP job to finish!")
                else:    
                    task_data["callback_url"] = settings.ATLAS_CALLBACK_URL
                    ran_with_callback = True
                    
            if max_date_mjd:
                task_data['mjd_max'] = max_date_mjd
            resp = s.post(
                f"{base_url}/queue/", headers=headers,
                data=task_data)

            if resp.status_code == 201:
                task_url = resp.json()["url"]
                logger.debug(f"The task url is {task_url}")
            elif resp.status_code == 429:
                message = resp.json()["detail"]
                logger.debug(f"{resp.status_code} {message}")
                t_sec = re.findall(r"available in (\d+) seconds", message)
                t_min = re.findall(r"available in (\d+) minutes", message)
                if t_sec:
                    waittime = int(t_sec[0])
                elif t_min:
                    waittime = int(t_min[0]) * 60
                else:
                    waittime = 10
                logger.debug(f"Waiting {waittime} seconds")
                time.sleep(waittime)
            else:
                logger.error(f"Failed to queue Atlas task: HTTP Error {resp.status_code} - {resp.text}")
                return False

    if ran_with_callback:
        logger.info("Queued ATLAS FP job, ATLAS will report back when job finishes, exiting")
        return True

    return ATLASProcessorView.process_atlas_fp_results(task_url, target, data_product_type)

