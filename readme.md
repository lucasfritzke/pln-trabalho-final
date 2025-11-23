# Arquitetura do Projeto: RAG de Filmes com MCP

Este documento detalha a arquitetura técnica do sistema de *Retrieval-Augmented Generation* (RAG) desenvolvido para recomendação de filmes, integrando LM Studio (Llama 3), PostgreSQL (pgvector) e o Protocolo MCP.

## 1. Estrutura de Dados Vetorial

O sistema utiliza um banco de dados relacional com suporte a vetores para armazenar e recuperar informações baseadas em similaridade semântica.

* **Banco de Dados:** PostgreSQL com extensão `vector`.
* **Dimensionalidade:** **768 dimensões**.
    * Os vetores são gerados pelo modelo `paraphrase-multilingual-mpnet-base-v2` (Sentence Transformers), que converte texto em arrays numéricos fixos.
* **Métrica de Busca:** Distância de Cosseno.
    * A similaridade é calculada pela fórmula `1 - (vetor_embedding <=> query_embedding)`.
    * Índice IVFFlat (`vector_cosine_ops`) é utilizado para otimizar a velocidade de busca.

## 2. Ingestão e Pré-processamento

O fluxo de ingestão (`ingest.py`) transforma arquivos de texto cru em dados estruturados e vetores pesquisáveis.

### Processamento de Arquivos
1.  **Leitura:** O script lê arquivos `.txt` onde a primeira linha é considerada o **Título** e as linhas subsequentes a **Resenha**.
2.  **Armazenamento do Pai (Full Context):** O texto completo (Título + Resenha) é salvo na tabela `movies` na coluna `resenha_completa`. Isso garante que o contexto integral esteja disponível para o LLM após a busca.

### Pipeline de Vetorização (Chunking)
1.  **Limpeza:** O texto é normalizado (lowercase, remoção de pontuação) e *stopwords* (palavras de conexão sem valor semântico) são removidas usando NLTK.
2.  **Fragmentação (Chunking):** O conteúdo é dividido usando `RecursiveCharacterTextSplitter`:
    * *Chunk Size:* 512 caracteres.
    * *Overlap:* 50 caracteres (para manter contexto nas bordas dos cortes).
3.  **Embedding:** Cada fragmento limpo é convertido em um vetor de 768 dimensões.
4.  **Persistência:** Os vetores são salvos na tabela `chunks`, vinculados ao `movie_id` do filme original.

## 3. Mecanismo de Busca (RAG)

A API (`api.py`) executa a lógica de recuperação híbrida: busca no micro (chunk) para entregar o macro (filme completo).

1.  **Query Embedding:** O prompt do usuário é convertido em vetor pelo mesmo modelo usado na ingestão.
2.  **Busca Vetorial:** O banco localiza os *chunks* mais próximos semanticamente da pergunta do usuário.
3.  **Join e Recuperação:**
    * O sistema faz um `JOIN` entre a tabela `chunks` (onde ocorreu o *match*) e a tabela `movies`.
    * **Crucial:** O retorno para o LLM não é o fragmento picotado, mas sim o campo `resenha_completa` da tabela `movies`.
4.  **Deduplicação:** Utiliza-se lógica (`DISTINCT ON` ou agrupamento) para garantir que, mesmo se 5 chunks do mesmo filme forem encontrados, o filme seja retornado apenas uma vez na lista final.

## 4. O que é MCP (Model Context Protocol)

O **MCP** é o protocolo que padroniza a comunicação entre o Assistente de IA (Cliente) e os dados locais (Servidor).

* **Servidor MCP:** O script `movies-rag.py` atua como o servidor. Ele expõe uma ferramenta chamada `searchMovies`.
* **Funcionamento:**
    1.  O **LM Studio (Llama 3)** identifica que precisa de dados externos para responder uma pergunta.
    2.  Ele envia uma solicitação JSON para o servidor MCP.
    3.  O servidor MCP consulta a API local (`api.py`) e retorna os dados dos filmes encontrados.
    4.  O Llama 3 processa o JSON retornado e formula a resposta em linguagem natural para o usuário.

## 5. Resumo da Stack Tecnológica

| Componente | Tecnologia | Função |
| :--- | :--- | :--- |
| **Interface / LLM** | LM Studio (Llama 3) | Interação com o usuário e raciocínio final. |
| **Protocolo** | MCP (Python SDK) | Conexão padronizada entre LLM e Ferramentas. |
| **Backend de Busca** | FastAPI | API REST que encapsula a lógica de busca. |
| **Banco de Dados** | PostgreSQL + pgvector | Armazenamento de metadados e vetores (768d). |
| **Embeddings** | Sentence-Transformers | Modelo `paraphrase-multilingual-mpnet-base-v2`. |