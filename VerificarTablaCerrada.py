import cv2
import numpy as np
import Config

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1280, max_alto=720):
    """
    Muestra la imagen redimensionada si excede el tamaño máximo, manteniendo la relación de aspecto.
    
    Esta función calcula una escala que se ajusta al tamaño máximo deseado (max_ancho, max_alto)
    y redimensiona la imagen si es necesario, para luego mostrarla en una ventana OpenCV.
    
    :param name_image: Nombre de la ventana donde se mostrará la imagen.
    :param image: Imagen (numpy array) a mostrar.
    :param max_ancho: Ancho máximo permitido para la imagen mostrada.
    :param max_alto: Alto máximo permitido para la imagen mostrada.
    """
    # Obtener dimensiones originales de la imagen
    alto_original, ancho_original = image.shape[:2]
    # Calcular el factor de escala basado en el ancho y alto máximo permitidos
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    # Si la escala es menor que 1, la imagen se reduce
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    # Mostrar la imagen redimensionada
    cv2.imshow(name_image, image)

def detectar_bordes_oscuros(image, axis):
    """
    Detecta bordes oscuros en la imagen y dibuja una línea en la posición del píxel más cercano al borde.
    
    La función analiza una región en uno de los bordes de la imagen (definido por el parámetro 'axis').
    Se convierte la imagen a espacio de color HSV para facilitar la detección de píxeles oscuros.
    Dependiendo de 'axis' ("top", "bottom", "left" o "right"), se extraen las primeras filas/columnas
    o las últimas filas/columnas, se crea una máscara para detectar píxeles oscuros y se determina la posición
    del borde. Finalmente, se dibuja una línea negra (con grosor 2) a lo largo del borde detectado.
    
    :param image: Imagen en formato BGR (numpy array).
    :param axis: Lado de la imagen a analizar ("top", "bottom", "left", o "right").
    """
    h, w = image.shape[:2]
    num_filas = 20  # Número de filas o columnas a analizar en el borde

    # Convertir la imagen a HSV para una mejor detección de tonos oscuros
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Definir el rango de colores que se consideran "oscuros"
    lower_dark = np.array([0, 0, 0])
    upper_dark = np.array([180, 255, 115])

    # Extraer la región de interés dependiendo del lado
    if axis == "top":
        region = hsv[:num_filas, :, :]
        mask = cv2.inRange(region, lower_dark, upper_dark)
        indices = np.column_stack(np.where(mask > 0))
        y = np.min(indices[:, 0]) if indices.size > 0 else 0
    elif axis == "bottom":
        region = hsv[-num_filas:, :, :]
        mask = cv2.inRange(region, lower_dark, upper_dark)
        indices = np.column_stack(np.where(mask > 0))
        y = h - (num_filas - np.max(indices[:, 0])) if indices.size > 0 else h - 1
    elif axis == "left":
        region = hsv[:, :num_filas, :]
        mask = cv2.inRange(region, lower_dark, upper_dark)
        indices = np.column_stack(np.where(mask > 0))
        x = np.min(indices[:, 1]) if indices.size > 0 else 0
    elif axis == "right":
        region = hsv[:, -num_filas:, :]
        mask = cv2.inRange(region, lower_dark, upper_dark)
        indices = np.column_stack(np.where(mask > 0))
        x = w - (num_filas - np.max(indices[:, 1])) if indices.size > 0 else w - 1
    else:
        return

    # Si se han detectado píxeles oscuros, se calcula el inicio y fin de la línea
    if indices.size > 0:
        # Para "top" o "bottom", se agrupan las posiciones en la dirección horizontal; para "left"/"right", en la vertical.
        inicio = np.min(indices[:, 1] if axis in ["top", "bottom"] else indices[:, 0])
        fin = np.max(indices[:, 1] if axis in ["top", "bottom"] else indices[:, 0])
        
        color_linea = (0, 0, 0)  # Color negro para la línea
        
        # Dibujar la línea en la posición detectada del borde
        if axis in ["top", "bottom"]:
            cv2.line(image, (inicio, y), (fin, y), color_linea, 2)
        else:  # Caso "left" o "right"
            cv2.line(image, (x, inicio), (x, fin), color_linea, 2)

def verificar_cierre(image):
    """
    Verifica que la tabla representada en una imagen esté "cerrada" en sus bordes.

    La función aplica la detección de bordes oscuros en los cuatro lados de la imagen (superior, inferior,
    izquierdo y derecho) para determinar si existe un contorno definido. Posteriormente, une las líneas cercanas
    mediante una operación morfológica para mejorar la detección de contornos.
    
    :param image: Imagen en formato BGR (numpy array).
    :return: Imagen modificada, en la que los bordes han sido "cerrados" y las líneas unidas.
    """
    # Detecta los bordes oscuros en cada lado
    detectar_bordes_oscuros(image, "top")
    detectar_bordes_oscuros(image, "bottom")
    detectar_bordes_oscuros(image, "left")
    detectar_bordes_oscuros(image, "right")

    # Unir las líneas que están muy cercanas entre sí para formar un contorno continuo
    image = unir_lineas_cercanas(image, kernel_size=3, iterations=2)

    return image

def unir_lineas_cercanas(image, kernel_size=3, iterations=1):
    """
    Une las líneas que están muy cercanas entre sí para mejorar la detección de contornos.

    Procedimiento:
      1. Si la imagen es en color, se convierte a escala de grises.
      2. Se aplica umbralización para obtener una imagen binaria invertida (líneas en negro sobre fondo blanco).
      3. Se utiliza dilatación para engrosar las líneas y unir espacios pequeños.
      4. Se aplica erosión para refinar y unir las líneas continuas.
      5. Se invierte la imagen resultante y se la convierte a formato BGR.
    
    :param image: Imagen de entrada (en escala de grises o color).
    :param kernel_size: Tamaño del kernel (matriz de unos) para operaciones de dilatación y erosión.
    :param iterations: Número de iteraciones para las operaciones morfológicas.
    :return: Imagen procesada con líneas unidas, en formato BGR.
    """
    # Convertir la imagen a escala de grises si es una imagen a color
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Aplicar umbral para obtener una imagen binaria invertida (líneas en negro)
    _, binary = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY_INV)

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen_Binarizada", binary)

    # Crear un kernel de unos para la dilatación
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=iterations)

    # Aplicar erosión para unir líneas fragmentadas
    eroded = cv2.erode(dilated, kernel, iterations=iterations)

    # Invertir la imagen para recuperar líneas negras sobre fondo blanco
    final_image = cv2.bitwise_not(eroded)
    
    # Convertir la imagen final a BGR para mantener el formato original
    final_image = cv2.cvtColor(final_image, cv2.COLOR_GRAY2BGR)
    
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Verificar tabla cerrada:", final_image)

    return final_image

# Código de prueba (comentado):
# La parte comentada a continuación es para pruebas individuales.
# Se puede descomentar para ejecutar la función sobre una imagen.
#
# image = cv2.imread("imagenes_De_Prueba/tabla_17_4.png", cv2.IMREAD_UNCHANGED)
# if image is None:
#     raise FileNotFoundError("No se pudo cargar la imagen.")
#
# image = verificar_cierre(image)
# image = unir_lineas_cercanas(image, kernel_size=3, iterations=2)
# cv2.imshow("Resultado", image)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
