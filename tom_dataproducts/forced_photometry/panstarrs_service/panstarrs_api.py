import logging

from django.conf import settings

import requests


logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


def get_base_url():
    """return the PanSTARRS MAST API base URL from settings
    """
    # the configuration in settings.py has all been vetted in
    # panstarrs.PanstarrsForcedPhotometryService.query_service()
    base_url = settings.FORCED_PHOTOMETRY_SERVICES.get('PANSTARRS', {}).get('url')

    return base_url


def get_data_release_choices():
    """return the PanSTARRS data release choices
    """
    return [
        ('dr1', 'PS1 DR1'),
        ('dr2', 'PS1 DR2'),
    ]


def get_catalog_choices(data_release='dr2'):
    """return the PanSTARRS catalog choices

    NOTE: at the moment, only queries to the 'Mean object' catalog are supported.

    Data Release 1 (DR1) has only mean and stacked object catalogs.
    Unless otherwise specified, return the full list of DR2 choices.
    """
    choices = [  # DR2 choices
        ('mean', 'Mean object'),
        # TODO: support additional catalogs
        # ('stack', 'Stacked object'),
        # ('forced_mean', 'Forced mean object'),
        # ('detection', 'Detections'),
    ]

    if data_release == 'dr1':
        choices = [  # DR1 choices
            ('mean', 'Mean object'),
            ('stack', 'Stacked object'),
        ]
    return choices


def get_default_columns(catalog='mean'):
    """Currently, only the 'Mean object' catalog is supported and only the columns
    specified in the default_columns list are returned.
    """
    default_columns = [
        'objID',
        'objName',
        'raMean',
        'decMean',
        'raMeanErr',
        'decMeanErr',
        'epochMean',  # MJD
        'nDetections',
        'ng',
        'nr',
        'ni',
        'nz',
        'ny',
        # g band
        'gMeanPSFMag',
        'gMeanPSFMagErr',
        # 'gMeanPSFMagStd',
        # 'gMeanPSFMagNpt',
        # 'gMeanPSFMagMin',
        # 'gMeanPSFMagMax',
        # 'gMeanKronMag',
        # 'gMeanKronMagErr',
        # 'gMeanKronMagStd',
        # 'gMeanKronMagNpt',
        # r band
        'rMeanPSFMag',
        'rMeanPSFMagErr',
        # 'rMeanPSFMagStd',
        # 'rMeanPSFMagNpt',
        # 'rMeanPSFMagMin',
        # 'rMeanPSFMagMax',
        # 'rMeanKronMag',
        # 'rMeanKronMagErr',
        # 'rMeanKronMagStd',
        # 'rMeanKronMagNpt',
        # i band
        'iMeanPSFMag',
        'iMeanPSFMagErr',
        # 'iMeanPSFMagStd',
        # 'iMeanPSFMagNpt',
        # 'iMeanPSFMagMin',
        # 'iMeanPSFMagMax',
        # 'iMeanKronMag',
        # 'iMeanKronMagErr',
        # 'iMeanKronMagStd',
        # 'iMeanKronMagNpt',
        # z band
        'zMeanPSFMag',
        'zMeanPSFMagErr',
        # 'zMeanPSFMagStd',
        # 'zMeanPSFMagNpt',
        # 'zMeanPSFMagMin',
        # 'zMeanPSFMagMax',
        # 'zMeanKronMag',
        # 'zMeanKronMagErr',
        # 'zMeanKronMagStd',
        # 'zMeanKronMagNpt',
        # y band
        'yMeanPSFMag',
        'yMeanPSFMagErr',
        # yMeanPSFMagStd',
        # yMeanPSFMagNpt',
        # yMeanPSFMagMin',
        # yMeanPSFMagMax',
        # yMeanKronMag',
        # yMeanKronMagErr',
        # yMeanKronMagStd',
        # yMeanKronMagNpt',
    ]
    return default_columns


def mast_query(request_data, table='mean', release='dr2', output_format='csv',
               columns=None, **kwargs):
    """Perform a MAST query.
    based on https://ps1images.stsci.edu/ps1_dr2_api.html

    Parameters

    Parameters
    ----------
    table (string): mean, stack, or detection
    release (string): dr1 or dr2
    format (string): csv, votable, json
    request_data (dict): dictionary of request data
    columns: list of column names to include (None means use defaults)
    **kw: other parameters (e.g., 'nDetections.min':2).  Note this is required!

    NOTE: for the moment the "default columns" differ from the default columns
    given by https://catalogs.mast.stsci.edu/panstarrs/. See the default_columns
    list for the current defaults.

    * table, release, format become part of the URL.
    * columns, request_data, and kwargs become part of the request parameters.
    ----------
    Returns HTTPResponse from the requests.get() call
    """
    url = f'{get_base_url()}/{release}/{table}.{output_format}'

    # set up the request data
    data = kwargs.copy()  # start with the kwargs
    data.update(request_data)  # add the request_data
    data['columns'] = get_default_columns()  # add the default columns

    logger.debug(f'url: {url}')
    logger.debug(f'data {data}')

    response = requests.get(url, params=data)
    response.raise_for_status()

    return response
