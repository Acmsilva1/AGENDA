import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import time

# --- CONFIGURAÇÃO E CONEXÃO COM GOOGLE SHEETS ---

# Certifique-se de que este ID corresponda à sua planilha real
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU" 
ABA_NOME = "AGENDA"

# 📌 Função de Conexão e Autenticação Segura (Lê st.secrets)
@st.cache_resource(ttl=3600)
def get_gspread_client():
    """Conecta-se ao Google Sheets usando as credenciais do Streamlit Secrets."""
    try:
        # Acessa as credenciais do secrets.toml
        creds = st.secrets["gspread"]
        
        # Conecta usando o método service_account_from_dict
        gc = gspread.service_account_from_dict(creds)
        
        spreadsheet = gc.open_by_key(PLANILHA_ID)
        return spreadsheet
    except Exception as e:
        st.error(f"Erro de conexão com Google Sheets: {e}")
        st.stop()
        
spreadsheet = get_gspread_client()
sheet = spreadsheet.worksheet(ABA_NOME)

# --- FUNÇÕES DE DADOS ---

@st.cache_data(ttl=10) # Cache de 10 segundos para leitura
def carregar_eventos(_sheet):
    """Lê todos os registros e retorna como DataFrame."""
    try:
        dados = _sheet.get_all_records()
        df = pd.DataFrame(dados)
        
        # Trata a coluna de data
        df['data_evento'] = pd.to_datetime(df['data_evento'], errors='coerce')
        
        # Garante que a coluna ID seja inteira ou string
        if 'id_evento' in df.columns:
            df['id_evento'] = df['id_evento'].astype(str)
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

def adicionar_evento(dados_evento):
    """Adiciona um novo evento à planilha."""
    # Encontra a primeira linha vazia para inserir
    proxima_linha = len(sheet.get_all_values()) + 1
    
    # Adiciona o ID (usa a linha como ID simples)
    dados_evento['id_evento'] = str(proxima_linha - 1) 
    
    # Converte o dicionário para a ordem correta das colunas antes de inserir
    cabecalhos = [h.lower() for h in sheet.row_values(1)] # Assume cabeçalhos minúsculos para mapeamento
    
    valores_para_inserir = [dados_evento.get(h, '') for h in cabecalhos]
    
    # Insere os dados
    sheet.append_row(valores_para_inserir)

# --- LAYOUT E INTERFACE ---

st.set_page_config(layout="wide", page_title="Agenda de Governança")

# Título principal
st.title("🤖 Painel de Governança de Eventos")

# Carrega os dados mais recentes
df_todos = carregar_eventos(sheet)

# --- BARRA LATERAL (FILTROS) ---
st.sidebar.header("🗄️ Filtros de Visualização")

# 📌 FILTRO DE STATUS AJUSTADO (Coerente com a regra PENDENTE/CONCLUÍDO)
filtro_status = st.sidebar.radio(
    "Mostrar eventos por status:", 
    options=["Pendentes", "Concluídos", "Todos"], 
    index=0 # Padrão: Mostrar apenas Pendentes
)

# Lógica de filtragem para exibição
if filtro_status == "Pendentes":
    df_exibicao = df_todos[df_todos['status'] == 'Pendente']
elif filtro_status == "Concluídos":
    df_exibicao = df_todos[df_todos['status'] == 'Concluído']
else: # Todos
    df_exibicao = df_todos
    
# --- DASHBOARD PRINCIPAL ---

col1, col2 = st.columns([3, 1])

# Coluna 1: Tabela de Eventos
with col1:
    st.subheader(f"Lista de Eventos ({filtro_status}) - {len(df_exibicao)} Registros")
    st.dataframe(df_exibicao.drop(columns=['id_evento'], errors='ignore'), use_container_width=True)

# Coluna 2: Métricas de Governança (Simples)
with col2:
    st.subheader("Métricas")
    
    total_pendentes = len(df_todos[df_todos['status'] == 'Pendente'])
    total_concluidos = len(df_todos[df_todos['status'] == 'Concluído'])
    
    # Calcula itens vencidos (para exibição)
    hoje = datetime.now().date()
    df_pendentes_vencidos = df_todos[
        (df_todos['status'] == 'Pendente') & 
        (df_todos['data_evento'].dt.date < hoje)
    ]
    total_vencidos = len(df_pendentes_vencidos)
    
    st.metric(label="Total de Pendentes", value=total_pendentes)
    st.metric(label="Total de Concluídos", value=total_concluidos)
    st.metric(label="🚨 Vencidos e Pendentes", value=total_vencidos, delta=-total_vencidos if total_vencidos > 0 else "0", delta_color="inverse")


# --- ADICIONAR NOVO EVENTO ---
st.markdown("---")
st.header("➕ Adicionar Novo Evento")

with st.form("form_novo_evento"):
    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        titulo = st.text_input("Título do Evento (Obrigatório)", max_chars=100)
        descricao = st.text_area("Descrição")
        local = st.text_input("Local / Link")
    
    with col_f2:
        data_evento = st.date_input("Data do Evento", value=hoje)
        hora_evento = st.time_input("Hora do Evento", value=datetime.now().time())
        
        # Opções de Prioridade
        prioridade_options = ['Baixa', 'Média', 'Alta']
        prioridade = st.selectbox("Prioridade", options=prioridade_options, index=1)
        
        # 📌 STATUS AJUSTADO NO FORMULÁRIO
        status_options = ['Pendente', 'Concluído']
        status_evento = st.selectbox("Status", options=status_options, index=0) 

    submitted = st.form_submit_button("Salvar Novo Evento")
    
    if submitted:
        if titulo:
            novo_evento = {
                'id_evento': '', # Será preenchido na função
                'titulo': titulo,
                'descricao': descricao,
                'data_evento': data_evento.strftime('%Y-%m-%d'), # Formato padrão ISO
                'hora_evento': hora_evento.strftime('%H:%M'),
                'local': local,
                'prioridade': prioridade,
                'status': status_evento
            }
            
            try:
                adicionar_evento(novo_evento)
                st.success(f"Evento '{titulo}' adicionado com sucesso!")
                
                # Força a atualização do cache e da tela após a inserção
                st.cache_data.clear()
                st.rerun() 
            except Exception as e:
                st.error(f"Erro ao salvar na planilha: {e}")
        else:
            st.error("O Título do Evento é obrigatório.")
