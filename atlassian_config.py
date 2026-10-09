from configparser import ConfigParser

from constants import ATLASSIAN_CONFIG_FILE

_ini_atlassian_config = ConfigParser()
_ini_atlassian_config.read(ATLASSIAN_CONFIG_FILE)

JIRA_AUTH_URL = _ini_atlassian_config['Jira']['auth_url']
JIRA_BASE_URL = _ini_atlassian_config['Jira']['base_url']
ATLASSIAN_USERNAME = _ini_atlassian_config['Jira']['username']
ATLASSIAN_PASSWORD = _ini_atlassian_config['Jira']['password']
ZEPHYR_URL = _ini_atlassian_config['Zephyr']['base_url']
