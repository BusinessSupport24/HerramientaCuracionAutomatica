import cv2
import numpy as np
import Config

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1280, max_alto=720):
    """Muestra la imagen redimensionada si excede el tamaño máximo, manteniendo la relación de aspecto."""
    alto_original, ancho_original = image.shape[:2]
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    cv2.imshow(name_image, image)

def detectar_bordes_oscuros(image, axis):
    """
    Detecta bordes oscuros en la imagen y dibuja una línea en la posición del píxel más cercano al borde.
    """

    h, w = image.shape[:2]
    num_filas = 20  # Analizar las primeras 3 filas o columnas

    # Convertir imagen a HSV para detectar colores oscuros
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # Definir rango de colores oscuros
    lower_dark = np.array([0, 0, 0])      # Mínimo tono, saturación y valor
    upper_dark = np.array([180, 255, 115])  # Máximo tono, saturación y valor

    # Extraer la región a analizar según el borde
    if axis == "top":
        region = hsv[:num_filas, :, :]
        mask = cv2.inRange(region, lower_dark, upper_dark)
        indices = np.column_stack(np.where(mask > 0))  # Obtener coordenadas de píxeles oscuros
        y = np.min(indices[:, 0]) if indices.size > 0 else 0  # Tomar el píxel más cercano al borde
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

    # Encontrar los límites izquierdo y derecho de la línea
    if indices.size > 0:
        inicio = np.min(indices[:, 1] if axis in ["top", "bottom"] else indices[:, 0])
        fin = np.max(indices[:, 1] if axis in ["top", "bottom"] else indices[:, 0])
        
        color_linea = (0, 0, 0)  # Color negro en BGR
        
        # Dibujar la línea en la posición exacta del borde detectado
        if axis in ["top", "bottom"]:
            cv2.line(image, (inicio, y), (fin, y), color_linea, 2)
        else:  # "left" o "right"
            cv2.line(image, (x, inicio), (x, fin), color_linea, 2)

def verificar_cierre(image):
    """Aplica la detección de bordes oscuros en cada lado de la imagen."""
    detectar_bordes_oscuros(image, "top")
    detectar_bordes_oscuros(image, "bottom")
    detectar_bordes_oscuros(image, "left")
    detectar_bordes_oscuros(image, "right")

    image = unir_lineas_cercanas(image, kernel_size=3, iterations=2)

    return image

def unir_lineas_cercanas(image, kernel_size=3, iterations=1):
    """
    Une las líneas que están muy cercanas entre sí para mejorar la detección de contornos.
    """
    # Convertir la imagen a escala de grises si no lo está
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # Aplicar binarización
    _, binary = cv2.threshold(gray, 170, 255, cv2.THRESH_BINARY_INV)

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen_Binarizada",binary)

    # Aplicar dilatación para engrosar líneas y unir espacios pequeños
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    dilated = cv2.dilate(binary, kernel, iterations=iterations)

    eroded = cv2.erode(dilated, kernel, iterations=iterations)

    # Invertir la imagen nuevamente para mantener formato original
    final_image = cv2.bitwise_not(eroded)

    final_image = cv2.cvtColor(final_image, cv2.COLOR_GRAY2BGR)
    
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Verificar tabla cerrada:",final_image)

    return final_image

# # Cargar la imagen
# image = cv2.imread("imagenes_De_Prueba/tabla_17_4.png", cv2.IMREAD_UNCHANGED)

# if image is None:
#     raise FileNotFoundError("No se pudo cargar la imagen.")

# # Aplicar la corrección de bordes oscuros
# image = verificar_cierre(image)

# # Unir líneas que están muy cercanas para mejorar la detección de contornos
# image = unir_lineas_cercanas(image, kernel_size=3, iterations=2)

# # Mostrar la imagen corregida
# cv2.imshow("Resultado", image)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
