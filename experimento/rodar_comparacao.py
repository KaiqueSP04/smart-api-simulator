
"""Executa nove rodadas adicionais do mock e do Gemini."""

import csv
import re
import shutil
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASTA = ROOT / "experimento"
RESULTADOS = PASTA / "resultados_comparacao"
RESULTADOS.mkdir(exist_ok=True)

RODADAS = 9
TIMEOUT = 180

TESTES = {
    "mock": PASTA / "teste_integracao_mock.py",
    "gemini": PASTA / "teste_integracao_gemini.py",
}

ARQUIVO_GEMINI = PASTA / "resultados_gemini.csv"

# Preserva a primeira medicao do Gemini.
if ARQUIVO_GEMINI.exists():
    shutil.copy2(
        ARQUIVO_GEMINI,
        RESULTADOS / "gemini_rodada_original.csv",
    )

registros = []
inicio_experimento = datetime.now().isoformat(timespec="seconds")


def executar(tipo, rodada):
    print(f"\n=== {tipo.upper()} | RODADA {rodada}/{RODADAS} ===", flush=True)

    try:
        processo = subprocess.run(
            [sys.executable, str(TESTES[tipo])],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )

        saida = processo.stdout + "\n" + processo.stderr
        codigo = processo.returncode

    except subprocess.TimeoutExpired:
        saida = f"Tempo limite excedido: {TIMEOUT} segundos"
        codigo = -1

    log = RESULTADOS / f"{tipo}_rodada_{rodada:02d}.txt"
    log.write_text(saida, encoding="utf-8")

    print(saida, flush=True)

    # Copia os dados individuais do Gemini antes da proxima rodada.
    if tipo == "gemini" and ARQUIVO_GEMINI.exists():
        shutil.copy2(
            ARQUIVO_GEMINI,
            RESULTADOS / f"gemini_rodada_{rodada:02d}.csv",
        )

    padrao = re.compile(
        r"\[(OK|FALHA|ERRO)\]\s+(.+?)\s+-\s+([\d.]+)\s+ms"
    )

    operacoes = []

    for linha in saida.splitlines():
        encontrado = padrao.search(linha)

        if encontrado:
            status, nome, tempo = encontrado.groups()

            operacoes.append({
                "gerador": tipo,
                "rodada": rodada,
                "operacao": nome,
                "status": status,
                "tempo_ms": float(tempo),
                "codigo_saida": codigo,
            })

    # Se o processo falhar antes de registrar operacoes,
    # preserva a falha sem inventar tempos.
    if not operacoes:
        operacoes.append({
            "gerador": tipo,
            "rodada": rodada,
            "operacao": "EXECUCAO",
            "status": "ERRO",
            "tempo_ms": "",
            "codigo_saida": codigo,
        })

    registros.extend(operacoes)

    aprovados = sum(
        item["status"] == "OK" for item in operacoes
    )

    print(
        f"Rodada {rodada}: {aprovados}/9 operacoes aprovadas",
        flush=True,
    )


try:
    for rodada in range(1, RODADAS + 1):
        executar("mock", rodada)
        executar("gemini", rodada)

except KeyboardInterrupt:
    print("\nExperimento interrompido. Salvando dados coletados.")

finally:
    arquivo = RESULTADOS / "comparacao_operacoes.csv"

    with arquivo.open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        escritor = csv.DictWriter(
            f,
            fieldnames=[
                "gerador",
                "rodada",
                "operacao",
                "status",
                "tempo_ms",
                "codigo_saida",
            ],
        )
        escritor.writeheader()
        escritor.writerows(registros)

    resumo = []

    print("\n=== RESUMO DAS NOVAS RODADAS ===")

    for tipo in ("mock", "gemini"):
        dados = [
            r for r in registros
            if r["gerador"] == tipo
        ]

        tempos = [
            r["tempo_ms"] for r in dados
            if isinstance(r["tempo_ms"], float)
        ]

        aprovados = sum(
            r["status"] == "OK" for r in dados
        )

        rodadas_realizadas = len({
            r["rodada"] for r in dados
        })

        total_esperado = rodadas_realizadas * 9

        resumo_item = {
            "gerador": tipo,
            "rodadas": rodadas_realizadas,
            "operacoes_aprovadas": aprovados,
            "operacoes_previstas": total_esperado,
            "media_ms": (
                statistics.mean(tempos) if tempos else ""
            ),
            "mediana_ms": (
                statistics.median(tempos) if tempos else ""
            ),
            "minimo_ms": min(tempos) if tempos else "",
            "maximo_ms": max(tempos) if tempos else "",
            "desvio_padrao_ms": (
                statistics.stdev(tempos)
                if len(tempos) > 1 else ""
            ),
        }

        resumo.append(resumo_item)

        print(f"\n{tipo.upper()}")
        print(f"Rodadas: {rodadas_realizadas}")
        print(f"Aprovadas: {aprovados}/{total_esperado}")

        if tempos:
            print(
                f"Media: {statistics.mean(tempos):.2f} ms"
            )
            print(
                f"Mediana: {statistics.median(tempos):.2f} ms"
            )
            print(
                f"Minimo: {min(tempos):.2f} ms"
            )
            print(
                f"Maximo: {max(tempos):.2f} ms"
            )

    with (RESULTADOS / "resumo_comparacao.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        escritor = csv.DictWriter(
            f, fieldnames=list(resumo[0].keys())
        )
        escritor.writeheader()
        escritor.writerows(resumo)

    print("\nArquivos salvos em:")
    print(RESULTADOS)
    print(f"Inicio: {inicio_experimento}")
    print(f"Fim: {datetime.now().isoformat(timespec='seconds')}")
