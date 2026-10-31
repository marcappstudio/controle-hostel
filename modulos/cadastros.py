import re
from datetime import datetime, time
import streamlit as st
import database as db

# ==========================================
# 1. FUNÇÕES AUXILIARES DE VALIDAÇÃO
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
# 2. GESTÃO DE HÓSPEDES
# ==========================================
def renderizar_hospedes():
    aba_cad, aba_cons = st.tabs(["➕ Cadastrar Hóspede", "📋 Consultar / Editar Hóspedes"])

    with aba_cad:
        with st.form("form_cad_hospede", clear_on_submit=True):
            nome = st.text_input("Nome Completo *").strip()
            nacionalidade = st.selectbox("Nacionalidade", ["Brasileira", "Estrangeira"])
            
            cpf = ""
            passaporte = ""
            if nacionalidade == "Brasileira":
                cpf = st.text_input("CPF *")
            else:
                passaporte = st.text_input("Passaporte / Documento Estrangeiro *")

            col1, col2 = st.columns(2)
            with col1:
                email = st.text_input("E-mail").strip().lower()
                telefone = st.text_input("WhatsApp / Telefone").strip()
            with col2:
                cidade = st.text_input("Cidade de Origem").strip()
                estado = st.text_input("Estado / País").strip()

            obs = st.text_area("Observações Adicionais (Alergias, restrições, etc.)")

            if st.form_submit_button("Salvar Hóspede", use_container_width=True):
                if not nome:
                    st.error("O nome do hóspede é obrigatório.")
                elif nacionalidade == "Brasileira" and not validar_cpf(cpf):
                    st.error("CPF inválido. Verifique os dígitos.")
                elif nacionalidade != "Brasileira" and not passaporte:
                    st.error("O número do passaporte ou documento é obrigatório.")
                else:
                    cpf_limpo = re.sub(r'\D', '', cpf) if cpf else None
                    try:
                        db.supabase.table("hospedes").insert({
                            "nome": nome,
                            "nacionalidade": nacionalidade,
                            "cpf": cpf_limpo,
                            "passaporte": passaporte if passaporte else None,
                            "email": email if email else None,
                            "telefone": telefone if telefone else None,
                            "cidade": cidade if cidade else None,
                            "estado": estado if estado else None,
                            "observacoes": obs if obs else None
                        }).execute()
                        db.notificar_sucesso("Hóspede cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar hóspede: {e}")

    with aba_cons:
        try:
            res = db.supabase.table("hospedes").select("*").order("nome").execute()
            hospedes = res.data or []
        except Exception as e:
            st.error(f"Erro ao carregar hóspedes: {e}")
            hospedes = []

        if not hospedes:
            st.info("Nenhum hóspede cadastrado até o momento.")
        else:
            opcoes_hospedes = ["-- Selecione um Hóspede para Editar --"] + [
                f"{h['nome']} (Doc: {h.get('cpf') or h.get('passaporte') or 'S/N'})" for h in hospedes
            ]
            escolha = st.selectbox("Buscar Hóspede:", opcoes_hospedes)

            if escolha != "-- Selecione um Hóspede para Editar --":
                idx = opcoes_hospedes.index(escolha) - 1
                h_sel = hospedes[idx]
                h_id = h_sel["id"]

                with st.form(f"form_edit_hosp_{h_id}"):
                    st.markdown(f"#### ✏️ Editando Hóspede: **{h_sel.get('nome')}**")
                    e_nome = st.text_input("Nome Completo", value=h_sel.get("nome", ""))
                    
                    col_e1, col_e2 = st.columns(2)
                    with col_e1:
                        e_email = st.text_input("E-mail", value=h_sel.get("email") or "")
                        e_tel = st.text_input("Telefone", value=h_sel.get("telefone") or "")
                    with col_e2:
                        e_cidade = st.text_input("Cidade", value=h_sel.get("cidade") or "")
                        e_estado = st.text_input("Estado / País", value=h_sel.get("estado") or "")

                    e_obs = st.text_area("Observações", value=h_sel.get("observacoes") or "")

                    if st.form_submit_button("Atualizar Cadastro do Hóspede", use_container_width=True):
                        try:
                            db.supabase.table("hospedes").update({
                                "nome": e_nome,
                                "email": e_email if e_email else None,
                                "telefone": e_tel if e_tel else None,
                                "cidade": e_cidade if e_cidade else None,
                                "estado": e_estado if e_estado else None,
                                "observacoes": e_obs if e_obs else None
                            }).eq("id", h_id).execute()
                            db.notificar_sucesso("Cadastro atualizado com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao atualizar: {e}")


