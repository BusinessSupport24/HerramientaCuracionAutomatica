import re
import numpy as np
import pikepdf
import fitz  # PyMuPDF
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io
import sys
import Config
# ===== Funciones auxiliares para matrices =====

def make_matrix(a, b, c, d, e, f):
    """
    Crea una matriz 3x3 afín usando la notación PDF:
      [ a   b   e ]
      [ c   d   f ]
      [ 0   0   1 ]
    """
    return np.array([[a, b, e],
                     [c, d, f],
                     [0, 0, 1]], dtype=float)

def apply_matrix(M, point):
    """Aplica la matriz M a un punto (x, y) y retorna (x', y')."""
    x, y = point
    v = np.array([x, y, 1])
    res = M.dot(v)
    return res[0], res[1]

# ===== Tokenización y procesamiento del stream =====

def tokenize_content(content):
    """
    Tokeniza el contenido extrayendo:
      - Nombres (ej. /XObj)
      - Números (enteros o decimales)
      - Operadores: q, Q, cm, Do
    """
    token_pattern = r'(/[^\s]+)|([+-]?\d*\.\d+|[+-]?\d+)|(q|Q|cm|Do)'
    tokens = []
    for m in re.finditer(token_pattern, content):
        if m.group(1):
            tokens.append(m.group(1))
        elif m.group(2):
            tokens.append(m.group(2))
        elif m.group(3):
            tokens.append(m.group(3))
    return tokens

def process_tokens(tokens):
    """
    Recorre la lista de tokens simulando la interpretación:
      - 'q' empuja la CTM actual en un stack.
      - 'Q' la saca.
      - 'cm' toma los 6 tokens previos, forma una matriz y actualiza la CTM.
      - 'Do' se registra el nombre del XObject (token previo) junto con la CTM actual.
    Retorna una lista de tuplas: (nombre_xobject, CTM_invocación)
    """
    ctm_stack = [np.identity(3)]
    results = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == 'q':
            ctm_stack.append(ctm_stack[-1].copy())
            i += 1
        elif token == 'Q':
            if len(ctm_stack) > 1:
                ctm_stack.pop()
            else:
                if Config.DEBUG_PRINTS:
                    print("¡Advertencia! Stack CTM vacío.")
            i += 1
        elif token == 'cm':
            if i < 6:
                if Config.DEBUG_PRINTS:
                    print("No hay suficientes tokens para 'cm'")
                i += 1
                continue
            try:
                nums = list(map(float, tokens[i-6:i]))
            except Exception as e:
                if Config.DEBUG_PRINTS:
                    print("Error al convertir tokens a float:", e)
                i += 1
                continue
            m = make_matrix(*nums)
            ctm_stack[-1] = ctm_stack[-1].dot(m)
            i += 1
        elif token == 'Do':
            if i == 0:
                i += 1
                continue
            # Se asume que el token inmediatamente anterior es el nombre (por ej, /XObjName)
            xobj_name = tokens[i-1]
            results.append((xobj_name, ctm_stack[-1].copy()))
            i += 1
        else:
            i += 1
    return results

# ===== Función para inyectar los XObjects calculados =====

