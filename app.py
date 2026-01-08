import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time, datetime
import time as t 
# from streamlit_autorefresh import st_autorefresh # ❌ REMOVIDO: Sem refresh automático!

# --- CONFIGURAÇÕES DO PROJETO ---
# ID da Planilha no seu Google Drive
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# Ordem de prioridade para exibição: 1-Pendente, 2-Concluído, 3-Cancelado
STATUS_PRIORITY_MAP = {
    'Pendente': 1,
    'Concluído': 2,
    'Cancelado': 3
}

# =================================================================
# === FUNÇÕES DE CONEXÃO E GOVERNANÇA (REUSADAS) ===
# =================================================================

# Mantida a lógica de cache e retentativa (governança)
@st.cache_resource(ttl=3600)
def conectar_sheets_resource():
    """Tenta conectar ao Google Sheets usando Streamlit Secrets com lógica de Retentativa."""
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        try:
            # st.secrets["gspread"] foi movido para o recurso (resource cache)
            gc = gspread.service_account_from_dict(st.secrets["gspread"])
            spreadsheet = gc.open_by_key(PLANILHA_ID)
            st.sidebar.success("✅ Conexão com Google Sheets estabelecida.")
            return spreadsheet
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait_time = 2 ** attempt
                st.sidebar.warning(f"⚠️ Falha de conexão momentânea (Tentativa {attempt + 1}/{MAX_RETRIES}). Retentando em {wait_time}s...")
                t.sleep(wait_time) 
            else:
                st.error(f"🚨 Erro fatal ao conectar após {MAX_RETRIES} tentativas. Erro: {e}")
                return None
    return None

# R (Read) - Lê todos os eventos com cache de 10 segundos
@st.cache_data(ttl=10)
def carregar_eventos(spreadsheet):
    """Lê todos os registros (ignorando o cabeçalho) e retorna como DataFrame."""
    
    if spreadsheet is None:
         return pd.DataFrame()
         
    try:
        sheet = spreadsheet.worksheet(ABA_NOME)
        # Forçando o valor como texto simples para evitar formatações de data/hora do Sheets
        dados = sheet.get_all_records(
             value_render_option='UNFORMATTED_VALUE', 
             head=1 
        )
        df = pd.DataFrame(dados)
        
        # Correção e Padronização de Colunas
        if not df.empty and 'data_evento' in df.columns and 'hora_evento' in df.columns:
            # Converte data para datetime para ordenação correta
            df['data_hora_ordenacao'] = pd.to_datetime(
                df['data_evento'].astype(str) + ' ' + df['hora_evento'].astype(str),
                errors='coerce'
            )
            df = df.dropna(subset=['data_hora_ordenacao']).copy()
            df['Ordem_Status'] = df['status'].map(STATUS_PRIORITY_MAP).fillna(99) # 99 para status desconhecido
        
        return df

    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# C (Create) - Adiciona um novo evento
def adicionar_evento(spreadsheet, dados_do_form):
    """Insere uma nova linha de evento no Sheets."""
    try:
        sheet = spreadsheet.worksheet(ABA_NOME)
        
        # Garantindo a ordem exata das 7 colunas (conforme seu código original 'app.py')
        colunas = ['id_evento', 'titulo', 'descricao', 'data_evento', 'hora_evento', 'local', 'status']
        nova_linha = [dados_do_form.get(col) for col in colunas]
        
        sheet.append_row(nova_linha, value_input_option='USER_ENTERED')
        st.success("🎉 Evento criado. **Recarregando dados...**")
        carregar_eventos.clear() # LIMPA O CACHE
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar evento: {e}")
        return False

# U (Update) - Atualiza um evento existente
def atualizar_evento(spreadsheet, id_evento, novos_dados):
    """Busca a linha pelo ID e atualiza os dados da linha."""
    try:
        sheet = spreadsheet.worksheet(ABA_NOME)
        cell = sheet.find(id_evento)
        linha_index = cell.row 
        
        colunas = ['id_evento', 'titulo', 'descricao', 'data_evento', 'hora_evento', 'local', 'status']
        valores_atualizados = [novos_dados.get(col) for col in colunas]

        # Atualiza a linha inteira a partir da coluna A
        sheet.update(f'A{linha_index}', [valores_atualizados], value_input_option='USER_ENTERED')
        st.success(f"🔄 Evento {id_evento[:8]}... atualizado. **Recarregando dados...**")
        carregar_eventos.clear() # LIMPA O CACHE
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o evento: {e}")
        return False

