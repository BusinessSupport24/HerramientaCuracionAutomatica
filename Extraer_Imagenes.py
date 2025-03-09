import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import os
import io
import Config

def extraer_imagenes(pdf_bytes,folder_path):

    # Carpeta de salida para las imágenes extraídas
    output_folder = folder_path+r"\imagenes_extraidas"

    if not os.path.exists(output_folder):  # Verifica si la carpeta no existe
        os.mkdir(output_folder)  # Crea la carpeta
        if Config.DEBUG_PRINTS:
            print(f"Carpeta '{output_folder}' creada con éxito.")
    else:
        if Config.DEBUG_PRINTS:
            print(f"La carpeta '{output_folder}' ya existe.")

    # os.makedirs(output_folder, exist_ok=True)

    # Abrir el documento PDF
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

    # Iterar sobre cada página
    for page_number in range(len(pdf_document)):
        if page_number != 1:
            page = pdf_document.load_page(page_number)
            image_list = page.get_images(full=True)

            # Iterar sobre cada imagen de la página
            for image_index, img in enumerate(image_list, start=1):
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]

                # Verificar si la imagen tiene una máscara de transparencia
                smask = base_image.get("smask")
                if smask:
                    # Extraer la máscara de transparencia
                    mask_image = pdf_document.extract_image(smask)
                    mask_bytes = mask_image["image"]

                    # Cargar la imagen base y la máscara en PIL
                    with Image.open(io.BytesIO(image_bytes)) as base_img:
                        with Image.open(io.BytesIO(mask_bytes)) as mask_img:
                            # Asegurarse de que la máscara esté en modo 'L' (escala de grises)
                            if mask_img.mode != 'L':
                                mask_img = mask_img.convert('L')

                            # Combinar la imagen base y la máscara para conservar la transparencia
                            base_img.putalpha(mask_img)
                            background = Image.new("RGB", base_img.size, (255, 255, 255))
                            base_img = Image.alpha_composite(background.convert("RGBA"), base_img).convert("RGB")

                            # Guardar la imagen resultante con transparencia
                            image_filename = f"Imagen_{page_number + 1}_{image_index}.jpg"
                            image_path = os.path.join(output_folder, image_filename)
                            base_img.save(image_path)
                            
                            if Config.DEBUG_PRINTS:
                                print(f"Imagen guardada en: {image_path}")
                else:
                    # Si no hay máscara, guardar la imagen base directamente
                    with Image.open(io.BytesIO(image_bytes)) as base_img:
                        image_filename = f"Imagen_{page_number + 1}_{image_index}.jpg"
                        image_path = os.path.join(output_folder, image_filename)
                        if base_img.mode == "RGBA":
                            background = Image.new("RGB", base_img.size, (255, 255, 255))
                            base_img = Image.alpha_composite(background.convert("RGBA"), base_img).convert("RGB")
                        else:
                            base_img = base_img.convert("RGB")
                        base_img.save(image_path)
                        if Config.DEBUG_PRINTS:
                            print(f"Imagen guardada en: {image_path}")

    print("IMAGENES OBTENIDAS CON EXITO.")