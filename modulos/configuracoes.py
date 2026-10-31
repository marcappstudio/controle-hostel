import base64
import json
import streamlit as st
import database as db

def obter_dados_hostel():
    try:
        res = db.supabase.table("configuracoes").select("valor").eq("chave", "dados_estabelecimento").execute()
        if res.data and len(res.data) > 0 and res.data[0].get("valor"):
            return json.loads(res.data[0]["valor"])
    except Exception:
        pass
    return {
        "nome_fantasia": "Hostel Central",
        "razao_social": "Hostel Gestão e Hospitalidade Ltda",
        "cnpj": "",
        "inscricao_municipal": "",
        "endereco": "",
        "cidade_uf": "Porto Alegre - RS",
        "telefone": "",
        "email": ""
    }

def renderizar_configuracoes(usuario_perfil):
    st.caption("Gerenciamento central de dados institucionais, identidade visual, tema e valores operacionais.")

    aba_dados, aba_tema, aba_precos, aba_horarios = st.tabs([
        "🏢 Dados do Estabelecimento & Logo",
        "🌓 Aparência & Temas (Claro / Escuro)",
        "💰 Preços Padrão de Adicionais",
        "⏱️ Horários Operacionais"
    ])

    # =========================================================================
    # ABA 1: DADOS INSTITUCIONAIS & LOGOTIPO
    # =========================================================================
    with aba_dados:
        st.subheader("🏢 Dados Oficiais do Hostel")
        st.caption("Estas informações serão exibidas nos recibos de check-out, cabeçalhos de PDF e mensagens.")

        dados_atuais = obter_dados_hostel()

        with st.form("form_dados_hostel"):
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                nome_fantasia = st.text_input("Nome Fantasia:", value=dados_atuais.get("nome_fantasia", ""))
                razao_social = st.text_input("Razão Social:", value=dados_atuais.get("razao_social", ""))
                cnpj = st.text_input("CNPJ:", value=dados_atuais.get("cnpj", ""))
                insc_mun = st.text_input("Inscrição Municipal:", value=dados_atuais.get("inscricao_municipal", ""))
            with col_d2:
                telefone = st.text_input("Telefone / WhatsApp Comercial:", value=dados_atuais.get("telefone", ""))
                email_comercial = st.text_input("E-mail de Contato:", value=dados_atuais.get("email", ""))
                endereco = st.text_input("Endereço Completo (Rua, Número, Bairro):", value=dados_atuais.get("endereco", ""))
                cidade_uf = st.text_input("Cidade / UF:", value=dados_atuais.get("cidade_uf", "Porto Alegre - RS"))

            if st.form_submit_button("Salvar Dados Oficiais", type="primary", use_container_width=True):
                novos_dados = {
                    "nome_fantasia": nome_fantasia, "razao_social": razao_social,
                    "cnpj": cnpj, "inscricao_municipal": insc_mun,
                    "telefone": telefone, "email": email_comercial,
                    "endereco": endereco, "cidade_uf": cidade_uf
                }
                db.supabase.table("configuracoes").upsert({
                    "chave": "dados_estabelecimento",
                    "valor": json.dumps(novos_dados)
                }).execute()
                st.success("Dados da empresa atualizados com sucesso!")
                st.rerun()

        st.markdown("---")
        st.subheader("🖼️ Identidade Visual (Logotipo)")
        col_img1, col_img2 = st.columns([1, 2])
        
        logo_atual = db.obter_logo()
        with col_img1:
            if logo_atual:
                st.image(logo_atual, caption="Logotipo Ativo", width=200)
            else:
                st.info("Nenhum logotipo cadastrado.")

        with col_img2:
            arquivo_img = st.file_uploader("Carregar novo logotipo (PNG, JPG):", type=["png", "jpg", "jpeg"], key="cfg_upload_logo")
            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                if st.button("Aplicar Logotipo", type="primary", use_container_width=True):
                    if arquivo_img:
                        data_uri = f"data:{arquivo_img.type or 'image/png'};base64,{base64.b64encode(arquivo_img.read()).decode('utf-8')}"
                        db.supabase.table("configuracoes").upsert({"chave": "logo_base64", "valor": data_uri}).execute()
                        st.success("Logotipo atualizado!")
                        st.rerun()
                    else:
                        st.error("Selecione um arquivo de imagem.")
            with c_btn2:
                if st.button("Remover Logotipo", use_container_width=True):
                    db.supabase.table("configuracoes").delete().eq("chave", "logo_base64").execute()
                    st.success("Logotipo removido!")
                    st.rerun()

    # =========================================================================
    # ABA 2: TEMAS E APARÊNCIA
    # =========================================================================
    with aba_tema:
        st.subheader("🌓 Esquema Visual da Interface")
        st.caption("Alterne entre o tema claro para o dia e o modo escuro de alto contraste para turnos noturnos.")

        tema_atual = st.session_state.get("tema_sistema", "Claro")

        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown(
                """
                <div style='background-color: #ffffff; border: 2px solid #cbd5e1; border-radius: 8px; padding: 16px; color: #0f172a;'>
                    <h4 style='margin: 0; color: #1e293b;'>☀️ Modo Claro (Clean Slate)</h4>
                    <p style='font-size: 0.9rem; color: #64748b;'>Visual clássico com fundo branco e tons neutros de cinza e azul marinho, ideal para turnos diurnos.</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Ativar Tema Claro", use_container_width=True, key="btn_tema_claro"):
                st.session_state["tema_sistema"] = "Claro"
                db.supabase.table("configuracoes").upsert({"chave": "tema_sistema", "valor": "Claro"}).execute()
                st.rerun()

        with col_t2:
            st.markdown(
                """
                <div style='background-color: #0f172a; border: 2px solid #334155; border-radius: 8px; padding: 16px; color: #f8fafc;'>
                    <h4 style='margin: 0; color: #60a5fa;'>🌙 Modo Escuro (Dark Charcoal)</h4>
                    <p style='font-size: 0.9rem; color: #94a3b8;'>Fundo grafite profundo com cartões escuros e textos de alta legibilidade, descansando a visão na recepção noturna.</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            if st.button("Ativar Tema Escuro", use_container_width=True, key="btn_tema_escuro"):
                st.session_state["tema_sistema"] = "Escuro"
                db.supabase.table("configuracoes").upsert({"chave": "tema_sistema", "valor": "Escuro"}).execute()
                st.rerun()

    # =========================================================================
    # ABA 3: PREÇOS PADRÃO & ADICIONAIS
    # =========================================================================
    with aba_precos:
        st.subheader("💰 Parâmetros de Preços Base e Serviços Extras")
        st.caption("Valores sugeridos quando o quarto ou cama não possuir precificação personalizada:")

        precos_salvos = db.obter_precos_padrao()

        with st.form("form_precos_adicionais"):
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                nova_diaria_fallback = c_p1.number_input(
                    "Diária Base Global de Fallback (R$):",
                    min_value=0.0,
                    value=float(precos_salvos.get("diaria", 80.0)),
                    step=5.0,
                    format="%.2f",
                    help="Utilizada se o quarto ou cama não tiver preço específico configurado."
                )
            with c_p2:
                novo_cafe = c_p2.number_input(
                    "Café da Manhã Unitário (R$):",
                    min_value=0.0,
                    value=float(precos_salvos.get("cafe", 25.0)),
                    step=1.0,
                    format="%.2f"
                )
            with c_p3:
                nova_toalha = c_p3.number_input(
                    "Kit de Toalha de Banho (R$):",
                    min_value=0.0,
                    value=float(precos_salvos.get("toalha", 10.0)),
                    step=1.0,
                    format="%.2f"
                )

            if st.form_submit_button("Salvar Tabela de Serviços Extras", type="primary", use_container_width=True):
                novos_precos_dict = {"diaria": nova_diaria_fallback, "cafe": novo_cafe, "toalha": nova_toalha}
                db.supabase.table("configuracoes").upsert({"chave": "precos_padrao", "valor": json.dumps(novos_precos_dict)}).execute()
                st.success("Valores atualizados com sucesso!")
                st.rerun()

    # =========================================================================
    # ABA 4: HORÁRIOS OPERACIONAIS
    # =========================================================================
    with aba_horarios:
        st.subheader("⏱️ Padrões de Horário de Balcão")
        
        cfg_horarios = {"checkin": "14:00", "checkout": "11:00"}
        res_h = db.supabase.table("configuracoes").select("valor").eq("chave", "horarios_operacionais").execute()
        if res_h.data and len(res_h.data) > 0 and res_h.data[0].get("valor"):
            try:
                cfg_horarios = json.loads(res_h.data[0]["valor"])
            except Exception:
                pass

        with st.form("form_horarios_hostel"):
            c_h1, c_h2 = st.columns(2)
            with c_h1:
                h_in = st.text_input("Horário Oficial de Check-in:", value=cfg_horarios.get("checkin", "14:00"))
            with c_h2:
                h_out = st.text_input("Horário Limite de Check-out:", value=cfg_horarios.get("checkout", "11:00"))

            if st.form_submit_button("Atualizar Horários Operacionais", use_container_width=True):
                db.supabase.table("configuracoes").upsert({
                    "chave": "horarios_operacionais",
                    "valor": json.dumps({"checkin": h_in, "checkout": h_out})
                }).execute()
                st.success("Horários atualizados!")
                st.rerun()