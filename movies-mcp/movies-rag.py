#!/usr/bin/env python3
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx

server = Server(name="movies-rag")


# -------------------------------------------------------------------
# Lista de ferramentas disponíveis
# -------------------------------------------------------------------
@server.list_tools()
async def list_tools():
    """Lista as ferramentas disponíveis."""
    return [
        Tool(
            name="searchMovies",
            description="Busca informações sobre filmes usando RAG",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Pergunta ou busca sobre filmes"
                    }
                },
                "required": ["prompt"]
            }
        )
    ]


# -------------------------------------------------------------------
# Execução de ferramentas
# -------------------------------------------------------------------
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Executa a ferramenta solicitada."""

    if name == "searchMovies":
        prompt = arguments.get("prompt", "")

        url = "http://localhost:8000/query"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"prompt": prompt})

            if response.status_code != 200:
                error_msg = f"Erro HTTP {response.status_code}: {response.text}"
                return [TextContent(type="text", text=error_msg)]

            data = response.json()
            result = json.dumps(data, indent=2, ensure_ascii=False)

            return [TextContent(type="text", text=result)]

        except Exception as e:
            error_msg = f"Erro ao chamar API: {str(e)}"
            return [TextContent(type="text", text=error_msg)]

    else:
        raise ValueError(f"Ferramenta desconhecida: {name}")


# -------------------------------------------------------------------
# Iniciar servidor MCP
# -------------------------------------------------------------------
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())