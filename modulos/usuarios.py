from datetime import datetime, time
import streamlit as st
import database as db

def renderizar_gestao_usuarios():
    st.markdown("### 👥 Gestão de Contas e Usuários do Sistema")
    st.caption("Controle de acessos, permissões, turnos e exclusão de contas.")

    tab_listar, tab_ajuda = st.tabs(["📋 Usuários Cadastrados", "ℹ️ Como Cadastrar Novo Usuário"])

    # ========================================================
    # ABA 1: CONSULTAR, EDITAR E EXCLUIR
    # ========================================================
    with tab_listar:
        try:
            res = db.supabase.table("colaboradores").select("*").order("nome").execute()
            usuarios = res.data or []
        except Exception as e:
            st.error(f"Erro ao consultar usuários no Supabase: {e}")
            usuarios = []

        if not usuarios:
            st.info("Nenhum usuário cadastrado até o momento.")
        else:
            opcoes_dropdown = ["-- Selecione um Usuário na Lista --"] + [
                f"{u['nome']} ({u.get('cargo', 'Sem Cargo')}) - {u.get('email', 'sem e-mail')}" for u in usuarios
            ]

            escolha = st.selectbox("Escolha o usuário para gerenciar:", opcoes_dropdown)

            if escolha != "-- Selecione um Usuário na Lista --":
                idx = opcoes_dropdown.index(escolha) - 1
                usr = usuarios[idx]
                usr_id = usr["id"]
                usr_email = usr.get("email", "")

                st.markdown("---")

                # Formulário de Edição de Permissões e Horários
                with st.form(f"form_editar_usuario_{usr_id}"):
                    st.markdown(f"#### ✏️ Gerenciando: **{usr.get('nome')}**")

                    col1, col2 = st.columns(2)
                    with col1:
                        e_nome = st.text_input("Nome Completo", value=usr.get("nome", ""))
                        e_email = st.text_input("E-mail de Login", value=usr_email).strip().lower()

                    with col2:
                        perfis_disponiveis = ["Recepção", "Limpeza", "Administrador", "Gerente", "Voluntário"]
                        idx_perfil = perfis_disponiveis.index(usr.get("cargo")) if usr.get("cargo") in perfis_disponiveis else 0
                        e_cargo = st.selectbox("Nível de Acesso (Cargo)", perfis_disponiveis, index=idx_perfil)

                        status_disponiveis = ["Ativo", "Suspenso", "Inativo"]
                        idx_status = status_disponiveis.index(usr.get("status")) if usr.get("status") in status_disponiveis else 0
                        e_status = st.selectbox("Status da Conta", status_disponiveis, index=idx_status)

                    st.markdown("---")
                    st.markdown("##### ⏰ Janela de Acesso Permitido")
                    e_restringir = st.checkbox(
                        "Bloquear login fora do horário estabelecido?", 
                        value=bool(usr.get("restringir_horario", False))
                    )

                    h_ini_val = time(8, 0)
                    if usr.get("horario_inicio"):
                        try:
                            h_ini_val = datetime.strptime(str(usr["horario_inicio"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    h_fim_val = time(17, 0)
                    if usr.get("horario_fim"):
                        try:
                            h_fim_val = datetime.strptime(str(usr["horario_fim"])[:8], "%H:%M:%S").time()
                        except Exception:
                            pass

                    col_h1, col_h2 = st.columns(2)
                    with col_h1:
                        e_h_inicio = st.time_input("Entrada Permitida", value=h_ini_val, step=1800, key=f"usr_ini_{usr_id}")
                    with col_h2:
                        e_h_fim = st.time_input("Saída Permitida", value=h_fim_val, step=1800, key=f"usr_fim_{usr_id}")

                    btn_salvar = st.form_submit_button("💾 Salvar Alterações", use_container_width=True)

                    if btn_salvar:
                        if not e_nome or not e_email:
                            st.error("Nome e E-mail são obrigatórios.")
                        else:
                            try:
                                db.supabase.table("colaboradores").update({
                                    "nome": e_nome,
                                    "email": e_email,
                                    "cargo": e_cargo,
                                    "status": e_status,
                                    "restringir_horario": e_restringir,
                                    "horario_inicio": e_h_inicio.strftime("%H:%M:%S"),
                                    "horario_fim": e_h_fim.strftime("%H:%M:%S")
                                }).eq("id", usr_id).execute()
                                db.notificar_sucesso("Dados do usuário atualizados!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")

                # Redefinição de Senha
                with st.expander("🔑 Redefinição de Senha", expanded=False):
                    st.write(f"Deseja enviar um link para que **{usr.get('nome')}** redefina sua senha?")
                    if st.button("Enviar E-mail de Recuperação de Senha", key=f"btn_recup_{usr_id}"):
                        if usr_email:
                            ok, msg = db.solicitar_recuperacao_senha(usr_email)
                            if ok:
                                st.success(msg)
                            else:
                                st.error(msg)
                        else:
                            st.error("Usuário não possui e-mail cadastrado.")

                # Exclusão Definitiva
                st.markdown("---")
                with st.expander("🗑️ Zona de Perigo: Excluir este Usuário", expanded=False):
                    st.warning(f"Atenção: A remoção de **{usr.get('nome')}** revogará qualquer sessão imediatamente e apagará seus dados de acesso.")
                    confirma_exclusao = st.checkbox("Confirmar exclusão definitiva do usuário", key=f"chk_del_usr_{usr_id}")

                    if st.button("Excluir Usuário Permanentemente", type="primary", use_container_width=True, key=f"btn_del_usr_{usr_id}"):
                        if not confirma_exclusao:
                            st.error("Marque a caixa de confirmação acima para autorizar a exclusão.")
                        else:
                            try:
                                db.supabase.table("colaboradores").delete().eq("id", usr_id).execute()
                                db.notificar_sucesso(f"Usuário {usr.get('nome')} excluído com sucesso!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao excluir do banco de dados: {e}")

    # ========================================================
    # ABA 2: ORIENTAÇÃO PARA NOVOS USUÁRIOS
    # ========================================================
    with tab_ajuda:
        st.info("""
        **Como conceder acesso a um novo colaborador:**
        1. Cadastre os dados e o e-mail dele na aba **📁 Cadastros ➔ Colaboradores**.
        2. Se ele ainda não tiver senha criada no Supabase, ele pode clicar em **'Esqueci Minha Senha'** na tela de login para registrar uma senha pessoal via e-mail, ou você pode cadastrá-lo diretamente no painel **Authentication** do Supabase.
        """)