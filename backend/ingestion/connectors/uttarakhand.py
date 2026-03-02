"""Uttarakhand eProcurement portal connector.
Portal: https://uktenders.gov.in
"""

from backend.ingestion.connectors.nic_base import NICBaseConnector


class UttarakhandConnector(NICBaseConnector):
    source_name = "uttarakhand"
    base_url = "https://uktenders.gov.in"
    state = "Uttarakhand"
