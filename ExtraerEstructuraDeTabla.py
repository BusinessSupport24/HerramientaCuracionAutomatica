import cv2
import numpy as np
import Config
import RenderizarTablaHTML

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1600, max_alto=900):
    """Muestra la imagen redimensionada si excede el tamaño máximo, manteniendo la relación de aspecto."""
    alto_original, ancho_original = image.shape[:2]
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    cv2.imshow(name_image, image)

def generar_malla(coordenadas_celdas, imagen_width, imagen_height):
    """Genera una malla basada en las coordenadas de las celdas y la dibuja en una imagen en blanco."""

    # Encontrar la anchura y altura más pequeñas entre todas las celdas
    umbral_minimo = 0  # Declarado pero no se usa por ahora
    anchuras = [w for _, x, y, w, h in coordenadas_celdas]
    alturas = [h for _, x, y, w, h in coordenadas_celdas]

    min_anchura = min(anchuras) if anchuras else 10  # Evitar división por cero
    min_altura = min(alturas) if alturas else 10  # Evitar división por cero

    # Definir umbrales de agrupación
    umbral_x = min_anchura / 1.5
    umbral_y = min_altura / 1.5

    # Obtener todas las coordenadas únicas en X e Y
    coordenadas_x = sorted(set(x for _, x, _, _, _ in coordenadas_celdas))
    coordenadas_y = sorted(set(y for _, _, y, _, _ in coordenadas_celdas))

    # Generar las líneas de la malla agrupando por umbral
    def agrupar_coordenadas(coordenadas, umbral):
        """Agrupa coordenadas cercanas usando un umbral de distancia."""
        if not coordenadas:
            return []
        grupos = [[coordenadas[0]]]
        for coord in coordenadas[1:]:
            if abs(coord - grupos[-1][-1]) <= umbral:
                grupos[-1].append(coord)
            else:
                grupos.append([coord])
        return [int(np.mean(grupo)) for grupo in grupos]

    # Agrupar coordenadas para definir las líneas de la malla
    lineas_x = agrupar_coordenadas(coordenadas_x, umbral_x)
    lineas_y = agrupar_coordenadas(coordenadas_y, umbral_y)

    # Determinar la cantidad de filas y columnas en la malla
    max_columnas = len(lineas_x)
    max_filas = len(lineas_y)

    # Crear una imagen en blanco del tamaño de la imagen original
    imagen_malla = np.ones((imagen_height, imagen_width, 3), dtype=np.uint8) * 255

    # Dibujar líneas verticales
    for x in lineas_x:
        cv2.line(imagen_malla, (x, 0), (x, imagen_height), (0, 0, 0), 1)

    # Dibujar líneas horizontales
    for y in lineas_y:
        cv2.line(imagen_malla, (0, y), (imagen_width, y), (0, 0, 0), 1)

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("malla creada",imagen_malla)

    # Mostrar la imagen con la malla generada
    # if Config.DEBUG_IMAGES:
    #   cv2.imshow("Malla Generada", imagen_malla)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    return lineas_x, lineas_y, max_filas, max_columnas, imagen_malla, umbral_x, umbral_y




