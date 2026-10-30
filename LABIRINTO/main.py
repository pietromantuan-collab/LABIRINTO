
import cv2
import numpy as np
import mediapipe as mp
import random
import json
import os
import time
import math

# ==================================================
# LABIRINTO - DESAFIO INTERATIVO 6.0
# Python + OpenCV + MediaPipe
# 6 fases, ranking, webcam e botoes clicaveis
# ==================================================

LARGURA = 1280
ALTURA = 720
JANELA = "LABIRINTO - DESAFIO INTERATIVO"

COLUNAS = 35
LINHAS = 23
CELULA = 24

LAB_X = 38
LAB_Y = 115

RAIO = 7
SENSIBILIDADE = 2.7

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO = os.path.join(
    PASTA, "ranking_hand_maze.json"
)

# ==================================================
# FASES
# ==================================================

FASES = [
    {
        "nome": "INICIANTE",
        "seed": 12,
        "limite": 0,
        "atalhos": 36
    },
    {
        "nome": "EXPLORADOR",
        "seed": 25,
        "limite": 150,
        "atalhos": 26
    },
    {
        "nome": "DESAFIADOR",
        "seed": 42,
        "limite": 120,
        "atalhos": 17
    },
    {
        "nome": "EXPERT",
        "seed": 66,
        "limite": 100,
        "atalhos": 11
    },
    {
        "nome": "MESTRE",
        "seed": 91,
        "limite": 85,
        "atalhos": 6
    },
    {
        "nome": "IMPOSSIVEL",
        "seed": 123,
        "limite": 70,
        "atalhos": 2
    }
]

# Cores no formato BGR
FUNDO = (25, 16, 12)
PAINEL = (54, 38, 32)
PAREDE = (135, 85, 30)
BORDA = (255, 190, 65)
CHAO = (43, 31, 25)

VERDE = (100, 240, 90)
AMARELO = (60, 230, 255)
BRANCO = (255, 255, 255)
CINZA = (190, 185, 175)
VERMELHO = (80, 80, 255)

# Botoes
BTN_RANKING = (940, 610, 1228, 657)
BTN_PROXIMA = (635, 344, 920, 395)
BTN_FECHAR = (1005, 78, 1049, 120)
BTN_LIMPAR = (755, 619, 1005, 660)

BTN_SIM = (390, 440, 610, 495)
BTN_NAO = (670, 440, 890, 495)

# ==================================================
# RANKING
# ==================================================

def carregar_ranking():
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            dados = json.load(f)

        if not isinstance(dados, dict):
            return {}

        resultado = {}

        for fase, valores in dados.items():

            if isinstance(valores, (int, float)):
                valores = [{
                    "nome": "RECORDE ANTIGO",
                    "tempo": valores
                }]

            if not isinstance(valores, list):
                continue

            registros = []

            for item in valores:
                if not isinstance(item, dict):
                    continue

                nome = item.get("nome")
                segundos = item.get("tempo")

                if (
                    isinstance(nome, str)
                    and isinstance(segundos, (int, float))
                    and not isinstance(segundos, bool)
                    and math.isfinite(segundos)
                    and segundos >= 0
                ):
                    registros.append({
                        "nome": nome[:15],
                        "tempo": float(segundos)
                    })

            registros.sort(key=lambda x: x["tempo"])
            resultado[fase] = registros

        return resultado

    except (OSError, ValueError):
        return {}


ranking = carregar_ranking()


def salvar_ranking(dados):
    temporario = ARQUIVO + ".tmp"

    try:
        with open(
            temporario, "w", encoding="utf-8"
        ) as f:
            json.dump(
                dados, f,
                indent=4,
                ensure_ascii=False
            )

        os.replace(temporario, ARQUIVO)
        return True

    except OSError as erro:
        print("Erro ao salvar ranking:", erro)
        return False


def obter_ranking(indice):
    return ranking.get(FASES[indice]["nome"], [])


# ==================================================
# GERADOR DE LABIRINTOS
# ==================================================

