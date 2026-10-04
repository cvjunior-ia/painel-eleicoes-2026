# Painel Eleições 2026 — TSE

Painel Streamlit para acompanhar resultados públicos do TSE.

## Publicação no Streamlit Community Cloud

1. Acesse https://share.streamlit.io
2. Entre com GitHub.
3. Clique em **Create app**.
4. Selecione este repositório.
5. Branch: `main`
6. Main file path: `streamlit_app.py`
7. Clique em **Deploy**.

O endereço final será parecido com:

`https://painel-eleicoes-2026.streamlit.app`

## Observações

- O painel consulta os arquivos JSON públicos do TSE.
- A atualização automática ocorre a cada 15 minutos.
- O armazenamento local da pasta `historico` no Streamlit Cloud é temporário e pode ser perdido quando a aplicação reiniciar. Isso não afeta a visualização ao vivo.
- Não coloque senhas, tokens ou credenciais dentro do código ou do repositório público.