def generar_estructura_tabla(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, umbral_x, umbral_y,tabla_actual):
    """
    Genera la estructura de la tabla con rowspan y colspan, identificando las celdas fusionadas con un umbral de tolerancia.
    También dibuja la tabla final con las celdas fusionadas detectadas.
    """

    # Inicializar la tabla con valores vacíos
    tabla = [[{"contenido": "", "rowspan": 1, "colspan": 1} for _ in range(max_columnas)] for _ in range(max_filas)]
    
    if Config.DEBUG_IMAGES:
        RenderizarTablaHTML.mostrar_html_pyqt(tabla,"malla html"+tabla_actual)
    
    # Convertir lista de coordenadas de celdas originales en un conjunto para búsqueda rápida con umbral
    def esta_dentro_de_celdas_originales(x, y):
        """Verifica si la coordenada (x, y) está dentro de las celdas detectadas con un margen de error (umbral)."""
        for id_celda, x_orig, y_orig, _, _ in coordenadas_celdas:
            if abs(x - x_orig) <= umbral_x and abs(y - y_orig) <= umbral_y:
                return id_celda
        return None

    # Crear una imagen en blanco para visualizar la tabla final
    imagen_tabla = np.ones((imagen_height, imagen_width, 3), dtype=np.uint8) * 255

    # Variable de seguimiento para evitar repetir celdas unidas
    celdas_asignadas = set()

    for fila in range(max_filas):
        for columna in range(max_columnas):
            celda = cuadricula[fila][columna]
            x, y, w, h = celda["x"], celda["y"], celda["w"], celda["h"]

            # Si ya fue asignada en otra celda fusionada, continuar con la siguiente
            if (fila, columna) in celdas_asignadas:
                continue

            # Verificar si la celda de la malla coincide con una celda detectada usando el umbral
            id_celda = esta_dentro_de_celdas_originales(x, y)
            if id_celda is None:
                continue  # Saltar esta celda porque es parte de una fusión detectada anteriormente

            # Determinar colspan (expansión a la derecha)
            colspan = 1
            while columna + colspan < max_columnas:
                siguiente_celda = cuadricula[fila][columna + colspan]
                if esta_dentro_de_celdas_originales(siguiente_celda["x"], siguiente_celda["y"]):
                    break  # Se encontró una nueva celda original, detener colspan
                celdas_asignadas.add((fila, columna + colspan))
                colspan += 1

            # Determinar rowspan (expansión hacia abajo)
            rowspan = 1
            while fila + rowspan < max_filas:
                siguiente_celda = cuadricula[fila + rowspan][columna]
                if esta_dentro_de_celdas_originales(siguiente_celda["x"], siguiente_celda["y"]):
                    break  # Se encontró una nueva celda original, detener rowspan
                celdas_asignadas.add((fila + rowspan, columna))
                rowspan += 1

            # Asignar a la tabla la celda fusionada
            # Calcular el centro de la celda
            centro_x = x + (w * colspan) / 2
            centro_y = y + (h * rowspan) / 2

            # Asignar la celda con ID y centro
            tabla[fila][columna] = {
                "id_celda": id_celda,
                "contenido": f"Celda ({fila},{columna})",
                "rowspan": rowspan,
                "colspan": colspan,
                "centro": (centro_x, centro_y)
            }

            # Marcar las celdas fusionadas con rowspan=0 y colspan=0
            for r in range(rowspan):
                for c in range(colspan):
                    if r == 0 and c == 0:
                        continue
                    tabla[fila + r][columna + c] = {
                        "id_celda": id_celda,  # Mantener el mismo identificador
                        "contenido": "",
                        "rowspan": 0,
                        "colspan": 0,
                        "centro": (centro_x, centro_y)  # Todas las celdas fusionadas tienen el mismo centro
                    }
                    celdas_asignadas.add((fila + r, columna + c))

            # Dibujar el rectángulo de la celda en la imagen de la tabla
            # cv2.rectangle(imagen_tabla, (x, y), (x + w * colspan, y + h * rowspan), (0, 0, 0), 2)

    # Mostrar la imagen con la tabla detectada
    # if Config.DEBUG_IMAGES:
    #   cv2.imshow("Tabla Detectada con Celdas Fusionadas", imagen_tabla)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    return tabla