# D (Delete) - Remove um evento
def deletar_evento(spreadsheet, id_evento):
    """Busca a linha pelo ID e a deleta."""
    try:
        sheet = spreadsheet.worksheet(ABA_NOME)
        cell = sheet.find(id_evento)
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Evento {id_evento[:8]}... deletado. **Recarregando dados...**")
        carregar_eventos.clear() # LIMPA O CACHE
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o evento: {e}")
        return False


# =================================================================
# === INTERFACE STREAMLIT (UI) ===
# =================================================================

st.set_page_config(layout="wide", page_title="Agenda de Eventos")

st.title("🗓️ **Agenda de Eventos** (Transplantada do Controle Financeiro)")

# Inicialização do Estado para o modo de Edição Inline
if 'id_edicao_ativa_agenda' not in st.session_state:
    st.session_state['id_edicao_ativa_agenda'] = None

# Conexão
spreadsheet = conectar_sheets_resource()
if spreadsheet is None:
    st.stop() 

# --- BLOCO DE REFRESH MANUAL (Governança e UX) ---
with st.sidebar:
    st.markdown("---")
    if st.button("Forçar Atualização Manual 🔄", help="Limpa o cache e busca os dados mais recentes do Google Sheets."):
        carregar_eventos.clear() 
        st.success("✅ Cache limpo! Recarregando dados...") 
        st.rerun() 
    st.markdown("---")
    st.info("Atualização: Apenas ao salvar/deletar, ou use o botão manual. Sem refresh automático.")


# Carregamento de Dados (Cacheado)
df_eventos = carregar_eventos(spreadsheet) 

# === SEÇÃO 1: CRIAR NOVO EVENTO ===
st.header("📥 Registrar Novo Evento")

with st.form("form_novo_evento", clear_on_submit=True):
    col1, col2 = st.columns(2)
    
    with col1:
        titulo = st.text_input("TÍTULO DO EVENTO", max_chars=100)
        local = st.text_input("Local ou Link da Reunião:")
        data = st.date_input("Data:", date.today(), format="DD/MM/YYYY") 
    
    with col2:
        hora = st.time_input("Hora:", time(9, 0)) 
        status_inicial = st.selectbox("Status Inicial:", ['Pendente', 'Rascunho']) # Mantido 'Rascunho' como opção inicial, mas 'Pendente' será o padrão na maioria
        st.markdown("---") # Espaçamento para alinhamento
    
    descricao = st.text_area("Descrição Detalhada:")
    
    submit_button = st.form_submit_button("Salvar Novo Evento")

    if submit_button:
        if titulo and data: 
            dados_para_sheet = {
                'id_evento': str(uuid.uuid4()),
                'titulo': titulo,
                'descricao': descricao,
                'data_evento': data.strftime('%Y-%m-%d'), # Formato ISO para Sheets
                'hora_evento': hora.strftime('%H:%M'),
                'local': local,
                'status': status_inicial if status_inicial != 'Rascunho' else 'Pendente' # Força 'Pendente' se for Rascunho
            }
            adicionar_evento(spreadsheet, dados_para_sheet)
            st.rerun() # Recarrega para mostrar o novo dado
        else:
            st.warning("O Título e a Data são obrigatórios. Não complique.")
            

st.divider()

# === SEÇÃO 2: VISUALIZAR E GERENCIAR (R, U, D) com UX Inline ===

st.header("📑 Meus Eventos Detalhados (Prioridade: Pendente Primeiro)")


if df_eventos.empty:
    st.info("Sem eventos válidos para exibição.")
