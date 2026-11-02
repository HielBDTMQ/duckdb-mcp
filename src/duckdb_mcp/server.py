"""DuckDB MCP server — expose SQL tools to MCP clients.

Design:
- Each tool opens its own DuckDB connection (stateless).
- Query results are truncated to 500 rows to keep context manageable.
- No auth, no state — this is a local-only, single-user tool.
- Sandboxed: database files and any file read from SQL must live under
  DUCKDB_MCP_ROOT, and database files are opened read-only.
"""

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("duckdb")


MAX_ROWS = 500

# The user picks this folder in the client config; the model never can. The
# default is the working directory, which is the repo under `uv --directory`.
DATA_ROOT = Path(os.environ.get("DUCKDB_MCP_ROOT", ".")).expanduser().resolve()


def _escape_cell(value: Any) -> Any:
    # Pipes and newlines would split or break rows in the markdown table.
    if isinstance(value, str):
        return value.replace("|", r"\|").replace("\n", " ")
    return value


def _to_markdown(df: pd.DataFrame) -> str:
    df = df.map(_escape_cell)
    df.columns = [_escape_cell(str(c)) for c in df.columns]
    return df.to_markdown(index=False)


def _check_path(db_path: str) -> str:
    if db_path == ":memory:":
        return db_path
    # resolve() follows ".." and symlinks, so "../secret.duckdb" cannot sneak out.
    resolved = Path(db_path).expanduser().resolve()
    if not resolved.is_relative_to(DATA_ROOT):
        raise PermissionError(f"db_path must be inside {DATA_ROOT}")
    return str(resolved)


def _sandbox(con: duckdb.DuckDBPyConnection) -> None:
    # Without this, SQL like read_csv('/anywhere') or glob('~/Downloads/*')
    # reaches every file the user can read. Order matters: allowed_directories
    # can only be set while external access is still on, and the lock stops
    # the model from undoing this with SET.
    con.execute("SET allowed_directories = ?", [[f"{DATA_ROOT}/"]])
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")


def _connect(db_path: str, must_exist: bool = False) -> duckdb.DuckDBPyConnection:
    db_path = _check_path(db_path)
    # duckdb.connect silently creates missing files; for read-only tools a
    # typo in the path should fail instead of reporting an empty database.
    if must_exist and not Path(db_path).is_file():
        raise FileNotFoundError(f"Database file not found: {db_path}")
    con = duckdb.connect(db_path, read_only=db_path != ":memory:")
    _sandbox(con)
    return con


@mcp.tool()
def query(sql: str, db_path: str = ":memory:") -> str:
    """Run a SQL query against DuckDB and return results as a markdown table.

    Args:
        sql: The SQL query to execute. Database files are opened read-only, so
             only ":memory:" accepts CREATE/INSERT. read_csv, read_parquet etc.
             only work on files inside the server's data folder.
        db_path: Path to a .duckdb file inside the server's data folder, or
                 ":memory:" (default) for an ephemeral DB.
                 ":memory:" starts empty and is discarded after each call, so tables
                 created there do not survive to the next call. Use it for one-shot
                 queries, e.g. reading CSV/Parquet files directly.
    """
    with _connect(db_path) as con:
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
        db_path: Path to a .duckdb file inside the server's data folder. Must exist.
    """
    with _connect(db_path, must_exist=True) as con:
        return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


@mcp.tool()
def describe(table: str, db_path: str) -> str:
    """Show the schema of a table (column names + types) as markdown.

    Args:
        table: Table name to describe.
        db_path: Path to a .duckdb file inside the server's data folder. Must exist.
    """
    with _connect(db_path, must_exist=True) as con:
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
