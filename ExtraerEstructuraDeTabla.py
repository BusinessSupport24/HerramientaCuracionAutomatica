import cv2
import numpy as np
import Config

def generar_malla(coordenadas_celdas, imagen_width, imagen_height):
    """Genera una malla basada en las coordenadas de las celdas y la dibuja en una imagen en blanco."""

    # Encontrar la anchura y altura más pequeñas entre todas las celdas
    umbral_minimo = 0  # Declarado pero no se usa por ahora
    anchuras = [w for _, x, y, w, h in coordenadas_celdas]
    alturas = [h for _, x, y, w, h in coordenadas_celdas]

    min_anchura = min(anchuras) if anchuras else 10  # Evitar división por cero
    min_altura = min(alturas) if alturas else 10  # Evitar división por cero

    # Definir umbrales de agrupación
    umbral_x = min_anchura / 2
    umbral_y = min_altura / 2

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

    # Mostrar la imagen con la malla generada
    # if Config.DEBUG_IMAGES:
    #   cv2.imshow("Malla Generada", imagen_malla)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()

    return lineas_x, lineas_y, max_filas, max_columnas, imagen_malla, umbral_x, umbral_y




def generar_estructura_tabla(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, umbral_x, umbral_y):
    """
    Genera la estructura de la tabla con rowspan y colspan, identificando las celdas fusionadas con un umbral de tolerancia.
    También dibuja la tabla final con las celdas fusionadas detectadas.
    """

    # Inicializar la tabla con valores vacíos
    tabla = [[{"contenido": "", "rowspan": 1, "colspan": 1} for _ in range(max_columnas)] for _ in range(max_filas)]
    
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


