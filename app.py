import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time
import time as t # 📌 CORREÇÃO: Usando 't' para o módulo de tempo (sleep)

# --- CONFIGURAÇÕES DO PROJETO ---

# ID da Planilha no seu Google Drive
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"

# --- CONFIGURAÇÃO DA GOVERNANÇA (Conexão Segura via Streamlit Secrets) ---

@st.cache_resource
def conectar_sheets():
    """Tenta conectar ao Google Sheets usando Streamlit Secrets (Recomendado para Cloud)."""
    try:
        gc = gspread.service_account_from_dict(st.secrets["gspread"])
        
        spreadsheet = gc.open_by_key(PLANILHA_ID)
        sheet = spreadsheet.worksheet(ABA_NOME)
        
        st.sidebar.success("✅ Conexão com Google Sheets estabelecida.")
        return sheet
    except KeyError:
        st.error("🚨 Secrets do 'gspread' não configurados. Por favor, adicione as chaves no Streamlit Cloud.")
    except Exception as e:
        st.error(f"🚨 Erro ao conectar ou acessar o Sheets. Verifique o compartilhamento com a Service Account. Erro: {e}")
    return None

# --- FUNÇÕES CORE DO CRUD ---

# R (Read) - Lê todos os eventos
def carregar_eventos(sheet):
    """Lê todos os registros (ignorando o cabeçalho) e retorna como DataFrame."""
    try:
        dados = sheet.get_all_records()
        return pd.DataFrame(dados)
    except Exception as e:
        st.warning(f"Não foi possível carregar os dados. Erro: {e}")
        return pd.DataFrame()

# C (Create) - Adiciona um novo evento
def adicionar_evento(sheet, dados_do_form):
    """Insere uma nova linha de evento no Sheets."""
    
    nova_linha = [
        dados_do_form.get('id_evento'),
        dados_do_form.get('titulo'),
        dados_do_form.get('descricao'),
        dados_do_form.get('data_evento'),
        dados_do_form.get('hora_evento'),
        dados_do_form.get('local'),
        dados_do_form.get('prioridade'),
        dados_do_form.get('status')
    ]
    
    sheet.append_row(nova_linha)
    st.success("🎉 Evento criado. Mais um compromisso para a sua vida.")

# U (Update) - Atualiza um evento existente
def atualizar_evento(sheet, id_evento, novos_dados):
    """Busca a linha pelo ID e atualiza os dados da linha."""
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row 

        valores_atualizados = [
            novos_dados['id_evento'],
            novos_dados['titulo'],
            novos_dados['descricao'],
            novos_dados['data_evento'],
            novos_dados['hora_evento'],
            novos_dados['local'],
            novos_dados['prioridade'],
            novos_dados['status']
        ]

        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Evento {id_evento[:8]}... atualizado com sucesso. Foco nos detalhes.")
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado. Algum erro na matriz.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o evento: {e}")
        return False

# D (Delete) - Remove um evento
def deletar_evento(sheet, id_evento):
    """Busca a linha pelo ID e a deleta."""
    try:
        cell = sheet.find(id_evento)
        linha_index = cell.row

        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Evento {id_evento[:8]}... deletado. Férias merecidas para esse compromisso.")
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento[:8]}...' não encontrado. Impossível apagar algo que não existe.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o evento: {e}")
        return False


# --- INTERFACE STREAMLIT (UI) ---

st.set_page_config(layout="wide")
st.title("🗓️ Agenda Sarcástica v1.0 (Python/Sheets)")

sheet = conectar_sheets()

if sheet is None:
    st.stop()


tab_criar, tab_visualizar_editar = st.tabs(["➕ Criar Evento", "👁️ Visualizar e Gerenciar"])


