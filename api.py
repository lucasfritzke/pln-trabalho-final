# api.py

import os
import uvicorn
import psycopg2
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv
from typing import List, Optional
from psycopg2.pool import SimpleConnectionPool

# --- Configuração Inicial ---
load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
SIMILARITY_THRESHOLD = 0.3  # Limite de 30%
TOP_K = 5  # Retornar os 5 chunks mais relevantes

# --- Carregar Modelo e App ---
app = FastAPI(title="Movie RAG API")

# Carregar o modelo em memória ao iniciar a API
try:
    model = SentenceTransformer(MODEL_NAME, device='cuda')
    print(f"Modelo de embedding '{MODEL_NAME}' carregado em CUDA.")
except Exception as e:
    print(f"Erro ao carregar modelo: {e}")
    model = None

# --- Conexão com DB (Pool) ---
db_pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=DB_URL)

def get_db_conn():
    """Obtém uma conexão do pool e registra o tipo vector."""
    conn = db_pool.getconn()
    try:
        register_vector(conn)
        yield conn
    finally:
        db_pool.putconn(conn)

# --- Modelos Pydantic (Entrada e Saída) ---
class QueryRequest(BaseModel):
    prompt: str
    top_k: Optional[int] = TOP_K

class QueryResponse(BaseModel):
    titulo: str
    chunk_texto: str
    similaridade: float

# --- Endpoints da API ---

@app.get("/")
def read_root():
    return {"status": "Movie RAG API está online."}


@app.post("/query", response_model=List[QueryResponse])
def query_movies(
    request: QueryRequest,
    conn: psycopg2.extensions.connection = Depends(get_db_conn)
):
    """
    Recebe um prompt, gera seu embedding e busca chunks relevantes no banco.
    """
    if not model:
        raise HTTPException(status_code=500, detail="Modelo de embedding não está carregado.")

    try:
        # 1. Gerar embedding para o prompt do usuário
        query_embedding = model.encode(request.prompt)

        # 2. Executar a busca no PGVector com JOIN
        search_query = """
            SELECT
                m.titulo,
                c.chunk_texto,
                1 - (c.vetor_embedding <=> %s) AS similaridade
            FROM
                chunks c
            JOIN
                movies m ON c.movie_id = m.movie_id
            WHERE
                1 - (c.vetor_embedding <=> %s) > %s
            ORDER BY
                similaridade DESC
            LIMIT %s;
        """

        with conn.cursor() as cursor:
            cursor.execute(
                search_query,
                (query_embedding, query_embedding, SIMILARITY_THRESHOLD, request.top_k)
            )
            results = cursor.fetchall()

        # 3. Formatar a resposta
        response = [
            QueryResponse(
                titulo=row[0],
                chunk_texto=row[1],
                similaridade=row[2]
            )
            for row in results
        ]

        return response

    except Exception as e:
        print(f"Erro durante a busca: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")

# --- Execução (para testes locais) ---
if __name__ == "__main__":
    print("Iniciando servidor Uvicorn em http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)