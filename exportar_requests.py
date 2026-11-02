
import csv
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGODB_URI")

if not uri:
    raise RuntimeError("MONGODB_URI não encontrada no .env")

client = MongoClient(uri, serverSelectionTimeoutMS=10000)

try:
    banco = client["smart_api_simulator"]
    colecao = banco["requests"]

    registros = list(colecao.find({}, {"_id": 0}))

    if not registros:
        print("Nenhum registro encontrado.")
    else:
        campos = sorted({
            campo
            for registro in registros
            for campo in registro.keys()
        })

        arquivo = "evidencia_requests.csv"

        with open(arquivo, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=campos)
            writer.writeheader()

            for registro in registros:
                linha = {
                    campo: (
                        valor.isoformat()
                        if isinstance(valor, datetime)
                        else str(valor) if isinstance(valor, (dict, list))
                        else valor
                    )
                    for campo, valor in registro.items()
                }
                writer.writerow(linha)

        print(f"Exportados {len(registros)} registros para {arquivo}")

finally:
    client.close()
