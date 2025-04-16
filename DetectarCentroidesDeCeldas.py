import cv2
import numpy as np
import VerificarTablaCerrada as vtc    # Módulo para asegurar que la tabla esté "cerrada"
import DibujarContornosCuadrados as dcc   # Módulo que se encarga de extraer contornos bien definidos
import Config

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1600, max_alto=900):
    """
    Muestra la imagen en una ventana redimensionada para ajustarse a un tamaño máximo
    sin perder la relación de aspecto.

    :param name_image: Nombre de la ventana de visualización.
    :param image: Imagen como array NumPy.
    :param max_ancho: Ancho máximo permitido (por defecto 1600).
    :param max_alto: Alto máximo permitido (por defecto 900).
    """
    # Obtener dimensiones originales
    alto_original, ancho_original = image.shape[:2]
    # Calcular el factor de escala manteniendo proporciones
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    # Si la imagen excede el tamaño máximo, se redimensiona
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    cv2.imshow(name_image, image)


def calcular_angulo(v1, v2):
    """
    Calcula el ángulo entre dos vectores en grados.

    :param v1: Primer vector (array NumPy).
    :param v2: Segundo vector (array NumPy).
    :return: Ángulo en grados entre v1 y v2.
    """
    # Aplanar vectores para asegurar formato correcto
    v1 = v1.flatten()
    v2 = v2.flatten()
    # Calcular el producto escalar y normalizar para obtener el coseno del ángulo
    cos_angulo = np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1.0, 1.0)
    return np.degrees(np.arccos(cos_angulo))


def sort_cropped_images(cropped_images, tolerance=4):
    """
    Ordena la lista de imágenes recortadas (cada elemento es un diccionario)
    basándose en la posición del centroide, primero por su coordenada Y y luego por X.
    
    :param cropped_images: Lista de diccionarios, cada uno conteniendo la imagen recortada y su centroide.
    :param tolerance: Tolerancia para agrupar (no se utiliza directamente en el sort, pero puede ser parte de la lógica).
    :return: La lista de imágenes ordenadas.
    """
    # Ordena por el segundo valor (coordenada Y) y luego por el primer valor (coordenada X) del centroide
    cropped_images.sort(key=lambda x: (x["centroide"][1], x["centroide"][0]))
    return cropped_images


def limpiar_imagen(imagen):
    """
    Procesa una imagen para "limpiar" el contenido colorido y conservar solo los tonos de gris.
    Se remueve el canal alfa (en caso de existir) y se aplica una máscara para mantener únicamente
    los píxeles en escala de grises.

    :param imagen: Imagen de entrada en formato NumPy (BGR o BGRA).
    :return: Imagen procesada en la que se han eliminado colores fuertes.
    """
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen Original", imagen)
    
    # Comprobar si la imagen tiene canal alfa (transparencia)
    if imagen.shape[2] == 4:
        # Separar canales de color y canal alfa
        bgr = imagen[:, :, :3]
        alpha = imagen[:, :, 3]
        # Crear un fondo blanco del mismo tamaño
        fondo_blanco = np.full_like(bgr, 255, dtype=np.uint8)
        # Normalizar el canal alfa a un rango [0, 1]
        alpha = alpha.astype(float) / 255.0
        alpha = alpha[:, :, np.newaxis]  # Agregar dimensión para multiplicación
        # Combinar la imagen con fondo blanco según la transparencia
        imagen_sin_transparencia = (bgr * alpha + fondo_blanco * (1 - alpha)).astype(np.uint8)
        if Config.DEBUG_PRINTS:
            print("Tiene transparencia")
    else:
        imagen_sin_transparencia = imagen.copy()
        if Config.DEBUG_PRINTS:
            print("No tiene transparencia")

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen sin transparencia", imagen_sin_transparencia)

    # Convertir la imagen a espacio de color HSV para facilitar la separación de tonos
    hsv = cv2.cvtColor(imagen_sin_transparencia, cv2.COLOR_BGR2HSV)
    
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen hsv", hsv)

    # Definir el rango para detectar colores intensos (fuera de escala de grises)
    lower_color = np.array([0, 150, 150])
    upper_color = np.array([180, 255, 255])
    mascara_colores = cv2.inRange(hsv, lower_color, upper_color)

    # Crear una imagen blanca que actuará como plantilla
    resultado = np.full_like(imagen_sin_transparencia, 255, dtype=np.uint8)
    # Conservar solo aquellos píxeles que NO estén dentro del rango de colores intensos,
    # dejando así únicamente los tonos de gris
    resultado[mascara_colores == 0] = imagen_sin_transparencia[mascara_colores == 0]

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen_Limpia", resultado)

    return resultado


