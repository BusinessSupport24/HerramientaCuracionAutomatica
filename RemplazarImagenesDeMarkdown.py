import os
import Config
import pypandoc


def remplazar_imagenes_en_md(markdown_result_imagenes_remplazadas,folder_path):

    ruta_carpeta = folder_path+r"\imagenes_extraidas"  # Cambia esto por tu ruta

    # Obtener todos los archivos en la carpeta y filtrar los .html
    archivos_jpg = [f for f in os.listdir(ruta_carpeta) if f.endswith(".txt")]

    # Iterar sobre los archivos encontrados
    for archivo in archivos_jpg:
        with open(os.path.join(ruta_carpeta, archivo), "r", encoding="utf-8") as archivo_txt:
            textxt = archivo_txt.read()  # Lee todo el contenido y lo guarda en un string
            # print("TXT\n")
            # print(textxt)
            text_imagen = ""
            text_imagen += pypandoc.convert_text(textxt, 'md', format='markdown')  # Convertir con Pandoc
            # print(text_imagen)
            llave_unica = "Llave_Unica_I"+archivo[1:].split(".txt")[0]
            # print("Llave Unica:\n")
            # print(llave_unica)
            # print("Markdown Result\n")
            # print(markdown_result_imagenes_remplazadas)
            markdown_result_imagenes_remplazadas = markdown_result_imagenes_remplazadas.replace(llave_unica,f"\n\n{text_imagen}\n\n")
    
    with open(folder_path+r"\markdown_imagenes_remplazadas.md", 'w', encoding='utf-8') as f:
        f.write(markdown_result_imagenes_remplazadas)

    return markdown_result_imagenes_remplazadas

# md = '''### Página 8

# -   Plan Multiasistencia Hogar: Llave_Unica_Imagen_8_1

#     Llave_Unica_Imagen_8_2 Plan MultiAsistencia Hogar: Por solo \$6.000

#     mensuales. Condiciones:
# '''

# remplazar_imagenes_en_md(md,"Curacion_PTAR 5071 Tarifa Esp_NuevosCamposdeJuego_NTC_TC_V21_0225")

