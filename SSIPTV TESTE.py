
import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse


# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Antes: 60 segundos
# Agora: 180 segundos = 3 VEZES MAIS TEMPO
TIMEOUT = 120

# Quantidade máxima de consultas simultâneas
MAX_THREADS = 100

# Extensões comuns usadas para listas IPTV/streams
EXTENSOES_LISTA = (
    ".m3u",
    ".m3u8",
    ".txt",
    ".playlist"
)

# Pasta onde está o próprio programa
PASTA_SCRIPT = os.path.dirname(os.path.abspath(__file__))

# Arquivos de saída
ARQUIVO_QUEBRADOS = os.path.join(
    PASTA_SCRIPT,
    "quebrados.txt"
)

ARQUIVO_BONS = os.path.join(
    PASTA_SCRIPT,
    "bons.txt"
)


# ============================================================
# LIMPAR TELA
# ============================================================

def limpar_tela():

    os.system(
        "cls" if os.name == "nt" else "clear"
    )


# ============================================================
# ENCONTRAR LISTAS
# ============================================================

def encontrar_listas():

    arquivos = []

    for arquivo in os.listdir(PASTA_SCRIPT):

        caminho = os.path.join(
            PASTA_SCRIPT,
            arquivo
        )

        if not os.path.isfile(caminho):
            continue

        # Não testar os arquivos gerados pelo próprio programa
        if os.path.abspath(caminho) in (
            os.path.abspath(ARQUIVO_QUEBRADOS),
            os.path.abspath(ARQUIVO_BONS)
        ):
            continue

        extensao = os.path.splitext(
            arquivo
        )[1].lower()

        if extensao in EXTENSOES_LISTA:

            arquivos.append(caminho)

    return sorted(arquivos)


# ============================================================
# ABRIR ARQUIVO COM VÁRIAS CODIFICAÇÕES
# ============================================================

def abrir_lista(arquivo):

    codificacoes = [
        "utf-8-sig",
        "utf-8",
        "latin-1",
        "cp1252"
    ]

    for encoding in codificacoes:

        try:

            with open(
                arquivo,
                "r",
                encoding=encoding,
                errors="ignore"
            ) as f:

                return f.readlines()

        except Exception:
            pass

    return []


# ============================================================
# VERIFICAR SE É UMA URL
# ============================================================

def eh_url(linha):

    linha = linha.strip()

    if not linha:
        return False

    try:

        parsed = urlparse(linha)

        return bool(
            parsed.scheme and
            parsed.netloc
        )

    except Exception:

        return False


# ============================================================
# LER LISTA
# ============================================================

def ler_lista(arquivo):

    canais = []

    linhas = abrir_lista(arquivo)

    if not linhas:
        return []

    nome = "Sem nome"
    extinf_original = None

    for linha in linhas:

        linha = linha.strip()

        if not linha:
            continue

        # ----------------------------------------------------
        # INFORMAÇÕES DO CANAL
        # ----------------------------------------------------

        if linha.upper().startswith("#EXTINF"):

            extinf_original = linha

            if "," in linha:

                nome = linha.split(
                    ",",
                    1
                )[1].strip()

            else:

                nome = "Sem nome"

            continue

        # ----------------------------------------------------
        # IGNORAR COMENTÁRIOS
        # ----------------------------------------------------

        if linha.startswith("#"):
            continue

        # ----------------------------------------------------
        # VERIFICAR URL
        # ----------------------------------------------------

        if eh_url(linha):

            canais.append({

                "nome": nome,

                "url": linha,

                "extinf": extinf_original

            })

            # Reset
            nome = "Sem nome"
            extinf_original = None

    return canais


# ============================================================
# TESTAR URL HTTP / HTTPS
# ============================================================

def testar_http(url):

    resposta = None

    inicio = time.time()

    try:

        resposta = requests.get(

            url,

            timeout=TIMEOUT,

            stream=True,

            allow_redirects=True,

            headers={
                "User-Agent":
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/153.0 Safari/537.36"
            }

        )

        codigo = resposta.status_code

        # URL final depois dos redirecionamentos
        url_final = resposta.url

        tempo = time.time() - inicio

        resposta.close()

        if 200 <= codigo < 400:

            return (
                True,
                f"HTTP {codigo}",
                tempo,
                url_final
            )

        return (
            False,
            f"HTTP {codigo}",
            tempo,
            url_final
        )

    except requests.exceptions.Timeout:

        tempo = time.time() - inicio

        return (
            False,
            f"Timeout após {tempo:.1f}s",
            tempo,
            url
        )

    except requests.exceptions.ConnectionError as e:

        tempo = time.time() - inicio

        return (
            False,
            "Falha de conexão",
            tempo,
            url
        )

    except requests.exceptions.TooManyRedirects:

        tempo = time.time() - inicio

        return (
            False,
            "Redirecionamentos demais",
            tempo,
            url
        )

    except requests.exceptions.RequestException as e:

        tempo = time.time() - inicio

        return (
            False,
            str(e),
            tempo,
            url
        )

    except Exception as e:

        tempo = time.time() - inicio

        return (
            False,
            str(e),
            tempo,
            url
        )


