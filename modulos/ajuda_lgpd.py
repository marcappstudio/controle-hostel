import pandas as pd
import streamlit as st
import database as db
from utils.formatadores import formatar_data_br, extrair_data

def renderizar_ajuda_lgpd(usuario_perfil):
    aba_manual, aba_lgpd, aba_termos = st.tabs([
        "❓ Central de Ajuda & Manual Universal",
        "🛡️ Governança LGPD & Anonimização",
        "📜 Termos de Uso & Política de Privacidade"
    ])

    # =========================================================================
    # ABA 1: AJUDA UNIVERSAL & MANUAL DO PMS
    # =========================================================================
    with aba_manual:
        st.subheader("📖 Manual Operacional e Fluxos de Balcão")
        st.caption("Guia rápido de treinamento para recepcionistas, gerentes e operadores do hostel.")

        with st.expander("🏨 1. Fluxo de Entrada e Reservas (Check-in)", expanded=True):
            st.markdown(
                """
                1. **Localização e Leito:** Acesse `📅 Nova Reserva & Edição`. Selecione o hóspede (ou cadastre-o antes em `👤 Hóspedes`) e a cama desejada. O sistema já identifica se o quarto possui **ar-condicionado** e puxa o preço individual daquele leito.
                2. **Orçamento e Período:** O período calcula automaticamente a entrada (14:00) e a saída (11:00).
                3. **Sinal / Adiantamento:** Escolha se o hóspede paga no check-out, se adianta 50% ou se quita 100% no balcão. O sistema já registra a forma de pagamento e calcula o saldo remanescente.
                4. **Localizador Único:** Toda reserva gera um código único (ex: `HST-A1B2C3`), impresso nos comprovantes e nos links de WhatsApp.
                """
            )

        with st.expander("📋 2. Fechamento de Conta e Saída (Check-out)", expanded=False):
            st.markdown(
                """
                1. **Acesso Direto:** Na tela `📋 Check-out & Histórico` (ou pelo botão rápido do card do Mapa), localize a gaveta do hóspede.
                2. **Extrato Consolidado:** O sistema soma as diárias, adicionais de café/toalha contratados, consumos da loja (PDV) e eventos, deduzindo automaticamente o sinal pago no check-in.
                3. **Quitação Mista:** Se houver saldo a pagar, receba via PIX, Dinheiro ou Cartão.
                4. **Envio e Emissão:** Ao concluir, o leito vai automaticamente para **Limpeza Pendente** e você pode baixar o recibo em PDF ou disparar o comprovante completo via WhatsApp com um clique.
                """
            )

        with st.expander("🛒 3. Loja, Conveniência e Fechamento de Caixa", expanded=False):
            st.markdown(
                """
                1. **Vendas a Hóspedes vs Avulsos:** Você pode lançar vendas para clientes avulsos ou vincular ao hóspede para pagar tudo no check-out.
                2. **Caixa por Turno:** Abra o turno com fundo de troco. Registre **Sangrias** (retiradas) ou **Suprimentos** (reforço) com justificativa.
                3. **Conferência Cega:** No encerramento do turno, conte o dinheiro físico. O sistema audita o valor esperado e registra se houve sobra ou falta de caixa.
                """
            )

        with st.expander("🔧 4. Manutenção Preventiva e Corretiva", expanded=False):
            st.markdown(
                """
                * **Corretiva:** Tomada estragada, vazamento ou ar sem gelar? Abra o chamado vinculando ao quarto ou cama. Se for classificada como **Alta** ou **Crítica**, ela gera aviso imediato na barra lateral.
                * **Preventiva:** Use a aba de rotinas programadas para agendar trocas de filtro de bebedouro (6 meses), limpeza de filtros de ar (3 meses) e dedetização periódica.
                """
            )

    # =========================================================================
    # ABA 2: GOVERNANÇA LGPD & ANONIMIZAÇÃO
    # =========================================================================
    with aba_lgpd:
        st.subheader("🛡️ Gestão de Privacidade e Direito ao Esquecimento")
        st.caption("Em conformidade com a Lei Geral de Proteção de Dados (Lei 13.709/2018), gerencie os consentimentos e atenda às solicitações de desidentificação de dados.")

        try:
            res_h = db.supabase.table("hospedes").select("id, nome, documento, email, telefone, lgpd_consentimento, lgpd_data_consentimento, anonimizado").execute()
            hospedes_lista = res_h.data or []

            tot_cad = len(hospedes_lista)
            tot_consent = len([h for h in hospedes_lista if h.get("lgpd_consentimento") and not h.get("anonimizado")])
            tot_anon = len([h for h in hospedes_lista if h.get("anonimizado")])

            col_lg1, col_lg2, col_lg3 = st.columns(3)
            col_lg1.metric("Hóspedes Cadastrados", tot_cad)
            col_lg2.metric("Consentimentos Ativos", tot_consent)
            col_lg3.metric("Titulares Anonimizados", tot_anon)
            st.markdown("---")

            st.markdown("##### 🗑️ Anonimizar Dados de Titular (Direito ao Esquecimento - Art. 18 da LGPD)")
            st.caption("Remove permanentemente CPF, passaporte, e-mail, telefone e foto do hóspede, mantendo a integridade histórica dos lançamentos contábeis sem quebrar relatórios fiscais.")

            hosp_elegiveis = [h for h in hospedes_lista if not h.get("anonimizado")]
            if not hosp_elegiveis:
                st.info("Nenhum hóspede ativo pendente de anonimização.")
            else:
                opcoes_anon = {f"{h['nome']} (Doc: {h.get('documento') or 'N/D'})": h for h in hosp_elegiveis}
                h_anon_sel = st.selectbox("Selecione o Titular que Solicitou a Exclusão dos Dados Pessoais:", list(opcoes_anon.keys()))
                h_alvo = opcoes_anon[h_anon_sel]

                confirmar_exclusao = st.checkbox(f"Estou ciente de que a remoção dos dados de '{h_alvo['nome']}' é irreversível.")
                if st.button("🚨 Anonimizar Dados Pessoais", type="primary"):
                    if not confirmar_exclusao:
                        st.error("Marque a confirmação para proceder com a anonimização.")
                    else:
                        agora_str = datetime.now().strftime("%d/%m/%Y às %H:%M")
                        db.supabase.table("hospedes").update({
                            "nome": f"Titular Anonimizado (LGPD #{h_alvo['id']})",
                            "cpf": None,
                            "passaporte_rne": None,
                            "documento": "ANONIMIZADO",
                            "email": None,
                            "telefone": None,
                            "foto": None,
                            "observacoes": f"Dados pessoais removidos a pedido do titular em conformidade com o Art. 18 da LGPD em {agora_str}.",
                            "anonimizado": True,
                            "lgpd_consentimento": False
                        }).eq("id", h_alvo["id"]).execute()
                        db.notificar_sucesso("Titular anonimizado com sucesso!")
                        st.rerun()

            st.markdown("---")
            st.markdown("##### 📜 Auditoria de Consentimentos Registrados")
            df_auditoria = pd.DataFrame([{
                "ID": h["id"],
                "Titular": h["nome"],
                "Documento": h.get("documento"),
                "Consentimento": "Ativo" if h.get("lgpd_consentimento") else "Revogado / N/A",
                "Data/Hora do Aceite": formatar_data_br(h.get("lgpd_data_consentimento")),
                "Situação Cadastral": "Anonimizado" if h.get("anonimizado") else "Regular"
            } for h in hospedes_lista])
            st.dataframe(df_auditoria, use_container_width=True)

        except Exception as e:
            st.error(f"Erro ao carregar governança LGPD: {e}")

    # =========================================================================
    # ABA 3: TERMOS DE USO & POLÍTICA DE PRIVACIDADE
    # =========================================================================
    with aba_termos:
        st.subheader("📜 Termos de Serviço e Política de Privacidade do Hostel")
        st.caption("Texto jurídico padrão para ciência do hóspede na ficha de check-in:")

        st.markdown(
            """
            ### 1. Coleta e Finalidade dos Dados Pessoais
            Em estrito cumprimento ao **Decreto Federal nº 7.381/2010** (Regulamento da Lei Geral do Turismo) e à **Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 - LGPD)**, 
            o estabelecimento coleta dados de identificação pessoal (Nome completo, CPF/Passaporte, E-mail, Telefone e Foto) exclusivamente para:
            * Identificação de segurança no controle de acesso aos quartos e áreas comuns;
            * Cumprimento de obrigação legal perante o Ministério do Turismo (FNRH - Ficha Nacional de Registro de Hóspedes);
            * Emissão de documentos fiscais municipais (NFS-e / RPS) e faturamento de diárias e consumo no hostel.

            ---

            ### 2. Compartilhamento e Sigilo
            Os dados coletados **jamais serão comercializados ou cedidos a terceiros** para fins publicitários. O compartilhamento ocorre única e exclusivamente com:
            * Órgãos públicos municipais, estaduais e federais por força de obrigação legal ou ordem judicial;
            * Sistemas de mensageria fiscal contratados para emissão de Nota Fiscal de Serviços Eletrônica.

            ---

            ### 3. Prazo de Armazenamento e Direito do Titular
            Os dados cadastrais serão mantidos pelos prazos exigidos pela legislação tributária e de turismo. 
            A qualquer momento, o hóspede titular poderá solicitar, perante a administração:
            * A confirmação da existência de tratamento de seus dados;
            * A correção de dados incompletos ou inexatos;
            * A anonimização ou bloqueio de dados desnecessários, ressalvadas as obrigações fiscais e regulatórias do estabelecimento.
            """,
            unsafe_allow_html=True
        )