else:
    
    # 3. Ordem de Registro: 1 - PENDENTE, 2 - CONCLUIDO
    df_display = df_eventos.copy().sort_values(
        by=['Ordem_Status', 'data_hora_ordenacao'], 
        ascending=[
            True,  # Ordem_Status (1=Pendente, 2=Concluído)
            True   # Data e Hora (Mais Antigo Primeiro)
        ]
    )
    
    # Cabeçalhos
    col_t, col_d, col_l, col_s, col_e, col_x = st.columns([0.25, 0.4, 0.15, 0.1, 0.05, 0.05])
    col_t.markdown("**Título / Data**")
    col_d.markdown("**Descrição**")
    col_l.markdown("**Local**")
    col_s.markdown("**Status**")
    col_e.markdown(" ") 
    col_x.markdown(" ") 
    st.markdown("---")
    
    # Loop sobre cada evento para exibição/edição inline
    for index, row in df_display.iterrows():
        
        id_evento = row['id_evento']
        
        # 1. Se a linha NÃO está em modo de edição (EXIBIÇÃO NORMAL + BOTÕES)
        if st.session_state.id_edicao_ativa_agenda != id_evento:
            
            col_t, col_d, col_l, col_s, col_e, col_x = st.columns([0.25, 0.4, 0.15, 0.1, 0.05, 0.05])
            
            status_cor = "orange" if row['status'] == 'Pendente' else ("green" if row['status'] == 'Concluído' else "gray")
            
            titulo_e_data = f"**{row['titulo']}**<br><small>{pd.to_datetime(row['data_evento']).strftime('%d/%m/%Y')} {row['hora_evento']}</small>"
            
            col_t.markdown(titulo_e_data, unsafe_allow_html=True)
            col_d.write(row['descricao'][:100] + "..." if len(row['descricao']) > 100 else row['descricao'])
            col_l.write(row['local'])
            col_s.markdown(f"**<span style='color:{status_cor}'>{row['status']}</span>**", unsafe_allow_html=True)

            if col_e.button("✍️", key=f'edit_ag_{id_evento}', help="Editar este evento"):
                st.session_state.id_edicao_ativa_agenda = id_evento 
                st.rerun() 

            if col_x.button("🗑️", key=f'del_ag_{id_evento}', help="Excluir este evento"):
                deletar_evento(spreadsheet, id_evento)
                st.rerun() 
        
            st.markdown("---") 
        
        # 2. Se a linha ESTÁ em modo de edição (FORMULÁRIO INLINE)
        else: 
            st.warning(f"📝 Editando Evento: **{row['titulo']}**")
            
            with st.form(key=f"form_update_ag_{id_evento}"):
                
                transacao_dados = row 
                
                col_upd_1, col_upd_2 = st.columns(2) 
                
                # INPUTS
                novo_titulo = col_upd_1.text_input("Título do Evento", value=transacao_dados['titulo'], key=f'ut_titulo_ag_{id_evento}')
                novo_local = col_upd_2.text_input("Local", value=transacao_dados['local'], key=f'ut_local_ag_{id_evento}')
                
                col_upd_3, col_upd_4, col_upd_5 = st.columns(3) 

                novo_data = col_upd_3.date_input(
                    "Data", 
                    value=pd.to_datetime(transacao_dados['data_evento']).date(),
                    format="DD/MM/YYYY",
                    key=f'ut_data_ag_{id_evento}'
                )
                
                novo_hora_str = transacao_dados['hora_evento']
                try:
                    # Garante que a hora seja carregada corretamente
                    novo_hora = col_upd_4.time_input("Hora", value=time(int(novo_hora_str[:2]), int(novo_hora_str[3:])), key=f'ut_hora_ag_{id_evento}')
                except:
                    novo_hora = col_upd_4.time_input("Hora (Padrão 09:00)", value=time(9, 0), key=f'ut_hora_ag_{id_evento}') 

                opcoes_status = ['Pendente', 'Concluído', 'Cancelado']
                status_idx = opcoes_status.index(transacao_dados['status'])
                novo_status = col_upd_5.selectbox("Status", opcoes_status, index=status_idx, key=f'ut_status_ag_{id_evento}')

                novo_descricao = st.text_area(
                    "Descrição", 
                    value=transacao_dados['descricao'], 
                    key=f'ut_desc_ag_{id_evento}'
                )
                
                # BOTÃO DE SALVAR (DENTRO DO FORM)
                update_button = st.form_submit_button("✅ Salvar Alterações")

                if update_button:
                    
                    if novo_titulo and novo_data:
                        dados_atualizados = {
                            'id_evento': id_evento, 
                            'titulo': novo_titulo,
                            'descricao': novo_descricao,
                            'data_evento': novo_data.strftime('%Y-%m-%d'),
                            'hora_evento': novo_hora.strftime('%H:%M'),
                            'local': novo_local,
                            'status': novo_status
                        }
                        atualizar_evento(spreadsheet, id_evento, dados_atualizados) 
                        st.session_state.id_edicao_ativa_agenda = None 
                        st.rerun()
                    else:
                        st.warning("Título e Data são obrigatórios na atualização.")

            # BOTÃO DE CANCELAR (FORA DO FORM)
            col_dummy_save, col_cancel_out = st.columns([1, 4])
            if col_cancel_out.button("Cancelar Edição", key=f'cancel_edit_ag_{id_evento}'):
                st.session_state.id_edicao_ativa_agenda = None
                st.rerun()

            st.markdown("---") # Separador para o formulário de edição


with st.sidebar:
    st.markdown("---")
    st.caption(f"Última leitura de dados (Cache/Sheets): {datetime.now().strftime('%H:%M:%S')}")