# ============================================================
# TESTAR OUTROS TIPOS DE STREAM
# ============================================================

def testar_outro_protocolo(url):

    inicio = time.time()

    parsed = urlparse(url)

    protocolo = parsed.scheme.lower()

    protocolos_suportados = (
        "rtsp",
        "rtmp",
        "udp",
        "tcp",
        "ftp",
        "file"
    )

    if protocolo in protocolos_suportados:

        return (
            False,
            f"Protocolo {protocolo.upper()} "
            f"não testado via HTTP",
            time.time() - inicio,
            url
        )

    return (
        False,
        f"Protocolo desconhecido: {protocolo}",
        time.time() - inicio,
        url
    )


# ============================================================
# TESTAR CANAL
# ============================================================

def testar_canal(canal):

    nome = canal["nome"]
    url = canal["url"]

    try:

        parsed = urlparse(url)

        protocolo = parsed.scheme.lower()

        # ----------------------------------------------------
        # HTTP / HTTPS
        # ----------------------------------------------------

        if protocolo in (
            "http",
            "https"
        ):

            (
                ok,
                motivo,
                tempo,
                url_final
            ) = testar_http(url)

        # ----------------------------------------------------
        # OUTROS PROTOCOLOS
        # ----------------------------------------------------

        else:

            (
                ok,
                motivo,
                tempo,
                url_final
            ) = testar_outro_protocolo(url)

        return {

            "ok": ok,

            "nome": nome,

            "url": url,

            "url_final": url_final,

            "extinf": canal.get("extinf"),

            "motivo": motivo,

            "tempo": tempo

        }

    except Exception as e:

        return {

            "ok": False,

            "nome": nome,

            "url": url,

            "url_final": url,

            "extinf": canal.get("extinf"),

            "motivo": str(e),

            "tempo": 0

        }


# ============================================================
# SALVAR LISTA M3U
# ============================================================

def salvar_lista(
    canais,
    arquivo,
    titulo
):

    try:

        with open(
            arquivo,
            "w",
            encoding="utf-8"
        ) as f:

            f.write("#EXTM3U\n")

            f.write(
                f"# {titulo}\n"
            )

            f.write(
                "# Gerado automaticamente "
                "pelo Verificador M3U\n"
            )

            f.write(
                "# ==================================================\n\n"
            )

            for canal in canais:

                # Preservar EXTINF original
                if canal.get("extinf"):

                    f.write(
                        canal["extinf"] +
                        "\n"
                    )

                else:

                    f.write(
                        f'#EXTINF:-1,{canal["nome"]}\n'
                    )

                f.write(
                    canal["url"] +
                    "\n\n"
                )

        return True

    except Exception as e:

        print(
            f"\nErro ao criar "
            f"{os.path.basename(arquivo)}: {e}"
        )

        return False


# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

