import sys
import os
import webbrowser
import tkinter as tk
import ctypes
import threading
import time

import firebase_config

import firebase_config

# Inicializar Firestore
db = firebase_config.db

# Prueba de lectura/escritura
try:
    doc_ref = db.collection('test').document('test_doc')
    doc_ref.set({
        'test_field': 'test_value'
    })
    print("Conexión exitosa y datos escritos en Firestore.")
except Exception as e:
    print(f"Error al conectar con Firestore: {e}")


# Leer los datos de Firestore con manejo de errores
try:
    nfc_urls_doc = db.collection('nfc_data').document('nfc_urls').get()
    nfc_info_doc = db.collection('nfc_data').document('nfc_info').get()

    nfc_urls = nfc_urls_doc.to_dict() if nfc_urls_doc.exists else {}
    nfc_info = nfc_info_doc.to_dict() if nfc_info_doc.exists else {}

    spotify_config_doc = db.collection('config').document('spotify').get()
    spotify_config = spotify_config_doc.to_dict() if spotify_config_doc.exists else {}
except Exception as e:
    print(f"Error al acceder a Firestore: {e}")
    nfc_urls = {}
    nfc_info = {}
    spotify_config = {}

# Verifica que la configuración de Spotify esté completa
if all(key in spotify_config for key in ['client_id', 'client_secret', 'redirect_uri', 'scope']):
    # Configuración de autenticación de Spotify
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=spotify_config['client_id'],
                                                   client_secret=spotify_config['client_secret'],
                                                   redirect_uri=spotify_config['redirect_uri'],
                                                   scope=spotify_config['scope']))
else:
    print("Error: Configuración de Spotify incompleta en Firestore.")
    sp = None  # Manejo del caso en que la configuración de Spotify no esté disponible

spotify_opened = False  # Bandera para verificar si Spotify ya fue abierto
running = True  # Bandera para detener el hilo de lectura de NFC
spotify_running = True  # Bandera para verificar si Spotify está corriendo
last_uid = None  # Almacenar el último UID leído para evitar reproducir múltiples veces
info_printed = {}  # Diccionario para verificar si la información ya ha sido impresa para cada tarjeta

def play_album(url):
    if sp is None:
        print("Spotify no está configurado correctamente.")
        return

    # Extraer el URI del Spotify de la URL del álbum
    album_uri = url.split("/")[-1].split("?")[0]

    # Verificar y obtener dispositivos disponibles
    devices = None
    for _ in range(10):  # Intentar durante 10 segundos
        devices = sp.devices()
        if devices['devices']:
            break
        time.sleep(1)

    if devices and devices['devices']:
        # Usar el primer dispositivo disponible
        device_id = devices['devices'][0]['id']

        # Transferir la reproducción al dispositivo (esto ayuda a inicializar el estado de Spotify)
        sp.transfer_playback(device_id=device_id, force_play=True)

        # Desactivar el modo aleatorio
        sp.shuffle(state=False, device_id=device_id)

        # Esperar un momento para asegurarse de que el comando shuffle se procese
        time.sleep(1)

        # Reproducir el álbum en el dispositivo
        sp.start_playback(device_id=device_id, context_uri=f"spotify:album:{album_uri}")
    else:
        print("No hay dispositivos disponibles")
        
def get_spotify_user_info():
    try:
        user_info = sp.current_user()
        top_artists = sp.current_user_top_artists(limit=5)['items']
        top_tracks = sp.current_user_top_tracks(limit=5)['items']

        user_data = {
            "Usuario": {
                "Nombre": user_info['display_name'],
                "ID": user_info['id'],
                "Email": user_info['email']
            },
            "Top Artistas": [{"Nombre": artist['name'], "Géneros": artist['genres']} for artist in top_artists],
            "Top Canciones": [{"Título": track['name'], "Artista": track['artists'][0]['name']} for track in top_tracks]
        }
        return user_data
    except Exception as e:
        print(f"Error obteniendo información de usuario de Spotify: {e}")
        return {}

def get_album_info(url):
    try:
        album_id = url.split("/")[-1].split("?")[0]
        album_info = sp.album(album_id)

        album_data = {
            "Álbum": {
                "Nombre": album_info['name'],
                "Artista": album_info['artists'][0]['name'],
                "Fecha de lanzamiento": album_info['release_date'],
                "Total de canciones": album_info['total_tracks']
            }
        }
        return album_data
    except Exception as e:
        print(f"Error obteniendo información del álbum: {e}")
        return {}

