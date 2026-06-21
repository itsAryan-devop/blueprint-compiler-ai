"""Output layer 1 of 5: the database schema (tables, columns, relations).

Shaped so it can be turned directly into real SQLite ``CREATE TABLE`` statements
in the runtime phase, and so each column can be checked against the API fields
that read and write it.
"""

from pydantic import Field

from contracts.common import FieldType, StrictModel


class Column(StrictModel):
    name: str = Field(..., description="Column name in snake_case.")
    type: FieldType = Field(..., description="Column data type.")
    primary_key: bool = Field(default=False, description="True if this column is the table's primary key.")
    required: bool = Field(default=True, description="True if the column is NOT NULL.")
    unique: bool = Field(default=False, description="True if values must be unique.")
    foreign_key: str | None = Field(
        default=None,
        description="If this column references another table, the target as 'table.column' (e.g. 'users.id'); otherwise null.",
    )
    description: str = Field(default="", description="What the column stores.")


class Table(StrictModel):
    name: str = Field(..., description="Table name in snake_case plural, e.g. 'contacts', 'users'.")
    description: str = Field(default="", description="What the table stores.")
    columns: list[Column] = Field(..., min_length=1, description="The table's columns.")


class DatabaseSchema(StrictModel):
    tables: list[Table] = Field(..., min_length=1, description="All database tables.")
