# duckdb-mcp

A minimal [MCP](https://modelcontextprotocol.io/) server exposing DuckDB SQL tools to Claude Desktop, Cursor, and other MCP-compatible clients. Built on the official Python SDK (`mcp` 2.x, `MCPServer`).

## Install

```bash
git clone https://github.com/HielBDTMQ/duckdb-mcp && cd duckdb-mcp
uv sync
```

Optional: create a small sample database (`test.duckdb` with a `sales` table):

```bash
uv run python test_db.py
```

## Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add a `duckdb` entry under `mcpServers` (keep any other keys in the file):

```json
{
  "mcpServers": {
    "duckdb": {
      "command": "/absolute/path/to/uv",
      "args": ["--directory", "/absolute/path/to/duckdb-mcp", "run", "duckdb-mcp"]
    }
  }
}
```

Use absolute paths: Claude Desktop does not use your shell `PATH`. Find uv with `which uv`.

Fully quit (Cmd-Q) and restart Claude Desktop. The server shows as "running" under Settings → Developer.

## Tools

- `query(sql, db_path)` — run SQL, return markdown table (capped at 500 rows)
- `list_tables(db_path)` — list all tables in a .duckdb file (read-only)
- `describe(table, db_path)` — show column names, types and nullability (read-only)

Pass absolute paths for `db_path`. `list_tables` and `describe` fail if the file does not exist instead of creating an empty database.

## Example prompt

> "I have a DuckDB file at /path/to/sales.duckdb. What's the top region by revenue in Q3?"

## Security note

`query` runs arbitrary SQL with your user's permissions. DuckDB can read any file you can (`read_csv`, `glob`, ...) and can write to `db_path`. Use it on local data you trust; it is not meant to be exposed to untrusted clients.

Built by [DatomIQ](https://datomiq.nl).
