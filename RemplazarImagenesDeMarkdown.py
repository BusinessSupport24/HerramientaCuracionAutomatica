import os
import Config
import pypandoc

def remplazar_imagenes_en_md(markdown_result_imagenes_remplazadas, folder_path):
    """
    Reemplaza las marcas de posición (llaves únicas) en el contenido Markdown por el texto
    correspondiente extraído de imágenes, tras convertir dicho texto a formato Markdown usando Pandoc.
    
    Proceso:
      1. Define la carpeta donde se encuentran los archivos de texto (resultado de la extracción de imágenes).
         Se asume que dichos archivos se encuentran en una subcarpeta "imagenes_extraidas" dentro de folder_path.
      2. Se listan los archivos en la carpeta y se filtran aquellos que terminen en ".txt".
      3. Para cada archivo:
         a. Se abre y se lee el contenido completo.
         b. Se convierte el contenido a Markdown usando pypandoc.
         c. Se genera una llave única basada en el nombre del archivo (omitido el primer carácter y sin la extensión ".txt").
         d. Se reemplazan todas las ocurrencias de dicha llave en el contenido Markdown original (markdown_result_imagenes_remplazadas)
            por la llave formateada seguida del texto convertido.
      4. Se guarda el resultado final en un archivo "markdown_imagenes_remplazadas.md" en folder_path.
    
    :param markdown_result_imagenes_remplazadas: String original en formato Markdown que contiene marcas de posición
                                                 (llaves) para las imágenes.
    :param folder_path: Ruta de la carpeta donde se encuentran los archivos extraídos y donde se guardará
                        el Markdown final con las imágenes reemplazadas.
    :return: String con el contenido Markdown final, tras haber realizado los reemplazos.
    """
    # Definir la ruta de la carpeta que contiene los textos extraídos de las imágenes.
    ruta_carpeta = folder_path + r"\imagenes_extraidas"

    # Obtener todos los archivos en la carpeta que terminen en .txt
    archivos_jpg = [f for f in os.listdir(ruta_carpeta) if f.endswith(".txt")]

    # Iterar sobre cada archivo .txt encontrado en la carpeta
    for archivo in archivos_jpg:
        # Abrir el archivo y leer su contenido
        with open(os.path.join(ruta_carpeta, archivo), "r", encoding="utf-8") as archivo_txt:
            textxt = archivo_txt.read()  # Leer todo el contenido del archivo en una cadena

            # Convertir el texto extraído a Markdown usando pypandoc
            text_imagen = pypandoc.convert_text(textxt, 'md', format='markdown')
            
            # Generar la llave única para la imagen a partir del nombre del archivo.
            # Se omite el primer carácter del nombre y se elimina la extensión ".txt".
            llave_unica = "Llave_Unica_I" + archivo[1:].split(".txt")[0]
            
            # Reemplazar en el markdown original todas las ocurrencias de la llave única con el texto formateado.
            # Se añaden saltos de línea para separar claramente el contenido.
            markdown_result_imagenes_remplazadas = markdown_result_imagenes_remplazadas.replace(
                llave_unica,
                f"\n\n{llave_unica}\n" + f"\n{text_imagen}\n\n"
            )

    # Guardar el Markdown final en un archivo dentro de la carpeta indicada.
    output_file_path = os.path.join(folder_path, "markdown_imagenes_remplazadas.md")
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(markdown_result_imagenes_remplazadas)

    return markdown_result_imagenes_remplazadas
