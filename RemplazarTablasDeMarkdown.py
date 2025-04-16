import os
import markdownify
import Config

import os
from bs4 import BeautifulSoup

def limpiar_tablas_combinadas(html_content):
    """
    Recibe una cadena de contenido HTML y devuelve el mismo contenido modificado,
    de forma que se "descombinan" las celdas de las tablas que tienen atributos rowspan/colspan.
    
    Para ello, se sigue el siguiente procedimiento:
      1. Se parsea el HTML utilizando BeautifulSoup.
      2. Se buscan todas las tablas (<table>).
      3. Para cada tabla, se obtienen las filas (<tr>) de primer nivel (sin recursión).
      4. Se calcula el número máximo de columnas de la tabla, considerando el atributo colspan de cada celda.
      5. Se crea una matriz (lista de listas) que representa la tabla expandida; cada sublista corresponde a una fila.
      6. Se recorren las filas originales y se colocan las celdas en la matriz respetando los valores de rowspan y colspan,
         replicando el contenido en las celdas "vacías" que reemplazan a las originales combinadas.
      7. Se eliminan las filas originales y se reconstruye la tabla nueva a partir de la matriz.
    
    :param html_content: Cadena con el contenido HTML original.
    :return: Cadena con el HTML resultante en que las celdas combinadas han sido "descombinadas".
    """
    soup = BeautifulSoup(html_content, "html.parser")
    tablas = soup.find_all("table")

    for tabla in tablas:
        filas = tabla.find_all("tr", recursive=False)

        # Si la tabla tiene una sola fila, se omite su procesamiento
        if len(filas) <= 1:
            continue

        # ----------------------------------------------------------------
        # 1. Calcular el número máximo de columnas considerando colspans
        # ----------------------------------------------------------------
        max_columnas = 0
        for fila in filas:
            celdas = fila.find_all(["td", "th"], recursive=False)
            col_index = 0
            for celda in celdas:
                colspan = int(celda.get("colspan", 1))
                col_index += colspan
            max_columnas = max(max_columnas, col_index)

        # ----------------------------------------------------------------
        # 2. Crear la matriz (tabla_matriz) para ubicar las celdas expandidas
        # ----------------------------------------------------------------
        tabla_matriz = []  # Cada sublista es una "fila" de la tabla expandida

        def obtener_fila_disponible(idx):
            """Asegura que exista una fila en la matriz en el índice 'idx'."""
            while len(tabla_matriz) <= idx:
                tabla_matriz.append([None] * max_columnas)
            return tabla_matriz[idx]

        fila_expandida_idx = 0

        # Recorrer cada fila de la tabla original para volcar su contenido en la matriz
        for fila in filas:
            # Buscar una fila disponible en la matriz que aún tenga celdas sin asignar
            while True:
                f_expandida = obtener_fila_disponible(fila_expandida_idx)
                if all(c is not None for c in f_expandida):
                    fila_expandida_idx += 1
                else:
                    break

            celdas = fila.find_all(["td", "th"], recursive=False)
            col_expandida_idx = 0

            for celda in celdas:
                rowspan = int(celda.get("rowspan", 1))
                colspan = int(celda.get("colspan", 1))
                contenido_celda = celda.get_text(strip=False)  # Se conserva el texto tal cual

                # Buscar la primera columna libre en la fila actual de la matriz
                while tabla_matriz[fila_expandida_idx][col_expandida_idx] is not None:
                    col_expandida_idx += 1

                # Rellenar la matriz en la posición correspondiente considerando rowspan y colspan
                for r in range(rowspan):
                    fila_target = obtener_fila_disponible(fila_expandida_idx + r)
                    for c in range(colspan):
                        expand_col = col_expandida_idx + c
                        if fila_target[expand_col] is None:
                            fila_target[expand_col] = contenido_celda

            fila_expandida_idx += 1

        # ----------------------------------------------------------------
        # 3. Reconstruir la tabla HTML sin rowspan ni colspan
        # ----------------------------------------------------------------
        # Eliminar las filas originales de la tabla
        for child in tabla.find_all("tr"):
            child.decompose()

        # Para cada fila de la matriz, crear una nueva fila <tr> y asignar las celdas correspondientes
        for fila_exp in tabla_matriz:
            # Ignorar filas que están completamente vacías
            if all(c is None for c in fila_exp):
                continue

            nuevo_tr = soup.new_tag("tr")
            tabla.append(nuevo_tr)
            for c in fila_exp:
                nueva_celda = soup.new_tag("td")
                nueva_celda.string = c if c is not None else ""
                nuevo_tr.append(nueva_celda)

    return str(soup)


def html_to_markdown(html_file_path):
    """
    Lee un archivo HTML, lo limpia (descombinando las celdas de las tablas) y lo convierte a Markdown.

    Procedimiento:
      - Se lee el contenido del archivo HTML.
      - Se llama a la función limpiar_tablas_combinadas para descomponer las celdas combinadas.
      - Se utiliza markdownify para convertir el HTML resultante a Markdown.

    :param html_file_path: Ruta del archivo HTML.
    :return: Cadena con el contenido convertido a Markdown.
    """
    # Leer el archivo HTML
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Limpiar el HTML descombinando las celdas
    html_limpio = limpiar_tablas_combinadas(html_content)
    
    # Convertir el HTML limpio a Markdown utilizando markdownify
    markdown_text = markdownify.markdownify(html_limpio)
    
    return markdown_text


def remplazar_tablas_en_md(markdown_result, folder_path):
    """
    Reemplaza en el contenido Markdown (markdown_result) las marcas de posición (llaves únicas) correspondientes
    a tablas por el contenido de las tablas convertidas desde HTML.

    Procedimiento:
      - Se define la ruta de la carpeta "tablas_html" dentro de folder_path.
      - Se listan los archivos HTML en la carpeta.
      - Para cada archivo HTML:
          a. Se convierte el HTML a Markdown utilizando la función html_to_markdown.
          b. Se genera una llave única a partir del nombre del archivo (ignorando el primer carácter y la extensión).
          c. Se reemplazan las ocurrencias de la llave en el contenido Markdown original por el Markdown convertido.
      - Se retorna el contenido Markdown final con los reemplazos realizados.

    :param markdown_result: Cadena original en Markdown que contiene marcas de posición para tablas.
    :param folder_path: Ruta de la carpeta donde se encuentran los archivos HTML de las tablas.
    :return: Cadena con el Markdown modificado, en el que se han reemplazado las marcas de posición
             por el contenido de las tablas.
    """
    # Definir la ruta de la carpeta donde se encuentran los archivos HTML
    ruta_carpeta = folder_path + r"\tablas_html"

    # Listar los archivos HTML en la carpeta
    archivos_html = [f for f in os.listdir(ruta_carpeta) if f.endswith(".html")]

    # Iterar sobre cada archivo HTML encontrado
    for archivo in archivos_html:
        tabla_path = os.path.join(ruta_carpeta, archivo)
        # Convertir el archivo HTML a Markdown
        tabla_md = html_to_markdown(tabla_path)
        # Generar una llave única para identificar la tabla en el Markdown original.
        # Se toma el nombre del archivo, se elimina el primer carácter y la extensión.
        llave_unica = "Llave_Unica_T" + archivo[1:].split(".html")[0]
        if Config.DEBUG_PRINTS:
            print(llave_unica)
            print(markdown_result)
        # Reemplazar la llave en el Markdown por la llave seguida del contenido de la tabla convertido
        markdown_result = markdown_result.replace(llave_unica,
                                                  f"\n\n{llave_unica}\n" + f"\n{tabla_md}\n\n")
    
    return markdown_result
