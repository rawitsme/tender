"""Registry to manage all connector instances."""

from typing import Dict
from backend.ingestion.base_connector import BaseConnector
from backend.ingestion.connectors.gem import GeMConnector

# Selenium-based connectors for CAPTCHA-protected portals
from backend.ingestion.connectors.cppp_selenium import CPPPSeleniumConnector
from backend.ingestion.connectors.nic_selenium import NICSeleniumConnector


CONNECTORS: Dict[str, type] = {
    "gem": GeMConnector,
}

# NIC Selenium connectors require state_key arg
NIC_STATES = ["cppp", "up", "maharashtra", "uttarakhand", "haryana", "mp"]


def get_connector(source: str) -> BaseConnector:
    """Get an instance of the connector for the given source."""
    if source in CONNECTORS:
        return CONNECTORS[source]()
    if source == "cppp":
        return CPPPSeleniumConnector()
    if source in NIC_STATES:
        return NICSeleniumConnector(source)
    raise ValueError(f"Unknown source: {source}. Available: {list(CONNECTORS.keys()) + NIC_STATES}")


def get_all_connectors() -> Dict[str, BaseConnector]:
    """Get instances of all connectors."""
    connectors = {name: cls() for name, cls in CONNECTORS.items()}
    connectors["cppp"] = CPPPSeleniumConnector()
    for state in ["up", "maharashtra", "uttarakhand", "haryana", "mp"]:
        connectors[state] = NICSeleniumConnector(state)
    return connectors