def inline_xobjects_with_transform(pdf_bytes, output_pdf_path):
    """
    Abre el PDF desde un objeto BytesIO, calcula para cada XObject (no imagen) la transformación
    final (usando la CTM de invocación y la matriz interna) y deduce un transformador
    T_inj que mapea el /BBox interno al bounding box final. Luego inyecta el contenido
    del XObject, envuelto con ese operador de transformación, en el stream principal de
    la página en el punto de inserción calculado.
    Se guarda el PDF modificado en output_pdf_path.
    """
    # Asegurarse de estar al inicio del stream
    pdf_bytes.seek(0)
    
    # Abrir con pikepdf usando el BytesIO
    with pikepdf.open(pdf_bytes) as pdf:
        # Para visualización opcional, abrimos también con PyMuPDF
        pdf_bytes.seek(0)
        doc_fitz = fitz.open("pdf", stream=pdf_bytes.getvalue())
        
        # Recorremos cada página del PDF
        for page in pdf.pages:
            if page.get("/Contents") is None:
                continue
            if isinstance(page.Contents, pikepdf.Array):
                original_content = ""
                for obj in page.Contents:
                    try:
                        original_content += obj.read_bytes().decode("latin1", errors="ignore") + "\n"
                    except Exception:
                        continue
            else:
                original_content = page.Contents.read_bytes().decode("latin1", errors="ignore")
            
            # Procesar el stream para obtener las invocaciones de XObjects
            tokens = tokenize_content(original_content)
            xobject_usages = process_tokens(tokens)
            inline_content = ""
            
            # Acceder a los recursos de la página
            resources = page.get("/Resources")
            if resources is None or "/XObject" not in resources:
                continue
            xobjects = resources["/XObject"]

            for usage in xobject_usages:
                xobj_name, ctm_content = usage
                # Solo procesamos los XObjects que estén en Resources y que no sean imágenes
                xobj = xobjects.get(xobj_name)
                if xobj is None:
                    continue
                subtype = xobj.get("/Subtype")
                if subtype == "/Image":
                    continue
                bbox = xobj.get("/BBox")
                if bbox is None:
                    continue
                # Convertir /BBox a float
                orig_x0, orig_y0, orig_x1, orig_y1 = (float(bbox[0]), float(bbox[1]),
                                                        float(bbox[2]), float(bbox[3]))
                # Obtener la matriz interna, si existe, o usar la identidad
                matrix = xobj.get("/Matrix")
                if matrix is not None:
                    matrix = [float(v) for v in matrix]
                    internal_matrix = make_matrix(*matrix)
                else:
                    internal_matrix = np.identity(3)
                
                # La CTM final aplicada al XObject
                final_ctm = ctm_content.dot(internal_matrix)
                
                # Calcular las 4 esquinas del /BBox original
                corners = [(orig_x0, orig_y0), (orig_x0, orig_y1),
                           (orig_x1, orig_y0), (orig_x1, orig_y1)]
                transformed_corners = [apply_matrix(final_ctm, pt) for pt in corners]
                xs = [pt[0] for pt in transformed_corners]
                ys = [pt[1] for pt in transformed_corners]
                final_bbox = (min(xs), min(ys), max(xs), max(ys))
                final_width = final_bbox[2] - final_bbox[0]
                final_height = final_bbox[3] - final_bbox[1]
                
                if (orig_x1 - orig_x0) == 0 or (orig_y1 - orig_y0) == 0:
                    continue
                scale_x = final_width / (orig_x1 - orig_x0)
                scale_y = final_height / (orig_y1 - orig_y0)
                trans_x = final_bbox[0] - orig_x0 * scale_x
                trans_y = final_bbox[1] - orig_y0 * scale_y

                # Cadena de transformación a inyectar (se envuelve con q ... Q)
                transform_str = f"{scale_x} 0 0 {scale_y} {trans_x} {trans_y} cm\n"
                try:
                    xobj_content = xobj.read_bytes().decode("latin1", errors="ignore")
                except Exception:
                    continue
                inline_piece = "q\n" + transform_str + xobj_content + "\nQ\n"
                inline_content += inline_piece
                
                # Información de depuración
                if Config.DEBUG_PRINTS:
                    print(f"XObject {xobj_name}:")
                    print(f"  /BBox original: ({orig_x0:.2f}, {orig_y0:.2f}, {orig_x1:.2f}, {orig_y1:.2f})")
                    print("  CTM de invocación (contenido):")
                    print(ctm_content)
                    print("  /Matrix interna:")
                    print(internal_matrix)
                    print("  CTM final aplicada:")
                    print(final_ctm)
                    insertion_point = apply_matrix(final_ctm, (0, 0))
                    print(f"  Punto de inserción: ({insertion_point[0]:.2f}, {insertion_point[1]:.2f})")
                    print(f"  Bounding box final: ({final_bbox[0]:.2f}, {final_bbox[1]:.2f}, {final_bbox[2]:.2f}, {final_bbox[3]:.2f})")
                    print(f"  Dimensiones finales: {final_width:.2f} x {final_height:.2f}")
                    print(f"  Factor de escala aplicado: ({scale_x:.4f}, {scale_y:.4f})")
                    print(f"  Traslación aplicada: ({trans_x:.2f}, {trans_y:.2f})\n")
            
            # Si se han generado inyecciones, anexarlas al stream original de la página
            if inline_content:
                new_content = original_content + "\n" + inline_content
                new_stream = pdf.make_stream(new_content.encode("latin1"))
                page.Contents = new_stream

        # pdf.save(output_pdf_path)
    # print(f"PDF modificado guardado en: {output_pdf_path}")
    return pdf

# ===== Función para convertir pdfplumber a BytesIO =====

def pdfplumber_to_fitz(pdf):
    pdf_bytes = io.BytesIO()
    pdf.stream.seek(0)  # Asegurar que estamos al inicio del stream
    pdf_bytes.write(pdf.stream.read())  # Escribir el contenido en memoria
    pdf_bytes.seek(0)
    return pdf_bytes

# ===== Función principal =====

def main(pdf_bytes, output_pdf_path):
    return inline_xobjects_with_transform(pdf_bytes, output_pdf_path)

# ===== Bloque principal para ejecución individual =====

if __name__ == "__main__":
    # Si se pasa un argumento, se asume que es la ruta de un PDF
    if len(sys.argv) > 1:
        input_pdf_path = sys.argv[1]
        with open(input_pdf_path, "rb") as f:
            pdf_bytes = io.BytesIO(f.read())
    # else:
    #     input_pdf = "Circular POWER Canal Presencial CON pago anticipado_010325.pdf"
    #     with open(input_pdf, "rb") as f:
    #         pdf_bytes = io.BytesIO(f.read())
    output_pdf = "inlined.pdf"
    inline_xobjects_with_transform(pdf_bytes, output_pdf)
