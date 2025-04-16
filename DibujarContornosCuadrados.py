import cv2
import numpy as np
import Config

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1280, max_alto=720):
    """
    Muestra la imagen redimensionada si excede un tamaño máximo dado, manteniendo la relación de aspecto.

    Se calcula un factor de escala que ajusta la imagen para que el ancho no supere max_ancho
    y el alto max_alto. Si la escala es menor que 1 (la imagen es muy grande), se redimensiona.

    :param name_image: Nombre de la ventana donde se mostrará la imagen.
    :param image: Imagen como array NumPy.
    :param max_ancho: Ancho máximo permitido (por defecto 1280).
    :param max_alto: Alto máximo permitido (por defecto 720).
    """
    alto_original, ancho_original = image.shape[:2]
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    # Si la escala es menor que 1, la imagen excede el tamaño deseado y se redimensiona.
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        # Redimensionar la imagen usando interpolación INTER_AREA para reducirla
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    # Mostrar la imagen en una ventana con el nombre especificado.
    cv2.imshow(name_image, image)


def calcular_angulo(p1, p2, p3):
    """
    Calcula el ángulo formado en el punto p2 dado tres puntos (p1, p2, p3) que pertenecen a un contorno.

    Se crean dos vectores: uno desde p2 a p1 y otro desde p2 a p3. Luego se utiliza el producto
    escalar para calcular el coseno del ángulo entre ellos, y se convierte a grados.

    :param p1: Coordenada del primer punto (por ejemplo, anterior a p2).
    :param p2: Coordenada del vértice donde se calcula el ángulo.
    :param p3: Coordenada del tercer punto (posterior a p2).
    :return: Ángulo en grados formado en p2.
    """
    # Convertir los puntos a arrays NumPy de tipo float32 y calcular los vectores v1 y v2
    v1 = np.array(p1, dtype=np.float32) - np.array(p2, dtype=np.float32)
    v2 = np.array(p3, dtype=np.float32) - np.array(p2, dtype=np.float32)
    
    # Calcular el producto escalar y las normas (magnitudes) de los vectores
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    # Si alguno de los vectores tiene norma cero, retornar 180° (ángulo indefinido)
    if norm_v1 == 0 or norm_v2 == 0:
        return 180
    
    # Calcular el coseno del ángulo y luego el ángulo en grados utilizando arccos
    cos_theta = np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))


def calcular_distancia(p1, p2):
    """
    Calcula la distancia euclidiana entre dos puntos.

    :param p1: Primera coordenada (tuple o array NumPy).
    :param p2: Segunda coordenada (tuple o array NumPy).
    :return: Distancia euclidiana entre p1 y p2.
    """
    return np.linalg.norm(np.array(p1) - np.array(p2))


def eliminar_vertices_alineados(contour, threshold_angle=170, min_distance=10):
    """
    Elimina vértices que resultan innecesarios en un contorno si se encuentran casi en línea recta.
    
    Para cada vértice del contorno se calcula el ángulo formado con el vértice anterior y el siguiente.
    Si el ángulo es muy cercano a 180° (o menor a 10°) se considera que el vértice está alineado y se elimina.
    Se utiliza un recorrido circular para asegurar la continuidad del contorno.

    :param contour: Array de puntos (vértices) del contorno.
    :param threshold_angle: Umbral en grados para considerar que el vértice es redundante (por defecto 170°).
    :param min_distance: Distancia mínima entre puntos para hacer una evaluación válida.
    :return: Contorno simplificado como array de NumPy con los vértices eliminados.
    """
    # Si el contorno tiene menos de 3 puntos, no se puede simplificar
    if len(contour) < 3:
        return contour

    # Convertir el contorno a una lista mutable
    contour = list(contour)
    n = len(contour)
    i = 0           # Índice de iteración
    eliminaciones = 0  # Contador de vértices eliminados
    evaluaciones = 0   # Contador para evitar bucles infinitos

    # Recorrer el contorno de manera circular hasta cumplir con los criterios de salida
    while eliminaciones < n and evaluaciones < n * 2:
        # Si el contorno se ha simplificado a menos de 3 puntos, salir del bucle
        if len(contour) < 3:
            break

        # Obtener el vértice actual, el anterior (de forma circular) y el siguiente
        v0 = contour[i - 1][0]  # Si i es 0, se toma el último punto
        v1 = contour[i][0]
        next_index = (i + 1) % len(contour)  # Siguiente vértice

        # Saltar puntos cercanos: si el siguiente vértice está muy cerca de v1, avanzar
        while next_index != i and np.linalg.norm(contour[next_index][0] - v1) < min_distance:
            next_index = (next_index + 1) % len(contour)

        if next_index == i:
            # Si no se encuentra un vértice adecuado, avanzar al siguiente
            i = (i + 1) % len(contour)
            evaluaciones += 1
            continue

        v2 = contour[next_index][0]

        # Si v1 está demasiado cerca de v0, saltar este vértice
        if np.linalg.norm(v1 - v0) < min_distance:
            i = (i + 1) % len(contour)
            evaluaciones += 1
            continue

        # Calcular los vectores entre los puntos
        vec1 = v1 - v0
        vec2 = v2 - v1

        # Calcular las normas (magnitudes) de los vectores
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            i = (i + 1) % len(contour)
            evaluaciones += 1
            continue

        # Calcular el ángulo usando el producto escalar
        cos_theta = np.dot(vec1, vec2) / (norm1 * norm2)
        angle = np.degrees(np.arccos(np.clip(cos_theta, -1.0, 1.0)))  # Convertir el ángulo a grados
        
        # Comprobar si el ángulo indica alineación (muy cercano a 180° o muy pequeño)
        if angle >= threshold_angle or angle <= 10:
            # Eliminar el vértice actual
            contour.pop(i)
            eliminaciones += 1
            n -= 1  # Actualizar el número total de puntos
            i = i % len(contour)  # Asegurarse de que el índice se mantenga dentro del rango
        else:
            # Si el ángulo es adecuado, pasar al siguiente vértice
            i = (i + 1) % len(contour)

        evaluaciones += 1

        # Si se han hecho demasiadas evaluaciones, salir para evitar bucles infinitos
        if evaluaciones >= n * 2:
            break

    # Convertir la lista de vértices simplificada a un array NumPy
    nuevo_contorno = np.array(contour, dtype=np.int32)
    return nuevo_contorno