def gerar_labirinto(indice):
    rng = random.Random(FASES[indice]["seed"])

    lab = np.ones(
        (LINHAS, COLUNAS),
        dtype=np.uint8
    )

    lab[1, 1] = 0
    pilha = [(1, 1)]

    while pilha:
        x, y = pilha[-1]

        direcoes = [
            (2, 0),
            (-2, 0),
            (0, 2),
            (0, -2)
        ]

        rng.shuffle(direcoes)
        vizinhos = []

        for dx, dy in direcoes:
            nx = x + dx
            ny = y + dy

            if (
                1 <= nx < COLUNAS - 1
                and 1 <= ny < LINHAS - 1
                and lab[ny, nx] == 1
            ):
                vizinhos.append((nx, ny, dx, dy))

        if vizinhos:
            nx, ny, dx, dy = vizinhos[0]

            lab[y + dy // 2, x + dx // 2] = 0
            lab[ny, nx] = 0

            pilha.append((nx, ny))
        else:
            pilha.pop()

    # Cria alguns atalhos.
    candidatos = []

    for y in range(2, LINHAS - 2):
        for x in range(2, COLUNAS - 2):
            if lab[y, x] == 0:
                continue

            horizontal = (
                lab[y, x - 1] == 0
                and lab[y, x + 1] == 0
            )

            vertical = (
                lab[y - 1, x] == 0
                and lab[y + 1, x] == 0
            )

            if horizontal or vertical:
                candidatos.append((x, y))

    rng.shuffle(candidatos)

    for x, y in candidatos[
        :FASES[indice]["atalhos"]
    ]:
        lab[y, x] = 0

    return lab


# ==================================================
# VARIAVEIS DO JOGO
# ==================================================

nivel = 0
labirinto = None

bola_x = 0.0
bola_y = 0.0

estado = "PRONTO"

inicio_tempo = 0.0
tempo_final = 0.0

dedo_anterior = None

nome_digitado = ""
ultimo_nome = ""
posicao_jogador = 0
novo_recorde = False
ranking_salvo = True

ranking_aberto = False
fase_ranking = 0
pagina_ranking = 0
confirmar_limpeza = False

mensagem_sistema = ""

# ==================================================
# CONFIGURACAO DOS NIVEIS
# ==================================================

def centro_celula(x, y):
    return (
        LAB_X + x * CELULA + CELULA / 2,
        LAB_Y + y * CELULA + CELULA / 2
    )


def preparar_fase(indice):
    global nivel, labirinto
    global bola_x, bola_y, estado
    global tempo_final, dedo_anterior
    global nome_digitado, novo_recorde
    global posicao_jogador, ranking_salvo

    nivel = indice
    labirinto = gerar_labirinto(nivel)

    bola_x, bola_y = centro_celula(1, 1)

    estado = "PRONTO"
    tempo_final = 0.0

    dedo_anterior = None
    nome_digitado = ""
    novo_recorde = False
    posicao_jogador = 0
    ranking_salvo = True

    print(
        f"Fase {nivel + 1}: {FASES[nivel]['nome']}"
    )


def iniciar_fase():
    global estado, inicio_tempo, dedo_anterior

    inicio_tempo = time.monotonic()
    estado = "JOGANDO"
    dedo_anterior = None


def concluir_fase(segundos):
    global estado, tempo_final
    global nome_digitado, dedo_anterior

    estado = "NOME"
    tempo_final = segundos
    nome_digitado = ""
    dedo_anterior = None

    print(
        f"Labirinto concluido em {segundos:.2f}s!"
    )


def registrar_jogador(nome, segundos):
    global ranking, ultimo_nome
    global posicao_jogador, novo_recorde
    global ranking_salvo

    nome = nome.strip().upper()[:15]

    if not nome:
        nome = "VISITANTE"

    fase = FASES[nivel]["nome"]
    anteriores = obter_ranking(nivel)

    novo_recorde = (
        not anteriores
        or segundos < anteriores[0]["tempo"]
    )

    entrada = {
        "nome": nome,
        "tempo": round(segundos, 2)
    }

    nova_lista = anteriores.copy()
    nova_lista.append(entrada)

    nova_lista.sort(
        key=lambda item: item["tempo"]
    )

    novos_dados = dict(ranking)
    novos_dados[fase] = nova_lista

    ranking_salvo = salvar_ranking(novos_dados)

    if ranking_salvo:
        ranking = novos_dados

    posicao_jogador = next(
        i + 1
        for i, item in enumerate(nova_lista)
        if item is entrada
    )

    ultimo_nome = nome

    print("Jogador:", nome)
    print("Fase:", fase)
    print("Posicao:", posicao_jogador)
    print("Ranking salvo:", ranking_salvo)


def avancar_fase():
    global ranking_aberto
    global confirmar_limpeza

    if estado != "VITORIA":
        return

    ranking_aberto = False
    confirmar_limpeza = False

    proximo = nivel + 1

    if proximo >= len(FASES):
        print("Todas as fases concluidas!")
        proximo = 0

    preparar_fase(proximo)


# ==================================================
# COLISOES
# ==================================================

def colide(px, py):
    # Amostras no contorno da bolinha.
    pontos = [
        (0, 0),
        (-RAIO, 0),
        (RAIO, 0),
        (0, -RAIO),
        (0, RAIO),
        (-5, -5),
        (5, -5),
        (-5, 5),
        (5, 5)
    ]

    for dx, dy in pontos:
        x = int(
            (px + dx - LAB_X) // CELULA
        )

        y = int(
            (py + dy - LAB_Y) // CELULA
        )

        if not (
            0 <= x < COLUNAS
            and 0 <= y < LINHAS
        ):
            return True

        if labirinto[y, x] == 1:
            return True

    return False


def mover_bola(dx, dy):
    global bola_x, bola_y

    # Movimento em pequenos passos para impedir
    # atravessar uma parede de uma vez.
    passos = max(
        1,
        math.ceil(max(abs(dx), abs(dy)) / 3)
    )

    sx = dx / passos
    sy = dy / passos

    for _ in range(passos):
        if not colide(bola_x + sx, bola_y):
            bola_x += sx

        if not colide(bola_x, bola_y + sy):
            bola_y += sy


def chegou_na_saida():
    fx, fy = centro_celula(
        COLUNAS - 2,
        LINHAS - 2
    )

    return math.hypot(
        bola_x - fx,
        bola_y - fy
    ) < 9


# ==================================================
# FUNCOES VISUAIS
# ==================================================

def texto(
    tela, mensagem, x, y,
    tamanho=0.6, cor=BRANCO, espessura=2
):
    cv2.putText(
        tela,
        str(mensagem),
        (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX,
        tamanho,
        cor,
        espessura,
        cv2.LINE_AA
    )


def caixa(tela, area, cor, contorno=False):
    x1, y1, x2, y2 = area

    cv2.rectangle(
        tela,
        (x1, y1),
        (x2, y2),
        cor,
        2 if contorno else -1
    )


def botao(tela, area, rotulo, cor, tam=0.52):
    caixa(tela, area, cor)
    caixa(tela, area, BORDA, True)

    x1, y1, x2, y2 = area

    (tw, th), _ = cv2.getTextSize(
        rotulo,
        cv2.FONT_HERSHEY_SIMPLEX,
        tam,
        2
    )

    tx = (x1 + x2 - tw) // 2
    ty = (y1 + y2 + th) // 2

    texto(tela, rotulo, tx, ty, tam)


def desenhar_labirinto(tela):
    for y in range(LINHAS):
        for x in range(COLUNAS):
            px = LAB_X + x * CELULA
            py = LAB_Y + y * CELULA

            area = (
                px, py,
                px + CELULA - 1,
                py + CELULA - 1
            )

            cor = (
                PAREDE if labirinto[y, x]
                else CHAO
            )

            caixa(tela, area, cor)

            if labirinto[y, x]:
                caixa(
                    tela,
                    (
                        px + 2,
                        py + 2,
                        px + CELULA - 3,
                        py + CELULA - 3
                    ),
                    BORDA,
                    True
                )

    # Entrada
    ix, iy = centro_celula(1, 1)

    cv2.circle(
        tela,
        (int(ix), int(iy)),
        11, VERDE, 2
    )

    # Saida
    fx, fy = centro_celula(
        COLUNAS - 2,
        LINHAS - 2
    )

    cv2.circle(
        tela,
        (int(fx), int(fy)),
        10, VERDE, -1
    )

    # Brilho da bolinha
    cv2.circle(
        tela,
        (int(bola_x), int(bola_y)),
        12,
        (95, 100, 130),
        -1
    )

    cv2.circle(
        tela,
        (int(bola_x), int(bola_y)),
        RAIO,
        AMARELO,
        -1
    )

    cv2.circle(
        tela,
        (int(bola_x - 2), int(bola_y - 2)),
        3,
        BRANCO,
        -1
    )


# ==================================================
# PAINEL LATERAL
# ==================================================

def desenhar_painel(tela, frame, status, tempo):
    caixa(
        tela,
        (910, 103, 1255, 674),
        PAINEL
    )

    texto(
        tela,
        f"NIVEL {nivel + 1}/{len(FASES)}",
        935, 144, 0.83, AMARELO
    )

    texto(
        tela,
        FASES[nivel]["nome"],
        935, 175, 0.63
    )

    texto(
        tela,
        "CRONOMETRO",
        935, 216, 0.52, CINZA
    )

    texto(
        tela,
        f"{tempo:.2f}s",
        935, 253, 1.0, VERDE
    )

    limite = FASES[nivel]["limite"]

    texto(
        tela,
        f"LIMITE: {limite}s" if limite
        else "SEM LIMITE",
        935, 282, 0.47, CINZA
    )

    melhores = obter_ranking(nivel)

    if melhores:
        texto(
            tela,
            f"RECORDE: {melhores[0]['tempo']:.2f}s",
            935, 313, 0.52, AMARELO
        )

        texto(
            tela,
            melhores[0]["nome"],
            935, 338, 0.43, CINZA
        )
    else:
        texto(
            tela,
            "RECORDE: --",
            935, 313, 0.52, AMARELO
        )

    # Miniatura da webcam
    if frame is not None:
        mini = cv2.resize(frame, (292, 180))
        tela[354:534, 935:1227] = mini
    else:
        caixa(
            tela,
            (935, 354, 1227, 534),
            (20, 20, 20)
        )

        texto(
            tela,
            "CAMERA OFF",
            975, 447
        )

    texto(
        tela,
        "MAO: " + status,
        935, 557, 0.46,
        VERDE if status == "ATIVA" else CINZA
    )

    avisos = {
        "PRONTO": "ESPACO: INICIAR",
        "JOGANDO": "ENCONTRE A SAIDA!",
        "NOME": "DIGITE SEU NOME",
        "VITORIA": "FASE CONCLUIDA!",
        "TEMPO ESGOTADO": "TEMPO ESGOTADO!"
    }

    texto(
        tela,
        avisos.get(estado, ""),
        935, 589, 0.51, AMARELO
    )

    habilitado = estado in (
        "PRONTO",
        "VITORIA",
        "TEMPO ESGOTADO"
    )

    botao(
        tela,
        BTN_RANKING,
        "VER RANKING",
        (115, 90, 35) if habilitado
        else (65, 58, 48)
    )

    texto(
        tela,
        "R: REINICIAR   Q: SAIR",
        939, 694, 0.42, CINZA
    )


# ==================================================
# TELA DE VITORIA
# ==================================================

def desenhar_vitoria(tela):
    caixa(
        tela,
        (275, 90, 1005, 665),
        (42, 27, 20)
    )

    caixa(
        tela,
        (275, 90, 1005, 665),
        BORDA,
        True
    )

    texto(
        tela,
        "LABIRINTO CONCLUIDO!",
        368, 146, 0.86, AMARELO
    )

    texto(
        tela,
        f"SEU TEMPO: {tempo_final:.2f}s",
        412, 194, 0.78, VERDE
    )

    if estado == "NOME":
        texto(
            tela,
            "DIGITE SEU NOME:",
            389, 246, 0.64
        )

        caixa(
            tela,
            (375, 266, 905, 326),
            (75, 52, 40)
        )

        cursor = (
            "_" if int(time.monotonic() * 2) % 2
            else ""
        )

        texto(
            tela,
            nome_digitado + cursor,
            394, 305, 0.85
        )

        texto(
            tela,
            "ENTER = SALVAR NO RANKING",
            390, 375, 0.61, VERDE
        )

    else:
        texto(
            tela,
            "JOGADOR: " + ultimo_nome,
            388, 246, 0.67
        )

        texto(
            tela,
            f"POSICAO: {posicao_jogador}",
            388, 282, 0.61, VERDE
        )

        if novo_recorde:
            texto(
                tela,
                "NOVO RECORDE!",
                388, 320, 0.62, AMARELO
            )

        if not ranking_salvo:
            texto(
                tela,
                "ERRO AO SALVAR RANKING",
                388, 343, 0.45, VERMELHO
            )

        botao(
            tela,
            BTN_PROXIMA,
            "PROXIMA FASE",
            (50, 125, 65),
            0.62
        )

    texto(
        tela,
        "TOP 5 - " + FASES[nivel]["nome"],
        390, 427, 0.62, AMARELO
    )

    melhores = obter_ranking(nivel)[:5]

    if not melhores:
        texto(
            tela,
            "SEJA O PRIMEIRO COLOCADO!",
            390, 470, 0.5, CINZA
        )

    for i, jogador in enumerate(melhores):
        yy = 462 + i * 36

        cor = AMARELO if i == 0 else BRANCO

        texto(
            tela,
            f"{i + 1}. {jogador['nome']}",
            390, yy, 0.56, cor
        )

        texto(
            tela,
            f"{jogador['tempo']:.2f}s",
            780, yy, 0.56, cor
        )


# ==================================================
# RANKING POR FASE
# ==================================================

def desenhar_ranking(tela):
    caixa(
        tela,
        (214, 49, 1065, 681),
        (37, 28, 24)
    )

    caixa(
        tela,
        (214, 49, 1065, 681),
        BORDA, True
    )

    texto(
        tela,
        "RANKING GLOBAL",
        425, 104, 0.95, AMARELO
    )

    botao(
        tela,
        BTN_FECHAR,
        "X",
        (95, 65, 115)
    )

    # Abas dos seis niveis
    for i, fase in enumerate(FASES):
        x = 250 + (i % 3) * 255
        y = 131 + (i // 3) * 52

        selecionado = i == fase_ranking

        botao(
            tela,
            (x, y, x + 240, y + 43),
            fase["nome"],
            (125, 100, 35) if selecionado
            else (64, 48, 40),
            0.48
        )

    lista = obter_ranking(fase_ranking)

    paginas = max(
        1,
        math.ceil(len(lista) / 7)
    )

    pagina_atual = min(
        pagina_ranking,
        paginas - 1
    )

    comeco = pagina_atual * 7

    texto(tela, "POS.", 277, 278, 0.52, CINZA)
    texto(tela, "JOGADOR", 399, 278, 0.52, CINZA)
    texto(tela, "TEMPO", 842, 278, 0.52, CINZA)

    if not lista:
        texto(
            tela,
            "NENHUM JOGADOR REGISTRADO",
            340, 381, 0.67, CINZA
        )

    for i, jogador in enumerate(
        lista[comeco:comeco + 7]
    ):
        y = 318 + i * 39
        pos = comeco + i + 1

        if i % 2 == 0:
            caixa(
                tela,
                (257, y - 27, 1021, y + 11),
                (53, 41, 35)
            )

        cor = AMARELO if pos == 1 else BRANCO

        texto(
            tela,
            f"{pos}.",
            276, y, 0.59, cor
        )

        texto(
            tela,
            jogador["nome"],
            400, y, 0.57, cor
        )

        texto(
            tela,
            f"{jogador['tempo']:.2f}s",
            840, y, 0.57, cor
        )

    texto(
        tela,
        f"JOGADORES: {len(lista)}",
        268, 607, 0.47, CINZA
    )

    texto(
        tela,
        f"PAGINA {pagina_atual + 1}/{paginas}",
        510, 607, 0.46, CINZA
    )

    if pagina_atual > 0:
        botao(
            tela,
            (278, 619, 423, 659),
            "ANTERIOR",
            (85, 68, 45)
        )

    if pagina_atual < paginas - 1:
        botao(
            tela,
            (437, 619, 582, 659),
            "PROXIMA",
            (85, 68, 45)
        )

    botao(
        tela,
        BTN_LIMPAR,
        "LIMPAR RANKING",
        (55, 55, 160),
        0.47
    )


def desenhar_confirmacao(tela):
    caixa(
        tela,
        (312, 235, 968, 527),
        (32, 26, 38)
    )

    caixa(
        tela,
        (312, 235, 968, 527),
        VERMELHO,
        True
    )

    texto(
        tela,
        "ATENCAO!",
        510, 294, 0.94, VERMELHO
    )

    texto(
        tela,
        "APAGAR O RANKING DE TODAS AS FASES?",
        360, 351, 0.57
    )

    texto(
        tela,
        "ESSA ACAO NAO PODE SER DESFEITA.",
        390, 388, 0.52, CINZA
    )

    botao(
        tela,
        BTN_SIM,
        "SIM, LIMPAR",
        (55, 55, 160)
    )

    botao(
        tela,
        BTN_NAO,
        "CANCELAR",
        (65, 105, 65)
    )


# ==================================================
# RENDERIZAR JOGO
# ==================================================

def renderizar(frame, status, segundos):
    tela = np.full(
        (ALTURA, LARGURA, 3),
        FUNDO,
        dtype=np.uint8
    )

    caixa(
        tela,
        (0, 0, LARGURA, 79),
        (46, 30, 25)
    )

    texto(
        tela,
        "LABIRINTO",
        38, 42, 1.06, AMARELO
    )

    texto(
        tela,
        "DESAFIO INTERATIVO",
        306, 41, 0.64
    )

    texto(
        tela,
        "VISAO COMPUTACIONAL + GESTOS",
        38, 93, 0.44, CINZA, 1
    )

    desenhar_labirinto(tela)
    desenhar_painel(tela, frame, status, segundos)

    if estado in ("NOME", "VITORIA"):
        desenhar_vitoria(tela)

    if ranking_aberto:
        desenhar_ranking(tela)

    if confirmar_limpeza:
        desenhar_confirmacao(tela)

    if mensagem_sistema:
        texto(
            tela,
            mensagem_sistema,
            22, 707, 0.44, AMARELO
        )

    return tela


# ==================================================
# CONTROLE DO MOUSE
# ==================================================

def dentro(x, y, area):
    return (
        area[0] <= x <= area[2]
        and area[1] <= y <= area[3]
    )


def evento_mouse(evento, x, y, flags, param):
    global ranking_aberto
    global fase_ranking
    global pagina_ranking
    global confirmar_limpeza
    global ranking
    global mensagem_sistema

    if evento != cv2.EVENT_LBUTTONDOWN:
        return

    # Confirmacao de limpeza
    if confirmar_limpeza:
        if dentro(x, y, BTN_SIM):
            if salvar_ranking({}):
                ranking = {}
                pagina_ranking = 0
                mensagem_sistema = "RANKING LIMPO!"
            else:
                mensagem_sistema = "ERRO AO LIMPAR RANKING"

            confirmar_limpeza = False

        elif dentro(x, y, BTN_NAO):
            confirmar_limpeza = False

        return

    # Ranking aberto
    if ranking_aberto:
        if dentro(x, y, BTN_FECHAR):
            ranking_aberto = False
            return

        if dentro(x, y, BTN_LIMPAR):
            confirmar_limpeza = True
            return

        # Selecionar fase
        for i in range(len(FASES)):
            ax = 250 + (i % 3) * 255
            ay = 131 + (i // 3) * 52

            if dentro(
                x, y,
                (ax, ay, ax + 240, ay + 43)
            ):
                fase_ranking = i
                pagina_ranking = 0
                return

        paginas = max(
            1,
            math.ceil(
                len(obter_ranking(fase_ranking)) / 7
            )
        )

        if dentro(x, y, (278, 619, 423, 659)):
            pagina_ranking = max(
                0, pagina_ranking - 1
            )

        elif dentro(x, y, (437, 619, 582, 659)):
            pagina_ranking = min(
                paginas - 1,
                pagina_ranking + 1
            )

        return

    # Proxima fase depois de salvar o nome
    if (
        estado == "VITORIA"
        and dentro(x, y, BTN_PROXIMA)
    ):
        avancar_fase()
        return

    # Abrir ranking
    if (
        estado in (
            "PRONTO",
            "VITORIA",
            "TEMPO ESGOTADO"
        )
        and dentro(x, y, BTN_RANKING)
    ):
        ranking_aberto = True
        fase_ranking = nivel
        pagina_ranking = 0
        mensagem_sistema = ""


# ==================================================
# WEBCAM
# ==================================================

def abrir_camera():
    camera = cv2.VideoCapture(
        0,
        cv2.CAP_DSHOW
    )

    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(0)

    if camera.isOpened():
        camera.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            640
        )

        camera.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            480
        )

        print("Webcam conectada!")
    else:
        print("Webcam indisponivel.")
        print("Use as setas do teclado.")

    return camera


# ==================================================
# PROGRAMA PRINCIPAL
# ==================================================

def main():
    global estado
    global tempo_final
    global dedo_anterior
    global nome_digitado
    global ranking_aberto
    global fase_ranking
    global pagina_ranking
    global confirmar_limpeza

    preparar_fase(0)
    camera = abrir_camera()

    # Inicializacao do MediaPipe
    try:
        from mediapipe.python.solutions import hands as mp_hands
        from mediapipe.python.solutions import drawing_utils as mp_draw
    except ImportError:
        mp_hands = mp.solutions.hands
        mp_draw = mp.solutions.drawing_utils

    detector = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.60
    )

    cv2.namedWindow(
        JANELA,
        cv2.WINDOW_NORMAL
    )

    cv2.resizeWindow(
        JANELA,
        LARGURA,
        ALTURA
    )

    cv2.setMouseCallback(
        JANELA,
        evento_mouse
    )

    ultimo_frame = time.monotonic()

    print("=" * 45)
    print("LABIRINTO - DESAFIO INTERATIVO 6.0")
    print("=" * 45)
    print("ESPACO = INICIAR")
    print("INDICADOR = MOVER BOLINHA")
    print("PINCA = PAUSAR CONTROLE")
    print("SETAS = CONTROLE PELO TECLADO")
    print("ENTER = SALVAR NOME")
    print("N = PROXIMA FASE")
    print("R = REINICIAR")
    print("Q = SAIR")
    print("RANKING = BOTAO NA TELA")

    try:
        while True:
            agora = time.monotonic()

            dt = min(
                0.05,
                agora - ultimo_frame
            )

            ultimo_frame = agora

            frame = None
            status = "SEM MAO"

            # ==================================
            # VISAO COMPUTACIONAL
            # ==================================

            if camera.isOpened():
                ok, imagem = camera.read()

                if ok:
                    frame = cv2.flip(imagem, 1)

                    rgb = cv2.cvtColor(
                        frame,
                        cv2.COLOR_BGR2RGB
                    )

                    rgb.flags.writeable = False
                    deteccao = detector.process(rgb)
                    rgb.flags.writeable = True

                    if deteccao.multi_hand_landmarks:
                        mao = deteccao.multi_hand_landmarks[0]

                        mp_draw.draw_landmarks(
                            frame,
                            mao,
                            mp_hands.HAND_CONNECTIONS
                        )

                        pontos = mao.landmark
                        indicador = pontos[8]
                        polegar = pontos[4]

                        px = indicador.x * frame.shape[1]
                        py = indicador.y * frame.shape[0]

                        distancia_pinca = math.hypot(
                            indicador.x - polegar.x,
                            indicador.y - polegar.y
                        )

                        pinca = distancia_pinca < 0.055

                        if pinca:
                            status = "PAUSADA"
                            dedo_anterior = None

                        else:
                            status = "ATIVA"

                            if (
                                estado == "JOGANDO"
                                and not ranking_aberto
                            ):
                                if dedo_anterior is not None:
                                    dx = (
                                        px - dedo_anterior[0]
                                    ) * SENSIBILIDADE

                                    dy = (
                                        py - dedo_anterior[1]
                                    ) * SENSIBILIDADE

                                    if (
                                        abs(dx) < 100
                                        and abs(dy) < 100
                                    ):
                                        mover_bola(dx, dy)

                                dedo_anterior = (px, py)

                            else:
                                dedo_anterior = None
                    else:
                        dedo_anterior = None

                else:
                    dedo_anterior = None
            else:
                dedo_anterior = None

            # ==================================
            # CRONOMETRO
            # ==================================

            if estado == "JOGANDO":
                segundos = agora - inicio_tempo
                limite = FASES[nivel]["limite"]

                if chegou_na_saida():
                    concluir_fase(segundos)

                elif limite and segundos >= limite:
                    estado = "TEMPO ESGOTADO"
                    tempo_final = limite
                    dedo_anterior = None

            elif estado in (
                "NOME",
                "VITORIA",
                "TEMPO ESGOTADO"
            ):
                segundos = tempo_final

            else:
                segundos = 0.0

            # ==================================
            # EXIBIR INTERFACE
            # ==================================

            tela = renderizar(
                frame,
                status,
                segundos
            )

            cv2.imshow(JANELA, tela)
            tecla = cv2.waitKeyEx(1)

            # ==================================
            # CONFIRMACAO DE LIMPEZA
            # ==================================

            if confirmar_limpeza:
                if tecla == 27:
                    confirmar_limpeza = False
                continue

            # ==================================
            # NAVEGACAO DO RANKING
            # ==================================

            if ranking_aberto:
                if tecla in (27, ord("b"), ord("B")):
                    ranking_aberto = False

                elif ord("1") <= tecla <= ord("6"):
                    fase_ranking = tecla - ord("1")
                    pagina_ranking = 0

                continue

            # ==================================
            # DIGITAR NOME DO PARTICIPANTE
            # ==================================

            if estado == "NOME":
                if tecla in (13, 10):
                    registrar_jogador(
                        nome_digitado,
                        tempo_final
                    )

                    estado = "VITORIA"

                elif tecla in (8, 127):
                    nome_digitado = nome_digitado[:-1]

                elif 32 <= tecla <= 126:
                    caractere = chr(tecla)

                    if (
                        len(nome_digitado) < 15
                        and (
                            caractere.isalnum()
                            or caractere in " _-"
                        )
                    ):
                        nome_digitado += caractere.upper()

                elif tecla == 27:
                    break

                continue

            # ==================================
            # CONTROLES GERAIS
            # ==================================

            if tecla in (ord("q"), ord("Q"), 27):
                break

            elif tecla == 32 and estado == "PRONTO":
                iniciar_fase()

            elif tecla in (ord("r"), ord("R")):
                preparar_fase(nivel)

            elif (
                tecla in (ord("n"), ord("N"))
                and estado == "VITORIA"
            ):
                avancar_fase()

            # ==================================
            # MOVIMENTO PELO TECLADO
            # ==================================

            if estado == "JOGANDO":
                velocidade = 220 * dt

                # Esquerda
                if tecla in (2424832, 81):
                    mover_bola(-velocidade, 0)

                # Direita
                elif tecla in (2555904, 83):
                    mover_bola(velocidade, 0)

                # Cima
                elif tecla in (2490368, 82):
                    mover_bola(0, -velocidade)

                # Baixo
                elif tecla in (2621440, 84):
                    mover_bola(0, velocidade)

    finally:
        camera.release()
        detector.close()
        cv2.destroyAllWindows()

        print("LABIRINTO ENCERRADO")


# ==================================================
# EXECUTAR
# ==================================================

if __name__ == "__main__":
    main()
