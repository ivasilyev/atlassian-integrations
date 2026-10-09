import difflib
import json
import os
import pprint
import random
import re
import warnings
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from logging import getLogger
from typing import List, Iterable, Dict, Any, Union
from typing import Optional
from typing import Type

from jsonpath_ng import parse, DatumInContext
from pydantic import BaseModel, ConfigDict, RootModel
from pydantic.dataclasses import dataclass
from urllib3.exceptions import InsecureRequestWarning

from constants import ENCODING_UTF8

DATE_POINT_CASE_TEMPLATE = "%d.%m.%Y"
DATE_KEBAB_CASE_TEMPLATE = "%Y-%m-%d"
DATE_CONCATENATED_TEMPLATE = "%Y%m%d"
TIME_KEBAB_CASE_TEMPLATE = "%Y-%m-%d %H:%M:%S"
TIME_KAFKA_TEMPLATE = "%d.%m.%Y, %H:%M:%S"
# UTC-only time template
TIME_Z_KEBAB_CASE_TEMPLATE = "%Y-%m-%dT%H:%M:%S.%fZ"


logger = getLogger(__name__)


def load_string(file, encoding: str = ENCODING_UTF8) -> str:
    logger.debug(f"Load file: '{file}'")
    with open(file, mode="r", encoding=encoding) as f:
        s = f.read()
        f.close()
    return s


def dump_string(s: str, file: str, encoding: str = ENCODING_UTF8):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, mode="w", encoding=encoding) as f:
        f.write(s)
        f.close()
    logger.debug(f"Saved '{file}'")

def get_json_content_type_header() -> dict:
    return {"Content-Type": "application/json"}


def filter_https_warnings():
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def is_empty(x):
    null_check = x is None
    zero_length_check = hasattr(x, "__len__") and len(x) == 0
    return null_check or zero_length_check


def randomize_amount():
    return random.randint(1, 100)


def randomize_digital_sequence(length: int):
    return "".join([str(random.randint(0, 9)) for _ in range(length)])


def remove_empty_values(x: Iterable[Any]):
    """
    A basic recursive method for nested structure sanitization
    """
    if isinstance(x, dict):
        d = dict()
        for key, value in x.items():
            sanitized_value = remove_empty_values(value)
            if not is_empty(sanitized_value):
                d[key] = sanitized_value
        return d
    if isinstance(x, list):
        queue = deque()
        for value in x:
            sanitized_value = remove_empty_values(value)
            if not is_empty(sanitized_value):
                queue.append(sanitized_value)
        return list(queue)
    if is_empty(x):
        return None
    return x


def find_intersections(x1: list, x2: list) -> list:
    return [i for i in x1 if i in x2]


def find_missing_items(x1: list, x2: list) -> list:
    """
    abcde
    |||
    cdefgh -> abfgh
    """
    left = [i for i in x1 if i not in x2]
    right = [i for i in x2 if i not in x1]
    return left + right


def coalesce(value, default):
    if is_empty(value):
        return default
    return value


def coalesce_integer(value: Optional[int], default: int) -> int:
    if is_empty(value) or int(value) == 0:
        return default
    return value


def set_attributes(obj: Any, attributes: Dict[Any, Any]):
    for attribute_key, attribute_value in attributes.items():
        if attribute_value is not None:
            setattr(obj, attribute_key, attribute_value)



def get_json_path_matches_from_dict(d: dict, json_path: str) -> List[DatumInContext]:
    json_path_expression = parse(json_path)
    matches: List[DatumInContext] = list(json_path_expression.find(d))
    return matches


def get_json_path_value_from_dict(d: dict, json_path: str) -> Any:
    # More convenient for use cases w/ depth = 1
    matches: List[DatumInContext] = get_json_path_matches_from_dict(d, json_path)
    if len(matches) > 0:
        return matches[0].value


def check_dict_by_json_path(d: dict, json_path: str) -> bool:
    if d is not None and len(d.keys()) > 0:
        matches: List[DatumInContext] = get_json_path_matches_from_dict(d, json_path)
        if not is_empty(matches):
            return True
    return False


def prettify_plain_dicts_as_table(rows: List[Dict[str, Any]]) -> str:
    """
    Renders TSV table
    """
    if is_empty(rows):
        return ""
    queue = deque()
    for row_dict in rows:
        if len(row_dict.keys()) == 0:
            continue
        if len(queue) == 0:
            header = "\t".join([str(i) for i in row_dict.keys()])
            queue.append(header)
        row = "\t".join([str(i) for i in row_dict.values()])
        queue.append(row)
    table = join_lines(queue)
    return table


