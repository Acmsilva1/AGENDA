import streamlit as st
import gspread
import pandas as pd
import uuid
from datetime import date, time

# --- CONFIGURAÇÕES E CREDENCIAIS (Governança) ---

# ID da Planilha que você compartilhou
PLANILHA_ID = "1S54b0QtWYaCAgrDNpdQM7ZG5f_KbYXpDztK5TSOn2vU"
ABA_NOME = "AGENDA"
ARQUIVO_CREDENCIAIS = "credentials.json" # Mantenha este arquivo fora do GitHub (.gitignore)

@st.cache_resource
def conectar_sheets():
    """Tenta conectar ao Google Sheets usando a Service Account."""
    try:
        # A Service Account é a melhor prática para backend/scripts.
        gc = gspread.service_account(filename=ARQUIVO_CREDENCIAIS)
        
        # Abre a planilha pela ID e a aba pelo nome
        spreadsheet = gc.open_by_key(PLANILHA_ID)
        sheet = spreadsheet.worksheet(ABA_NOME)
        
        return sheet
    except FileNotFoundError:
        st.error(f"🚨 Arquivo de credenciais '{ARQUIVO_CREDENCIAIS}' não encontrado. O sistema de agendamento não será iniciado sem a identidade.")
    except Exception as e:
        st.error(f"🚨 Erro ao conectar ao Sheets. Verifique a ID, nome da ABA ou o compartilhamento. Erro: {e}")
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
    
    # Lista de valores na ordem exata das colunas do Sheets
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
        # 1. Encontra a linha pelo 'id_evento' (coluna 1)
        cell = sheet.find(id_evento)
        linha_index = cell.row # A linha que será atualizada (ex: 2, 3, 4...)

        # 2. Prepara os novos valores na ordem correta das colunas
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

        # 3. Atualiza todas as células daquela linha de uma vez (a partir da coluna 'A')
        sheet.update(f'A{linha_index}', [valores_atualizados])
        st.success(f"🔄 Evento {id_evento} atualizado com sucesso. Foco nos detalhes.")
        return True

    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento}' não encontrado. Algum erro na matriz.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao atualizar o evento: {e}")
        return False

# D (Delete) - Remove um evento
def deletar_evento(sheet, id_evento):
    """Busca a linha pelo ID e a deleta."""
    try:
        # 1. Encontra a linha pelo 'id_evento'
        cell = sheet.find(id_evento)
        linha_index = cell.row

        # 2. Deleta a linha inteira
        sheet.delete_rows(linha_index)
        st.success(f"🗑️ Evento {id_evento} deletado. Férias merecidas para esse compromisso.")
        return True
    except gspread.exceptions.CellNotFound:
        st.error(f"🚫 ID de Evento '{id_evento}' não encontrado. Impossível apagar algo que não existe.")
        return False
    except Exception as e:
        st.error(f"🚫 Erro ao deletar o evento: {e}")
        return False


# --- INTERFACE STREAMLIT (UI) ---

st.set_page_config(layout="wide")
st.title("🗓️ Agenda Sarcástica v1.0 (Python/Sheets)")

sheet = conectar_sheets()

# Se a conexão falhar, o Streamlit para aqui
if sheet is None:
    st.stop()


# Organização da UI em abas para melhor UX
tab_criar, tab_visualizar_editar = st.tabs(["➕ Criar Evento", "👁️ Visualizar e Gerenciar"])


# === ABA CRIAR ===
with tab_criar:
    st.header("Novo Evento: O Início da Sua Jornada")
    
    with st.form("form_novo_evento", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            titulo = st.text_input("Título Principal (Exato!)", max_chars=100)
            local = st.text_input("Local ou Link da Reunião:")
            data = st.date_input("Data:", date.today())
        
        with col2:
            prioridade = st.selectbox("Prioridade:", ["Média", "Alta", "Baixa"])
            hora = st.time_input("Hora:", time(9, 0))
            status_inicial = st.selectbox("Status Inicial:", ['Pendente', 'Rascunho'])
        
        descricao = st.text_area("Descrição Detalhada:")
        
        submit_button = st.form_submit_button("Salvar Novo Evento")

        if submit_button:
            if titulo and data: 
                dados_para_sheet = {
                    'id_evento': str(uuid.uuid4()), # ID único para governança
                    'titulo': titulo,
                    'descricao': descricao,
                    'data_evento': data.strftime('%Y-%m-%d'),
                    'hora_evento': hora.strftime('%H:%M'),
                    'local': local,
                    'prioridade': prioridade,
                    'status': status_inicial
                }
                adicionar_evento(sheet, dados_para_sheet)
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
        # Exibe os dados de forma editável, mas apenas para referência
        st.dataframe(df_eventos.sort_values(by='data_evento', ascending=False), use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🛠️ Edição e Exclusão (U e D)")

        # Permite selecionar o evento a ser editado/deletado
        eventos_atuais = df_eventos['id_evento'].tolist()
        evento_selecionado_id = st.selectbox(
            "Selecione o ID do Evento para Ação:",
            options=eventos_atuais,
            index=0 if eventos_atuais else None,
            format_func=lambda x: f"{df_eventos[df_eventos['id_evento'] == x]['titulo'].iloc[0]} ({x[:4]}...)"
        )
        
        if evento_selecionado_id:
            # Pega a linha completa do evento selecionado
            evento_dados = df_eventos[df_eventos['id_evento'] == evento_selecionado_id].iloc[0]

            col_u, col_d = st.columns([3, 1])

            with col_u:
                st.markdown("##### Atualizar Evento Selecionado")
                with st.form("form_update_evento"):
                    # Pré-popula o formulário com os dados atuais do evento
                    novo_titulo = st.text_input("Título", value=evento_dados['titulo'])
                    nova_descricao = st.text_area("Descrição", value=evento_dados['descricao'])

                    col_data_hora, col_local_prioridade = st.columns(2)

                    with col_data_hora:
                        novo_data = st.date_input("Data", value=pd.to_datetime(evento_dados['data_evento']).date())
                        novo_hora_str = evento_dados['hora_evento']
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
                            st.experimental_rerun() # Recarrega a tela para mostrar a mudança
            
            with col_d:
                st.markdown("##### Excluir Evento")
                st.write(f"Você tem certeza que quer excluir **{evento_dados['titulo']}**?")
                
                # Botão de exclusão separado
                if st.button("🔴 EXCLUIR EVENTO (Delete)", type="primary"):
                    if deletar_evento(sheet, evento_selecionado_id):
                        st.experimental_rerun()
