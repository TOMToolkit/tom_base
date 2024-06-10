from django.conf import settings
import pyvo

from tom_alerts.alerts import GenericAlert, GenericBroker, GenericQueryForm


class RSPQueryForm(GenericQueryForm):
    """"""
    pass


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

    def build_query(self):
        """"""
        return "SELECT TOP 10 * FROM dp02_dc2_catalogs.Object"

    def fetch_alerts(self, parameters):
        """"""
        query = self.build_query()
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
        pass
