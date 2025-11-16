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

# Carregue as variáveis de ambiente
DB_URL = "postgresql://postgres:senha123@localhost:5432/filmes_rag"
REVIEWS_DIR = "resenhas"
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

# Baixar recursos do NLTK (apenas na primeira vez)
nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("stopwords")

STOPWORDS_PT = set(nltk.corpus.stopwords.words('portuguese'))

# Carregar modelo de embedding, forçando o uso de CUDA
print(f"Carregando modelo de embedding: {MODEL_NAME} (usando CUDA)...")
model = SentenceTransformer(MODEL_NAME, device='cuda')
print("Modelo carregado com sucesso.")


# --- Funções Auxiliares ---

def preprocess_text(text: str) -> str:
    """Limpa e pré-processa o texto para embedding."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    tokens = nltk.word_tokenize(text, language='portuguese')
    tokens = [word for word in tokens if word.isalnum() and word not in STOPWORDS_PT]
    return " ".join(tokens)


def get_db_connection():
    """Estabelece conexão com o banco de dados e registra o tipo vector."""
    try:
        conn = psycopg2.connect(DB_URL)
        register_vector(conn)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None


def process_and_ingest_movie(filepath: str, conn):
    """Processa um único arquivo e insere nas tabelas normalizadas."""
    filename = os.path.basename(filepath)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            print(f"Arquivo {filename} está vazio. Pulando.")
            return

        # Assumindo formato: Linha 1 = Título, Linha 2+ = Resenha
        title = lines[0].strip()
        review_content = " ".join([line.strip() for line in lines[1:]])

        print(f"\nProcessando filme: {title}")

        with conn.cursor() as cursor:

            # --- Etapa 1: Inserir/Obter o Filme ---
            cursor.execute(
                "INSERT INTO movies (titulo) VALUES (%s) ON CONFLICT (titulo) DO NOTHING",
                (title,)
            )
            cursor.execute("SELECT movie_id FROM movies WHERE titulo = %s", (title,))
            result = cursor.fetchone()
            if not result:
                print(f"  > Erro: Não consegui inserir ou encontrar o filme '{title}'.")
                return

            movie_id = result[0]

            # --- Etapa 2: Limpar chunks antigos deste filme ---
            cursor.execute("DELETE FROM chunks WHERE movie_id = %s", (movie_id,))

            # --- Etapa 3: Gerar e inserir embedding PARA O TÍTULO ---
            preprocessed_title = preprocess_text(title)
            title_embedding = model.encode(preprocessed_title)

            cursor.execute(
                """
                INSERT INTO chunks (movie_id, chunk_texto, chunk_index, vetor_embedding)
                VALUES (%s, %s, %s, %s)
                """,
                (movie_id, title, 0, title_embedding)  # chunk_index = 0
            )
            print(f"  > Inserido embedding do título (Chunk 0) para movie_id {movie_id}.")

            # --- Etapa 4: "Chunkar" e inserir resenha ---
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=512, chunk_overlap=50, length_function=len
            )
            chunks = text_splitter.split_text(review_content)

            chunk_data_list = []
            for i, chunk in enumerate(chunks):
                preprocessed_chunk = preprocess_text(chunk)
                if not preprocessed_chunk:
                    continue

                chunk_embedding = model.encode(preprocessed_chunk)
                chunk_index = i + 1  # 1, 2, 3...

                chunk_data_list.append(
                    (movie_id, chunk, chunk_index, chunk_embedding)
                )

            # Inserir todos os chunks de uma vez (mais rápido)
            if chunk_data_list:
                # 'extras' foi importado na Linha 6
                extras.execute_values(
                    cursor,
                    """
                    INSERT INTO chunks (movie_id, chunk_texto, chunk_index, vetor_embedding)
                    VALUES %s ON CONFLICT (movie_id, chunk_index) DO NOTHING;
                    """,
                    chunk_data_list
                )
                print(f"  > Inseridos {len(chunk_data_list)} chunks da resenha.")

            conn.commit()

    except Exception as e:
        print(f"Erro ao processar o arquivo {filename}: {e}")
        conn.rollback()


# --- Função Principal ---

def main():
    parser = argparse.ArgumentParser(description="Script de ingestão de resenhas de filmes para o PGVector.")
    parser.add_argument(
        '--file',
        type=str,
        help="Caminho para um arquivo .txt específico para processar."
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help="Processar todos os arquivos .txt no diretório 'resenhas'."
    )

    args = parser.parse_args()

    conn = get_db_connection()
    if not conn:
        return

    if args.file:
        if os.path.exists(args.file):
            process_and_ingest_movie(args.file, conn)
        else:
            print(f"Erro: Arquivo {args.file} não encontrado.")

    elif args.all:
        print(f"Iniciando processamento de todos os arquivos em '{REVIEWS_DIR}'...")
        if not os.path.exists(REVIEWS_DIR):
            print(f"Erro: Diretório '{REVIEWS_DIR}' não encontrado.")
            return

        for filename in os.listdir(REVIEWS_DIR):
            if filename.endswith(".txt"):
                filepath = os.path.join(REVIEWS_DIR, filename)
                process_and_ingest_movie(filepath, conn)
        print("\nProcessamento de todos os arquivos concluído.")

    else:
        print("Nenhuma ação especificada. Use --file <caminho> ou --all.")

    conn.close()


if __name__ == "__main__":
    main()