def convert_dict_to_pretty_string(d: Union[Dict[Any, Any], List[Dict[Any, Any]]]) -> str:
    try:
        return json.dumps(d, sort_keys=True, ensure_ascii=False, indent=2)
    except:
        try:
            return pprint.pformat(d)
        except:
            return str(d)


def update_dict(d: dict, updater: dict):
    for k, v in updater.items():
        if not is_empty(v):
            d.update({k: v})


def replace_value_if_key_exists(d: dict, k, v) -> None:
    if k in d.keys():
        d[k] = v


def replace_value_if_jsonpath_exists(
    d: dict,
    json_path: str,
    value: str = "***",
) -> dict:
    _d = deepcopy(d)
    matches: List[DatumInContext] = get_json_path_matches_from_dict(d=_d, json_path=json_path)
    if len(matches) > 0:
        matches[0].full_path.update(_d, value)
    return _d


def convert_dict_to_web_payload(d: dict) -> str:
    _d: dict = replace_value_if_jsonpath_exists(d, "password")
    logger.debug(f"Send web data:\n\t{convert_dict_to_pretty_string(_d)}")
    payload = json.dumps(d, separators=(',', ':'))
    return payload


def get_first_dict_key(d: dict):
    return list(d.keys())[0]


def assert_dicts_equality(expected: dict, actual: dict):
    logger.debug("assert_dicts_equality")
    _expected = remove_empty_values(expected)
    _actual = remove_empty_values(actual)
    # No .equals() or .hashCode() fun here
    if _expected != _actual:
        _expected_string = convert_dict_to_pretty_string(_expected)
        _actual_string = convert_dict_to_pretty_string(_actual)
        logger.debug("Expected:\n\t" + _expected_string)
        logger.debug("Actual:\n\t" + _actual_string)
        diff = difflib.ndiff(
            split_lines(_expected_string),
            split_lines(_actual_string),
        )
        raw_lines = list(diff)
        lines = [i.strip("\n") for i in raw_lines]
        msg = "Found differences:\n\t" + join_lines(lines)
        logger.error(msg)
        raise AssertionError(msg)


def add_prefix(s: str, prefix: str) -> str:
    if s is not None:
        s = str(s)
        if not s.startswith(prefix):
            s = f"{prefix}{s}"
    return s


def split_values(s: str, sep: str = "\t"):
    values = [i.strip() for i in re.split(f"[{sep}]+", s)]
    return remove_empty_values(values)


def split_lines(s: str):
    return re.split("[\r\n]+", s)


def split_and_strip_lines(s: str):
    lines = split_lines(s)
    return "".join([i.strip() for i in lines])


def join_columns(x: List[Any], sep: str = "\t"):
    if is_empty(x):
        return ""
    return sep.join([str(i) for i in x])


def join_lines(x: Iterable[Any], eol: str = "\n"):
    if is_empty(x):
        return ""
    return eol.join([str(i) for i in x]) + eol


def get_default_base_model_config() -> dict:
    return ConfigDict(arbitrary_types_allowed=True)


def get_default_data_class_config() -> dict:
    return dict(config=get_default_base_model_config())


def is_object_model(x):
    return type(type(x)).__name__ in ["ModelMetaclass", "ModelMetaclass"]


def convert_model_to_dict(x: Union[BaseModel, dataclass]) -> dict:
    """
    Convert a Pydantic Model class instance into a dictionary recursively
    """
    try:
        return x.model_dump()
    except AttributeError:
        return RootModel(x).model_dump()


def convert_model_to_dict_bytes(x: Union[BaseModel, Dict[str, Any], List[Any]]) -> bytes:
    d: dict = convert_model_to_dict(x)
    b: bytes = convert_dict_to_bytes(d)
    return b


def convert_models_list_to_dicts_list(x: Iterable[BaseModel]) -> list:
    return [convert_model_to_dict(i) for i in x]


def dump_dtos_list(x: Iterable[BaseModel], file: str):
    export_list = convert_models_list_to_dicts_list(x)
    dump_dict(export_list, file)


