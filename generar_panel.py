import subprocess
import json
import os
import hashlib

# --- CONFIGURACIÓN ---
REMOTE = "onedrive_qr"
BASE_FOLDER = "CarpetaPrueba"
OUTPUT_ADMIN = "panel_admin.html" # Panel de uso estrictamente local/privado

# Carpeta que contendrá TODO lo que se va a subir a GitHub (index.html y la carpeta public)
GITHUB_DEPLOY_DIR = "github_deploy" 
OUTPUT_DASHBOARD = os.path.join(GITHUB_DEPLOY_DIR, "index.html")

# URL base pública para el dashboard alojado en GitHub Pages
# ⚠️ IMPORTANTE: Ajusta "TU_USUARIO" y "TU_REPO" según sea el caso de tu cuenta.
BASE_DASHBOARD_URL = "https://eduardo-zepeda-j.github.io/qr_creator/index.html"

def generar_id_maquina(nombre):
    """Genera un hash seguro y único como identificador de cada máquina."""
    return hashlib.sha256(nombre.encode('utf-8')).hexdigest()[:16]

def run_rclone(args):
    """Ejecuta comandos de rclone y retorna la salida."""
    try:
        result = subprocess.run(["rclone"] + args, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error ejecutando rclone: {e.stderr}")
        return None

DB_FILE = "links_db.json"

def cargar_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def guardar_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

def obtener_datos():
    print(f"🚀 Iniciando escaneo en {REMOTE}:{BASE_FOLDER}...")
    
    db = cargar_db()
    if db:
        print(f"📦 Se han encontrado {len(db)} enlaces cacheados en disco.")
    cambios_db = False
    
    # 1. Listar carpetas de máquinas
    dirs_json = run_rclone(["lsjson", f"{REMOTE}:{BASE_FOLDER}", "--dirs-only"])
    if not dirs_json: return {}
    
    carpetas = json.loads(dirs_json)
    biblioteca = {}

    try:
        for c in carpetas:
            nombre_maquina = c['Name']
            print(f"📦 Procesando Máquina: {nombre_maquina}...")
            
            # Generar o recuperar QR link de la carpeta
            # Generar o recuperar QR link de la carpeta
            clave_carpeta = f"carpeta_{nombre_maquina}"
            url_carpeta = ""
            if clave_carpeta in db:
                url_carpeta = db[clave_carpeta]
                print(f"  ⚡ Usando link cacheado (carpeta): {nombre_maquina}")
            else:
                print(f"  🔗 Generando QR link (carpeta): {nombre_maquina}")
                link_carpeta = run_rclone(["link", f"{REMOTE}:{BASE_FOLDER}/{nombre_maquina}"])
                if link_carpeta:
                    url_carpeta = link_carpeta.strip()
                    db[clave_carpeta] = url_carpeta
                    cambios_db = True

            # 2. Listar TODOS los documentos dentro de la carpeta de la máquina
            files_json = run_rclone(["lsjson", f"{REMOTE}:{BASE_FOLDER}/{nombre_maquina}", "--files-only"])
            
            documentos_encontrados = []
            if files_json:
                try:
                    archivos = json.loads(files_json)
                except json.JSONDecodeError:
                    print(f"  ⚠️ Advertencia: respuesta inválida al consultar la carpeta de {nombre_maquina}")
                    archivos = []
                
                if isinstance(archivos, list):
                    for f in archivos:
                        if not isinstance(f, dict):
                            continue
                        nombre_doc = f.get('Name')
                        if not nombre_doc:
                            continue
                            
                        clave_doc = f"doc_{nombre_maquina}_{nombre_doc}"
                        link_valido = ""
                        
                        is_image = nombre_doc.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))
                        
                        if is_image:
                            m_id = generar_id_maquina(nombre_maquina)
                            media_dir = os.path.join(GITHUB_DEPLOY_DIR, "public", "media", m_id)
                            os.makedirs(media_dir, exist_ok=True)
                            
                            nombre_base = os.path.splitext(nombre_doc)[0]
                            final_name = f"{nombre_base}.jpg"
                            final_path = os.path.join(media_dir, final_name)
                            url_relativa = f"public/media/{m_id}/{final_name}"
                            
                            if os.path.exists(final_path):
                                print(f"  ⚡ Usando imagen local cacheada: {nombre_doc}")
                                link_valido = url_relativa
                            else:
                                print(f"  📥 Descargando y comprimiendo imagen: {nombre_doc}")
                                tmp_path = os.path.join(media_dir, f"tmp_{nombre_doc}")
                                args_copy = ["copyto", f"{REMOTE}:{BASE_FOLDER}/{nombre_maquina}/{nombre_doc}", tmp_path]
                                res = subprocess.run(["rclone"] + args_copy, capture_output=True, text=True)
                                
                                if res.returncode == 0 and os.path.exists(tmp_path):
                                    try:
                                        from PIL import Image
                                        with Image.open(tmp_path) as img:
                                            if img.mode in ("RGBA", "P"):
                                                img = img.convert("RGB")
                                            # Redimensionar conservando relación de aspecto (max 1600x1600)
                                            img.thumbnail((1600, 1600))
                                            # Comprimir para carga hiper-rápida web
                                            img.save(final_path, "JPEG", quality=75, optimize=True)
                                        link_valido = url_relativa
                                    except ImportError:
                                        print(f"  ⚠️ Instalación faltante, instala Pillow para comprimir imágenes: pip install Pillow")
                                    except Exception as e:
                                        print(f"  ❌ Error al procesar imagen: {e}")
                                    finally:
                                        if os.path.exists(tmp_path):
                                            os.remove(tmp_path)
                                else:
                                    print(f"  ❌ Error descargando: {nombre_doc}")
                                    
                                if link_valido:
                                    db[clave_doc] = link_valido
                                    cambios_db = True
                        else:
                            if clave_doc in db:
                                link_valido = db[clave_doc]
                                print(f"  ⚡ Usando link cacheado para: {nombre_doc}")
                            else:
                                # 3. Obtener el link de visualización de OneDrive si no existe
                                print(f"  🔗 Generando link para: {nombre_doc}")
                                link = run_rclone(["link", f"{REMOTE}:{BASE_FOLDER}/{nombre_maquina}/{nombre_doc}"])
                                if link:
                                    link_valido = link.strip()
                                
                                if link_valido:
                                    db[clave_doc] = link_valido
                                    cambios_db = True
                        
                        if link_valido:
                            documentos_encontrados.append({
                                "nombre": nombre_doc,
                                "url": link_valido
                            })

            if documentos_encontrados or url_carpeta:
                biblioteca[nombre_maquina] = {
                    "qr_url": url_carpeta,
                    "documentos": documentos_encontrados
                }
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso cancelado por el usuario (Ctrl+C). Guardando enlaces generados hasta el momento...")
    finally:
        if cambios_db:
            guardar_db(db)
            print(f"💾 Base de datos de links (links_db.json) guardada/actualizada con {len(db)} enlaces.")

    return biblioteca

