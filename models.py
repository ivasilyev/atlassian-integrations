from typing import Optional, List

from pydantic import BaseModel


class ZephyrTestStatus:
    ZEPHYR_TEST_PASSED: str = "Pass"
    ZEPHYR_TEST_FAILED: str = "Fail"


class ZephyrTestCaseStepDto(BaseModel):
    description: str
    expectedResult: str
    testData: str


class ZephyrTestCaseDto(BaseModel):
    folder: str
    priority_name: str
    project_key: str
    status_name: str
    test_case_key: Optional[str] = None
    test_case_name: str
    test_case_objective: str
    test_case_steps: List[ZephyrTestCaseStepDto]