def dfs_serialize(x):
    if isinstance(x, list):
        return [dfs_serialize(i) for i in x]
    if isinstance(x, dict):
        return {k: dfs_serialize(v) for k, v in x.items()}
    if issubclass(type(x), BaseModel):
        d = dict(x)
        return dfs_serialize(d)
    if not is_empty(x):
        return x


def convert_dict_to_model(d: dict, cls: Type[BaseModel]) -> BaseModel:
    try:
        model: BaseModel = cls(**d)
        return model
    except Exception as e:
        logger.warning(e)


def unmarshal_list_of_dicts(x: Iterable, cls: Type[BaseModel]) -> list:
    values = remove_empty_values(x)
    results = [convert_dict_to_model(i, cls) for i in values]
    return remove_empty_values(results)


def unmarshal_data_file(file: str, cls: Type[BaseModel]) -> list:
    d = load_dict(file)
    return unmarshal_list_of_dicts(d, cls)


def convert_bytes_to_dict(b: bytes) -> dict:
    s = b.decode(ENCODING_UTF8)
    d = json.loads(s)
    return d


def convert_dict_to_bytes(d: dict) -> bytes:
    s = json.dumps(d)
    b = s.encode(ENCODING_UTF8)
    return b


def end_with_slash(s: str):
    return s.strip("/") + "/"


def load_lines(file) -> List[str]:
    s = load_string(file)
    lines: List[str] = re.split("[\r\n]+", s)
    return lines


def dump_list(x: Iterable, file: str, eol: str = "\n"):
    s = eol.join([str(i) for i in x]) + eol
    dump_string(s, file)


def load_dict(file) -> dict:
    s = load_string(file)
    d = json.loads(s)
    return d


def dump_dict(d: Union[Dict[str, Any], List[Any]], file: str):
    s = convert_dict_to_pretty_string(d)
    dump_string(s, file)


def load_bytes(file) -> bytes:
    logger.debug(f"Load file: '{file}'")
    with open(file, mode="rb") as f:
        b = f.read()
        f.close()
    return b


def check_is_substring_in_file(substring: str, file: str) -> bool:
    s = load_string(file)
    return substring in s


def get_today_date_in_point_case():
    return datetime.strftime(datetime.now(), DATE_POINT_CASE_TEMPLATE)


def get_today_date_in_kebab_case():
    return datetime.strftime(datetime.now(), DATE_KEBAB_CASE_TEMPLATE)


def convert_date_from_point_case_to_kebab_case(s: str) -> str:
    dt: datetime = datetime.strptime(s, DATE_POINT_CASE_TEMPLATE)
    return dt.strftime(DATE_KEBAB_CASE_TEMPLATE)


def convert_date_from_kebab_case_to_point_case(s: str) -> str:
    dt: datetime = datetime.strptime(s, DATE_KEBAB_CASE_TEMPLATE)
    return dt.strftime(DATE_POINT_CASE_TEMPLATE)


def get_present_utc_time() -> datetime:
    return datetime.now(timezone.utc)


def convert_utc_time_to_local_time(utc_time: datetime) -> datetime:
    return utc_time.astimezone()


def get_timestamp_in_kebab_case_z():
    dt: datetime = get_present_utc_time()
    return datetime.strftime(dt, TIME_Z_KEBAB_CASE_TEMPLATE)


def convert_timedelta_to_seconds(t: timedelta) -> int:
    # ceiling workaround
    return t.seconds + 1


def get_duration_seconds(utc_start: datetime, utc_end: Optional[datetime] = None) -> int:
    try:
        td: timedelta = utc_end - utc_start
    # TypeError: can't subtract offset-naive and offset-aware datetimes
    except TypeError:
        td: timedelta = utc_end.replace(tzinfo=timezone.utc) - utc_start.replace(tzinfo=timezone.utc)
    duration_seconds = convert_timedelta_to_seconds(td)
    return duration_seconds


def get_elapsed_seconds(utc_datetime: datetime) -> int:
    elapsed_seconds = get_duration_seconds(utc_start=utc_datetime, utc_end=get_present_utc_time())
    return elapsed_seconds


def get_timestamp() -> str:
    s = datetime.now().isoformat()
    return re.sub(":", "-", s)


def get_next_day_utc_datetime() -> datetime:
    return get_present_utc_time() + timedelta(days=1)


def get_next_month_utc_datetime() -> datetime:
    return get_present_utc_time() + timedelta(days=32)
