import cv2
import numpy as np
import Config
import RenderizarTablaHTML

def mostrar_imagen_redimensionada(name_image, image, max_ancho=1600, max_alto=900):
    """
    Muestra una imagen en una ventana de OpenCV, redimensionándola si sus dimensiones exceden los valores
    máximos especificados, manteniendo la relación de aspecto.

    :param name_image: Nombre de la ventana de visualización.
    :param image: Imagen a mostrar (array NumPy).
    :param max_ancho: Ancho máximo permitido.
    :param max_alto: Alto máximo permitido.
    """
    alto_original, ancho_original = image.shape[:2]
    escala = min(max_ancho / ancho_original, max_alto / alto_original)
    
    if escala < 1:
        nuevo_ancho = int(ancho_original * escala)
        nuevo_alto = int(alto_original * escala)
        image = cv2.resize(image, (nuevo_ancho, nuevo_alto), interpolation=cv2.INTER_AREA)
    
    cv2.imshow(name_image, image)


def generar_malla(coordenadas_celdas, imagen_width, imagen_height):
    """
    Genera y dibuja una malla basada en las coordenadas de las celdas detectadas de la tabla.
    
    Este proceso se lleva a cabo mediante los siguientes pasos:
      1. Se extraen las coordenadas (eje X e Y) de las celdas.
      2. Se calcula el valor mínimo de ancho y alto entre las celdas, para definir umbrales
         de agrupación.
      3. Se agrupan las coordenadas cercanas utilizando una función auxiliar (agrupar_coordenadas),
         con un umbral en cada eje.
      4. Se generan las líneas de la malla a partir de las coordenadas agrupadas.
      5. Se dibuja la malla sobre una imagen en blanco de las dimensiones originales.

    :param coordenadas_celdas: Lista de tuplas (id_celda, x, y, w, h) que representan las celdas detectadas.
    :param imagen_width: Ancho de la imagen original.
    :param imagen_height: Alto de la imagen original.
    :return: Tuple que contiene:
             - lineas_x: Lista de coordenadas X agrupadas.
             - lineas_y: Lista de coordenadas Y agrupadas.
             - max_filas: Número de filas de la malla.
             - max_columnas: Número de columnas de la malla.
             - imagen_malla: Imagen en blanco con la malla dibujada.
             - umbral_x: Umbral utilizado para agrupar las coordenadas en X.
             - umbral_y: Umbral utilizado para agrupar las coordenadas en Y.
    """

    # Extraer la anchura y altura de cada celda para determinar umbrales mínimos.
    anchuras = [w for _, x, y, w, h in coordenadas_celdas]
    alturas = [h for _, x, y, w, h in coordenadas_celdas]

    min_anchura = min(anchuras) if anchuras else 10  # Evita división por cero
    min_altura = min(alturas) if alturas else 10      # Evita división por cero

    # Definir umbrales de agrupación basados en la dimensión mínima de las celdas
    umbral_x = min_anchura / 1.5
    umbral_y = min_altura / 1.5

    # Extraer y ordenar las coordenadas únicas en X e Y
    coordenadas_x = sorted(set(x for _, x, y, w, h in coordenadas_celdas))
    coordenadas_y = sorted(set(y for _, x, y, w, h in coordenadas_celdas))

    def agrupar_coordenadas(coordenadas, umbral):
        """
        Agrupa coordenadas cercanas usando un umbral de distancia.

        :param coordenadas: Lista de coordenadas (números).
        :param umbral: Distancia máxima para considerar que dos coordenadas pertenecen al mismo grupo.
        :return: Lista de coordenadas agrupadas, calculadas como la media de cada grupo.
        """
        if not coordenadas:
            return []
        grupos = [[coordenadas[0]]]
        for coord in coordenadas[1:]:
            if abs(coord - grupos[-1][-1]) <= umbral:
                grupos[-1].append(coord)
            else:
                grupos.append([coord])
        # Se devuelve la media de cada grupo, redondeada a entero.
        return [int(np.mean(grupo)) for grupo in grupos]

    # Agrupar las coordenadas para obtener líneas de malla
    lineas_x = agrupar_coordenadas(coordenadas_x, umbral_x)
    lineas_y = agrupar_coordenadas(coordenadas_y, umbral_y)

    max_columnas = len(lineas_x)
    max_filas = len(lineas_y)

    # Crear una imagen en blanco para dibujar la malla
    imagen_malla = np.ones((imagen_height, imagen_width, 3), dtype=np.uint8) * 255

    # Dibujar líneas verticales
    for x in lineas_x:
        cv2.line(imagen_malla, (x, 0), (x, imagen_height), (0, 0, 0), 1)

    # Dibujar líneas horizontales
    for y in lineas_y:
        cv2.line(imagen_malla, (0, y), (imagen_width, y), (0, 0, 0), 1)

    if Config.DEBUG_IMAGES:
        mostrar_imagen_redimensionada("malla creada", imagen_malla)

    return lineas_x, lineas_y, max_filas, max_columnas, imagen_malla, umbral_x, umbral_y


