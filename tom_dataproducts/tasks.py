# Place dramatiq asynchronous tasks here - they are auto-discovered

import dramatiq
import requests
import time
import logging
import re
from astropy.time import Time
from urllib.parse import urlparse
from django.conf import settings
from django.utils import timezone
from django.core.files.base import ContentFile

from tom_targets.models import Target
from tom_dataproducts.models import DataProduct
from tom_dataproducts.exceptions import InvalidFileFormatException
from tom_dataproducts.data_processor import run_data_processor

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@dramatiq.actor(max_retries=0)
def atlas_query(min_date_mjd, max_date_mjd, target_id, data_product_type):
    logger.debug('Calling atlas query!')
    target = Target.objects.get(pk=target_id)
    headers = {"Authorization": f"Token {settings.FORCED_PHOTOMETRY_SERVICES.get('ATLAS', {}).get('api_key')}",
               "Accept": "application/json"}
    base_url = settings.FORCED_PHOTOMETRY_SERVICES.get('ATLAS', {}).get('url')
    task_url = None
    while not task_url:
        with requests.Session() as s:
            task_data = {"ra": target.ra, "dec": target.dec, "mjd_min": min_date_mjd, "send_email": False}
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

    result_url = None
    taskstarted_printed = False
    while not result_url:
        with requests.Session() as s:
            resp = s.get(task_url, headers=headers)

            if resp.status_code == 200:
                if resp.json()["finishtimestamp"]:
                    result_url = resp.json()["result_url"]  # PART WHEN QUERY IS COMPLETE
                    logger.debug(f"Task is complete with results available at {result_url}")
                elif resp.json()["starttimestamp"]:
                    if not taskstarted_printed:
                        logger.debug(f"Task is running (started at {resp.json()['starttimestamp']})")
                        taskstarted_printed = True
                    time.sleep(2)
                else:
                    logger.debug(f"Waiting for job to start (queued at {resp.json()['timestamp']})")
                    time.sleep(4)
            else:
                logger.error(f"Failed to retrieve Atlas task status: HTTP Error {resp.status_code} - {resp.text}")
                return False

    results = requests.get(result_url, headers=headers)
    dp_name = f"atlas_{Time(min_date_mjd, format='mjd').strftime('%Y_%m_%d')}"
    if max_date_mjd:
        dp_name += f"-{Time(max_date_mjd, format='mjd').strftime('%Y_%m_%d')}"
    dp_name += f"_{urlparse(result_url)[2].rpartition('/')[2]}"
    file = ContentFile(results.content, name=dp_name)

    dp = DataProduct.objects.create(
        product_id=dp_name,
        target=target,
        data=file,
        data_product_type=data_product_type,
        extra_data=f'Queried from Atlas within the TOM on {timezone.now().isoformat()}'
    )
    logger.info(f"Created dataproduct {dp_name} from atlas query")

    try:
        run_data_processor(dp)
    except InvalidFileFormatException as e:
        logger.error(f"Error processing returned Atlas data into ReducedDatums: {repr(e)}")
        return False

    return True
