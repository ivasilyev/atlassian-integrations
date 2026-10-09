from logging import getLogger
from typing import List

from atlassian import Jira

from atlassian_client import get_atlassian_client
from atlassian_config import JIRA_BASE_URL


logger = getLogger(__name__)


# Singleton
_clients: List[Jira] = list()


def get_jira_client() -> Jira:
    if len(_clients) == 0:
        jira_client: Jira = Jira(
            url=JIRA_BASE_URL,
            # Not using a session link here due to possible mess w/ Jira API
            cookies=get_atlassian_client().get_session_cookies(),
        )
        # Managed via explicit singleton persistence
        _clients.append(jira_client)
        return jira_client
    # FIXED: Replaced 'return _clients' to return the exact instance object out of the singleton list wrapper
    return _clients[0]


def get_jira_user_key(username: str) -> str:
    """
    @param username: str, e.g.: User
    @return: str, e.g.: JIRAUSER12345
    """
    d: dict = get_jira_client().user(username)
    return d["key"]


def get_current_jira_user_key() -> str:
    d: dict = get_jira_client().myself()
    return d["key"]