def cargar_imagen(image):
    """
    Carga una imagen de entrada, realiza el preprocesamiento para detectar contornos relevantes
    y filtra aquellos que se correspondan a celdas de una tabla.

    Pasos:
    1. Convertir la imagen a escala de grises (si es en color).
    2. Aplicar una binarización inversa para que los contornos sean detectables.
    3. Encontrar contornos usando findContours.
    4. Filtrar contornos basados en el área mínima para descartar ruido.
    5. Eliminar los contornos que son internos (utilizando la jerarquía).
    6. Simplificar cada contorno eliminando vértices alineados.
    7. Dibujar y mostrar los contornos simplificados (para depuración).

    :param image: Imagen de entrada (puede ser en BGR o escala de grises).
    :return: Lista de contornos procesados (simplificados).
    """
    # Convertir a escala de grises si la imagen es a color
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Aplicar binarización inversa para resaltar las áreas oscuras sobre fondo claro
    _, binary = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY_INV)
    
    # Encontrar contornos en la imagen binarizada
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    alto, ancho = image.shape
    area_min = (alto * ancho) / 2000  # Definir un umbral mínimo basado en el área de la imagen
    
    # Extraer la jerarquía (si existe)
    hierarchy = hierarchy[0] if hierarchy is not None else []

    filtered_contours = []
    index_map = {}         # Mapear índices originales a nuevos índices (si fuera necesario)
    new_hierarchy_list = []  # Almacenar la jerarquía filtrada

    new_index = 0
    # Filtrar los contornos por área
    for i, cnt in enumerate(contours):
        if cv2.contourArea(cnt) >= area_min:
            filtered_contours.append(cnt)
            index_map[i] = new_index
            new_hierarchy_list.append(list(hierarchy[i]))  # Guardar la jerarquía correspondiente
            new_index += 1

    # Ajustar la jerarquía de acuerdo a los nuevos índices
    if filtered_contours:
        new_hierarchy = np.array(new_hierarchy_list)
        for i in range(len(new_hierarchy)):
            for j in range(4):  # Actualizar Next, Previous, First_Child, Parent
                if new_hierarchy[i][j] != -1 and new_hierarchy[i][j] in index_map:
                    new_hierarchy[i][j] = index_map[new_hierarchy[i][j]]
                else:
                    new_hierarchy[i][j] = -1
    else:
        new_hierarchy = None

    # Si hay jerarquía, se extraen los contornos sin hijos (los que no contienen otros contornos)
    if new_hierarchy is not None:
        contornos_sin_hijos = [filtered_contours[i] for i in range(len(filtered_contours)) if new_hierarchy[i][2] == -1]
    else:
        contornos_sin_hijos = filtered_contours

    # Dibujar los contornos sin hijos en una copia de la imagen para visualización
    image_sin_hijos = cv2.cvtColor(image.copy(), cv2.COLOR_GRAY2BGR)
    cv2.drawContours(image_sin_hijos, contornos_sin_hijos, -1, (0, 255, 0), 1)

    # Preparar la imagen final para dibujar los contornos simplificados y centroides
    result = cv2.cvtColor(image.copy(), cv2.COLOR_GRAY2BGR)

    for idx, cnt in enumerate(contornos_sin_hijos):
        # Simplificar el contorno eliminando vértices que estén alineados
        nuevo_contorno = eliminar_vertices_alineados(cnt)
        contornos_sin_hijos[idx] = nuevo_contorno

        # Dibujar el contorno simplificado en color verde sobre la imagen de resultado
        cv2.drawContours(result, [nuevo_contorno], -1, (0, 255, 0), 3)
        idv = 0
        # Dibujar cada vértice y su índice para facilitar la depuración
        for point in nuevo_contorno:
            x, y = point[0]
            cv2.circle(result, (x, y), 5, (0, 0, 255), -1)  # Vértice en rojo
            cv2.putText(result, str(idv), (x + 5, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            idv += 1

        # Calcular el centroide del contorno y dibujar el índice del contorno
        M = cv2.moments(nuevo_contorno)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.putText(result, str(idx), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # Mostrar el resultado en cada iteración si se está en modo depuración
        if Config.DEBUG_IMAGES:
            mostrar_imagen_redimensionada("Resultado", result)
    
    # Retornar los contornos procesados (simplificados) para uso posterior en detección de celdas
    return contornos_sin_hijos
