## Ideia

Na pasta filmestxcts temos o título do filme e suas resenhas em arquivos txt. 
Quero fazer o RAG para buscar o filme e resenha pelo input do usuário.

Ex: quero um filme divertido, o RAG me retorna "Apertem os cintos... o piloto sumiu" e sua resenha.


## Arquitetura

Banco de Dados:
- PostgreSQL com pgVector para armazenar os vetores das resenhas dos filmes.
- Tabela "filmes" com colunas: id, titulo, resenha, vetor_resenha.
- Um filme podera ter vário linhas (cada linha será um chunck da resenha).

## Linguagem de programação
- Python 3.10

# Quero fazer o calculo do embedding localmente, sem usar API externa.

# Especs técnicas:

- Notebook dell g15
- 16 GB RAM
- GPU RTX 3050 6GB
- Processador i5 13th gen
- SSD 512 GB

É possível fazer? 

Me de o código comentado e bem separado em métodos

também escreva um manual detalhado de como implantar e rodar o sistema.