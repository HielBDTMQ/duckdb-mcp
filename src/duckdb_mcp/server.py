"""DuckDB MCP server — expose SQL tools to MCP clients.

Design:
- Each tool opens its own DuckDB connection (stateless).
- Query results are truncated to 500 rows to keep context manageable.
- No auth, no state — this is a local-only, single-user tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("duckdb")


MAX_ROWS = 500


def _escape_cell(value: Any) -> Any:
    # Pipes and newlines would split or break rows in the markdown table.
    if isinstance(value, str):
        return value.replace("|", r"\|").replace("\n", " ")
    return value


def _to_markdown(df: pd.DataFrame) -> str:
    df = df.map(_escape_cell)
    df.columns = [_escape_cell(str(c)) for c in df.columns]
    return df.to_markdown(index=False)


def _connect_existing(db_path: str) -> duckdb.DuckDBPyConnection:
    # duckdb.connect silently creates missing files; for read-only tools a
    # typo in the path should fail instead of reporting an empty database.
    if not Path(db_path).is_file():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    return duckdb.connect(db_path, read_only=True)


@mcp.tool()
def query(sql: str, db_path: str = ":memory:") -> str:
    """Run a SQL query against DuckDB and return results as a markdown table.

    Args:
        sql: The SQL query to execute. SELECT, WITH, SHOW etc are safe.
             DDL (CREATE/DROP) and DML (INSERT/UPDATE) also work but mutate db_path.
        db_path: Path to a .duckdb file, or ":memory:" (default) for an ephemeral DB.
                 ":memory:" starts empty and is discarded after each call, so tables
                 created there do not survive to the next call. Use it for one-shot
                 queries, e.g. reading CSV/Parquet files directly. Use a file path
                 when data must be kept across calls.
    """
    with duckdb.connect(db_path) as con:
        # Limit inside DuckDB so huge results never reach pandas; the extra row
        # tells us whether truncation happened.
        df = con.sql(sql).limit(MAX_ROWS + 1).df()
    truncated = len(df) > MAX_ROWS
    if truncated:
        df = df.head(MAX_ROWS)
    md = _to_markdown(df)
    if truncated:
        md += f"\n\n_(truncated to first {MAX_ROWS} rows)_"
    return md


@mcp.tool()
def list_tables(db_path: str) -> list[str]:
    """List all tables in a DuckDB file.

    Args:
        db_path: Path to a .duckdb file. Must exist.
    """
    with _connect_existing(db_path) as con:
        return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


@mcp.tool()
def describe(table: str, db_path: str) -> str:
    """Show the schema of a table (column names + types) as markdown.

    Args:
        table: Table name to describe.
        db_path: Path to the .duckdb file containing the table. Must exist.
    """
    with _connect_existing(db_path) as con:
        # Bound parameter, not string formatting: the table name is never parsed as SQL.
        df = con.execute(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = ? ORDER BY ordinal_position",
            [table],
        ).df()
    if df.empty:
        raise ValueError(f"Table not found: {table}")
    return _to_markdown(df)


def main() -> None:
    """Entry point for the console script."""
    mcp.run()


if __name__ == "__main__":
    main()
