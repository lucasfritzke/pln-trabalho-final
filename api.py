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

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
SIMILARITY_THRESHOLD = 0.50
TOP_K = 3

app = FastAPI(title="Movie RAG API")

try:
    # Ajuste device conforme hardware ('cuda' ou 'cpu')
    model = SentenceTransformer(MODEL_NAME, device='cpu')
except Exception as e:
    model = None

db_pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=DB_URL)

def get_db_conn():
    conn = db_pool.getconn()
    try:
        register_vector(conn)
        yield conn
    finally:
        db_pool.putconn(conn)

class QueryRequest(BaseModel):
    prompt: str
    top_k: Optional[int] = TOP_K

class QueryResponse(BaseModel):
    titulo: str
    conteudo_completo: str # Mudado de chunk_texto para conteudo_completo
    similaridade: float

@app.post("/query", response_model=List[QueryResponse])
def query_movies(request: QueryRequest, conn: psycopg2.extensions.connection = Depends(get_db_conn)):
    if not model:
        raise HTTPException(status_code=500, detail="Modelo não carregado.")

    try:
        query_embedding = model.encode(request.prompt)

        # LÓGICA ATUALIZADA:
        # 1. Encontra os melhores chunks
        # 2. Faz JOIN com a tabela movies para pegar a resenha_completa
        # 3. Usa DISTINCT ON para retornar apenas um resultado por filme (o de maior similaridade)
        search_query = """
            SELECT DISTINCT ON (m.movie_id)
                m.titulo,
                m.resenha_completa,
                1 - (c.vetor_embedding <=> %s) AS similaridade
            FROM
                chunks c
            JOIN
                movies m ON c.movie_id = m.movie_id
            WHERE
                1 - (c.vetor_embedding <=> %s) > %s
            ORDER BY
                m.movie_id, similaridade DESC
            LIMIT %s;
        """

        with conn.cursor() as cursor:
            cursor.execute(
                search_query,
                (query_embedding, query_embedding, SIMILARITY_THRESHOLD, request.top_k)
            )
            results = cursor.fetchall()

        # Reordenar por similaridade final (já que o DISTINCT ON bagunça a ordem global)
        results.sort(key=lambda x: x[2], reverse=True)

        response = [
            QueryResponse(
                titulo=row[0],
                conteudo_completo=row[1], # resenha inteira
                similaridade=row[2]
            )
            for row in results
        ]

        return response

    except Exception as e:
        print(f"Erro: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)