def generar_estructura_tabla_new(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, tabla_actual):
    """
    Genera la estructura de la tabla a partir de la cuadricula y las celdas detectadas.
    Para cada celda de la cuadricula se asigna el ID de la celda detectada (obtenido al 
    verificar en qué bounding box cae el centro de la celda de la cuadricula). Posteriormente,
    se fusionan (con rowspan y colspan) aquellas celdas contiguas que tengan el mismo ID.
    
    Parámetros:
      - coordenadas_celdas: lista de tuplas (id_celda, x, y, w, h) de las celdas detectadas.
      - cuadricula: matriz (lista de listas) de diccionarios con las claves "x", "y", "w" y "h".
      - max_filas, max_columnas: dimensiones de la cuadricula.
      - imagen_width, imagen_height: dimensiones de la imagen original.
      - tabla_actual: (opcional) cadena o identificador para visualización o debugging.
      
    Retorna:
      - tabla: estructura (matriz) donde cada celda es un diccionario con:
          "id": ID asignado de la celda detectada,
          "rowspan": número de filas fusionadas,
          "colspan": número de columnas fusionadas,
          "centro": coordenadas del centro de la celda fusionada.
    """

    # Función para obtener el ID de la celda detectada según el centro (center_x, center_y)
    def obtener_id_celda(center_x, center_y):
        for id_celda, x, y, w, h in coordenadas_celdas:
            # Verificar si el centro cae dentro del bounding box de la celda detectada
            if center_x >= x and center_x <= x + w and center_y >= y and center_y <= y + h:
                return id_celda
        return None

    # Crear una estructura inicial para la tabla a partir de la cuadricula.
    # Se asigna a cada celda el ID detectado según el centro de la celda de la cuadricula.
    tabla = [[None for _ in range(max_columnas)] for _ in range(max_filas)]
    for i in range(max_filas):
        for j in range(max_columnas):
            celda = cuadricula[i][j]
            center_x = celda["x"] + celda["w"] / 2
            center_y = celda["y"] + celda["h"] / 2
            detected_id = obtener_id_celda(center_x, center_y)
            tabla[i][j] = {
                "id_celda": detected_id,
                "contenido": f"Celda ({i},{j})",
                "rowspan": 1,
                "colspan": 1,
                "centro": (center_x, center_y)
            }

    # Fusionar celdas contiguas que tengan el mismo ID (para generar rowspan y colspan)
    celdas_asignadas = set()
    for i in range(max_filas):
        for j in range(max_columnas):
            if (i, j) in celdas_asignadas:
                continue

            current_id = tabla[i][j]["id_celda"]
            if current_id is None:
                continue

            # Expandir horizontalmente (calcular colspan)
            colspan = 1
            while j + colspan < max_columnas and tabla[i][j + colspan]["id_celda"] == current_id:
                celdas_asignadas.add((i, j + colspan))
                colspan += 1

            # Expandir verticalmente (calcular rowspan)
            rowspan = 1
            vertical_fusion_possible = True
            while i + rowspan < max_filas and vertical_fusion_possible:
                for col in range(j, j + colspan):
                    if tabla[i + rowspan][col]["id_celda"] != current_id:
                        vertical_fusion_possible = False
                        break
                if vertical_fusion_possible:
                    for col in range(j, j + colspan):
                        celdas_asignadas.add((i + rowspan, col))
                    rowspan += 1

            # Asignar en la celda principal los valores de la fusión
            tabla[i][j]["rowspan"] = rowspan
            tabla[i][j]["colspan"] = colspan

            # Marcar las celdas fusionadas (excepto la principal) con rowspan=0 y colspan=0
            for r in range(i, i + rowspan):
                for c in range(j, j + colspan):
                    if r == i and c == j:
                        continue
                    tabla[r][c] = {
                        "id_celda": current_id,
                        "contenido": "",
                        "rowspan": 0,
                        "colspan": 0,
                        "centro": tabla[i][j]["centro"]
                    }

    # (Opcional) Visualización o renderización de la tabla HTML usando tabla_actual, si es requerido.
    # Por ejemplo:
    # if Config.DEBUG_IMAGES:
    #     RenderizarTablaHTML.mostrar_html_pyqt(tabla, "Tabla HTML " + tabla_actual)

    return tabla


