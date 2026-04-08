import streamlit as st
import pandas as pd
import requests
import base64
import re
import sqlite3
from io import BytesIO
from openpyxl import load_workbook
from bs4 import BeautifulSoup
import unicodedata

st.set_page_config(page_title="Shopee Uploader", layout="wide")

IMGBB_API_KEY = "5ebf9740e61741d80a644637d5602009"
DB = "produtos.db"

def normalizar_texto(texto):
    texto = str(texto).lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c)!= 'Mn')
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return texto

@st.cache_data
def carregar_categorias():
    try:
        df_cat = pd.read_excel("template_shopee_Categoria.xlsx").fillna('')
        # Detecta automaticamente a coluna de ID e nome
        col_id = [col for col in df_cat.columns if 'id' in col.lower() and 'categoria' in col.lower()][0]
        col_nome_cats = [col for col in df_cat.columns if 'categoria' in col.lower() and 'id' not in col.lower()]

        dicionario = []
        for _, row in df_cat.iterrows():
            partes_nome = [str(row[col]) for col in col_nome_cats if row[col]]
            texto_completo = " > ".join(partes_nome)
            palavras_chave = normalizar_texto(texto_completo)
            id_categoria = row[col_id]
            if id_categoria and texto_completo:
                dicionario.append({
                    "id": str(int(id_categoria)),
                    "nome_completo": texto_completo.strip(),
                    "palavras": palavras_chave
                })
        return dicionario
    except Exception as e:
        st.error(f"Erro ao ler categorias: {e}")
        return []

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS produtos
                 (id INTEGER PRIMARY KEY, nome TEXT, preco REAL, url_ali TEXT, url_imgbb TEXT,
                  categoria_id TEXT, categoria_nome TEXT, peso REAL, comprimento REAL, largura REAL, altura REAL)''')
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

def salvar_produto(nome, preco, url_ali, cat_id, cat_nome):
    url_imgbb = rehost_imgbb(url_ali)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO produtos (nome, preco, url_ali, url_imgbb, categoria_id, categoria_nome, peso, comprimento, largura, altura) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (nome, preco, url_ali, url_imgbb, cat_id, cat_nome, 0.5, 10, 10, 10))
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

    wb = load_workbook("template_shopee.xlsx")
    ws = wb.active
    header_map = {str(cell.value).replace("\n", " ").strip(): col_idx for col_idx, cell in enumerate(ws[3], 1) if cell.value}

    for i, row in df.iterrows():
        linha = 7 + i
        urls = [f"{row['url_imgbb']}?v={j}" for j in range(1, 4)] if row['url_imgbb'] else [None]*3
        dados = {
            "Nome do Produto": row['nome'][:120], "Preço": row['preco'],
            "Imagem de Capa": urls[0], "Imagem 1": urls[0], "Imagem 2": urls[1], "Imagem 3": urls[2],
            "Categoria": row['categoria_id'], "Estoque": 10, "Peso": row['peso'],
            "Comprimento": row['comprimento'], "Largura": row['largura'], "Altura": row['altura'],
            "Descrição do Produto": f"Produto: {row['nome']}<br>Envio rápido. Garantia 7 dias.",
            "Marca": "Sem marca", "Condição": "Novo", "Material": "Plástico",
            "País de Origem": "China", "Duração da Garantia": "7 dias"
        }
        for col_nome, valor in dados.items():
            if col_nome in header_map and valor:
                ws.cell(row=linha, column=header_map[col_nome], value=valor)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()

init_db()
DIC_CATEGORIAS = carregar_categorias()

st.title("🚀 Painel Shopee Uploader")
st.caption(f"Categorias carregadas: {len(DIC_CATEGORIAS)}")

tab1, tab2 = st.tabs(["📦 Adicionar Produtos", "📋 Gerenciar e Exportar"])

with tab1:
    st.subheader("Colar dados do AliExpress")
    nome = st.text_input("Nome do Produto")
    preco = st.number_input("Preço", min_value=0.0, format="%.2f")
    url_ali = st.text_input("URL da Imagem Principal")

    # Busca de categoria com selectbox
    busca_cat = st.text_input("Buscar categoria", placeholder="Digite: fone, blusa, luminaria...")
    cats_filtradas = DIC_CATEGORIAS
    if busca_cat:
        busca_norm = normalizar_texto(busca_cat)
        cats_filtradas = [c for c in DIC_CATEGORIAS if busca_norm in c["palavras"]]

    opcoes_cat = {c["nome_completo"]: c["id"] for c in cats_filtradas[:50]} # Mostra só 50 pra não travar
    opcoes_cat["-- Nenhuma / Preencher depois --"] = ""

    cat_selecionada_nome = st.selectbox("Selecione a Categoria", options=list(opcoes_cat.keys()))
    cat_id_final = opcoes_cat[cat_selecionada_nome]

    if cat_id_final:
        st.success(f"ID da Categoria: {cat_id_final}")
    else:
        st.warning("Sem categoria. Você pode preencher depois direto na Shopee.")

    if st.button("Salvar Produto", type="primary"):
        if nome and url_ali:
            salvar_produto(nome, preco, url_ali, cat_id_final, cat_selecionada_nome)
            st.success("Produto salvo!")
            st.rerun()

with tab2:
    df = carregar_produtos()
    st.subheader(f"Produtos cadastrados: {len(df)}")
    if not df.empty:
        st.dataframe(df[['nome', 'preco', 'categoria_nome', 'url_imgbb']], use_container_width=True, hide_index=True)
        st.divider()
        excel_bytes = gerar_excel_shopee()
        st.download_button("📥 Baixar Excel Pronto pra Shopee", data=excel_bytes, file_name="shopee_upload.xlsx", type="primary")
    else:
        st.info("Nenhum produto cadastrado.")
