import fitz  # PyMuPDF
import pikepdf
import re

def extraer_estilos_y_texto(pdf_path):
    """
    Extrae texto junto con información de estilos como negrilla, color, tamaño, listas numeradas y bullets.
    """
    doc = fitz.open(pdf_path)
    resultados = []

    for page_num, page in enumerate(doc):
        texto_pagina = []
        bloques = page.get_text("dict")["blocks"]

        for bloque in bloques:
            for linea in bloque.get("lines", []):
                for span in linea.get("spans", []):
                    texto = span["text"].strip()
                    fuente = span["font"]  # Nombre de la fuente
                    negrilla = "Bold" in fuente or "Black" in fuente  # Detectar negrilla
                    color = span["color"]  # Color en formato entero
                    tamano = span["size"]  # Tamaño de fuente

                    # Convertir color de entero a RGB
                    color_rgb = (
                        (color >> 16) & 255,  # Rojo
                        (color >> 8) & 255,   # Verde
                        color & 255           # Azul
                    )

                    # Detectar numeración y bullets
                    es_bullet = re.match(r'^[-•◦▪‣✓]\s+', texto)
                    es_numerado = re.match(r'^\d+\.\s+', texto)
                    es_letra = re.match(r'^[a-zA-Z]\.\s+', texto)

                    texto_pagina.append({
                        "texto": texto,
                        "fuente": fuente,
                        "negrilla": negrilla,
                        "color": color_rgb,
                        "tamano": tamano,
                        "es_bullet": bool(es_bullet),
                        "es_numerado": bool(es_numerado),
                        "es_letra": bool(es_letra)
                    })

        resultados.append({
            "pagina": page_num + 1,
            "contenido": texto_pagina
        })

    return resultados

pdf_path = "documento_verticalizado_llaves_tablas_imagenes.pdf"  # Reemplaza con tu PDF
resultado = extraer_estilos_y_texto(pdf_path)

for pagina in resultado:
    print(f"\n## Página {pagina['pagina']} ##")
    for linea in pagina["contenido"]:
        print(f"Texto: {linea['texto']}")
        print(f" - Fuente: {linea['fuente']}")
        print(f" - Negrilla: {linea['negrilla']}")
        print(f" - Color: {linea['color']}")
        print(f" - Tamaño: {linea['tamano']}")
        if linea["es_bullet"]:
            print(" - Tipo: Bullet")
        if linea["es_numerado"]:
            print(" - Tipo: Lista Numerada")
        if linea["es_letra"]:
            print(" - Tipo: Lista Alfabética")
        print()