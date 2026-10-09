import os.path
from datetime import datetime, timedelta
from logging import getLogger
from time import sleep
from typing import List, Any, Dict, Optional, AnyStr

from zephyr import API_V1, ZephyrScale

from atlassian_client import get_atlassian_client, shutdown_atlassian_client
from atlassian_config import ZEPHYR_URL
from constants import ZEPHYR_TEST_RUN_KEY, ZEPHYR_SYNC
from jira_client import get_current_jira_user_key
from models import ZephyrTestCaseDto, ZephyrTestStatus
from utils import TIME_Z_KEBAB_CASE_TEMPLATE, get_timestamp, get_duration_seconds, get_present_utc_time, is_empty, convert_dict_to_pretty_string, dump_string, convert_model_to_dict, convert_models_list_to_dicts_list, end_with_slash

logger = getLogger(__name__)


def get_test_status(b: bool) -> str:
    if b:
        return ZephyrTestStatus.ZEPHYR_TEST_PASSED
    return ZephyrTestStatus.ZEPHYR_TEST_FAILED

# Singleton
_clients: List[ZephyrScale] = list()


def get_zephyr_client() -> ZephyrScale:
    if len(_clients) == 0:
        base_url = end_with_slash(ZEPHYR_URL)
        zscale: ZephyrScale = ZephyrScale(
            base_url=base_url,
            api_version=API_V1,
            cookies=get_atlassian_client().get_session_cookies(),
        )
        _clients.append(zscale)
        return zscale
    return _clients[0]


def create_test_case(
    project_key: str,
    test_case_name: str,
    test_case_objective: str,
    folder: str,
    status_name: str,
    priority_name: str,
    test_case_steps: List[Dict[str, str]],
    test_case_key: Optional[str] = None,
) -> str:
    logger.info("create_test_case")
    zapi = get_zephyr_client().api
    if is_empty(test_case_key):
        kwargs = {
            "project_key": project_key,
            "name": test_case_name,
            "objective": test_case_objective,
            "folder": folder,
            "status": status_name,
            "priority": priority_name,
        }
        logger.debug("create_test_case payload=" + convert_dict_to_pretty_string(kwargs))
        response: dict = zapi.test_cases.create_test_case(**kwargs)
        # {'key': 'PROJ123-T123'}
        logger.debug("create_test_case response=" + convert_dict_to_pretty_string(response))
        test_case_key = response.get("key")
    else:
        logger.debug(f"Skip test case ID creation as it exists: '{test_case_key}'")
    assert not is_empty(test_case_key)
    steps_payload = {
        "testScript": {
            "type": "STEP_BY_STEP",
            "steps": test_case_steps
        }
    }
    logger.debug(f"create_test_case steps_payload=" + convert_dict_to_pretty_string(steps_payload))
    steps_response = zapi.session.put(endpoint=f"testcase/{test_case_key}", json=steps_payload)  # ''
    logger.debug(f"create_test_case steps_response=" + steps_response)
    return test_case_key


def create_test_case_by_dto(dto: ZephyrTestCaseDto):
    d0: dict = convert_model_to_dict(dto)
    test_case_key: str = create_test_case(**d0)
    dto.test_case_key = test_case_key
    d1: dict = convert_model_to_dict(dto)
    logger.debug("Updated ZephyrTestCase:\n\t" + convert_dict_to_pretty_string(d1))


def create_test_cases(dtos: List[ZephyrTestCaseDto]):
    for dto in dtos:
        try:
            create_test_case_by_dto(dto)
        except Exception as e:
            logger.warning(e)
        sleep(5)
    dicts: List[dict] = convert_models_list_to_dicts_list(dtos)
    string = convert_dict_to_pretty_string(dicts)
    logger.info("Final ZephyrTestCases:\n\t" + string)


def create_test_run(
    project_key: str = None,
    name: str = None,
):
    """
    @param project_key:
    @param name:
    @return:
    """
    payload = dict(
        folder="Python",
        description="Created via REST API",
    )
    d: dict = get_zephyr_client().api.test_runs.create_test_run(
        project_key=project_key,
        name=name,
        **payload,
    )
    logger.debug(convert_dict_to_pretty_string(d))
    # The value Python was not found for field folder on project PROJ12
    return d


