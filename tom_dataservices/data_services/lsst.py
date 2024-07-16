from django.conf import settings
from django import forms
from crispy_forms.layout import HTML, Layout, Fieldset, Row, Column
import pyvo

from tom_alerts.alerts import GenericAlert, GenericBroker, GenericQueryForm


class RSPQueryForm(GenericQueryForm):
    """"""
    rubin_id = forms.CharField(
        required=False,
        label='Rubin ID',
    )
    ra = forms.FloatField(
        required=False,
        label='RA',
        widget=forms.TextInput(attrs={'placeholder': 'RA (Degrees)'})
    )
    dec = forms.FloatField(
        required=False,
        label='Dec',
        widget=forms.TextInput(attrs={'placeholder': 'Dec (Degrees)'})
    )
    radius = forms.IntegerField(
        required=False,
        label='Search Radius',
        widget=forms.TextInput(attrs={'placeholder': 'Radius (Arcseconds)'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            HTML('''
                <p>
                Please see the <a href="https://data.lsst.cloud/" target="_blank">Ruben Science Platform homepage</a> 
                for information about how to access the RSP Portal.
            '''),
            self.common_layout,
            Fieldset(
                'Identifier Search',
                Row(
                    Column('rubin_id'),
                )
            ),
            Fieldset(
                'Cone Search',
                Row(
                    Column('ra'),
                    Column('dec'),
                    Column('radius'),
                )
            ),
        )

    def clean(self):
        cleaned_data = super().clean()

        # Ensure that all cone search fields are present
        if (any(cleaned_data[k] for k in ['ra', 'dec', 'radius'])
                and not all(cleaned_data[k] for k in ['ra', 'dec', 'radius'])):
            raise forms.ValidationError('All of RA, Dec, and Search Radius must be included to execute a cone search.')


class RSPMultiTargetDataService(GenericBroker):
    """"""
    name = 'RSP'
    form = RSPQueryForm

    def query_service(self, query):
        """"""
        RSP_TAP_SERVICE = 'https://data.lsst.cloud/api/tap'
        token_str = settings.RSP_TOKEN
        cred = pyvo.auth.CredentialStore()
        cred.set_password("x-oauth-basic", token_str)
        credential = cred.get("ivo://ivoa.net/sso#BasicAA")
        rsp_tap = pyvo.dal.TAPService(RSP_TAP_SERVICE, credential)
        results = rsp_tap.run_sync(query)
        return results.to_table()

    def get_catalogs(self):
        """"""
        query = "SELECT * FROM tap_schema.tables " \
            "WHERE tap_schema.tables.schema_name = 'dp02_dc2_catalogs' " \
            "order by table_index ASC"
        results = self.query_service(query)
        return results['table_name']

    def build_query(self, parameters):
        """"""
        max_rec = '10'
        if all([parameters['ra'], parameters['dec'], parameters['radius']]):
            return f"SELECT TOP {max_rec} * FROM dp02_dc2_catalogs.Object " \
                   f"WHERE CONTAINS(POINT('ICRS', coord_ra, coord_dec), " \
                   f"CIRCLE('ICRS', {parameters['ra']}, {parameters['dec']}, {parameters['radius']}/3600.0)) = 1 " \
                   f"AND detect_isPrimary = 1 "
        elif parameters['rubin_id']:
            return f"SELECT * FROM dp02_dc2_catalogs.Object " \
                   f"WHERE objectId = '{parameters['rubin_id']}'"
        return "SELECT TOP 10 * FROM dp02_dc2_catalogs.Object"

    def fetch_alerts(self, parameters):
        """"""
        query = self.build_query(parameters)
        results = self.query_service(query)
        return iter(results)

    def to_generic_alert(self, alert):
        """"""
        return GenericAlert(
            timestamp=None,
            url=None,
            id=alert['objectId'],
            name=alert['objectId'],
            ra=alert['coord_ra'],
            dec=alert['coord_dec'],
            mag=None,
            score=None
        )