def crear_admin(datos):
    admin_data = {}
    for maquina, info in datos.items():
        admin_data[maquina] = {
            "id": generar_id_maquina(maquina)
        }
    
    json_data = json.dumps(admin_data)
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Panel Administrador - QRs</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
        <!-- Include jsPDF for PDF generation -->
        <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
        <style>
            :root {{
                --glass-bg: rgba(255, 255, 255, 0.15);
                --glass-border: rgba(255, 255, 255, 0.3);
                --text-color: #ffffff;
            }}
            body {{
                font-family: 'Outfit', sans-serif;
                background: linear-gradient(135deg, #1a1c20 0%, #2d3136 100%);
                background-attachment: fixed;
                color: #ffffff;
                min-height: 100vh;
            }}
            .glass-panel {{
                background: rgba(45, 49, 54, 0.6);
                backdrop-filter: blur(16px);
                -webkit-backdrop-filter: blur(16px);
                border: 1px solid rgba(255, 107, 0, 0.3);
                border-radius: 24px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
                padding: 2.5rem;
            }}
            .machine-card {{
                background: rgba(30, 33, 38, 0.8);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-left: 4px solid #ff6b00;
                border-radius: 12px;
                transition: all 0.3s ease;
                overflow: hidden;
            }}
            .machine-card:hover {{
                transform: translateY(-5px);
                border-color: #ff6b00;
                box-shadow: 0 10px 20px rgba(255, 107, 0, 0.2);
            }}
            .qr-container {{
                background: white;
                padding: 10px;
                border-radius: 8px;
                display: inline-block;
                margin-top: 10px;
                cursor: pointer;
                /* Smaller QR display for admin UI */
            }}
            .qr-container canvas, .qr-container img {{
                margin: 0 auto;
                width: 120px;
                height: 120px;
                pointer-events: none; /* Let clicks pass to the <a> tag */
            }}
            .btn-primary-glass {{
                background: linear-gradient(45deg, #ff6b00 0%, #ff8800 100%);
                color: #fff;
                border: 1px solid #ff8800;
                box-shadow: 0 4px 15px rgba(255, 107, 0, 0.4);
                transition: 0.3s;
                border-radius: 10px;
                font-weight: bold;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            .btn-primary-glass:hover {{
                box-shadow: 0 6px 20px rgba(255, 107, 0, 0.6);
                transform: translateY(-2px);
                color: white;
                background: linear-gradient(45deg, #ff8800 0%, #ff6b00 100%);
            }}
            /* Header action section */
            .admin-actions {{
                background: rgba(0,0,0,0.2);
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
        </style>
    </head>
    <body>
        <div class="container py-5">
            <div class="glass-panel">
                <div class="admin-actions">
                    <h1 class="mb-0 fw-bold" style="letter-spacing: 1px;">⚙️ Panel Admin</h1>
                    <button class="btn btn-primary-glass px-4 py-3" onclick="descargarTodosPDF()">
                        🖨️ Descargar Todos los QRs (PDF)
                    </button>
                </div>
                
                <p class="text-white-50 mb-4">
                    Los QRs generados apuntan a: <code>{BASE_DASHBOARD_URL}?id=[HASH_SEGURO]</code><br>
                    <strong>Nota:</strong> Ingresa a la carpeta <code>github_deploy/</code> y arrastra TODO su contenido a la raíz de tu GitHub Pages.
                </p>

                <div class="row g-4" id="grid-maquinas"></div>
            </div>
            
            <!-- Hidden container to render high-res QRs for the PDF -->
            <div id="hidden-qrs" style="display: none;"></div>
        </div>

        <script>
            const data = {json_data};
            const BASE_URL = "{BASE_DASHBOARD_URL}";

            function generarQR(text, containerId, size=120) {{
                const container = document.getElementById(containerId);
                if (!container) return null;
                container.innerHTML = '';
                if (!text) return null;
                return new QRCode(container, {{
                    text: text,
                    width: size,
                    height: size,
                    colorDark : "#000000",
                    colorLight : "#ffffff",
                    correctLevel : QRCode.CorrectLevel.H
                }});
            }}

            async function descargarTodosPDF() {{
                const {{ jsPDF }} = window.jspdf;
                const doc = new jsPDF({{ orientation: "portrait", unit: "mm", format: "a4" }});
                
                // Config A4
                const pageWidth = 210;
                const pageHeight = 297;
                
                // Config Grid (Ej: 3 columnas x 4 filas = 12 QRs por página)
                const marginX = 20;
                const marginY = 20;
                const cols = 3;
                const rows = 4;
                
                const cellW = (pageWidth - marginX * 2) / cols; // Ancho celda aprox 56mm
                const cellH = (pageHeight - marginY * 2) / rows; // Alto celda aprox 64mm
                
                const qrSize = 40; // Tamaño del QR en mm (bastante leíble)
                
                let currentItem = 0;
                const maquinas = Object.keys(data);
                
                if(maquinas.length === 0) {{
                    alert("No hay máquinas para exportar.");
                    return;
                }}

                // Generate high res dataURLs
                const hiddenContainer = document.getElementById('hidden-qrs');
                
                for (let i = 0; i < maquinas.length; i++) {{
                    const maquina = maquinas[i];
                    // Link to user dashboard using secure ID
                    const urlDestino = BASE_URL + "?id=" + encodeURIComponent(data[maquina].id);
                    
                    // Create temporary div for high res QR (500x500 px)
                    const tempDiv = document.createElement('div');
                    const tempId = 'hq-qr-' + i;
                    tempDiv.id = tempId;
                    hiddenContainer.appendChild(tempDiv);
                    
                    generarQR(urlDestino, tempId, 500);
                    
                    // Wait slightly for canvas to render
                    await new Promise(r => setTimeout(r, 50));
                    
                    const canvas = tempDiv.querySelector('canvas');
                    const qrDataUrl = canvas.toDataURL("image/png");
                    
                    // Positioning math
                    const rowIndex = Math.floor(currentItem / cols) % rows;
                    const colIndex = currentItem % cols;
                    
                    // Add new page if needed
                    if (currentItem > 0 && rowIndex === 0 && colIndex === 0) {{
                        doc.addPage();
                    }}
                    
                    const x = marginX + (colIndex * cellW);
                    const y = marginY + (rowIndex * cellH);
                    
                    // Draw crop marks (guias de recorte)
                    doc.setDrawColor(200, 200, 200);
                    doc.setLineWidth(0.2);
                    // Top-Left
                    doc.line(x, y-2, x, y+2); 
                    doc.line(x-2, y, x+2, y);
                    // Top-Right
                    doc.line(x+cellW, y-2, x+cellW, y+2); 
                    doc.line(x+cellW-2, y, x+cellW+2, y);
                    // Bottom-Left
                    doc.line(x, y+cellH-2, x, y+cellH+2); 
                    doc.line(x-2, y+cellH, x+2, y+cellH);
                    // Bottom-Right
                    doc.line(x+cellW, y+cellH-2, x+cellW, y+cellH+2); 
                    doc.line(x+cellW-2, y+cellH, x+cellW+2, y+cellH);
                    
                    // Draw QR centered in cell
                    const qrX = x + (cellW - qrSize) / 2;
                    const qrY = y + (cellH - qrSize) / 2 - 5; // A bit higher to leave room for text
                    doc.addImage(qrDataUrl, "PNG", qrX, qrY, qrSize, qrSize);
                    
                    // Draw Machine Name below QR
                    doc.setFontSize(10);
                    doc.setTextColor(0, 0, 0);
                    // Split text if too long
                    const textLines = doc.splitTextToSize(maquina, cellW - 5);
                    doc.text(textLines, x + cellW/2, qrY + qrSize + 5, {{ align: "center" }});
                    
                    currentItem++;
                    hiddenContainer.innerHTML = ''; // clean up
                }}
                
                doc.save("QRs_Para_Imprimir.pdf");
            }}

            function cargarMaquinasAdmin() {{
                const grid = document.getElementById('grid-maquinas');
                grid.innerHTML = '';
                
                Object.keys(data).forEach((maquina, index) => {{
                    const qrId = 'qr-' + index;
                    const urlDestino = BASE_URL + "?id=" + encodeURIComponent(data[maquina].id);
                    
                    const col = document.createElement('div');
                    col.className = 'col-lg-3 col-md-4 col-sm-6'; // Smaller cards for more density
                    
                    let htmlCard = `
                        <div class="card h-100 machine-card p-3 text-center">
                            <h4 class="card-title h6 fw-bold mb-2 text-white">${{maquina}}</h4>
                            <a href="${{urlDestino}}" target="_blank" class="text-decoration-none" title="Haz clic para abrir el Dashboard de esta máquina">
                                <div class="qr-container mx-auto shadow-sm" style="transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'" id="${{qrId}}"></div>
                            </a>
                            <small class="text-white-50 mt-2" style="font-size: 0.7rem;">Clic en el QR para ir al Dashboard</small>
                        </div>`;
                        
                    col.innerHTML = htmlCard;
                    grid.appendChild(col);
                    
                    setTimeout(() => generarQR(urlDestino, qrId, 120), 100);
                }});
            }}

            cargarMaquinasAdmin();
        </script>
    </body>
    </html>
    """
    with open(OUTPUT_ADMIN, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"\n✅ Panel ADMIN generado en: '{OUTPUT_ADMIN}'")


def crear_dashboard(datos):
    # Crear estructura para publicación
    public_data_dir = os.path.join(GITHUB_DEPLOY_DIR, "public", "data")
    os.makedirs(public_data_dir, exist_ok=True)
    
    # Exportar JSON seguro individualizado por cada máquina
    for maquina, info in datos.items():
        m_id = generar_id_maquina(maquina)
        datos_maquina = {
            "nombre": maquina,
            "documentos": info["documentos"]
        }
        with open(os.path.join(public_data_dir, f"{m_id}.json"), "w", encoding="utf-8") as f:
            json.dump(datos_maquina, f, ensure_ascii=False)
            
    html_template = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Documentos de Máquina</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {{
                --glass-bg: rgba(255, 255, 255, 0.15);
                --glass-border: rgba(255, 255, 255, 0.3);
            }}
            body {{
                font-family: 'Outfit', sans-serif;
                background: linear-gradient(135deg, #1a1c20 0%, #2d3136 100%);
                background-attachment: fixed;
                color: #ffffff;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 20px;
            }}
            .glass-panel {{
                background: rgba(45, 49, 54, 0.6);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 107, 0, 0.3);
                border-radius: 24px;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
                padding: 3rem;
                width: 100%;
                max-width: 800px;
            }}
            .btn-pdf {{ 
                text-align: left; 
                padding: 18px 25px; 
                font-size: 1.2rem; 
                border-radius: 15px;
                background: rgba(30, 33, 38, 0.8);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-left: 4px solid #ff6b00;
                color: white;
                font-weight: 500;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 15px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }}
            .btn-pdf:hover {{
                background: rgba(255, 107, 0, 0.1);
                transform: translateY(-5px);
                border-color: #ff6b00;
                color: #ff6b00;
                box-shadow: 0 8px 25px rgba(255, 107, 0, 0.2);
            }}
            .machine-card {{
                background: rgba(30, 33, 38, 0.8);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-left: 4px solid #ff6b00;
                border-radius: 12px;
                transition: all 0.3s ease;
                padding: 20px;
                text-align: center;
            }}
            .machine-card:hover {{
                transform: translateY(-5px);
                border-color: #ff6b00;
                box-shadow: 0 10px 20px rgba(255, 107, 0, 0.2);
            }}
            .btn-nav {{
                display: inline-flex;
                align-items: center;
                gap: 10px;
                padding: 10px 20px;
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.1);
                color: white;
                text-decoration: none;
                transition: 0.3s;
                border: 1px solid rgba(255, 255, 255, 0.2);
                margin-bottom: 25px;
                font-weight: 600;
            }}
            .btn-nav:hover {{
                background: rgba(255, 107, 0, 0.2);
                border-color: #ff6b00;
                color: #ff6b00;
            }}
            .error-state {{
                text-align: center;
                opacity: 0.8;
            }}
        </style>
    </head>
    <body>
        <div class="glass-panel" id="main-content">
            <div id="nav-container"></div>
            <div class="text-center mb-5">
                <h1 id="titulo-pagina" class="display-4 fw-bold mb-3" style="letter-spacing: -1px;">Cargando...</h1>
                <p id="subtitulo-pagina" class="lead opacity-75">Centro de Documentación</p>
            </div>
            
            <div class="row g-4" id="contenedor-dinamico">
                <!-- Contenido inyectado por JS -->
            </div>
        </div>

        <script>
            const urlParams = new URLSearchParams(window.location.search);
            const idParam = urlParams.get('id');

            const titulo = document.getElementById('titulo-pagina');
            const subtitulo = document.getElementById('subtitulo-pagina');
            const contenedor = document.getElementById('contenedor-dinamico');
            const navContainer = document.getElementById('nav-container');

            async function cargarDatos() {{
                if (!idParam) {{
                    mostrarError();
                    return;
                }}

                try {{
                    // Solo solicitamos la información de este identificador
                    const response = await fetch(`public/data/${{idParam}}.json`);
                    if (!response.ok) throw new Error("No encontrado");
                    const data = await response.json();
                    mostrarDocumentos(data);
                }} catch (error) {{
                    mostrarError();
                }}
            }}

            function mostrarError() {{
                document.title = "Acceso Denegado";
                titulo.innerText = "Acceso Denegado";
                subtitulo.innerText = "Por favor, escanee un código QR válido.";
                contenedor.innerHTML = `
                    <div class="error-state py-4 w-100">
                        <h4 class="text-white">QR Inválido o Máquina no encontrada</h4>
                        <p class="text-white-50">Acceso restringido. Por favor, utilice el panel o el código QR exacto que le fue asignado al equipo.</p>
                    </div>`;
            }}

            function mostrarDocumentos(maquinaData) {{
                document.title = maquinaData.nombre + " - Documentos";
                titulo.innerText = maquinaData.nombre;
                subtitulo.innerText = "Documentos y Recursos";
                contenedor.className = "d-grid gap-4";
                
                const documentos = maquinaData.documentos || [];
                
                if (documentos.length === 0) {{
                    contenedor.innerHTML = `
                        <div class="alert alert-info border-0 rounded-4" style="background: rgba(255,255,255,0.2); color: white;">
                            No hay documentos disponibles para esta máquina en este momento.
                        </div>`;
                    return;
                }}
                
                // Separar imágenes de otros documentos
                const isImage = (name) => name.toLowerCase().match(/\.(jpg|jpeg|png|gif|webp)$/);
                const imagenes = documentos.filter(doc => isImage(doc.nombre));
                const otrosDocs = documentos.filter(doc => !isImage(doc.nombre));

                contenedor.innerHTML = '';

                // Renderizar imágenes resaltadas en la parte superior
                if (imagenes.length > 0) {{
                    const gallery = document.createElement('div');
                    gallery.className = "row g-4 mb-3";
                    
                    imagenes.forEach(img => {{
                        const col = document.createElement('div');
                        col.className = "col-12 text-center";
                        col.innerHTML = `
                            <div class="p-3 rounded-4" style="background: rgba(30, 33, 38, 0.8); border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 5px 15px rgba(0,0,0,0.3);">
                                <h5 class="text-white mb-3" style="font-size: 1rem; opacity: 0.9;">${{img.nombre}}</h5>
                                <div style="border-radius: 12px; overflow: hidden; background: #000;">
                                    <img src="${{img.url}}" alt="${{img.nombre}}" class="img-fluid" style="max-height: 400px; width: 100%; object-fit: contain;">
                                </div>
                                <div class="mt-3">
                                    <a href="${{img.url}}" target="_blank" class="btn btn-sm btn-outline-light px-4 rounded-pill">Ver tamaño original</a>
                                </div>
                            </div>
                        `;
                        gallery.appendChild(col);
                    }});
                    
                    contenedor.appendChild(gallery);
                }}

                // Renderizar botones para los demás documentos
                if (otrosDocs.length > 0) {{
                    const listContainer = document.createElement('div');
                    listContainer.className = "d-grid gap-3";
                    
                    otrosDocs.forEach(doc => {{
                        const btn = document.createElement('a');
                        btn.href = doc.url;
                        btn.target = "_blank";
                        btn.className = "btn-pdf text-decoration-none";
                        
                        let icon = '📄';
                        const nameLower = doc.nombre.toLowerCase();
                        if (nameLower.endsWith('.pdf')) icon = '📕';
                        else if (nameLower.match(/\.(doc|docx)$/)) icon = '📘';
                        else if (nameLower.match(/\.(xls|xlsx|csv)$/)) icon = '📗';
                        else if (nameLower.match(/\.(mp4|mov|avi)$/)) icon = '🎥';
                        else if (nameLower.match(/\.(zip|rar|7z)$/)) icon = '📦';
                        
                        btn.innerHTML = `<span style="font-size: 2rem">${{icon}}</span> <span>${{doc.nombre}}</span>`;
                        listContainer.appendChild(btn);
                    }});
                    
                    contenedor.appendChild(listContainer);
                }}
            }}

            cargarDatos();
        </script>
    </body>
    </html>
    """
    with open(OUTPUT_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"✅ Panel USUARIO generado en: '{OUTPUT_DASHBOARD}'")


if __name__ == "__main__":
    biblioteca_datos = obtener_datos()
    if biblioteca_datos:
        crear_admin(biblioteca_datos)
        crear_dashboard(biblioteca_datos)
        print(f"\\n¡Todo listo!\\n- Panel Administrativo LOCAL (No público) generado en: {OUTPUT_ADMIN}")
        print(f"- Archivos listos para subir a GitHub generados en la carpeta: '{GITHUB_DEPLOY_DIR}'")
        print("\\n🔒 INSTRUCCIONES DE SEGURIDAD Y DEPLOY A GITHUB:")
        print(f"  1. Ve a la carpeta '{GITHUB_DEPLOY_DIR}' en tu explorador de archivos.")
        print("  2. Arrastra TODO el contenido que está dentro (el archivo 'index.html' y la carpeta 'public') directamente a tu repositorio en github.com.")
        print("     Asegúrate de dejarlos en la raíz (es decir, que al entrar a tu repo se vea qr_creator/index.html y qr_creator/public/).")
        print("  Nunca subas 'generar_panel.py', 'links_db.json' ni 'panel_admin.html'.")
    else:
        print("❌ No se encontraron datos o carpetas.")