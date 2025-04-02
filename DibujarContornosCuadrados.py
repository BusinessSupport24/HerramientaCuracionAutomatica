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

def calcular_angulo(p1, p2, p3):
    """Calcula el ángulo formado por tres puntos en un contorno."""
    v1 = np.array(p1, dtype=np.float32) - np.array(p2, dtype=np.float32)
    v2 = np.array(p3, dtype=np.float32) - np.array(p2, dtype=np.float32)
    
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    
    if norm_v1 == 0 or norm_v2 == 0:
        return 180
    
    cos_theta = np.clip(dot_product / (norm_v1 * norm_v2), -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))

def calcular_distancia(p1, p2):
    """Calcula la distancia euclidiana entre dos puntos."""
    return np.linalg.norm(np.array(p1) - np.array(p2))



def eliminar_vertices_alineados(contour, threshold_angle=170, min_distance=10):
    """
    Elimina vértices innecesarios de un contorno si están en una línea recta, usando un recorrido circular.

    Parámetros:
    - contour: array de puntos (vértices) del contorno.
    - threshold_angle: umbral en grados para considerar que los puntos están alineados (default 170°).
    - min_distance: distancia mínima entre los puntos para evaluar el ángulo correctamente.

    Retorna:
    - Un nuevo contorno simplificado.
    """
    if len(contour) < 3:
        return contour  # No se puede simplificar si hay menos de 3 puntos

    # if Config.DEBUG_PRINTS:
    #   print("Contorno Original:")
    # for i, punto in enumerate(contour):
    #     if Config.DEBUG_PRINTS:
    #       print(f"  Vértice #{i}: Coordenadas: {punto[0]}")

    contour = list(contour)  # Convertimos el contorno a una lista mutable
    n = len(contour)
    i = 0  # Índice de inicio
    eliminaciones = 0  # Contador de eliminaciones
    evaluaciones = 0  # Contador de evaluaciones para evitar ciclos infinitos

    while eliminaciones < n and evaluaciones < n * 2:  
        if len(contour) < 3:
            break  # Si quedan menos de 3 puntos, terminamos

        v0 = contour[i - 1][0]  # Punto anterior (circular, -1 equivale al último)
        v1 = contour[i][0]  # Punto actual
        next_index = (i + 1) % len(contour)  # Índice circular para el siguiente punto válido

        # Buscar un punto v2 que no esté demasiado cerca de v1
        while next_index != i and np.linalg.norm(contour[next_index][0] - v1) < min_distance:
            next_index = (next_index + 1) % len(contour)

        if next_index == i:  # No se encontró un punto v2 válido
            i = (i + 1) % len(contour)
            evaluaciones += 1
            continue

        v2 = contour[next_index][0]  # Nuevo punto de referencia

        # Buscar un nuevo v1 si está demasiado cerca de v0
        if np.linalg.norm(v1 - v0) < min_distance:
            i = (i + 1) % len(contour)
            evaluaciones += 1
            continue  # Volver a evaluar con un nuevo v1

        # Vectores
        vec1 = v1 - v0
        vec2 = v2 - v1

        # Normalización de los vectores
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            i = (i + 1) % len(contour)
            evaluaciones += 1
            continue

        # Calcular el ángulo usando el producto escalar
        cos_theta = np.dot(vec1, vec2) / (norm1 * norm2)
        angle = np.degrees(np.arccos(np.clip(cos_theta, -1.0, 1.0)))  # Convertir a grados
        
        # if Config.DEBUG_PRINTS:
        #   print(f"  Evaluando vértice #{i}: {v1}, Ángulo entre [{v0} → {v1} → {v2}]: {angle:.2f}°")

        if angle >= threshold_angle or angle <= 10:
            # if Config.DEBUG_PRINTS:
            #   print(f"  → Eliminando el vértice #{i}")
            contour.pop(i)  # Eliminamos el vértice
            eliminaciones += 1  # Aumentamos el contador de eliminaciones
            n -= 1  # Disminuimos la cantidad de vértices
            i = i % len(contour)  # Nos aseguramos de seguir dentro del índice correcto
        else:
            # if Config.DEBUG_PRINTS:
            #   print(f"  → Manteniendo el vértice #{i}")
            i = (i + 1) % len(contour)  # Pasamos al siguiente vértice

        evaluaciones += 1

        # Si hicimos más evaluaciones que el doble de los vértices originales, paramos
        if evaluaciones >= n * 2:
            break  

    nuevo_contorno = np.array(contour, dtype=np.int32)
    
    # if Config.DEBUG_PRINTS:
    #   print("\nContorno Modificado:")
    # for i, punto in enumerate(nuevo_contorno):
    #     if Config.DEBUG_PRINTS:
    #       print(f"  Vértice #{i}: Coordenadas: {punto[0]}")

    # if Config.DEBUG_PRINTS:
    #   print("\n")

    return nuevo_contorno

