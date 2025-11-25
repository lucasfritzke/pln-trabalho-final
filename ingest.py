import os
import psycopg2
from psycopg2 import extras
import nltk
import re
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pgvector.psycopg2 import register_vector
from langchain_text_splitters import RecursiveCharacterTextSplitter
import argparse

# --- Configuração Inicial ---
load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:senha123@localhost:5432/filmes_rag")
REVIEWS_DIR = "sinopses"
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

# Baixar recursos do NLTK
nltk.download("punkt")
nltk.download("stopwords")

STOPWORDS_PT = set(nltk.corpus.stopwords.words('portuguese'))

print(f"Carregando modelo: {MODEL_NAME}...")
model = SentenceTransformer(MODEL_NAME, device='cpu')  # Use 'cuda' se tiver GPU
print("Modelo carregado.")


def preprocess_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = nltk.word_tokenize(text, language='portuguese')
    tokens = [word for word in tokens if word.isalnum() and word not in STOPWORDS_PT]
    return " ".join(tokens)


def get_db_connection():
    try:
        conn = psycopg2.connect(DB_URL)
        register_vector(conn)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco: {e}")
        return None


def process_and_ingest_movie(filepath: str, conn):
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            return

        # Linha 1 = Título, Resto = Resenha
        title = lines[0].strip()
        review_content = " ".join([line.strip() for line in lines[1:]])

        # Texto completo para salvar no banco (Título + Conteúdo) para contexto do LLM
        full_text_storage = f"{title}\n{review_content}"

        print(f"\nProcessando: {title}")

        with conn.cursor() as cursor:
            # 1. Inserir Filme com a RESENHA COMPLETA
            cursor.execute(
                """
                INSERT INTO movies (titulo, resenha_completa)
                VALUES (%s, %s) ON CONFLICT (titulo) 
                DO
                UPDATE SET resenha_completa = EXCLUDED.resenha_completa
                    RETURNING movie_id
                """,
                (title, full_text_storage)
            )

            result = cursor.fetchone()
            if not result:
                # Se caiu no conflict e não retornou (caso o DO UPDATE não retornasse), buscamos:
                cursor.execute("SELECT movie_id FROM movies WHERE titulo = %s", (title,))
                result = cursor.fetchone()

            movie_id = result[0]

            # 2. Limpar chunks antigos
            cursor.execute("DELETE FROM chunks WHERE movie_id = %s", (movie_id,))

            # 3. Chunking (NÃO CRIA MAIS O CHUNK 0 APENAS COM TÍTULO)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=128, chunk_overlap=50, length_function=len
            )

            # Chunkamos o conteúdo da resenha
            chunks = text_splitter.split_text(review_content)

            chunk_data_list = []
            for i, chunk in enumerate(chunks):
                # Pré-processa para o embedding (vetor), mas salva o texto original no chunk_texto
                preprocessed_chunk = preprocess_text(chunk)

                # Se o chunk for vazio após processamento, pula
                if not preprocessed_chunk.strip():
                    continue

                # Embeddings
                chunk_embedding = model.encode(preprocessed_chunk)
                chunk_index = i + 1

                chunk_data_list.append(
                    (movie_id, chunk, chunk_index, chunk_embedding)
                )

            if chunk_data_list:
                extras.execute_values(
                    cursor,
                    """
                    INSERT INTO chunks (movie_id, chunk_texto, chunk_index, vetor_embedding)
                    VALUES %s;
                    """,
                    chunk_data_list
                )
                print(f"  > Inseridos {len(chunk_data_list)} chunks.")

            conn.commit()

    except Exception as e:
        print(f"Erro ao processar {filename}: {e}")
        conn.rollback()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=str)
    parser.add_argument('--all', action='store_true')
    args = parser.parse_args()

    conn = get_db_connection()
    if not conn: return

    if args.file and os.path.exists(args.file):
        process_and_ingest_movie(args.file, conn)
    elif args.all and os.path.exists(REVIEWS_DIR):
        for fn in os.listdir(REVIEWS_DIR):
            if fn.endswith(".txt"):
                process_and_ingest_movie(os.path.join(REVIEWS_DIR, fn), conn)

    conn.close()


if __name__ == "__main__":
    main()