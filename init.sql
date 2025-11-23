CREATE EXTENSION IF NOT EXISTS vector;

-- Tabela de Filmes (Agora com a resenha completa)
CREATE TABLE IF NOT EXISTS public.movies (
	movie_id serial4 NOT NULL,
	titulo varchar(500) NOT NULL,
    resenha_completa text NULL, -- NOVA COLUNA
	data_insercao timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT movies_pkey PRIMARY KEY (movie_id),
	CONSTRAINT movies_titulo_key UNIQUE (titulo)
);

-- Tabela de Chunks (Vetores)
CREATE TABLE IF NOT EXISTS public.chunks (
	chunk_id serial4 NOT NULL,
	movie_id int4 NOT NULL,
	chunk_texto text NOT NULL,
	chunk_index int4 NOT NULL,
	vetor_embedding public.vector(768) NULL, -- Mantendo 768 dimensões
	CONSTRAINT chunks_movie_chunk_idx UNIQUE (movie_id, chunk_index),
	CONSTRAINT chunks_pkey PRIMARY KEY (chunk_id),
	CONSTRAINT chunks_movie_id_fkey FOREIGN KEY (movie_id) REFERENCES public.movies(movie_id) ON DELETE CASCADE
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_chunks_movie_id ON public.chunks USING btree (movie_id);
CREATE INDEX IF NOT EXISTS idx_chunks_vetor ON public.chunks USING ivfflat (vetor_embedding vector_cosine_ops) WITH (lists='100');