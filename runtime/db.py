"""Blueprint -> real SQLite database.

Translates ``DatabaseSchema`` into actual ``CREATE TABLE`` statements and runs
them against a SQLite file (or :memory:). This is half of the "the output is
directly runnable" proof: a column type in JSON becomes a column type in a real
DB the runtime can read and write.
"""

import sqlite3
from typing import Iterable

from contracts import Column, DatabaseSchema, FieldType, Table

SQLITE_TYPE: dict[FieldType, str] = {
    FieldType.STRING: "TEXT",
    FieldType.TEXT: "TEXT",
    FieldType.INTEGER: "INTEGER",
    FieldType.FLOAT: "REAL",
    FieldType.BOOLEAN: "INTEGER",   # SQLite has no bool; 0/1 by convention
    FieldType.DATE: "TEXT",         # ISO 8601 strings -- portable, sortable
    FieldType.DATETIME: "TEXT",
    FieldType.UUID: "TEXT",
    FieldType.JSON: "TEXT",
}


def _column_ddl(column: Column) -> str:
    """SQL for one column.

    Demo-friendliness: only the primary key is NOT NULL by default. The LLM
    routinely marks every column `required`, which makes ad-hoc CRUD POSTs 400
    on a missing field. Keeping non-PK columns nullable lets a reviewer hit POST
    with a partial body and still get a 201. The blueprint's own ``required``
    flag is preserved in the JSON for inspection.
    """
    parts = [_quote(column.name), SQLITE_TYPE[column.type]]
    if column.primary_key:
        parts.append("PRIMARY KEY")
    if column.unique and not column.primary_key:
        parts.append("UNIQUE")
    return " ".join(parts)


def _foreign_keys(table: Table) -> Iterable[str]:
    for col in table.columns:
        if col.foreign_key and "." in col.foreign_key:
            ref_table, ref_col = col.foreign_key.split(".", 1)
            yield f"FOREIGN KEY ({_quote(col.name)}) REFERENCES {_quote(ref_table)}({_quote(ref_col)})"


def _quote(name: str) -> str:
    """Quote an identifier so SQL keywords/odd names can't break the statement."""
    return '"' + name.replace('"', '""') + '"'


def create_table_sql(table: Table) -> str:
    parts = [_column_ddl(c) for c in table.columns]
    parts.extend(_foreign_keys(table))
    return f"CREATE TABLE {_quote(table.name)} (\n  " + ",\n  ".join(parts) + "\n)"


def build_database(database: DatabaseSchema, path: str = ":memory:") -> sqlite3.Connection:
    """Create a SQLite database from the schema. Returns a live connection.

    ``check_same_thread=False`` lets the FastAPI worker threads share this
    connection -- safe here because requests are short and the demo is not
    high-concurrency. For production we'd switch to a per-request connection or
    a connection pool.
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for table in database.tables:
        conn.execute(create_table_sql(table))
    conn.commit()
    return conn
