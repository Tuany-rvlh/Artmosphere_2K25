import cv2
import numpy as np
import time
from ultralytics import YOLO

# ---------- CONFIGURAÇÕES ----------
model = YOLO(r"C:\Users\persi\OneDrive\Desktop\Artmosphere_2K25\Software\artmosphere\best (4).pt")  # Carrega o modelo YOLOv8 treinado (para detectar a ponta da varinha)
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Abre a webcam (índice 1 indica a utilização da porta USB do computador para a webcam.)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Define largura do vídeo
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Define altura do vídeo

# Cria a tela de desenho branca (resolução 1280x720)
tela_width = 1280
tela_height = 720
tela_desenho = np.ones((tela_height, tela_width, 3), dtype=np.uint8) * 255
cv2.namedWindow("Paint", cv2.WINDOW_NORMAL)  # Cria janela redimensionável
cv2.setWindowProperty("Paint", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)  # Define janela em tela cheia

# Função para desenhar o botão "LIMPAR" na tela
def desenhar_botao(img):
    cv2.rectangle(img, (10, 630), (180, 710), (100, 100, 100), -1)  # Retângulo cinza
    cv2.putText(img, "LIMPAR", (30, 685), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255,255,255), 3)  # Texto branco

desenhar_botao(tela_desenho)  # Desenha o botão uma vez no início

# ---------- ESTADO ----------
strokes = []  # Lista com todos os traços desenhados
current_stroke = []  # Traço atual em andamento

ultimo_centro = None  # Última posição detectada da ponta da varinha
contagem_perdida = 0  # Contador de frames sem detecção
skip_frames = 5  # Quantos frames pode "interpolar" sem perder o desenho

btn_rect = (10, 630, 180, 710)  # Coordenadas do botão "LIMPAR"
clear_cooldown = 0.5  # Tempo mínimo entre duas limpezas (em segundos)
ultimo_tempo_limpar = 0.0  # Último momento em que a tela foi limpa

# ---------- FUNÇÕES GEOMÉTRICAS ----------
def point_in_rect(p, rect):
    # Verifica se um ponto está dentro de um retângulo
    x, y = p
    x1, y1, x2, y2 = rect
    return x1 <= x <= x2 and y1 <= y <= y2

def orient(a, b, c):
    # Calcula a orientação entre três pontos (para detectar interseções)
    return (b[1]-a[1])*(c[0]-b[0]) - (b[0]-a[0])*(c[1]-b[1])

def on_segment(a, b, c):
    # Verifica se o ponto c está sobre o segmento ab
    return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1])

def segments_intersect(p1, p2, q1, q2):
    # Verifica se dois segmentos de reta se cruzam
    o1 = orient(p1, p2, q1)
    o2 = orient(p1, p2, q2)
    o3 = orient(q1, q2, p1)
    o4 = orient(q1, q2, p2)
    if o1 == 0 and on_segment(p1, p2, q1): return True
    if o2 == 0 and on_segment(p1, p2, q2): return True
    if o3 == 0 and on_segment(q1, q2, p1): return True
    if o4 == 0 and on_segment(q1, q2, p2): return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)

def segment_intersects_rect(p1, p2, rect):
    # Verifica se um segmento toca ou cruza um retângulo
    x1,y1,x2,y2 = rect
    if point_in_rect(p1, rect) or point_in_rect(p2, rect):
        return True
    r1 = (x1,y1); r2 = (x2,y1); r3 = (x2,y2); r4 = (x1,y2)
    if segments_intersect(p1,p2,r1,r2): return True
    if segments_intersect(p1,p2,r2,r3): return True
    if segments_intersect(p1,p2,r3,r4): return True
    if segments_intersect(p1,p2,r4,r1): return True
    return False

