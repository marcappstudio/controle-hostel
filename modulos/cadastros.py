import re
from datetime import datetime, time
import streamlit as st
import database as db

# ==========================================
# FUNÇÕES AUXILIARES DE VALIDAÇÃO
# ==========================================
def validar_cpf(cpf: str) -> bool:
    """Valida o formato e os dígitos verificadores do CPF."""
    if not cpf:
        return False
    cpf_limpo = re.sub(r'\D', '', str(cpf))
    if len(cpf_limpo) != 11 or cpf_limpo == cpf_limpo[0] * 11:
        return False

    # Primeiro dígito verificador
    soma = sum(int(cpf_limpo[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    if resto != int(cpf_limpo[9]):
        return False

    # Segundo dígito verificador
    soma = sum(int(cpf_limpo[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    if resto == 10:
        resto = 0
    return resto == int(cpf_limpo[10])


# ==========================================
# MÓDULO DE GESTÃO DE COLABORADORES
# ==========================================
def renderizar_colaboradores():
    aba_cad_colab, aba_cons_colab = st.tabs(["➕ Cadastrar Colaborador", "📋 Consultar, Editar ou Excluir"])

    # ----------------------------------------------------
    # ABA 1: NOVO CADASTRO
    # ----------------------------------------------------
    with aba_cad_colab:
        with st.form("form_cad_colab", clear_on_submit=True):
            c_nome = st.text_input("Nome Completo *")
            c_email = st.text_input("E-mail de Acesso ao Sistema *").strip().lower()
            c_nac = st.selectbox("Nacionalidade", ["Brasileira", "Estrangeira"])
            c_cpf = st.text_input("CPF") if c_nac == "Brasileira" else ""
            c_pass = st.text_input("Passaporte / RNE") if c_nac != "Brasileira" else ""
            c_cargo = st.selectbox("Função / Cargo", ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"])
            c_tel = st.text_input("Telefone de Contato")

            st.markdown("---")
            st.markdown("##### ⏰ Janela de Acesso Permitido")
            c_restringir = st.checkbox("Restringir horário de login deste colaborador?", value=False)
            
            col_h1, col_h2 = st.columns(2)
            with col_h1:
                c_h_inicio = st.time_input("Horário de Entrada Permitida", value=time(8, 0), step=1800)
            with col_h2:
                c_h_fim = st.time_input("Horário de Saída Permitida", value=time(17, 0), step=1800)

            if st.form_submit_button("Salvar Colaborador", use_container_width=True):
                if not c_nome:
                    st.error("O nome do colaborador é obrigatório.")
                elif not c_email:
                    st.error("O e-mail de acesso ao sistema é obrigatório.")
                elif c_nac == "Brasileira" and not validar_cpf(c_cpf):
                    st.error("CPF inválido.")
                else:
                    cpf_limpo = re.sub(r'\D', '', c_cpf) if c_cpf else None
                    try:
                        db.supabase.table("colaboradores").insert({
                            "nome": c_nome,
                            "email": c_email,
                            "nacionalidade": c_nac,
                            "cpf": cpf_limpo,
                            "passaporte_rne": c_pass if c_pass else None,
                            "cargo": c_cargo,
                            "telefone": c_tel,
                            "status": "Ativo",
                            "restringir_horario": c_restringir,
                            "horario_inicio": c_h_inicio.strftime("%H:%M:%S"),
                            "horario_fim": c_h_fim.strftime("%H:%M:%S")
                        }).execute()
                        db.notificar_sucesso("Colaborador cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco de dados: {e}")

    # ----------------------------------------------------
    # ABA 2: CONSULTAR, EDITAR OU EXCLUIR
    # ----------------------------------------------------
    with aba_cons_colab:
        try:
            res_col = db.supabase.table("colaboradores").select("*").order("nome").execute()
            lista_col = res_col.data or []
        except Exception as e:
            st.error(f"Erro ao buscar colaboradores: {e}")
            lista_col = []

        if not lista_col:
            st.info("Nenhum colaborador cadastrado.")
        else:
            opcoes_dropdown = ["-- Selecione um Colaborador na Lista --"] + [
                f"{c['nome']} ({c.get('cargo', 'Geral')}) - {c.get('email', 'sem e-mail')}" for c in lista_col
            ]
            
            escolha = st.selectbox("Escolha o colaborador para gerenciar:", opcoes_dropdown)

            if escolha != "-- Selecione um Colaborador na Lista --":
                idx_selecionado = opcoes_dropdown.index(escolha) - 1
                colab = lista_col[idx_selecionado]
                colab_id = colab["id"]

                st.markdown("---")
                
                # Formulário de Edição
                with st.form(f"form_editar_colab_{colab_id}"):
                    st.markdown(f"#### ✏️ Editando: **{colab.get('nome')}**")
                    
                    e_nome = st.text_input("Nome Completo", value=colab.get("nome", ""))
                    e_email = st.text_input("E-mail de Acesso", value=colab.get("email", "")).strip().lower()
                    
                    cargos_opcoes = ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"]
                    idx_cargo = cargos_opcoes.index(colab.get("cargo")) if colab.get("cargo") in cargos_opcoes else 0
                    e_cargo = st.selectbox("Função / Cargo", cargos_opcoes, index=idx_cargo)
                    
                    e_tel = st.text_input("Telefone / WhatsApp", value=colab.get("telefone", ""))
                    
                    status_opcoes = ["Ativo", "Inativo"]
                    idx_status = 0 if colab.get("status") == "Ativo" else 1
                    e_status = st.selectbox("Situação", status_opcoes, index=idx_status)

                    st.markdown("##### ⏰ Janela de Acesso Permitido")
                    e_restringir = st.checkbox(
                        "Restringir horário de login deste colaborador?", 
                        value=bool(colab.get("restringir_horario", False))
                    )

                    # Recupera os horários já salvos no banco
                    h_ini_val = time(8, 0)
                    if colab.get("horario_inicio"):
                        try:
                            h_ini_val = datetime.strptime(str(colab["horario_inicio"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    h_fim_val = time(17, 0)
                    if colab.get("horario_fim"):
                        try:
                            h_fim_val = datetime.strptime(str(colab["horario_fim"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    col_eh1, col_eh2 = st.columns(2)
                    with col_eh1:
                        e_h_inicio = st.time_input("Entrada Permitida", value=h_ini_val, step=1800, key=f"ini_{colab_id}")
                    with col_eh2:
                        e_h_fim = st.time_input("Saída Permitida", value=h_fim_val, step=1800, key=f"fim_{colab_id}")

                    btn_salvar_edicao = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)

                    if btn_salvar_edicao:
                        if not e_nome or not e_email:
                            st.error("Nome e E-mail são obrigatórios.")
                        else:
                            try:
                                db.supabase.table("colaboradores").update({
                                    "nome": e_nome,
                                    "email": e_email,
                                    "cargo": e_cargo,
                                    "telefone": e_tel,
                                    "status": e_status,
                                    "restringir_horario": e_restringir,
                                    "horario_inicio": e_h_inicio.strftime("%H:%M:%S"),
                                    "horario_fim": e_h_fim.strftime("%H:%M:%S")
                                }).eq("id", colab_id).execute()
                                db.notificar_sucesso("Colaborador atualizado com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao atualizar colaborador: {e}")

                # Área de Exclusão Segura
                st.markdown("---")
                with st.expander("🗑️ Zona de Perigo: Excluir este Colaborador", expanded=False):
                    st.warning(f"Tem certeza de que deseja remover permanentemente o registro de **{colab.get('nome')}**?")
                    confirma_exclusao = st.checkbox("Sim, confirmo a exclusão definitiva", key=f"chk_del_{colab_id}")
                    
                    if st.button("Excluir Colaborador Permanentemente", type="primary", use_container_width=True, key=f"btn_del_{colab_id}"):
                        if not confirma_exclusao:
                            st.error("Marque a caixa de confirmação acima para autorizar a exclusão.")
                        else:
                            try:
                                db.supabase.table("colaboradores").delete().eq("id", colab_id).execute()
                                db.notificar_sucesso(f"Colaborador {colab.get('nome')} excluído com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir do banco de dados: {e}")