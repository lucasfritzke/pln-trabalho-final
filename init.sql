-- Criar extensão pgVector
CREATE EXTENSION IF NOT EXISTS vector;

-- Criar tabela de filmes
CREATE TABLE IF NOT EXISTS filmes (
    id SERIAL PRIMARY KEY,
    titulo VARCHAR(500) NOT NULL,
    chunk_texto TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    vetor_embedding vector(768),
    data_insercao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_filmes_vetor
ON filmes
USING ivfflat (vetor_embedding vector_cosine_ops)
WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_filmes_titulo
ON filmes(titulo);

CREATE UNIQUE INDEX IF NOT EXISTS idx_filmes_titulo_chunk
ON filmes(titulo, chunk_index);