#!/usr/bin/env python3
import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import httpx

server = Server(name="movies-rag")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="searchMovies",
            description="Busca filmes no banco de dados. Retorna resenhas completas baseadas no tema.",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Tema, gênero ou descrição do filme"
                    }
                },
                "required": ["prompt"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "searchMovies":
        prompt = arguments.get("prompt", "")
        # URL da API FastAPI
        url = "http://localhost:8000/query"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json={"prompt": prompt}, timeout=30.0)

            if response.status_code != 200:
                return [TextContent(type="text", text=f"Erro na API: {response.text}")]

            data = response.json()

            # Formata o JSON para o LLM ler claramente
            result_text = json.dumps(data, indent=2, ensure_ascii=False)
            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(type="text", text=f"Erro de conexão: {str(e)}")]
    else:
        raise ValueError(f"Ferramenta desconhecida: {name}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())