def detectar_celdas(path_imagen):
    """
    Detecta las celdas en una imagen de una tabla, obteniendo recortes de cada celda y calculando
    sus centroides. Se utiliza para identificar la estructura de la tabla a partir de contornos.
    
    - Se carga la imagen desde la ruta especificada.
    - Se limpia la imagen eliminando colores no deseados.
    - Se verifica el "cierre" de la tabla (por ejemplo, asegurar que los bordes estén completos).
    - Se extraen los contornos relevantes utilizando funciones definidas en 'dcc'.
    - Se calculan los momentos y centroides, y se guarda la información de cada celda.
    - Se dibujan los rectángulos y se muestran los centroides para verificación visual (usando OpenCV).
    
    :param path_imagen: Ruta al archivo de imagen que contiene la tabla.
    :return: Tuple que contiene:
             - imagenes_celdas: Lista de imágenes (cortes) de cada celda.
             - coordenadas_celdas: Lista de tuplas (id_celda, x, y, w, h) de cada celda.
             - coordenadas_centros: Lista de tuplas (id_celda, cX, cY) con el centro de cada celda.
             - imagen_width: Ancho original de la imagen.
             - imagen_height: Alto original de la imagen.
             - dimensiones_tabla: Tuple (xt1, xt2, yt1, yt2) que delimita el área completa de la tabla.
    """
    # Cargar la imagen
    image = cv2.imread(path_imagen, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen en: {path_imagen}")

    # Procesar la imagen para eliminar colores no deseados y dejar solo tonos de gris
    clean_image = limpiar_imagen(image)

    # Verificar y corregir el cierre de la tabla (se llama a un módulo externo para esto)
    clean_image = vtc.verificar_cierre(clean_image)

    # Mostrar imagen limpia para revisión
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen limpia........", clean_image)

    # Extraer contornos de la imagen utilizando funciones del módulo dcc
    contours_to_keep = dcc.cargar_imagen(clean_image)

    cropped_images = []  # Lista para almacenar datos de cada celda detectada
    id_celda = 1         # Identificador único para cada celda

    # Inicializar variables para delimitar el área global de la tabla
    xt1 = float('inf')   # Menor valor de X detectado
    yt1 = float('inf')   # Menor valor de Y detectado
    xt2 = 0              # Mayor valor en X + ancho
    yt2 = 0              # Mayor valor en Y + alto

    for contour in contours_to_keep:
        # Calcular el perímetro del contorno
        perimeter = cv2.arcLength(contour, True)
        # Aproximar el contorno a una forma poligonal simple
        approx = cv2.approxPolyDP(contour, 0.015 * perimeter, True)

        # Si el contorno aproximado tiene 4 lados, se considera como posible celda
        if len(approx) == 4:
            # Calcular el ángulo en cada vértice y comprobar si es aproximadamente un cuadrado
            es_cuadrado = all(80 <= calcular_angulo(approx[i] - approx[(i - 1) % 4],
                                                    approx[(i + 1) % 4] - approx[i]) <= 100 
                                for i in range(4))
            # Si cumple con ser cuadrado, continuar con el procesamiento
            if es_cuadrado:
                # Calcular momentos para encontrar el centroide
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    # Obtener el bounding rectangle (cuadro delimitador) de la celda
                    x, y, w, h = cv2.boundingRect(approx)
                    if Config.DEBUG_PRINTS:
                        print("x, w, y, h:", x, w, y, h)
                    # Actualizar límites globales de la tabla
                    xt1 = min(xt1, x)
                    yt1 = min(yt1, y)
                    xt2 = max(xt2, x + w)
                    yt2 = max(yt2, y + h)
                    # Extraer el recorte de la celda de la imagen limpia
                    cropped = clean_image[y:y+h, x:x+w]
                    # Almacenar los datos de la celda en un diccionario
                    cropped_images.append({
                        "id_celda": id_celda,
                        "imagen": cropped,
                        "coordenadas": (id_celda, x, y, w, h),
                        "centroide": (id_celda, cX, cY)
                    })
                    id_celda += 1

    # Ordenar las celdas en función de la posición de sus centroides
    sorted_images = sort_cropped_images(cropped_images, tolerance=10)

    # Extraer listas separadas para imágenes, coordenadas y centroides
    imagenes_celdas = [img_data["imagen"] for img_data in sorted_images]
    coordenadas_celdas = [img_data["coordenadas"] for img_data in sorted_images]
    coordenadas_centros = [img_data["centroide"] for img_data in sorted_images]

    # Obtener las dimensiones de la imagen original
    imagen_height, imagen_width, _ = image.shape
    # Las dimensiones globales de la tabla se basan en los límites detectados
    dimensiones_tabla = (xt1, xt2, yt1, yt2)

    # Dibujar los rectángulos y centroides sobre la imagen limpia para verificación visual
    image_copy = clean_image.copy()
    for (id_celda, x, y, w, h), (_, cX, cY) in zip(coordenadas_celdas, coordenadas_centros):
        cv2.rectangle(image_copy, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Dibujar rectángulo en verde
        cv2.circle(image_copy, (cX, cY), 5, (0, 0, 255), -1)             # Dibujar centroide en rojo
        cv2.putText(image_copy, str(id_celda), (x + 5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    # Mostrar la imagen con los rectángulos y centroides detectados
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Celdas Detectadas", image_copy)

    return imagenes_celdas, coordenadas_celdas, coordenadas_centros, imagen_width, imagen_height, dimensiones_tabla
