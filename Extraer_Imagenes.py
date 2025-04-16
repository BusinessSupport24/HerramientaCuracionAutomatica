import fitz  # PyMuPDF: para abrir y manipular el PDF
from PIL import Image  # Para manipulación de imágenes
import numpy as np  # Para operaciones numéricas y manejo de arrays
import os  # Para operaciones de sistema de archivos
import io  # Para manejo de flujos de bytes
import Config  # Archivo de configuración con banderas y parámetros globales

def extraer_imagenes(pdf_bytes, folder_path):
    """
    Extrae todas las imágenes de un PDF y las guarda en una carpeta específica.

    Procedimiento:
      1. Se crea (o valida) una carpeta de salida denominada "imagenes_extraidas" dentro de folder_path.
      2. Se abre el PDF a partir de los bytes (pdf_bytes) utilizando PyMuPDF (fitz.open).
      3. Se itera sobre cada página del PDF (se salta la página con índice 1, según la condición).
      4. Por cada página, se obtienen las imágenes usando get_images(full=True).
      5. Para cada imagen:
         - Se extrae el identificador (xref) y se obtiene la imagen base.
         - Se verifica si la imagen posee una máscara de transparencia (smask).
         - Si existe smask:
             a. Se extrae la máscara de la imagen.
             b. Se abren tanto la imagen base como la máscara usando PIL.
             c. Se asegura que la máscara esté en modo 'L' (escala de grises) y, si es necesario, se redimensiona para que coincida con el tamaño de la imagen base.
             d. Se combina la imagen base y la máscara usando putalpha para conservar la transparencia.
             e. Se compone la imagen final sobre un fondo blanco y se guarda en formato JPG.
         - Si no existe smask:
             a. Se abre la imagen base y se convierte a RGB (si es necesario) para asegurarse de que esté en el formato correcto.
             b. Se guarda la imagen en formato JPG.
      6. Se imprime un mensaje de éxito al finalizar la extracción de imágenes.

    :param pdf_bytes: Objeto BytesIO que contiene el PDF original.
    :param folder_path: Ruta de la carpeta donde se guardarán las imágenes extraídas.
    """
    # Definir la ruta de salida para las imágenes extraídas
    output_folder = folder_path + r"\imagenes_extraidas"

    # Crear la carpeta si no existe
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
        if Config.DEBUG_PRINTS:
            print(f"Carpeta '{output_folder}' creada con éxito.")
    else:
        if Config.DEBUG_PRINTS:
            print(f"La carpeta '{output_folder}' ya existe.")

    # Abrir el documento PDF a partir del stream (pdf_bytes)
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Iterar sobre cada página del PDF
    for page_number in range(len(pdf_document)):
        # Se omite la página con índice 1 (según la condición establecida)
        if page_number != 1:
            page = pdf_document.load_page(page_number)
            # Obtener la lista completa de imágenes en la página
            image_list = page.get_images(full=True)

            # Iterar sobre cada imagen encontrada en la página
            for image_index, img in enumerate(image_list, start=1):
                xref = img[0]
                # Extraer la imagen base usando el xref
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]

                # Verificar si la imagen tiene máscara de transparencia
                smask = base_image.get("smask")
                if smask:
                    # Si existe una máscara, extraerla
                    mask_image = pdf_document.extract_image(smask)
                    mask_bytes = mask_image["image"]

                    # Abrir la imagen base y la máscara en PIL usando BytesIO
                    with Image.open(io.BytesIO(image_bytes)) as base_img:
                        with Image.open(io.BytesIO(mask_bytes)) as mask_img:
                            # Convertir la máscara a modo 'L' si no lo está
                            if mask_img.mode != 'L':
                                mask_img = mask_img.convert('L')

                            # Si la máscara no tiene el mismo tamaño que la imagen base, redimensionarla
                            if mask_img.size != base_img.size:
                                mask_img = mask_img.resize(base_img.size, Image.Resampling.LANCZOS)

                            # Agregar el canal alfa a la imagen base utilizando la máscara
                            base_img.putalpha(mask_img)
                            # Crear un fondo blanco para componer la imagen final
                            background = Image.new("RGB", base_img.size, (255, 255, 255))
                            # Combinar la imagen base con el fondo blanco para mantener la transparencia
                            base_img = Image.alpha_composite(background.convert("RGBA"), base_img).convert("RGB")

                            # Guardar la imagen resultante en formato JPG
                            image_filename = f"Imagen_{page_number + 1}_{image_index}.jpg"
                            image_path = os.path.join(output_folder, image_filename)
                            base_img.save(image_path)
                            
                            if Config.DEBUG_PRINTS:
                                print(f"Imagen guardada en: {image_path}")
                else:
                    # Si no hay máscara de transparencia, se utiliza la imagen base directamente
                    with Image.open(io.BytesIO(image_bytes)) as base_img:
                        image_filename = f"Imagen_{page_number + 1}_{image_index}.jpg"
                        image_path = os.path.join(output_folder, image_filename)
                        # Si la imagen está en modo RGBA, convertirla a RGB con fondo blanco
                        if base_img.mode == "RGBA":
                            background = Image.new("RGB", base_img.size, (255, 255, 255))
                            base_img = Image.alpha_composite(background.convert("RGBA"), base_img).convert("RGB")
                        else:
                            base_img = base_img.convert("RGB")
                        base_img.save(image_path)
                        if Config.DEBUG_PRINTS:
                            print(f"Imagen guardada en: {image_path}")

    print("IMAGENES OBTENIDAS CON EXITO.")