def generar_estructura_tabla(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, umbral_x, umbral_y, tabla_actual):
    """
    Genera la estructura de la tabla a partir de los datos de la malla obtenida y las celdas detectadas.

    Se crea una tabla (matriz) inicial asignando a cada celda de la cuadricula un placeholder
    que incluye un identificador (ID) detectado, usando los centros de las celdas. Luego se fusionan
    las celdas contiguas que tienen el mismo ID para generar los valores de 'rowspan' y 'colspan'.

    :param coordenadas_celdas: Lista de tuplas (id_celda, x, y, w, h) de las celdas detectadas.
    :param cuadricula: Matriz (lista de listas) de diccionarios con claves "x", "y", "w" y "h" para cada celda de la malla.
    :param max_filas: Número de filas de la cuadricula.
    :param max_columnas: Número de columnas de la cuadricula.
    :param imagen_width: Ancho de la imagen original.
    :param imagen_height: Alto de la imagen original.
    :param umbral_x: Umbral utilizado para agrupar coordenadas en el eje X.
    :param umbral_y: Umbral utilizado para agrupar coordenadas en el eje Y.
    :param tabla_actual: Identificador o nombre de la tabla (para depuración o visualización).
    :return: Matriz (lista de listas) que representa la estructura final de la tabla. Cada celda es un diccionario con:
             - "id_celda": ID asignado de la celda.
             - "contenido": Texto asociado o placeholder.
             - "rowspan": Número de filas fusionadas.
             - "colspan": Número de columnas fusionadas.
             - "centro": Coordenadas del centro de la celda fusionada.
    """
    # Función auxiliar para determinar el ID de la celda detectada dada la posición central
    def obtener_id_celda(center_x, center_y):
        for id_celda, x, y, w, h in coordenadas_celdas:
            if center_x >= x and center_x <= x + w and center_y >= y and center_y <= y + h:
                return id_celda
        return None

    # Inicializar la tabla vacía
    tabla = [[None for _ in range(max_columnas)] for _ in range(max_filas)]
    for i in range(max_filas):
        for j in range(max_columnas):
            celda = cuadricula[i][j]
            center_x = celda["x"] + celda["w"] / 2
            center_y = celda["y"] + celda["h"] / 2
            detected_id = None
            # Buscar el ID de la celda que contenga el centro de la celda de la cuadricula
            for id_celda, x, y, w, h in coordenadas_celdas:
                if center_x >= x and center_x <= x + w and center_y >= y and center_y <= y + h:
                    detected_id = id_celda
                    break
            tabla[i][j] = {
                "id_celda": detected_id,
                "contenido": f"Celda ({i},{j})",
                "rowspan": 1,
                "colspan": 1,
                "centro": (center_x, center_y)
            }

    # Fusionar celdas contiguas que tengan el mismo ID para generar estructura de rowspan y colspan
    celdas_asignadas = set()
    for i in range(max_filas):
        for j in range(max_columnas):
            if (i, j) in celdas_asignadas:
                continue
            current_id = tabla[i][j]["id_celda"]
            if current_id is None:
                continue

            # Expansión horizontal: calcular el colspan
            colspan = 1
            while j + colspan < max_columnas and tabla[i][j + colspan]["id_celda"] == current_id:
                celdas_asignadas.add((i, j + colspan))
                colspan += 1

            # Expansión vertical: calcular el rowspan
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

            # Asignar a la celda principal los valores de la fusión
            tabla[i][j]["rowspan"] = rowspan
            tabla[i][j]["colspan"] = colspan

            # Marcar las celdas fusionadas, excepto la principal, con rowspan y colspan en cero
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
                    celdas_asignadas.add((r, c))

    return tabla


