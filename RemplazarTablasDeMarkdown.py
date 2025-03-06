import os
import markdownify
import Config

import os
from bs4 import BeautifulSoup

def limpiar_tablas_combinadas(html_content):
    """
    Recibe el contenido HTML original como cadena.
    Devuelve el contenido HTML modificado,
    donde se han descombinado las celdas (rowspan/colspan),
    replicando su contenido en las celdas que reemplazan.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    tablas = soup.find_all("table")

    for tabla in tablas:
        filas = tabla.find_all("tr", recursive=False)

        # Verificar si la tabla tiene más de una fila
        if len(filas) <= 1:
            continue

        # ----------------------------------------------------------------
        # 1. Calcular el número de columnas máximo, considerando colspans
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
        # 2. Crear matriz para ubicar celdas expandidas
        # ----------------------------------------------------------------
        tabla_matriz = []  # lista de listas (cada sublista es una "fila" expandida)

        def obtener_fila_disponible(idx):
            """Asegura que exista la fila con índice 'idx' en tabla_matriz."""
            while len(tabla_matriz) <= idx:
                tabla_matriz.append([None] * max_columnas)
            return tabla_matriz[idx]

        fila_expandida_idx = 0

        for fila in filas:
            # Buscar una fila donde colocar las celdas
            while True:
                f_expandida = obtener_fila_disponible(fila_expandida_idx)
                # Si la fila está llena (sin None), pasamos a la siguiente
                if all(c is not None for c in f_expandida):
                    fila_expandida_idx += 1
                else:
                    break

            celdas = fila.find_all(["td", "th"], recursive=False)
            col_expandida_idx = 0

            for celda in celdas:
                rowspan = int(celda.get("rowspan", 1))
                colspan = int(celda.get("colspan", 1))
                contenido_celda = celda.get_text(strip=False)  # Guardamos el texto

                # Buscar primera columna libre
                while tabla_matriz[fila_expandida_idx][col_expandida_idx] is not None:
                    col_expandida_idx += 1

                # Rellenar matriz para rowspan x colspan con el contenido original
                for r in range(rowspan):
                    fila_target = obtener_fila_disponible(fila_expandida_idx + r)
                    for c in range(colspan):
                        expand_col = col_expandida_idx + c
                        if fila_target[expand_col] is None:
                            fila_target[expand_col] = contenido_celda  # Guardamos el texto

            fila_expandida_idx += 1

        # ----------------------------------------------------------------
        # 3. Reconstruir tabla sin rowspans/colspans, replicando contenido
        # ----------------------------------------------------------------
        for child in tabla.find_all("tr"):
            child.decompose()  # Eliminamos las filas originales

        for fila_exp in tabla_matriz:
            # Si la fila es completamente None, la ignoramos
            if all(c is None for c in fila_exp):
                continue

            nuevo_tr = soup.new_tag("tr")
            tabla.append(nuevo_tr)
            for c in fila_exp:
                nueva_celda = soup.new_tag("td")
                nueva_celda.string = c if c is not None else ""  # Si c es None, dejamos vacío
                nuevo_tr.append(nueva_celda)

    return str(soup)


def html_to_markdown(html_file_path):
    """
    Busca un archivo HTML en el folder dado que contenga la clave en su nombre,
    lo convierte a Markdown y devuelve el contenido convertido.
    
    :param folder_path: Ruta del folder donde buscar el archivo HTML.
    :param file_key: Clave o parte del nombre del archivo HTML a buscar.
    :return: Contenido de la tabla en formato Markdown.
    """
    
    # Leer contenido del archivo HTML
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Reemplazar saltos de línea por espacios para evitar problemas de formato
    # html_content = html_content.replace('\n', ' ')
    html_limpio = limpiar_tablas_combinadas(html_content)
    
    # Convertir a Markdown
    markdown_text = markdownify.markdownify(html_limpio)

    # print(markdown_text)
    
    return markdown_text

def remplazar_tablas_en_md(markdown_result,folder_path):

    ruta_carpeta = folder_path+r"\tablas_html"  # Cambia esto por tu ruta

    # Obtener todos los archivos en la carpeta y filtrar los .html
    archivos_html = [f for f in os.listdir(ruta_carpeta) if f.endswith(".html")]

    # Iterar sobre los archivos encontrados
    for archivo in archivos_html:
        tabla_path = os.path.join(ruta_carpeta, archivo)
        tabla_md = html_to_markdown(tabla_path)
        llave_unica = "Llave_Unica_T"+archivo[1:].split(".html")[0]
        if Config.DEBUG_PRINTS:
            print(llave_unica)
            print(markdown_result)
        markdown_result = markdown_result.replace(llave_unica,f"\n\n{tabla_md}\n\n")
    
    return markdown_result


