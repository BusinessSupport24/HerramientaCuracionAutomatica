import os
import markdownify
import Config

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
    html_content = html_content.replace('\n', ' ')
    
    # Convertir a Markdown
    markdown_text = markdownify.markdownify(html_content)

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