# === ABA CRIAR ===
with tab_criar:
    st.header("Novo Evento: O Início da Sua Jornada")
    
    with st.form("form_novo_evento", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            titulo = st.text_input("Título Principal (Exato!)", max_chars=100)
            local = st.text_input("Local ou Link da Reunião:")
            data = st.date_input("Data:", date.today(), format="DD/MM/YYYY") 
        
        with col2:
            prioridade = st.selectbox("Prioridade:", ["Média", "Alta", "Baixa"])
            # 📌 CORREÇÃO: O 'time' aqui é a função construtora, não o módulo.
            hora = st.time_input("Hora:", time(9, 0)) 
            status_inicial = st.selectbox("Status Inicial:", ['Pendente', 'Rascunho'])
        
        descricao = st.text_area("Descrição Detalhada:")
        
        submit_button = st.form_submit_button("Salvar Novo Evento")

        if submit_button:
            if titulo and data: 
                dados_para_sheet = {
                    'id_evento': str(uuid.uuid4()),
                    'titulo': titulo,
                    'descricao': descricao,
                    'data_evento': data.strftime('%Y-%m-%d'), 
                    'hora_evento': hora.strftime('%H:%M'),
                    'local': local,
                    'prioridade': prioridade,
                    'status': status_inicial
                }
                adicionar_evento(sheet, dados_para_sheet)
                
                conectar_sheets.clear()
                
                st.experimental_rerun()
            else:
                st.warning("O Título e a Data são obrigatórios. Não complique.")


# === ABA VISUALIZAR E GERENCIAR (R, U, D) ===
with tab_visualizar_editar:
    st.header("Seus Eventos Atuais (CRUD)")
    df_eventos = carregar_eventos(sheet)
    
    if df_eventos.empty:
        st.info("Nenhum evento na agenda. Você está de férias ou está procrastinando?")
    else:
        
        df_display = df_eventos.copy()
        
        if 'data_evento' in df_display.columns:
            df_display['data_evento'] = pd.to_datetime(df_display['data_evento'], errors='coerce').dt.strftime('%d/%m/%Y')
        
        df_display.rename(columns={
            'id_evento': 'ID', 
            'titulo': 'Título', 
            'data_evento': 'Data',
            'hora_evento': 'Hora',
            'descricao': 'Descrição',
            'local': 'Local',
            'prioridade': 'Prioridade',
            'status': 'Status'
        }, inplace=True)
        
        st.dataframe(df_display.sort_values(by='Data', ascending=False), use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🛠️ Edição e Exclusão (U e D)")

        if not df_eventos.empty:
            eventos_atuais = df_eventos['id_evento'].tolist()
            
            def formatar_selecao(id_val):
                titulo = df_eventos[df_eventos['id_evento'] == id_val]['titulo'].iloc[0]
                return f"{titulo} ({id_val[:4]}...)"

            evento_selecionado_id = st.selectbox(
                "Selecione o ID do Evento para Ação:",
                options=eventos_atuais,
                index=0 if eventos_atuais else None,
                format_func=formatar_selecao
            )
        
        if evento_selecionado_id:
            evento_dados = df_eventos[df_eventos['id_evento'] == evento_selecionado_id].iloc[0]

            col_u, col_d = st.columns([3, 1])

            with col_u:
                st.markdown("##### Atualizar Evento Selecionado")
                with st.form("form_update_evento"):
                    novo_titulo = st.text_input("Título", value=evento_dados['titulo'])
                    nova_descricao = st.text_area("Descrição", value=evento_dados['descricao'])

                    col_data_hora, col_local_prioridade = st.columns(2)

                    with col_data_hora:
                        novo_data = st.date_input(
                            "Data", 
                            value=pd.to_datetime(evento_dados['data_evento']).date(),
                            format="DD/MM/YYYY"
                        )
                        novo_hora_str = evento_dados['hora_evento']
                        # 📌 CORREÇÃO: O 'time' aqui é a função construtora
                        novo_hora = st.time_input("Hora", value=time(int(novo_hora_str[:2]), int(novo_hora_str[3:]))) 
                    
                    with col_local_prioridade:
                        novo_local = st.text_input("Local", value=evento_dados['local'])
                        novo_prioridade = st.selectbox("Prioridade", ["Alta", "Média", "Baixa"], index=["Alta", "Média", "Baixa"].index(evento_dados['prioridade']))
                        novo_status = st.selectbox("Status", ['Pendente', 'Concluído', 'Cancelado'], index=['Pendente', 'Concluído', 'Cancelado'].index(evento_dados['status']))

                    update_button = st.form_submit_button("Salvar Atualizações (Update)")

                    if update_button:
                        dados_atualizados = {
                            'id_evento': evento_selecionado_id, 
                            'titulo': novo_titulo,
                            'descricao': nova_descricao,
                            'data_evento': novo_data.strftime('%Y-%m-%d'),
                            'hora_evento': novo_hora.strftime('%H:%M'),
                            'local': novo_local,
                            'prioridade': novo_prioridade,
                            'status': novo_status
                        }
                        if atualizar_evento(sheet, evento_selecionado_id, dados_atualizados):
                            
                            conectar_sheets.clear()
                            
                            st.experimental_rerun()
            
            with col_d:
                st.markdown("##### Excluir Evento")
                st.warning(f"Excluindo: **{evento_dados['titulo']}**")
                
                if st.button("🔴 EXCLUIR EVENTO (Delete)", type="primary"):
                    if deletar_evento(sheet, evento_selecionado_id):
                        
                        conectar_sheets.clear()
                        
                        # Usa o alias 't' para o time.sleep
                        t.sleep(0.5) 
                        
                        st.experimental_rerun()
