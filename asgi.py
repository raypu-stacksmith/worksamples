import os
from app import mcp

os.environ["MCP_TRANSPORT"] = "http"
app = mcp.http_app()