# ==========================================
# 3. GESTÃO DE QUARTOS E CAMAS
# ==========================================
def renderizar_quartos():
    aba_cad, aba_cons = st.tabs(["➕ Cadastrar Quarto / Cama", "📋 Estrutura Atual"])

    with aba_cad:
        with st.form("form_cad_quarto", clear_on_submit=True):
            nome_quarto = st.text_input("Identificação do Quarto (ex: Quarto 101, Dormitório Misto) *").strip()
            tipo_quarto = st.selectbox("Tipo de Acomodação", ["Dormitório Compartilhado", "Quarto Privativo", "Suíte"])
            qtd_camas = st.number_input("Quantidade de Camas / Vagas", min_value=1, max_value=30, value=1, step=1)
            valor_padrao = st.number_input("Preço Base da Diária (R$)", min_value=0.0, value=70.0, step=5.0)

            if st.form_submit_button("Salvar Quarto", use_container_width=True):
                if not nome_quarto:
                    st.error("Informe a identificação do quarto.")
                else:
                    try:
                        db.supabase.table("quartos").insert({
                            "nome": nome_quarto,
                            "tipo": tipo_quarto,
                            "quantidade_camas": int(qtd_camas),
                            "valor_diaria": float(valor_padrao),
                            "status": "Disponível"
                        }).execute()
                        db.notificar_sucesso("Quarto cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar acomodação: {e}")

    with aba_cons:
        try:
            res = db.supabase.table("quartos").select("*").order("nome").execute()
            quartos = res.data or []
        except Exception as e:
            st.error(f"Erro ao buscar quartos: {e}")
            quartos = []

        if not quartos:
            st.info("Nenhum quarto cadastrado.")
        else:
            for q in quartos:
                with st.expander(f"🚪 {q.get('nome')} — {q.get('tipo', 'Geral')} ({q.get('quantidade_camas', 1)} camas)"):
                    st.write(f"**Valor base da diária:** R$ {q.get('valor_diaria', 0.0):.2f}")
                    st.write(f"**Situação:** {q.get('status', 'Disponível')}")


# ==========================================
# 4. GESTÃO DE COLABORADORES DA EQUIPE
# ==========================================
def renderizar_colaboradores():
    aba_cad_colab, aba_cons_colab = st.tabs(["➕ Cadastrar Colaborador", "📋 Consultar, Editar ou Excluir"])

    # ----------------------------------------------------
    # ABA A: CADASTRAR COLABORADOR
    # ----------------------------------------------------
    with aba_cad_colab:
        with st.form("form_cad_colab", clear_on_submit=True):
            c_nome = st.text_input("Nome Completo *").strip()
            c_email = st.text_input("E-mail de Acesso ao Sistema *").strip().lower()
            c_nac = st.selectbox("Nacionalidade", ["Brasileira", "Estrangeira"])
            c_cpf = st.text_input("CPF") if c_nac == "Brasileira" else ""
            c_pass = st.text_input("Passaporte / RNE") if c_nac != "Brasileira" else ""
            c_cargo = st.selectbox("Função / Cargo", ["Limpeza", "Recepção", "Voluntário", "Gerente", "Manutenção", "Outros"])
            c_tel = st.text_input("Telefone de Contato").strip()

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
    # ABA B: CONSULTAR, EDITAR OU EXCLUIR (DROPDOWN)
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

                    # Recupera os horários já salvos no banco de dados
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