# ---------- LOOP PRINCIPAL ----------
while True:
    ret, frame = cap.read()  # Lê um frame da webcam
    if not ret:
        break
    frame = cv2.flip(frame, 1)  # Espelha a imagem horizontalmente (efeito espelho)
    detected_center = None  # Centro da ponta detectada (na tela)
    center_on_frame = None  # Centro da ponta (na imagem da webcam)

    # YOLO - detecção da ponta da varinha
    resized = cv2.resize(frame, (320, 240))  # Reduz a imagem para processar mais rápido
    results = model(resized, conf=0.25, verbose=False)  # Executa detecção (confiança mínima de 25%)

    # Se houver detecção válida
    if results[0].boxes is not None and len(results[0].boxes) > 0:
        box = results[0].boxes[0]  # Pega a primeira caixa detectada
        x1, y1, x2, y2 = map(int, box.xyxy[0])  # Converte coordenadas para inteiros
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2  # Calcula o centro da caixa (ponta detectada)

        # Converte coordenadas do frame (320x240) para a tela (1280x720)
        scale_x = tela_width / 320
        scale_y = tela_height / 240
        detected_center = (int(cx * scale_x), int(cy * scale_y))

        # Escala equivalente na miniatura da webcam (para aparecer a tela pequena mostrando a pessoa)
        scale_fx = frame.shape[1] / 320
        scale_fy = frame.shape[0] / 240
        center_on_frame = (int(cx * scale_fx), int(cy * scale_fy))

        # Atualiza último centro
        ultimo_centro = detected_center
        contagem_perdida = 0
    else:
        # Caso não detecte a ponta
        contagem_perdida += 1
        if contagem_perdida <= skip_frames and ultimo_centro is not None:
            detected_center = ultimo_centro  # Mantém a posição por alguns frames
        else:
            detected_center = None
            ultimo_centro = None

    # Verifica se o traço cruza o botão "LIMPAR"
    prev_point = None
    if current_stroke:
        prev_point = current_stroke[-1]
    elif strokes and strokes[-1]:
        prev_point = strokes[-1][-1]

    now = time.time()
    cleared = False
    if detected_center is not None and prev_point is not None:
        if segment_intersects_rect(prev_point, detected_center, btn_rect):
            if now - ultimo_tempo_limpar > clear_cooldown:
                if np.any(tela_desenho != 255):  # Só limpa se houver algo desenhado
                    tela_desenho[:] = 255
                    desenhar_botao(tela_desenho)
                    strokes = []
                    current_stroke = []
                    ultimo_centro = None
                    contagem_perdida = 0
                    ultimo_tempo_limpar = now
                    cleared = True
    if not cleared and detected_center is not None and point_in_rect(detected_center, btn_rect):
        # Também limpa se o ponto estiver dentro do botão
        if now - ultimo_tempo_limpar > clear_cooldown:
            if np.any(tela_desenho != 255):
                tela_desenho[:] = 255
                desenhar_botao(tela_desenho)
                strokes = []
                current_stroke = []
                ultimo_centro = None
                contagem_perdida = 0
                ultimo_tempo_limpar = now
                cleared = True

    if cleared:
        detected_center = None  # Evita continuar desenhando após limpar

    # Se há ponto detectado, adiciona ao traço atual
    if detected_center is not None:
        current_stroke.append(detected_center)
    else:
        # Quando o ponto é perdido, encerra o traço atual
        if current_stroke:
            strokes.append(current_stroke)
            current_stroke = []

    # Desenha todos os traços salvos na tela
    for stroke in strokes + [current_stroke]:
        for i in range(1, len(stroke)):
            pt1 = stroke[i-1]
            pt2 = stroke[i]
            cv2.line(tela_desenho, pt1, pt2, (0,0,0), 2)  # Linha preta de 2 px

    # Desenha ponto vermelho na miniatura da webcam
    if center_on_frame is not None:
        cv2.circle(frame, center_on_frame, 10, (0, 0, 255), -1)

    # Insere a imagem da webcam como miniatura no canto inferior direito
    cam_thumb = cv2.resize(frame, (240, 180))
    y_offset = tela_height - 180 - 10
    x_offset = tela_width - 240 - 10
    tela_desenho[y_offset:y_offset+180, x_offset:x_offset+240] = cam_thumb

    # Mostra a tela de desenho
    cv2.imshow("Paint", tela_desenho)
    if cv2.waitKey(1) & 0xFF == ord("q"):  # Sai se apertar 'q'
        break

cap.release()
cv2.destroyAllWindows()
