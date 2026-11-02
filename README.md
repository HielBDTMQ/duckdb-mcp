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
      "args": ["--directory", "/absolute/path/to/duckdb-mcp", "run", "duckdb-mcp"],
      "env": { "DUCKDB_MCP_ROOT": "/absolute/path/to/your/data" }
    }
  }
}
```

Use absolute paths: Claude Desktop does not use your shell `PATH`. Find uv with `which uv`.

Fully quit (Cmd-Q) and restart Claude Desktop. The server shows as "running" under Settings → Developer.

## Tools

- `query(sql, db_path)` — run SQL, return markdown table (capped at 500 rows); database files are read-only
- `list_tables(db_path)` — list all tables in a .duckdb file (read-only)
- `describe(table, db_path)` — show column names, types and nullability (read-only)

Pass absolute paths for `db_path`. `list_tables` and `describe` fail if the file does not exist instead of creating an empty database.

## Sandbox

The model only gets access to one folder: `DUCKDB_MCP_ROOT`. It defaults to the working directory, which is the repo itself when started with `uv --directory`.

- `db_path` must be inside that folder (`..` and symlinks are resolved first).
- DuckDB runs with `enable_external_access = false` and `allowed_directories` set to that folder, so `read_csv`, `glob`, `read_text`, `ATTACH`, `COPY ... TO` and `INSTALL` cannot reach anything outside it. `lock_configuration = true` stops the model from turning this off with `SET`.
- Database files are opened read-only. Only `:memory:` accepts `CREATE` and `INSERT`.

## Example prompt

> "I have a DuckDB file at /path/to/sales.duckdb. What's the top region by revenue in Q3?"

Built by [DatomIQ](https://datomiq.nl).
