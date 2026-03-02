"""Madhya Pradesh eProcurement portal connector.
Portal: https://mptenders.gov.in
"""

from backend.ingestion.connectors.nic_base import NICBaseConnector


class MPConnector(NICBaseConnector):
    source_name = "mp"
    base_url = "https://mptenders.gov.in"
    state = "Madhya Pradesh"
