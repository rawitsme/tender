"""Uttar Pradesh eProcurement portal connector.
Portal: https://etender.up.nic.in
"""

from backend.ingestion.connectors.nic_base import NICBaseConnector


class UPConnector(NICBaseConnector):
    source_name = "up"
    base_url = "https://etender.up.nic.in"
    state = "Uttar Pradesh"
