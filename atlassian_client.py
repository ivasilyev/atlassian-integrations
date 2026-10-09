import warnings
from logging import getLogger
from typing import Any, List

from requests import Session, Response
from requests.cookies import RequestsCookieJar

from atlassian_config import ATLASSIAN_USERNAME, ATLASSIAN_PASSWORD, JIRA_AUTH_URL
from utils import get_json_content_type_header, is_empty, filter_https_warnings, convert_dict_to_web_payload, convert_dict_to_pretty_string, \
    replace_value_if_jsonpath_exists


logger = getLogger(__name__)


class AtlassianClient:
    def __init__(self):
        self._session: Session = Session()
        self._is_logged_in: bool = False

    def get_session(self) -> Session:
        return self._session

    def get_session_cookies(self) -> RequestsCookieJar:
        return self._session.cookies

    @staticmethod
    def _log_masked_response_data(d: dict):
        # Mask JSESSIONID
        _d = replace_value_if_jsonpath_exists(d, "session.value")
        logger.debug(f"Response data:\n\t{convert_dict_to_pretty_string(_d)}")

    def get(
        self,
        url: str,
        headers: dict = None,
    ) -> Response:
        logger.debug(f"Get from URL: '{url}'")
        if is_empty(headers):
            headers = get_json_content_type_header()
        with warnings.catch_warnings():
            filter_https_warnings()
            response = self._session.get(
                url=url,
                headers=headers,
                stream=True,
                # verify=False,
            )
        self._log_masked_response_data(response.json())
        return response

    def post(
        self,
        url: str,
        payload: dict = None,
        headers: dict = None,
        files: dict = None,
    ) -> Response:
        logger.debug(f"Post to URL: '{url}'")
        if isinstance(payload, dict):
            data: str = convert_dict_to_web_payload(payload)
        else:
            data: Any = payload

        if is_empty(headers):
            headers = get_json_content_type_header()
        with warnings.catch_warnings():
            filter_https_warnings()
            response = self._session.post(
                url,
                data=data,
                headers=headers,
                files=files,
                stream=True,
                # verify=False,
            )
        self._log_masked_response_data(response.json())
        return response


    def login_to_jira(self):
        url = JIRA_AUTH_URL
        try:
            self._session.head(url)
        except:
            # trust website certificate logic
            pass
        # Use Jira as the central authentication point
        request_body = {
            "username": ATLASSIAN_USERNAME,
            "password": ATLASSIAN_PASSWORD,
        }
        response = self.post(
            url,
            payload=request_body,
        )
        assert response.status_code == 200, f"{ATLASSIAN_USERNAME} | Unable to login to Jira"
        logger.info(f"{ATLASSIAN_USERNAME} | Logged into Jira")

    def __enter__(self):
        if self._is_logged_in:
            return
        self.login_to_jira()
        return self

    def __exit__(self, exc_type=None, exc_val=None, exc_tb=None):
        if not self._is_logged_in:
            return
        self._session.close()
        self._is_logged_in = False
        return self

    def get_jsessionid(self) -> str:
        return self._session.cookies.get("JSESSIONID")

    def get_xsrf_token(self) -> str:
        return self._session.cookies.get("atlassian.xsrf.token")


# Singleton
_clients: List[AtlassianClient] = list()


def get_atlassian_client() -> AtlassianClient:
    if len(_clients) == 0:
        atlassian_client: AtlassianClient = AtlassianClient()
        atlassian_client.__enter__()
        _clients.append(atlassian_client)
        return atlassian_client
    return _clients[0]


def atlassian_get(
    url: str,
    headers: dict = None,
) -> Response:
    return get_atlassian_client().get(
        url=url,
        headers=headers,
    )


def atlassian_post(
    url: str,
    payload: dict = None,
    headers: dict = None,
    files: dict = None,
) -> Response:
    return get_atlassian_client().post(
        url=url,
        payload=payload,
        headers=headers,
        files=files,
    )


def shutdown_atlassian_client():
    get_atlassian_client().__exit__()