def get_test_run_results(test_run_key: str) -> dict:
    """
    @param test_run_key: Тестовый прогон, может включать данные из разных тест-кейсов - Test Player
    @return: dict, e.g.:
    [
        {
            "executedBy": "JIRAUSER123456",
            "actualEndDate": "2020-01-11T11:11:11.111Z",
            "executionDate": "2020-01-11T11:11:11.111Z",
            "scriptResults": [
                {
                    "index": 0,
                    "status": "Not Executed"
                }
            ],
            "userKey": "JIRAUSER111",
            "assignedTo": "JIRAUSER111",
            "executionTime": 0,
            "testCaseKey": "PROJ123-T123",
            "automated": false,
            "actualStartDate": "2020-01-11T11:11:11.111Z",
            "id": 261545,
            "projectId": 12345,
            "key": "PROJ123-E1234",
            "status": "Pass"
        }
    ]
            },
            {
                "executedBy": null,
                "actualEndDate": "2020-11-11T11:11:21.111Z",
                "testCaseKey": "PROJ12-T123",
                "automated": true,
                "executionDate": "2020-11-11T11:11:21.111Z",
                "actualStartDate": "2020-11-11T11:11:21.111Z",
                "scriptResults": [
                    {
                        "index": 0,
                        "status": "Not Executed"
                    }
                ],
                "id": 123456,
                "projectId": 12345,
                "key": "PROJ12-E123456",
                "status": "Not Executed"
            }
        ]
    """
    return get_zephyr_client().api.test_runs.get_test_run_results(test_run_key=test_run_key)


def create_test_result(
    test_run_key: str,
    test_case_key: str,
    payload: dict = None,
) -> dict:
    """
    @param test_run_key: Тестовый прогон, может включать данные из разных тест-кейсов - Test Player key
    @param test_case_key: Тест-кейс, может включать данные из разных прогонов - Test case key
    @param payload: dict
    @return: dict w/ test ID, e.g.:
    {
        "id": 123456
    }
    """
    if payload is None:
        payload = dict()
    logger.debug(f"create_test_result test_run_key={test_run_key} test_case_key={test_case_key} "
                 f"payload={convert_dict_to_pretty_string(payload)}")
    return get_zephyr_client().api.test_runs.create_test_result(
        test_run_key=test_run_key,
        test_case_key=test_case_key,
        **payload,
    )


def update_latest_test_result(
    test_run_key: str,
    test_case_key: str,
    payload: dict = None,
) -> dict:
    """
    @param test_run_key: Тестовый прогон, может включать данные из разных тест-кейсов - Test Player key
    @param test_case_key: Тест-кейс, может включать данные из разных прогонов - Test case key
    @param payload: dict
    @return: dict w/ test ID, e.g.:
    {
        "id": 123456
    }
    """
    if payload is None:
        payload = dict()
    logger.debug(f"update_latest_test_result test_run_key={test_run_key} test_case_key={test_case_key} "
                 f"payload={convert_dict_to_pretty_string(payload)}")
    return get_zephyr_client().api.test_runs.update_test_result(
        test_run_key=test_run_key,
        test_case_key=test_case_key,
        **payload,
    )


def get_test_key_by_id(
    test_run_key: str,
    test_id: int,
):
    """
    @param test_run_key: Test run, may include data from various test cases - Test Player key,
    e.g.: PROJ12-C28
    @param test_id: Test ID, e.g.: 123456
    @return: Test Run Key, e.g.: PROJ12-E123456
    """
    test_run_results: dict = get_test_run_results(test_run_key)
    for test_run_result in test_run_results:
        if isinstance(test_run_result, dict):
            test_run_result_id = test_run_result.get("id")
            if not is_empty(test_run_result_id) and test_run_result_id == test_id:
                return test_run_result.get("key")


def get_test_result_creation_payload(
    status: Optional[str] = None,
    comment: Optional[str] = None,
    utc_start_datetime: Optional[datetime] = None,
    environment: Optional[str] = None,
    assigned_to: Optional[str] = None,
    executed_by: Optional[str] = None,
) -> dict:
    logger.debug(f"status={status} comment={comment} utc_start_datetime={utc_start_datetime} "
                 f"environment={environment} assigned_to={assigned_to} executed_by={executed_by}")
    current_jira_user_key = get_current_jira_user_key()
    if is_empty(assigned_to):
        assigned_to = current_jira_user_key
    if is_empty(executed_by):
        executed_by = current_jira_user_key
    raw_payload: Dict[str, Any] = dict(
        status=status,
        comment=comment,
        environment=environment,
        assignedTo=assigned_to,
        executedBy=executed_by,
    )
    if utc_start_datetime is not None:
        start_time_string = datetime.strftime(utc_start_datetime, TIME_Z_KEBAB_CASE_TEMPLATE)
        utc_end_datetime = get_present_utc_time()
        end_time_string = datetime.strftime(utc_end_datetime, TIME_Z_KEBAB_CASE_TEMPLATE)
        duration_seconds = get_duration_seconds(utc_start_datetime, utc_end=utc_end_datetime)
        duration = duration_seconds * (10 ** 3)
        raw_payload.update(dict(
            actualStartDate=start_time_string,
            actualEndDate=end_time_string,
            executionTime=duration,
        ))
    filtered_payload = {k: v for k, v in raw_payload.items() if not is_empty(v)}
    return filtered_payload


