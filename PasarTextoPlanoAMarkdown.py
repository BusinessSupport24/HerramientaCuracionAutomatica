import pdfplumber
import os
import io
import Config
import sys
import mistune
import re
import pypandoc
import RemplazarTablasDeMarkdown
pypandoc.download_pandoc()

def convertir_pdf_a_markdown(pdf_bytes):
    pdf_bytes.seek(0)
    pdf_copy = io.BytesIO(pdf_bytes.getvalue())
    pdf = pdfplumber.open(pdf_copy)

    markdown_text = ""

    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        print("--"*50)
        print("Texto extraido\n")
        print("--"*50)

        if text:
            text = limpiar_texto(text)  # Preprocesar el texto antes de pasarlo a Pandoc
            # markdown_text += f"\n\n### Página {i+1}\n\n"  # Agregar encabezado de página
            markdown_text += pypandoc.convert_text(text, 'md', format='markdown')  # Convertir con Pandoc
            print("--"*50)
            print("Texto MD\n",markdown_text)
            print("--"*50)


    return markdown_text

def limpiar_texto(texto):
    """
    Aplica preprocesamiento al texto extraído:
    - Elimina espacios múltiples
    - Formatea títulos y negritas
    - Agrega saltos de línea para una mejor conversión a Markdown
    """
    texto = re.sub(r'_{2,}', '', texto)  # Elimina subrayados repetidos
    texto = re.sub(r'\n{2,}', '\n', texto)  # Evita múltiples saltos de línea
    texto = re.sub(r'(Pagina\s\d+)', r'# \1', texto)  # Convierte "Pagina X" en encabezado Markdown
    texto = re.sub(r'\b(OFERTA .+|POLÍTICAS GENERALES)\b', r'## \1', texto)  # Encabezados secundarios
    texto = re.sub(r'-\s', r'* ', texto)  # Convierte listas en Markdown
    return texto.strip()


def main(pdf_bytes,folder_path):
    """
    Función principal que muestra tablas de un PDF con pdfplumber y botones.
    
    Parámetros:
        ruta_pdf (str): Ruta del PDF a procesar.
    """
    # output_md_path = os.path.join(folder_path, "Texto_Extraido.txt")
    # Llamar a la función con un archivo PDF en memoria
    markdown_result = convertir_pdf_a_markdown(pdf_bytes)
    with open(folder_path+r"\markdown_puro.md", 'w', encoding='utf-8') as f:
        f.write("".join(markdown_result.split("\n")))
    markdown_result_tablas_remplazadas = RemplazarTablasDeMarkdown.remplazar_tablas_en_md("".join(markdown_result.split("\n")),folder_path)
    # print(markdown_result_tablas_remplazadas)
    with open(folder_path+r"\markdown_tablas_remplazadas.md", 'w', encoding='utf-8') as f:
        f.write(markdown_result_tablas_remplazadas)
    
    return markdown_result_tablas_remplazadas

def pdfplumber_to_fitz(pdf):
    pdf_bytes = io.BytesIO()
    
    pdf.stream.seek(0)  # Asegurar que estamos al inicio del archivo
    pdf_bytes.write(pdf.stream.read())  # Guardar el contenido en memoria
    pdf_bytes.seek(0)  # Volver al inicio para que fitz lo lea correctamente

    return pdf_bytes  # Retornar el PDF en memoria

# Si el script se ejecuta directamente desde la terminal
if __name__ == "__main__":
    # Verifica si se pasó un argumento desde la línea de comandos
    if len(sys.argv) > 1:
        pdf_bytes = sys.argv[1]  # Toma el primer argumento después del script
    else:
        pdf_path = "documento_verticalizado_llaves_tablas_imagenes.pdf"  # Valor por defecto si no se pasa argumento}
        folder_path = "Curacion_Md_"+pdf_path.split(".pdf")[0]
        if not os.path.exists(folder_path):  # Verifica si la carpeta no existe
            os.mkdir(folder_path)  # Crea la carpeta
            if Config.DEBUG_PRINTS:
                print(f"Carpeta '{folder_path}' creada con éxito.")
        else:
            if Config.DEBUG_PRINTS:
                print(f"La carpeta '{folder_path}' ya existe.")

        with pdfplumber.open(pdf_path) as pdf:
            pdf_bytes = pdfplumber_to_fitz(pdf)  # Convertir pdfplumber a BytesIO para fitz    
            # Asegurar que el stream está en la posición correcta antes de usarlo
            pdf_bytes.seek(0)

    main(pdf_bytes,folder_path)  # Llama a la función con el argumento