from dataclasses import dataclass
from typing import List, Optional, Set
import re

from sqlglot import exp, parse
from sqlglot.errors import ParseError


DANGEROUS_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "COPY",
    "INSTALL",
    "LOAD",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "TRUNCATE",
    "MERGE",
    "REPLACE",
}

UNSAFE_FILE_FUNCTIONS = {
    "READ_CSV",
    "READ_CSV_AUTO",
    "READ_JSON",
    "READ_JSON_AUTO",
    "READ_NDJSON",
    "READ_PARQUET",
    "READ_TEXT",
    "GLOB",
}

CLASS_TO_OPERATION = {
    "Insert": "INSERT",
    "Update": "UPDATE",
    "Delete": "DELETE",
    "Drop": "DROP",
    "Alter": "ALTER",
    "Create": "CREATE",
    "Copy": "COPY",
    "Pragma": "PRAGMA",
    "TruncateTable": "TRUNCATE",
    "Merge": "MERGE",
    "Replace": "REPLACE",
}


@dataclass(frozen=True)
class SqlGuardResult:
    status: str
    is_read_only: bool
    estimated_safe: bool
    blocked_operations: List[str]
    normalized_sql: Optional[str]


def guard_sql(sql: str) -> SqlGuardResult:
    blocked: Set[str] = set(_keyword_scan(sql))

    try:
        statements = [statement for statement in parse(sql, read="duckdb") if statement is not None]
    except ParseError:
        if not blocked:
            blocked.add("PARSE_ERROR")
        return _blocked(blocked)

    if len(statements) != 1:
        blocked.add("MULTIPLE_STATEMENTS")
        for statement in statements:
            blocked.update(_collect_blocked_operations(statement))
        return _blocked(blocked)

    statement = statements[0]
    blocked.update(_collect_blocked_operations(statement))

    if not isinstance(statement, exp.Select):
        blocked.add(_root_operation(statement))

    if blocked:
        return _blocked(blocked)

    return SqlGuardResult(
        status="ok",
        is_read_only=True,
        estimated_safe=True,
        blocked_operations=[],
        normalized_sql=statement.sql(dialect="duckdb"),
    )


def _blocked(blocked: Set[str]) -> SqlGuardResult:
    return SqlGuardResult(
        status="blocked",
        is_read_only=False,
        estimated_safe=False,
        blocked_operations=sorted(blocked),
        normalized_sql=None,
    )


def _collect_blocked_operations(statement: exp.Expression) -> Set[str]:
    blocked: Set[str] = set()
    class_map = {
        getattr(exp, class_name): operation
        for class_name, operation in CLASS_TO_OPERATION.items()
        if hasattr(exp, class_name)
    }
    command_cls = getattr(exp, "Command", None)
    anonymous_cls = getattr(exp, "Anonymous", None)
    for node in statement.walk():
        for cls, operation in class_map.items():
            if isinstance(node, cls):
                blocked.add(operation)
        if command_cls is not None and isinstance(node, command_cls):
            command_name = str(node.this).upper()
            if command_name in DANGEROUS_KEYWORDS:
                blocked.add(command_name)
        if anonymous_cls is not None and isinstance(node, anonymous_cls):
            function_name = str(node.this).upper()
            if function_name in UNSAFE_FILE_FUNCTIONS:
                blocked.add(function_name)
    return blocked


def _root_operation(statement: exp.Expression) -> str:
    for class_name, operation in CLASS_TO_OPERATION.items():
        cls = getattr(exp, class_name, None)
        if cls is not None and isinstance(statement, cls):
            return operation
    command_cls = getattr(exp, "Command", None)
    if command_cls is not None and isinstance(statement, command_cls):
        command_name = str(statement.this).upper()
        if command_name:
            return command_name
    return "NON_SELECT"


def _keyword_scan(sql: str) -> Set[str]:
    cleaned = _strip_comments_and_strings(sql)
    return {
        keyword
        for keyword in DANGEROUS_KEYWORDS
        if re.search(rf"\b{re.escape(keyword)}\b", cleaned, flags=re.IGNORECASE)
    }


def _strip_comments_and_strings(sql: str) -> str:
    without_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line_comments = re.sub(r"--.*?$", " ", without_block_comments, flags=re.MULTILINE)
    without_strings = re.sub(r"'(?:''|[^'])*'", " ", without_line_comments)
    return re.sub(r'"(?:""|[^"])*"', " ", without_strings)