def generar_estructura_tabla_new(coordenadas_celdas, cuadricula, max_filas, max_columnas, imagen_width, imagen_height, tabla_actual):
    """
    Variante de la función 'generar_estructura_tabla' que genera la estructura final de la tabla a partir de la cuadricula
    y las celdas detectadas. Para cada celda de la cuadricula, se determina el ID basado en el centro de la misma; luego,
    se fusionan aquellas celdas contiguas que tienen el mismo ID para determinar los valores de rowspan y colspan.

    :param coordenadas_celdas: Lista de tuplas (id_celda, x, y, w, h) de las celdas detectadas.
    :param cuadricula: Matriz (lista de listas) de diccionarios que definen las celdas con claves "x", "y", "w", "h".
    :param max_filas: Número de filas en la cuadricula.
    :param max_columnas: Número de columnas en la cuadricula.
    :param imagen_width: Ancho de la imagen original.
    :param imagen_height: Alto de la imagen original.
    :param tabla_actual: Identificador o nombre de la tabla para propósitos de depuración o visualización.
    :return: Matriz (lista de listas) que representa la tabla final, donde cada celda es un diccionario con:
             "id_celda", "contenido", "rowspan", "colspan" y "centro".
    """
    
    # Función auxiliar: asigna un ID a la celda basada en si el centro cae dentro del bounding box de alguna celda detectada.
    def obtener_id_celda(center_x, center_y):
        for id_celda, x, y, w, h in coordenadas_celdas:
            if center_x >= x and center_x <= x + w and center_y >= y and center_y <= y + h:
                return id_celda
        return None

    # Inicializar la tabla como una matriz vacía
    tabla = [[None for _ in range(max_columnas)] for _ in range(max_filas)]
    for i in range(max_filas):
        for j in range(max_columnas):
            celda = cuadricula[i][j]
            center_x = celda["x"] + celda["w"] / 2
            center_y = celda["y"] + celda["h"] / 2
            detected_id = None
            # Determinar el ID de la celda detectada a partir de su centro
            for id_celda, x, y, w, h in coordenadas_celdas:
                if center_x >= x and center_x <= x + w and center_y >= y and center_y <= y + h:
                    detected_id = id_celda
                    break
            tabla[i][j] = {
                "id_celda": detected_id,
                "contenido": f"Celda ({i},{j})",
                "rowspan": 1,
                "colspan": 1,
                "centro": (center_x, center_y)
            }

    # Fusionar celdas contiguas que tengan el mismo ID para asignar rowspan y colspan
    celdas_asignadas = set()
    for i in range(max_filas):
        for j in range(max_columnas):
            if (i, j) in celdas_asignadas:
                continue
            current_id = tabla[i][j]["id_celda"]
            if current_id is None:
                continue

            # Calcular el colspan expandiéndose a la derecha
            colspan = 1
            while j + colspan < max_columnas and tabla[i][j + colspan]["id_celda"] == current_id:
                celdas_asignadas.add((i, j + colspan))
                colspan += 1

            # Calcular el rowspan expandiéndose hacia abajo
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

            # Asignar en la celda principal los valores de fusión
            tabla[i][j]["rowspan"] = rowspan
            tabla[i][j]["colspan"] = colspan

            # Marcar las celdas fusionadas (excepto la principal) con rowspan=0 y colspan=0, conservando el centro.
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
                    celdas_asignadas.add((r, c))

    return tabla