def create_attachment(
    test_result_id: int,
    file_path: str,
) -> dict:
    """
    @param test_result_id: int, e.g. 123456
    @param file_path: str
    @return: dict, e.g.:
    {
        "id": 123456
    }
    """
    logger.debug(f"create_attachment test_result_id={test_result_id} file_path={file_path}")
    d: dict = get_zephyr_client().api.test_results.create_attachment(
        test_result_id=test_result_id,
        file_path=file_path,
    )
    return d


def upload_new_test_result_to_zephyr(
    is_test_passed: bool = True,
    comment_html: str = None,
    utc_start_datetime: datetime = None,
    test_run_key: str = ZEPHYR_TEST_RUN_KEY,
    test_case_key: str = None,
    attachment_files: List[str] = None,
    assigned_to: str = None,
    executed_by: str = None,
):
    if not ZEPHYR_SYNC:
        logger.info("Skip upload_new_test_result_to_zephyr")
        return
    if is_empty(test_case_key):
        logger.info("Empty test_case_key")
        return
    msg = f"is_test_passed={is_test_passed} comment={comment_html} " \
          f"utc_start_datetime={utc_start_datetime} test_run_key={test_run_key} test_case_key={test_case_key} " \
          f"attachment_files={attachment_files}"
    logger.debug(
        f"upload_new_test_result_to_zephyr {msg}"
    )
    status = get_test_status(is_test_passed)
    if comment_html is None:
        comment_html = f"<br>{msg}"
    payload: dict = get_test_result_creation_payload(
        status=status,
        comment=comment_html,
        utc_start_datetime=utc_start_datetime,
        assigned_to=assigned_to,
        executed_by=executed_by,
    )
    create_test_result_response_dict: dict = create_test_result(
        test_run_key=test_run_key,
        test_case_key=test_case_key,
        payload=payload,
    )
    test_result_id: int = create_test_result_response_dict["id"]
    if not is_empty(attachment_files):
        for attachment_file in attachment_files:
            create_attachment(
                test_result_id=test_result_id,
                file_path=attachment_file,
            )

def sync_zephyr(
        test_case_id: str,
        is_call_report: bool,
        is_report_passed: bool,
        comment: str,
        node_id: str,
        report_text: str,
        elapsed_seconds: int,
        captured_log: Optional[AnyStr] = None,
):
    # Sync test output w/ Zephyr
    logger.debug(f"sync_zephyr test_case_id={test_case_id} is_call_report={is_call_report} "
                 f"is_report_passed={is_report_passed} comment={comment} node_id={node_id} "
                 f"report_text={report_text} elapsed_seconds={elapsed_seconds} captured_log={captured_log}")
    if not is_empty(test_case_id) and is_call_report:
        comment_html = ""
        if is_report_passed:
            status = ZephyrTestStatus.ZEPHYR_TEST_PASSED
        else:
            status = ZephyrTestStatus.ZEPHYR_TEST_FAILED
        if not is_empty(comment):
            comment_html = f"{comment}<br>{node_id}"
        if not is_report_passed:
            newline = '\n'
            comment_html = f"{node_id}<br><strong>ERROR:</strong><br>{report_text.replace(newline, '<br>')}"
        log_file = os.path.join("/tmp", f"{get_timestamp()}.log")
        dump_string(captured_log, log_file)
        upload_new_test_result_to_zephyr(
            is_test_passed=is_report_passed,
            comment_html=comment_html,
            utc_start_datetime=datetime.utcnow() - timedelta(seconds=elapsed_seconds),
            test_run_key=ZEPHYR_TEST_RUN_KEY,
            test_case_key=test_case_id,
            attachment_files=[log_file, ],
        )
        shutdown_atlassian_client()