def main():

    limpar_tela()

    print("=" * 90)

    print(
        "                 VERIFICADOR UNIVERSAL DE LISTAS"
    )

    print("=" * 90)

    print()

    print(
        "TEMPO MÁXIMO POR CONSULTA: "
        f"{TIMEOUT} segundos"
    )

    print(
        "THREADS SIMULTÂNEAS: "
        f"{MAX_THREADS}"
    )

    print(
        "TIMEOUT ORIGINAL: 60 segundos"
    )

    print(
        "TIMEOUT ATUAL: 180 segundos "
        "(3X MAIOR)"
    )

    print()

    print("Pasta do programa:")

    print(
        PASTA_SCRIPT
    )

    print()


    # ========================================================
    # PROCURAR LISTAS
    # ========================================================

    arquivos = encontrar_listas()

    if not arquivos:

        print(
            "Nenhuma lista encontrada."
        )

        print()

        print(
            "Extensões procuradas:"
        )

        for extensao in EXTENSOES_LISTA:

            print(
                f"  {extensao}"
            )

        print()

        print(
            "Coloque a lista na mesma "
            "pasta deste programa."
        )

        input(
            "\nPressione ENTER para sair..."
        )

        return


    # ========================================================
    # ESCOLHER LISTA
    # ========================================================

    if len(arquivos) == 1:

        arquivo_lista = arquivos[0]

        print(
            "Lista encontrada:"
        )

        print(
            os.path.basename(
                arquivo_lista
            )
        )

        print()

    else:

        print(
            "Foram encontradas várias listas:"
        )

        print()

        for i, arquivo in enumerate(
            arquivos,
            1
        ):

            print(
                f"{i} - "
                f"{os.path.basename(arquivo)}"
            )

        print()

        while True:

            try:

                escolha = int(
                    input(
                        "Escolha a lista: "
                    )
                )

                if (
                    1 <= escolha <=
                    len(arquivos)
                ):

                    arquivo_lista = arquivos[
                        escolha - 1
                    ]

                    break

            except ValueError:

                pass

            print(
                "Escolha inválida."
            )


    # ========================================================
    # LER LISTA
    # ========================================================

    print()

    print(
        "Lendo lista..."
    )

    canais = ler_lista(
        arquivo_lista
    )

    if not canais:

        print()

        print(
            "Nenhuma URL encontrada "
            "na lista."
        )

        input(
            "\nPressione ENTER para sair..."
        )

        return


    total_canais = len(canais)

    print()

    print("=" * 90)

    print(
        "                 LISTA CARREGADA"
    )

    print("=" * 90)

    print()

    print(
        f"Arquivo: {os.path.basename(arquivo_lista)}"
    )

    print(
        f"TOTAL DE CANAIS ENCONTRADOS: {total_canais}"
    )

    print()

    print(
        "Cada consulta poderá aguardar até "
        f"{TIMEOUT} segundos."
    )

    print()

    print("=" * 90)

    print(
        "                 INICIANDO TESTE"
    )

    print("=" * 90)

    print()


    inicio = time.time()

    funcionando = []
    quebrados = []


    # ========================================================
    # TESTE PARALELO
    # ========================================================

    with ThreadPoolExecutor(
        max_workers=MAX_THREADS
    ) as executor:

        tarefas = {

            executor.submit(
                testar_canal,
                canal
            ): canal

            for canal in canais

        }

        total = len(tarefas)

        concluido = 0

        for tarefa in as_completed(
            tarefas
        ):

            concluido += 1

            try:

                resultado = tarefa.result()

            except Exception as e:

                canal_original = tarefas[
                    tarefa
                ]

                resultado = {

                    "ok": False,

                    "nome":
                        canal_original.get(
                            "nome",
                            "Sem nome"
                        ),

                    "url":
                        canal_original.get(
                            "url",
                            ""
                        ),

                    "extinf":
                        canal_original.get(
                            "extinf"
                        ),

                    "motivo":
                        f"Erro interno: {e}",

                    "tempo": 0

                }


            # =================================================
            # CANAL FUNCIONANDO
            # =================================================

            if resultado["ok"]:

                funcionando.append(
                    resultado
                )

                print(
                    f"[{concluido:04d}/{total:04d}] "
                    f"[ CONEXAO ATIVA NO LINK ] "
                    f"{resultado['nome']}"
                )

                print(
                    f"       URL: "
                    f"{resultado['url']}"
                )

                print(
                    f"       Status: "
                    f"{resultado['motivo']}"
                )

                print(
                    f"       Tempo: "
                    f"{resultado['tempo']:.2f}s"
                )

                print()


            # =================================================
            # CANAL QUEBRADO
            # =================================================

            else:

                quebrados.append(
                    resultado
                )

                print(
                    f"[{concluido:04d}/{total:04d}] "
                    f"[ERRO] "
                    f"{resultado['nome']}"
                )

                print(
                    f"       URL: "
                    f"{resultado['url']}"
                )

                print(
                    f"       Motivo: "
                    f"{resultado['motivo']}"
                )

                print(
                    f"       Tempo: "
                    f"{resultado['tempo']:.2f}s"
                )

                print()


    # ========================================================
    # TEMPO TOTAL
    # ========================================================

    tempo_total = (
        time.time() - inicio
    )

    total_testados = (
        len(funcionando) +
        len(quebrados)
    )

    if total_testados > 0:

        media = (
            tempo_total /
            total_testados
        )

    else:

        media = 0


    # ========================================================
    # ORDENAR RESULTADOS
    # ========================================================

    funcionando.sort(
        key=lambda x: x["nome"].lower()
    )

    quebrados.sort(
        key=lambda x: x["nome"].lower()
    )


    # ========================================================
    # SALVAR ARQUIVOS
    # ========================================================

    print()

    print("=" * 90)

    print(
        "                    SALVANDO RESULTADOS"
    )

    print("=" * 90)

    print()

    salvar_lista(

        funcionando,

        ARQUIVO_BONS,

        "CANAIS FUNCIONANDO"

    )

    salvar_lista(

        quebrados,

        ARQUIVO_QUEBRADOS,

        "CANAIS QUEBRADOS"

    )


    # ========================================================
    # RESULTADO FINAL
    # ========================================================

    print()

    print("=" * 90)

    print(
        "                         RESULTADO FINAL"
    )

    print("=" * 90)

    print()

    print(
        f"Arquivo analisado: "
        f"{os.path.basename(arquivo_lista)}"
    )

    print()

    print(
        f"TOTAL DE CANAIS ENCONTRADOS: "
        f"{total_canais}"
    )

    print(
        f"TOTAL DE CANAIS TESTADOS:    "
        f"{total_testados}"
    )

    print()

    print(
        f"FUNCIONANDO:                  "
        f"{len(funcionando)}"
    )

    print(
        f"QUEBRADOS:                    "
        f"{len(quebrados)}"
    )

    print()

    print(
        f"Tempo total:                  "
        f"{tempo_total:.2f} segundos"
    )

    print(
        f"Tempo médio por canal:        "
        f"{media:.2f} segundos"
    )

    print()

    print(
        f"Timeout configurado:          "
        f"{TIMEOUT} segundos"
    )

    print(
        "Aumento em relação ao original:"
        " 3X"
    )

    print()


    # ========================================================
    # ARQUIVOS GERADOS
    # ========================================================

    print("=" * 90)

    print(
        "                     ARQUIVOS GERADOS"
    )

    print("=" * 90)

    print()

    print(
        "LINKS FUNCIONANDO:"
    )

    print(
        ARQUIVO_BONS
    )

    print()

    print(
        "LINKS QUEBRADOS:"
    )

    print(
        ARQUIVO_QUEBRADOS
    )

    print()


    # ========================================================
    # RESUMO DOS CANAIS FUNCIONANDO
    # ========================================================

    if funcionando:

        print("=" * 90)

        print(
            f"             TODOS OS {len(funcionando)} CANAIS FUNCIONANDO"
        )

        print("=" * 90)

        print()

        for i, canal in enumerate(
            funcionando,
            1
        ):

            print(
                f"[OK {i:04d}/{len(funcionando):04d}] "
                f"{canal['nome']}"
            )

            print(
                f"       {canal['url']}"
            )

            print(
                f"       {canal['motivo']} | "
                f"{canal['tempo']:.2f}s"
            )

            print()


    # ========================================================
    # RESUMO DOS CANAIS QUEBRADOS
    # ========================================================

    if quebrados:

        print("=" * 90)

        print(
            f"             TODOS OS {len(quebrados)} CANAIS QUEBRADOS"
        )

        print("=" * 90)

        print()

        for i, canal in enumerate(
            quebrados,
            1
        ):

            print(
                f"[ERRO {i:04d}/{len(quebrados):04d}] "
                f"{canal['nome']}"
            )

            print(
                f"       {canal['url']}"
            )

            print(
                f"       Motivo: "
                f"{canal['motivo']}"
            )

            print(
                f"       Tempo: "
                f"{canal['tempo']:.2f}s"
            )

            print()


    # ========================================================
    # RESUMO ABSOLUTO
    # ========================================================

    print("=" * 90)

    print(
        "                         RESUMO"
    )

    print("=" * 90)

    print()

    print(
        f"TOTAL ENCONTRADOS : {total_canais}"
    )

    print(
        f"TOTAL TESTADOS    : {total_testados}"
    )

    print(
        f"FUNCIONANDO       : {len(funcionando)}"
    )

    print(
        f"QUEBRADOS         : {len(quebrados)}"
    )

    print(
        f"TEMPO TOTAL       : {tempo_total:.2f}s"
    )

    print(
        f"MÉDIA POR CANAL   : {media:.2f}s"
    )

    print()

    print(
        "CONSULTA MÁXIMA   : "
        f"{TIMEOUT}s"
    )

    print(
        "THREADS           : "
        f"{MAX_THREADS}"
    )

    print()

    print("=" * 90)

    print(
        "                         FINALIZADO"
    )

    print("=" * 90)

    print()

    print(
        "Pressione ENTER para sair..."
    )

    input()


# ============================================================
# EXECUTAR
# ============================================================

if __name__ == "__main__":

    main()
