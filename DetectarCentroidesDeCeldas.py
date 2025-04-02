import cv2
import numpy as np
import VerificarTablaCerrada as vtc
import DibujarContornosCuadrados as dcc
import Config

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1600, max_alto=900):
    """Muestra la imagen redimensionada si excede el tamaño máximo, manteniendo la relación de aspecto."""
    alto_original, ancho_original = image.shape[:2]
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    cv2.imshow(name_image, image)

def calcular_angulo(v1, v2):
    """Calcula el ángulo entre dos vectores en grados."""
    v1 = v1.flatten()
    v2 = v2.flatten()
    cos_angulo = np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1.0, 1.0)
    return np.degrees(np.arccos(cos_angulo))

def sort_cropped_images(cropped_images, tolerance=4):
    """Ordena las imágenes recortadas en una sola lista basada en sus centroides."""
    cropped_images.sort(key=lambda x: (x["centroide"][1], x["centroide"][0]))  # Ordenar por Y y luego por X
    return cropped_images

def limpiar_imagen(imagen):
    """Elimina colores y conserva solo escala de grises (de gris claro a negro)."""

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen Original",imagen)
    
    if imagen.shape[2] == 4:  # Si tiene canal alfa (transparencia)
        bgr = imagen[:, :, :3]  # Canales de color
        alpha = imagen[:, :, 3]  # Canal alfa
        fondo_blanco = np.full_like(bgr, 255, dtype=np.uint8)
        alpha = alpha.astype(float) / 255.0
        alpha = alpha[:, :, np.newaxis]
        imagen_sin_transparencia = (bgr * alpha + fondo_blanco * (1 - alpha)).astype(np.uint8)
        if Config.DEBUG_PRINTS:
            print("Tiene transparencia")
    else:
        imagen_sin_transparencia = imagen.copy()
        if Config.DEBUG_PRINTS:
            print("No tiene transparencia")

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen sin transparencia",imagen_sin_transparencia)

    # Convertimos a HSV
    hsv = cv2.cvtColor(imagen_sin_transparencia, cv2.COLOR_BGR2HSV)
    
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen hsv",hsv)

    # Máscara para colores (excluye escala de grises)
    lower_color = np.array([0, 150, 150])   # Valores con saturación alta (color)
    upper_color = np.array([180, 255, 255])
    mascara_colores = cv2.inRange(hsv, lower_color, upper_color)

    # Crear una imagen blanca
    resultado = np.full_like(imagen_sin_transparencia, 255, dtype=np.uint8)

    # Conservar solo los píxeles en escala de grises (no detectados en la máscara de colores)
    resultado[mascara_colores == 0] = imagen_sin_transparencia[mascara_colores == 0]

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Imagen_Limpia",resultado)

    return resultado


