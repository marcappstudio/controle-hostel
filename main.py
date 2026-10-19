import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega as variáveis do arquivo .env
load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

if not url or not key:
    print("Erro: As credenciais do Supabase não foram encontradas no arquivo .env!")
    exit()

supabase: Client = create_client(url, key)

def listar_quartos():
    response = supabase.table("quartos").select("*").execute()
    print("\n--- Lista de Quartos ---")
    if not response.data:
        print("Nenhum quarto cadastrado ainda.")
        return
    for q in response.data:
        status = "Disponível" if q['disponivel'] else "Ocupado"
        print(f"ID: {q['id']} | Quarto {q['numero']} ({q['tipo']}) - R$ {q['preco_diaria']}/dia [{status}]")

def cadastrar_quarto():
    print("\n--- Cadastrar Novo Quarto ---")
    numero = int(input("Número do quarto: "))
    tipo = input("Tipo (ex: Compartilhado 6 leitos, Privativo): ")
    capacidade = int(input("Capacidade de pessoas: "))
    preco = float(input("Preço da diária (R$): "))

    data = {
        "numero": numero,
        "tipo": tipo,
        "capacidade": capacidade,
        "preco_diaria": preco,
        "disponivel": True
    }
    supabase.table("quartos").insert(data).execute()
    print("Quarto cadastrado com sucesso no Supabase!")

def cadastrar_hospede():
    print("\n--- Cadastrar Hóspede ---")
    nome = input("Nome completo: ")
    documento = input("Documento (CPF/RG/Passaporte): ")
    telefone = input("Telefone: ")

    data = {
        "nome": nome,
        "documento": documento,
        "telefone": telefone
    }
    supabase.table("hospedes").insert(data).execute()
    print("Hóspede cadastrado com sucesso!")

def criar_reserva():
    print("\n--- Nova Reserva ---")
    documento = input("Digite o documento do hóspede: ")
    
    # Busca o hóspede
    h_resp = supabase.table("hospedes").select("*").eq("documento", documento).execute()
    if not h_resp.data:
        print("Hóspede não encontrado. Cadastre o hóspede primeiro.")
        return
    hospede = h_resp.data[0]

    # Lista quartos disponíveis
    q_resp = supabase.table("quartos").select("*").eq("disponivel", True).execute()
    if not q_resp.data:
        print("Não há quartos disponíveis no momento.")
        return
    
    print("\nQuartos disponíveis:")
    for q in q_resp.data:
        print(f"ID: {q['id']} | Quarto {q['numero']} ({q['tipo']}) - R$ {q['preco_diaria']}/dia")

    quarto_id = int(input("Digite o ID do quarto escolhido: "))
    dias = int(input("Quantidade de dias: "))

    # Busca o preço do quarto escolhido
    quarto_selecionado = next((q for q in q_resp.data if q['id'] == quarto_id), None)
    if not quarto_selecionado:
        print("Quarto inválido ou indisponível.")
        return

    valor_total = quarto_selecionado['preco_diaria'] * dias

    # Salva a reserva
    reserva_data = {
        "hospede_id": hospede['id'],
        "quarto_id": quarto_id,
        "dias": dias,
        "valor_total": valor_total
    }
    supabase.table("reservas").insert(reserva_data).execute()

    # Atualiza o quarto para indisponível
    supabase.table("quartos").update({"disponivel": False}).eq("id", quarto_id).execute()

    print(f"Reserva criada com sucesso! Valor total: R$ {valor_total:.2f}")

def menu():
    while True:
        print("\n=== SISTEMA DE CONTROLE DE HOSTEL ===")
        print("1. Listar Quartos")
        print("2. Cadastrar Quarto")
        print("3. Cadastrar Hóspede")
        print("4. Criar Reserva")
        print("0. Sair")
        
        opcao = input("Escolha uma opção: ")
        
        if opcao == "1":
            listar_quartos()
        elif opcao == "2":
            cadastrar_quarto()
        elif opcao == "3":
            cadastrar_hospede()
        elif opcao == "4":
            criar_reserva()
        elif opcao == "0":
            print("Saindo do sistema...")
            break
        else:
            print("Opção inválida, tente novamente.")

if __name__ == "__main__":
    menu()