def cargar_imagen(image):
    """Carga una imagen, encuentra y filtra los contornos."""
    if len(image.shape) == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    _, binary = cv2.threshold(image, 150, 255, cv2.THRESH_BINARY_INV)
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    alto, ancho = image.shape
    area_min = (alto * ancho) / 2000
    
    hierarchy = hierarchy[0] if hierarchy is not None else []

    # Filtrar contornos por área
    filtered_contours = []
    index_map = {}  # Mapeo de índices originales a índices filtrados
    new_hierarchy_list = []

    new_index = 0
    for i, cnt in enumerate(contours):
        if cv2.contourArea(cnt) >= area_min:
            filtered_contours.append(cnt)
            index_map[i] = new_index  # Guardar nuevo índice
            new_hierarchy_list.append(list(hierarchy[i]))  # Copiar la jerarquía original
            new_index += 1

    # Ajustar la jerarquía para reflejar los nuevos índices
    if filtered_contours:
        new_hierarchy = np.array(new_hierarchy_list)

        for i in range(len(new_hierarchy)):
            for j in range(4):  # Actualizar (Next, Previous, First_Child, Parent)
                if new_hierarchy[i][j] != -1 and new_hierarchy[i][j] in index_map:
                    new_hierarchy[i][j] = index_map[new_hierarchy[i][j]]
                else:
                    new_hierarchy[i][j] = -1  # Si el índice original no está, eliminamos la referencia

    else:
        new_hierarchy = None

    if new_hierarchy is not None:
        contornos_sin_hijos = [filtered_contours[i] for i in range(len(filtered_contours)) if new_hierarchy[i][2] == -1]
    else:
        contornos_sin_hijos = filtered_contours  # Si no hay jerarquía, todos los contornos son válidos

    
    image_sin_hijos = cv2.cvtColor(image.copy(), cv2.COLOR_GRAY2BGR)

    cv2.drawContours(image_sin_hijos, contornos_sin_hijos, -1, (0, 255, 0), 1)

    # if Config.DEBUG_IMAGES:
    #   mostrar_imagen_redimensionada("image_sin_hijos", image_sin_hijos)

    result = cv2.cvtColor(image.copy(), cv2.COLOR_GRAY2BGR)

    for idx, cnt in enumerate(contornos_sin_hijos):
        nuevo_contorno = eliminar_vertices_alineados(cnt)
        contornos_sin_hijos[idx]=nuevo_contorno

        # result = cv2.cvtColor(image.copy(), cv2.COLOR_GRAY2BGR)

        cv2.drawContours(result, [nuevo_contorno], -1, (0, 255, 0), 3)
        idv=0
        for point in nuevo_contorno:
            x, y = point[0]
            cv2.circle(result, (x, y), 5, (0, 0, 255), -1)
            cv2.putText(result, str(idv), (x+5, y+5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            # if Config.DEBUG_PRINTS:
            #   print(f"Dibujando vertice #{idv} con coords [{x} {y}]")
            idv+=1

        M = cv2.moments(nuevo_contorno)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            cv2.putText(result, str(idx), (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        
        # input()
        if Config.DEBUG_IMAGES:
            mostrar_imagen_redimensionada("Resultado", result)
    
    return contornos_sin_hijos

    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