def handle_uid(uid):
    global spotify_opened, last_uid, info_printed
    if uid == last_uid:
        return  # No hacer nada si el mismo UID se detecta nuevamente
    last_uid = uid

    if uid in nfc_urls:
        clear_label()  # Limpiar la etiqueta antes de comenzar
        update_label("Espera un momento")
        webbrowser.open(nfc_urls[uid])
        time.sleep(2)
        play_album(nfc_urls[uid])
        if not spotify_opened:
            resize_window(300, 300)
            spotify_opened = True
        monitor_spotify()

        # Obtener y mostrar información adicional
        user_info = get_spotify_user_info()
        album_info = get_album_info(nfc_urls[uid])
        card_info = nfc_info.get(uid, "No disponible")

        info = {
            "Tarjeta NFC": card_info,
            "Usuario de Spotify": user_info,
            "Álbum": album_info
        }

        if uid not in info_printed:
            display_info(info)
            info_printed[uid] = True

        # Secuencia de mensajes con retrasos
        root.after(2000, lambda: update_label("Ahora puedes retirar el display"))
        root.after(4000, lambda: update_label("Puedes hacerlo cuantas veces quieras"))
        root.after(6000, lambda: update_label("Para cerrar la app, cierra Spotify"))
        root.after(8000, lambda: update_label("O presiona la tecla F7"))
        root.after(10000, lambda: (clear_label(), root.after(2000, lambda: update_label("Acerca tu display al lector"))))  # Limpiar la etiqueta y mostrar mensaje inicial después de 2 segundos
    else:
        print("Display no compatible")
        update_label("Display no compatible")
    print("Información adicional de la tarjeta:", nfc_info.get(uid, "No disponible"))

def display_info(info):
    # Mostrar la información de manera ordenada
    print("Información de la tarjeta y Spotify:")
    for category, data in info.items():
        print(f"\n{category}:")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                print(f"  - {item}")

def read_nfc():
    global running, spotify_running
    try:
        while running and spotify_running:
            r = readers()
            if len(r) == 0:
                root.after(0, update_label, "Conecta tu New Face Connection Reader")
                time.sleep(1)
                continue
            else:
                root.after(0, update_label, "Acerca tu display al lector")
                reader = r[0]

                while running and spotify_running:
                    try:
                        connection = reader.createConnection()
                        connection.connect()

                        card_present = False
                        while running and spotify_running and not card_present:
                            try:
                                # Intentar leer la tarjeta
                                apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                                response, sw1, sw2 = connection.transmit(apdu)
                                if sw1 == 0x90 and sw2 == 0x00:
                                    uid = toHexString(response)
                                    card_info = get_card_info(connection, uid)
                                    nfc_info[uid] = card_info
                                    handle_uid(uid)
                                    card_present = True
                                else:
                                    time.sleep(0.5)
                            except Exception:
                                time.sleep(0.5)

                        if card_present:
                            while running and spotify_running and card_present:
                                try:
                                    # Verificar si la tarjeta sigue presente
                                    apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
                                    response, sw1, sw2 = connection.transmit(apdu)
                                    if not (sw1 == 0x90 and sw2 == 0x00):
                                        card_present = False
                                        last_uid = None  # Resetear el último UID al remover la tarjeta
                                        if uid in info_printed:
                                            del info_printed[uid]  # Permitir imprimir la información nuevamente cuando se lea una nueva tarjeta
                                    time.sleep(0.5)
                                except Exception:
                                    card_present = False
                                    last_uid = None  # Resetear el último UID al remover la tarjeta
                                    if uid in info_printed:
                                        del info_printed[uid]  # Permitir imprimir la información nuevamente cuando se lea una nueva tarjeta

                    except Exception:
                        time.sleep(0.5)

    except Exception as e:
        print(f"Error leyendo NFC: {e}")

def get_card_info(connection, uid):
    # Intentar leer más información de la tarjeta (por ejemplo, tipo de tarjeta y bloques de memoria)
    try:
        # Leer el tipo de tarjeta
        apdu = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        response, sw1, sw2 = connection.transmit(apdu)
        card_type = "Desconocido"
        if response:
            card_type = "MIFARE"  # Ejemplo simplificado, ajustar según tipo real

        # Leer los primeros bloques de memoria
        memory_data = {}
        for block in range(4):  # Leer los primeros 4 bloques como ejemplo
            apdu = [0xFF, 0xB0, 0x00, block, 0x10]  # Comando para leer un bloque
            response, sw1, sw2 = connection.transmit(apdu)
            if sw1 == 0x90 and sw2 == 0x00:
                memory_data[block] = toHexString(response)
            else:
                memory_data[block] = "No disponible"

        return {"UID": uid, "Tipo": card_type, "Memoria": memory_data}

    except Exception as e:
        return {"UID": uid, "Error": str(e)}

