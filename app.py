import streamlit as st
import pandas as pd
import requests
import base64
import re
import sqlite3
from io import BytesIO
from openpyxl import load_workbook
from bs4 import BeautifulSoup

st.set_page_config(page_title="Shopee Uploader", layout="wide")

IMGBB_API_KEY = "5ebf9740e61741d80a644637d5602009"
DB = "produtos.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS produtos
                 (id INTEGER PRIMARY KEY, nome TEXT, preco REAL, url_ali TEXT, url_imgbb TEXT,
                  categoria_id TEXT, peso REAL, comprimento REAL, largura REAL, altura REAL, atributos TEXT)''')
    conn.commit()
    conn.close()

def rehost_imgbb(url_original):
    if not url_original or "i.ibb.co" in url_original: return url_original
    try:
        resp = requests.get(url_original, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        if resp.status_code == 200:
            img_b64 = base64.b64encode(resp.content)
            payload = {"key": IMGBB_API_KEY, "image": img_b64}
            upload = requests.post("https://api.imgbb.com/1/upload", data=payload, timeout=30).json()
            if upload.get("success"): return upload["data"]["url"]
    except: pass
    return None

def salvar_produto(nome, preco, url_ali):
    url_imgbb = rehost_imgbb(url_ali)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO produtos (nome, preco, url_ali, url_imgbb, peso, comprimento, largura, altura, atributos) VALUES (?,?,?,?,?,?,?,?,?)",
              (nome, preco, url_ali, url_imgbb, 0.5, 10, 10, 10, 'Marca:Sem marca|Condição:Novo|Material:Plástico|País de Origem:China|Duração da Garantia:7 dias'))
    conn.commit()
    conn.close()

def carregar_produtos():
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM produtos", conn)
    conn.close()
    return df

def gerar_excel_shopee():
    df = carregar_produtos()
    if df.empty: return None

    # Aqui você coloca seu template_shopee.xlsx na raiz do projeto no Streamlit
    wb = load_workbook("template_shopee.xlsx")
    ws = wb.active

    header_map = {str(cell.value).replace("\n", " ").strip(): col_idx
                  for col_idx, cell in enumerate(ws[3], 1) if cell.value}

    for i, row in df.iterrows():
        linha = 7 + i
        urls = [f"{row['url_imgbb']}?v={j}" for j in range(1, 4)] if row['url_imgbb'] else [None]*3

        dados = {
            "Nome do Produto": row['nome'][:120],
            "Preço": row['preco'],
            "Imagem de Capa": urls[0], "Imagem 1": urls[0], "Imagem 2": urls[1], "Imagem 3": urls[2],
            "Estoque": 10, "Peso": row['peso'], "Comprimento": row['comprimento'],
            "Largura": row['largura'], "Altura": row['altura'],
            "Descrição do Produto": f"Produto: {row['nome']}<br>Envio rápido. Garantia 7 dias."
        }

        for attr in row['atributos'].split('|'):
            k, v = attr.split(':')
            dados[k.strip()] = v.strip()

        for col_nome, valor in dados.items():
            if col_nome in header_map and valor:
                ws.cell(row=linha, column=header_map[col_nome], value=valor)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()

init_db()
st.title("🚀 Painel Shopee Uploader")

tab1, tab2 = st.tabs(["📦 Adicionar Produtos", "📋 Gerenciar e Exportar"])

with tab1:
    st.subheader("Colar dados do AliExpress")
    nome = st.text_input("Nome do Produto")
    preco = st.number_input("Preço", min_value=0.0, format="%.2f")
    url_ali = st.text_input("URL da Imagem Principal")
    if st.button("Salvar Produto", type="primary"):
        if nome and url_ali:
            salvar_produto(nome, preco, url_ali)
            st.success("Produto salvo! Vá na aba 'Gerenciar' pra exportar.")
            st.rerun()

with tab2:
    df = carregar_produtos()
    st.subheader(f"Produtos cadastrados: {len(df)}")
    if not df.empty:
        st.dataframe(df[['nome', 'preco', 'url_imgbb']], use_container_width=True, hide_index=True)
        st.divider()
        excel_bytes = gerar_excel_shopee()
        st.download_button(
            label="📥 Baixar Excel Pronto pra Shopee",
            data=excel_bytes,
            file_name="shopee_upload.xlsx",
            mime="application/vnd.ms-excel",
            type="primary"
        )
    else:
        st.info("Nenhum produto cadastrado. Vá em 'Adicionar Produtos'.")