def detectar_celdas(path_imagen):
    """Detecta las celdas en una imagen de tabla y retorna las celdas ordenadas junto con sus centroides."""
    # Cargar la imagen
    image = cv2.imread(path_imagen, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"No se pudo cargar la imagen en: {path_imagen}")

    # Limpiar imagen
    clean_image = limpiar_imagen(image)

    clean_image = vtc.verificar_cierre(clean_image)

    contours_to_keep = dcc.cargar_imagen(clean_image)

    # cv2.waitKey(0)

    # # Convertir a escala de grises y binarizar
    # gray = cv2.cvtColor(clean_image, cv2.COLOR_BGR2GRAY)
    # # _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

    # if Config.DEBUG_IMAGES:
    #   cv2.imshow("Gausiano",binary)

    # # Encontrar contornos
    # contours, _ = cv2.findContours(gray, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    # # Filtrar contornos grandes (evitar bordes de la imagen)
    # height, width = gray.shape
    # image_area = height * width
    # area_chica_threshold = image_area*0.0005
    # area_grande_threshold = image_area*0.5
    # contours_to_keep = [c for c in contours if cv2.contourArea(c) < 0.75 * image_area]

    # # Lista para almacenar las celdas detectadas
    cropped_images = []

    id_celda = 1

    # Inicializar límites de la tabla
    xt1 = float('inf')  # x más a la izquierda
    yt1 = float('inf')  # y más arriba
    xt2 = 0             # x+w más a la derecha
    yt2 = 0             # y+h más abajo

    for contour in contours_to_keep:
        # area = cv2.contourArea(contour)
        # if area > area_chica_threshold and area < area_grande_threshold:
        perimeter = cv2.arcLength(contour, True)


        approx = cv2.approxPolyDP(contour, 0.015 * perimeter, True)

        # clean_image_copy = clean_image.copy()

        # cv2.drawContours(clean_image_copy, [approx], -1, (0, 255, 0), 2)

        # if Config.DEBUG_IMAGES:
        #   mostrar_imagen_redimensionada("contornos a mantener", clean_image_copy)
        # if Config.DEBUG_IMAGES:
            # cv2.imshow("contornos a mantener",clean_image_copy)

        # cv2.waitKey(0)

        if len(approx) == 4:  # Verificar si tiene 4 lados
            es_cuadrado = all(80 <= calcular_angulo(approx[i] - approx[(i - 1) % 4], 
                                                    approx[(i + 1) % 4] - approx[i]) <= 100 
                                for i in range(4))

            if es_cuadrado:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cX, cY = int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])
                    x, y, w, h = cv2.boundingRect(approx)
                    if Config.DEBUG_PRINTS:
                        print("x,w,y,h\n",x,w,y,h)
                    # Actualizar límites de la tabla
                    if x < xt1:
                        xt1 = x
                    if y < yt1:
                        yt1 = y
                    if x + w > xt2:
                        xt2 = x + w
                    if y + h > yt2:
                        yt2 = y + h

                    # Guardar información de la celda
                    cropped = clean_image[y:y+h, x:x+w]

                    cropped_images.append({
                        "id_celda": id_celda,  # Asignar identificador único
                        "imagen": cropped,
                        "coordenadas": (id_celda, x, y, w, h),  # Incluir ID junto con coordenadas
                        "centroide": (id_celda, cX, cY)  # Incluir ID junto con el centro
                    })

                    id_celda += 1  # Incrementar ID para la siguiente celda

    # Ordenar celdas en una sola lista
    sorted_images = sort_cropped_images(cropped_images, tolerance=10)

    # Extraer las imágenes y los centroides en listas separadas
    imagenes_celdas = [img_data["imagen"] for img_data in sorted_images]
    # if Config.DEBUG_IMAGES:
        # cv2.imshow(path_imagen,clean_image)

        # for i in imagenes_celdas:
        #     cv2.imshow("celda encontrada",i)
        #     cv2.waitKey(0)



    coordenadas_celdas = [img_data["coordenadas"] for img_data in sorted_images]
    coordenadas_centros = [img_data["centroide"] for img_data in sorted_images]
    imagen_height, imagen_width, _ = image.shape

        # **Dibujar las celdas detectadas en la imagen original**
    image_copy = clean_image.copy()
    
    celdas_revisar = []

    for (id_celda, x, y, w, h), (id_celda_centro, cX, cY) in zip(coordenadas_celdas, coordenadas_centros):
        cv2.rectangle(image_copy, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Rectángulo verde
        cv2.circle(image_copy, (cX, cY), 5, (0, 0, 255), -1)  # Centroide rojo
        cv2.putText(image_copy, str(id_celda), (x + 5, y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        celdas_revisar.append(image_copy[y:y+h, x:x+w])


    dimensiones_tabla = (xt1, xt2, yt1, yt2)
    
    # Mostrar la imagen con celdas resaltadas
    # if Config.DEBUG_IMAGES:
    #   cv2.imshow("Celdas Detectadas", image_copy)
    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("Celdas Detectadas",image_copy)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    # if Config.DEBUG_IMAGES:
        # for i in celdas_revisar:
            # cv2.imshow("celda a revisar",i)
            # cv2.waitKey(0)


    return imagenes_celdas, coordenadas_celdas, coordenadas_centros, imagen_width, imagen_height, dimensiones_tabla