def check_nfc_reader():
    global current_label_text
    r = readers()
    if len(r) == 0:
        new_label_text = "Conecta tu New Face Connection Reader"
    else:
        new_label_text = "Acerca tu display al lector"
    
    if new_label_text != current_label_text:
        update_label(new_label_text)
        current_label_text = new_label_text
    
    root.after(1000, check_nfc_reader)  # Verificar cada segundo

def update_label(text):
    label.config(text=text)
    label.update_idletasks()
    update_canvas_size()

def clear_label():
    label.config(text="")
    label.update_idletasks()
    update_canvas_size()

def update_canvas_size():
    label.update_idletasks()
    bbox = label.bbox()
    if bbox:
        width, height = bbox[2], bbox[3]
        canvas.config(width=width + 40, height=height + 40)  # Ajuste para mayor espacio en el margen

def create_rounded_window(window, radius):
    # Obtener el manejador de la ventana
    hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

    # Crear una región redondeada
    region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, window.winfo_width(), window.winfo_height(), radius, radius)

    # Establecer la región redondeada como la forma de la ventana
    ctypes.windll.user32.SetWindowRgn(hwnd, region, True)

def resize_window(new_width, new_height):
    x = root.winfo_x()
    y = root.winfo_y()
    root.geometry(f"{new_width}x{new_height}+{x}+{y}")
    scale = min(new_width / 500, new_height / 500)
    canvas.scale("all", 0, 0, scale, scale)
    canvas.config(width=new_width, height=new_height)

    # Reposicionar la ventana en el área deseada después del redimensionamiento
    reposition_window()

    # Actualizar la forma de la ventana
    root.update_idletasks()
    create_rounded_window(root, int(50 * scale))

def reposition_window():
    # Ajustar estos valores según sea necesario para la posición final deseada
    final_x = 1500
    final_y = 300
    root.geometry(f"+{final_x}+{final_y}")

def monitor_spotify():
    def check_spotify():
        global spotify_running
        if not any("Spotify.exe" in p.name() for p in psutil.process_iter()):
            spotify_running = False
            root.quit()  # Cerrar la aplicación si Spotify no se está ejecutando
        else:
            root.after(1000, check_spotify)  # Verificar cada segundo

    check_spotify()

# Funciones para mover la ventana
def start_move(event):
    global x_start, y_start
    x_start = event.x
    y_start = event.y

def stop_move(event):
    global x_start, y_start
    x_start = None
    y_start = None

def on_move(event):
    x = event.x_root - x_start
    y = event.y_root - y_start
    root.geometry(f'+{x}+{y}')

# Funciones para redimensionar la ventana
def start_resize(event):
    global width_start, height_start, x_start, y_start
    width_start = root.winfo_width()
    height_start = root.winfo_height()
    x_start = event.x
    y_start = event.y

def on_resize(event):
    new_width = width_start + (event.x - x_start)
    new_height = height_start + (event.y - y_start)
    resize_window(new_width, new_height)

def on_closing():
    global running
    running = False
    root.after(100, check_thread_status)  # Verificar el estado del hilo después de un breve retraso

def check_thread_status():
    if not nfc_thread.is_alive():
        root.destroy()
    else:
        root.after(100, check_thread_status)

# Crear la interfaz gráfica
root = tk.Tk()
root.title("New Face Connection")
root.overrideredirect(True)  # Eliminar la barra de título y los bordes

# Mantener la ventana siempre en primer plano
root.attributes("-topmost", True)

# Configuración de la ventana principal
root.geometry("500x500")
root.configure(bg="#0E0E0E")

# Centrar la ventana en la pantalla
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x_cordinate = int((screen_width/2) - (500/2))
y_cordinate = int((screen_height/2) - (500/2))
root.geometry(f"{500}x500+{x_cordinate}+{y_cordinate}")

# Crear un Canvas para la personalización
canvas = tk.Canvas(root, width=500, height=500, bg="#0E0E0E", highlightthickness=0)
canvas.pack(fill="both", expand=True)

# Crear un rectángulo con bordes redondeados en el Canvas
def create_rounded_rectangle(canvas, x1, y1, x2, y2, radius=25, **kwargs):
    points = [
        x1 + radius, y1,
        x1 + radius, y1,
        x2 - radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, **kwargs, smooth=True)

rounded_rect = create_rounded_rectangle(canvas, 50, 100, 450, 450, radius=50, outline="#00ebff", width=12, fill="#121212")

# Cargar la imagen PNG
logo_image = Image.open(r"C:/Users/mario/OneDrive/Escritorio/NewFaceCode/programa/phyton/new-face.png")
logo_image = logo_image.resize((200, 200), resample=Image.LANCZOS) # Opcional: puedes usar Image.BILINEAR en lugar de Image.LANCZOS
logo_image = ImageTk.PhotoImage(logo_image)

