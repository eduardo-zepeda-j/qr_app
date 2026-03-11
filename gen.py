from fpdf import FPDF

machines = ["Aura-X5", "SwiftPick-V3", "Titan-Mini", "Cereal-Dry-2000", "Form-Logic-Pro"]
docs = ["Manual_Operacion", "Especificaciones", "Cuidados", "Ensamble"]

for machine in machines:
    for doc in docs:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt=f"{machine} - {doc.replace('_', ' ')}", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 10, txt="ESTO ES UNA SIMULACION, NO ES UN DOCUMENTO REAL.\n\n"
                                  "Este es un texto de relleno para probar la gestion de archivos "
                                  f"en la aplicacion de documentos para la maquina {machine}.")
        pdf.output(f"{machine}_{doc}.pdf")

print("¡PDFs generados con éxito!")