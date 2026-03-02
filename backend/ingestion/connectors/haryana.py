"""Haryana eProcurement portal connector.
Portal: https://etenders.hry.nic.in
"""

from backend.ingestion.connectors.nic_base import NICBaseConnector


class HaryanaConnector(NICBaseConnector):
    source_name = "haryana"
    base_url = "https://etenders.hry.nic.in"
    state = "Haryana"