# Crear el logo en el Canvas
logo = canvas.create_image(250, 275, image=logo_image)  # Ajustar la posición del logo para el nuevo diseño

# Asegúrate de mantener una referencia a logo_image para evitar que sea eliminado por el recolector de basura
canvas.logo_image = logo_image

# Crear un Frame para la etiqueta con padding y fondo transparente
label_frame = tk.Frame(root, bg="#0E0E0E")
label_window = canvas.create_window(250, 50, window=label_frame)  # Ajustar la posición de la etiqueta

# Etiqueta de instrucciones en el Frame
label = tk.Label(label_frame, text="", fg="#00ebff", bg="#0E0E0E", font=("Roboto", 12), padx=10, pady=5)
label.pack()

def update_label(text):
    label.config(text=text)
    label.update_idletasks()
    update_canvas_size()

def clear_label():
    label.config(text="")
    label.update_idletasks()
    update_canvas_size()

def update_canvas_size():
    label.update_idletasks()
    bbox = label.bbox()
    if bbox:
        width, height = bbox[2], bbox[3]
        canvas.config(width=width + 40, height=height + 40)  # Ajuste para mayor espacio en el margen

# Función para hacer desaparecer la etiqueta con fade out
def fade_out_label(alpha=1.0):
    if alpha > 0:
        alpha -= 0.05
        label.config(fg=f"#{int(255 * alpha):02x}{int(235 * alpha):02x}{int(255 * alpha):02x}")
        root.after(50, fade_out_label, alpha)
    else:
        canvas.itemconfig(label_window, state="hidden")

# Función para revisar el estado del lector NFC
current_label_text = ""  # Variable global para almacenar el texto actual de la etiqueta

def check_nfc_reader():
    global current_label_text
    r = readers()
    if len(r) == 0:
        new_label_text = "Conecta tu New Face Connection Reader"
    else:
        new_label_text = "Acerca tu display al lector"
    
    if new_label_text != current_label_text:
        update_label(new_label_text)
        current_label_text = new_label_text
    
    root.after(1000, check_nfc_reader)  # Verificar cada segundo

# Función para animar el rectángulo interno con ease-in y ease-out y efecto neón
def animate_rect():
    start_width = 8
    end_width = 12
    steps = 60
    current_step = 0
    growing = True

    def ease_in_out(t):
        return t * t * (3 - 2 * t)

    def pulse():
        nonlocal current_step, growing
        t = current_step / steps
        t = ease_in_out(t)

        if growing:
            new_width = start_width + (end_width - start_width) * t
        else:
            new_width = end_width - (end_width - start_width) * t

        canvas.itemconfig(rounded_rect, width=new_width)
        current_step += 1
        if current_step > steps:
            current_step = 0
            growing = not growing
        
        # Desenfoque simulado mediante el color del borde (ajuste según sea necesario)
        blur_factor = 0.1 + 0.9 * t if growing else 0.1 + 0.9 * (1 - t)
        new_color = f'#{int(0 * blur_factor):02x}{int(235 * blur_factor):02x}{int(255 * blur_factor):02x}'
        canvas.itemconfig(rounded_rect, outline=new_color)

        root.after(50, pulse)  # Cambiar cada 50 ms para una animación suave

    pulse()

# Función para cerrar la aplicación con F1
def close_app(event):
    on_closing()

# Vincular la tecla F1 para cerrar la aplicación
root.bind('<F7>', close_app)

# Iniciar la animación
animate_rect()

# Iniciar la revisión del lector NFC
check_nfc_reader()

# Iniciar la lectura de NFC en un hilo separado
nfc_thread = threading.Thread(target=read_nfc)
nfc_thread.start()

# Eventos para mover y redimensionar la ventana
root.bind('<ButtonPress-1>', start_move)
root.bind('<B1-Motion>', on_move)
root.bind('<ButtonRelease-1>', stop_move)

# Agregar un borde invisible para redimensionar la ventana
resize_frame = tk.Frame(root, cursor='bottom_right_corner', bg='#0E0E0E')
resize_frame.pack(side='right', anchor='se', fill='both', expand=True)
resize_frame.bind('<ButtonPress-1>', start_resize)
resize_frame.bind('<B1-Motion>', on_resize)

# Crear la región redondeada después de que la ventana se haya mostrado
root.update_idletasks()
create_rounded_window(root, 50)

# Manejar el cierre de la ventana correctamente
root.protocol("WM_DELETE_WINDOW", on_closing)

# Ejecutar la interfaz gráfica
root.mainloop()
