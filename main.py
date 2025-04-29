import sys, os
import logging
from logging.handlers import RotatingFileHandler
from kivy.core.window import Window
import custom_widgets

# Configuración inicial de la ventana
Window.size = (360, 640)

# ----------------------------
# Configuración de Logging con RotatingFileHandler
# ----------------------------
LOG_FILE = "app.log"
LOG_MAX_BYTES = 1_000_000  # 1 MB por archivo
LOG_BACKUP_COUNT = 3

# Creamos un logger específico para nuestra app
logger = logging.getLogger("myapp")
if not logger.handlers:  # Si aún no se han agregado handlers...
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    # No usamos logging.debug() de inmediato para evitar posibles recursiones

# Ahora, si en alguna parte usamos logger.debug("..."), usaremos nuestro logger "myapp"
logger.debug("Logger 'myapp' configurado correctamente.")

# ----------------------------
# Importaciones de Kivy y Pantallas
# ----------------------------
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp

# Importar pantallas (asegúrate de que estas están en la carpeta 'screens')
from screens.main_menu import MainMenu
from screens.add_envio import AddEnvio
from screens.add_recepcion import AddRecepcion
from screens.manage_matches import ManageMatches
from screens.pdf_report import PDFReport
from screens.modify_operacion import ModifyOperacion
from screens.swipe_matches import SwipeMatches

# Importar módulos de backend (ahora usando SQLite)
from backend import operations
from backend.operations import fetch_paises_envio, fetch_paises_recepcion


# Componentes personalizados y utilidades
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.animation import Animation
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.properties import StringProperty, NumericProperty, ListProperty, ObjectProperty
from kivymd.uix.label import MDLabel
from kivymd.uix.chip import MDChip, MDChipText
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.list import OneLineListItem, OneLineIconListItem, IconLeftWidget
from kivymd.uix.card import MDCard
from kivy.app import App

# Función helper para centrar menús
def center_menu(menu):
    menu.pos = ((Window.width - menu.width) / 2, (Window.height - menu.height) / 2)

# Función helper para crear dropdowns
def crear_dropdown_menu(caller, items, auto_open=True, **kwargs):
    from kivymd.uix.menu import MDDropdownMenu
    from kivy.metrics import dp
    defaults = {
        "position": "center",
        "width_mult": 4,
        "radius": [24, 24, 24, 0],
        "elevation": 2,
        "max_height": dp(300),
        "border_margin": dp(20),
        "background_color": (1, 1, 1, 0.98),
    }
    defaults.update(kwargs)
    menu = MDDropdownMenu(caller=caller, items=items, **defaults)
    from kivy.clock import Clock
    Clock.schedule_once(lambda dt: center_menu(menu), 0.1)
    if auto_open:
        menu.open()
    return menu



# Definición de widgets personalizados...
class MyChip(MDChip):
    def __init__(self, **kwargs):
        super(MyChip, self).__init__(**kwargs)
        self.md_bg_color = (0.9, 0.9, 0.9, 1)
        self.text_color = (0, 0, 0, 1)
        self.add_widget(MDChipText(text=self.text))

    def on_kv_post(self, base_widget):
        if "text" in self.ids:
            self.ids.text.text_color = self.text_color

    def eliminar_chip(self, instance):
        if self.parent:
            self.parent.remove_widget(self)

class BadgeLabel(MDLabel):
    badge_color = ListProperty([0, 0, 0, 0])
    def __init__(self, **kwargs):
        super(BadgeLabel, self).__init__(**kwargs)
        self.bind(text=self.update_color)
    def update_color(self, instance, text):
        try:
            count = int(text) if text else 0
            self.badge_color = ((1, 0, 0, 1) if count > 0 else (0.5, 0.5, 0.5, 1) if text else (0, 0, 0, 0))
        except ValueError:
            self.badge_color = (0, 0, 0, 0)

class SwipeCard(RelativeLayout):
    match_text = StringProperty("")
    rotation = NumericProperty(0)
    threshold = NumericProperty(100)
    card_color = ListProperty([0.2, 0.6, 0.8, 1])
    match_data = ObjectProperty(None)

    def __init__(self, **kwargs):
        super(SwipeCard, self).__init__(**kwargs)
        self.size_hint = (0.8, 0.6)
        self.pos_hint = {"center_x": 0.5, "center_y": 0.5}
        with self.canvas.before:
            from kivy.graphics import Color, RoundedRectangle
            Color(rgba=self.card_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(15)])
        self.content = BoxLayout(orientation="vertical", padding=dp(20), spacing=dp(10))
        self.label = MDLabel(
            text=self.match_text,
            halign="center",
            theme_text_color="Primary",
            font_style="H6",
            valign="middle",
        )
        self.content.add_widget(self.label)
        self.add_widget(self.content)
        self.bind(pos=self.update_rect, size=self.update_rect, match_text=self.update_label_text)

    def update_label_text(self, instance, value):
        self.label.text = value

    def update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.initial_touch_pos = touch.pos
            return True
        return super(SwipeCard, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            try:
                dx = touch.x - touch.ox
                dy = touch.y - touch.oy
                self.rotation = dx * 0.2
                self.x += dx * 0.3
                self.y += dy * 0.3
                if abs(dx) > abs(dy):
                    self.card_color = [1, 0.5, 0, 1] if dx > 0 else [0.8, 0.2, 0.2, 1]
                return True
            except Exception as e:
                logging.exception("Error en on_touch_move de SwipeCard")
        return super(SwipeCard, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            try:
                dx = touch.x - touch.ox
                dy = touch.y - touch.oy
                if abs(dx) > self.threshold or abs(dy) > self.threshold:
                    self.finalizar_swipe(dx, dy)
                else:
                    self.reset_position()
                return True
            except Exception as e:
                logging.exception("Error en on_touch_up de SwipeCard")
        return super(SwipeCard, self).on_touch_up(touch)

    def finalizar_swipe(self, dx, dy):
        try:
            direction = (
                "right" if dx > 0 else
                "left" if abs(dx) > abs(dy) else
                "up" if dy > 0 else "down"
            )
            anim = Animation(
                x=self.x + dx * 2,
                y=self.y + dy * 2,
                rotation=self.rotation * 2,
                opacity=0,
                duration=0.3,
            )
            anim.bind(on_complete=lambda *x: self.procesar_swipe(direction))
            anim.start(self)
        except Exception as e:
            logging.exception("Error en finalizar_swipe de SwipeCard")

    def procesar_swipe(self, direction):
        try:
            app = MDApp.get_running_app()
            if not self.match_data or "MatchID" not in self.match_data:
                logging.error("match_data falta la clave 'MatchID' en SwipeCard")
                return
            if direction in ["right", "up"]:
                # Verifica que el parent tenga los ids esperados antes de acceder a ellos.
                if self.parent and hasattr(self.parent, "ids") and "main_card" in self.parent.ids:
                    if self == self.parent.ids.main_card:
                        from backend.operations import confirm_match_ui
                        confirm_match_ui(self.match_data["MatchID"])
                else:
                    # Aquí se puede implementar lógica adicional para matches secundarios.
                    pass
            else:
                from backend.operations import reject_match_ui
                reject_match_ui(self.match_data["MatchID"])
            if hasattr(app, "cargar_matches"):
                app.cargar_matches()
        except Exception as e:
            logging.exception("Error en procesar_swipe de SwipeCard")

    def reset_position(self):
        try:
            Animation.cancel_all(self)
            if self.parent:
                new_x = self.parent.center_x - self.width / 2
                new_y = self.parent.center_y - self.height / 2
            else:
                new_x, new_y = 0, 0  # Valor por defecto en caso de no tener parent
            anim = Animation(x=new_x, y=new_y, rotation=0, duration=0.3)
            anim.start(self)
        except Exception as e:
            logging.exception("Error en reset_position de SwipeCard")



class VerticalSwipeCard(MDCard):
    # Propiedades para guardar la posición original y la posición inicial del toque
    original_pos = ListProperty([0, 0])
    initial_touch_pos = ListProperty([0, 0])
    
    def __init__(self, **kwargs):
        super(VerticalSwipeCard, self).__init__(**kwargs)
        self.match_data = None  # Inicialmente en None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Guarda la posición actual y la posición de inicio del toque
            self.original_pos = self.pos[:]
            self.initial_touch_pos = touch.pos[:]
            return True
        return super(VerticalSwipeCard, self).on_touch_down(touch)
    
    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos):
            try:
                dx = touch.x - self.initial_touch_pos[0]
                dy = touch.y - self.initial_touch_pos[1]
                self.pos = (self.original_pos[0] + dx, self.original_pos[1] + dy)
                return True
            except Exception as e:
                print("Error en on_touch_move:", e)
        return super(VerticalSwipeCard, self).on_touch_move(touch)
    
    def on_touch_up(self, touch):
        from kivymd.app import MDApp
        if self.collide_point(*touch.pos):
            app = MDApp.get_running_app()
            swipe_screen = app.root.get_screen("swipe_matches")
            top_card    = swipe_screen.ids.top_card
            bottom_card = swipe_screen.ids.bottom_card
            envio_data  = self.match_data.get("envio")  # dict con 'id', 'monto', etc.

            # 1) Si se suelta SOBRE la tarjeta superior:
            if self.collide_widget(top_card) and top_card.match_data:
                recep_id = top_card.match_data["recepcion"]["id"]
                app.marcar_como_pendiente(envio_data["id"], recep_id)

            # 2) Si se suelta SOBRE la tarjeta inferior:
            elif self.collide_widget(bottom_card) and bottom_card.match_data:
                recep_id = bottom_card.match_data["recepcion"]["id"]
                app.marcar_como_pendiente(envio_data["id"], recep_id)

            # 3) Finalmente, devolver la carta a su lugar y refrescar
            self.reset_position()
            return True

        return super(VerticalSwipeCard, self).on_touch_up(touch)


    
    def reset_position(self):
        # Animación para regresar la tarjeta a su posición predefinida
        Animation(pos=self.original_pos, duration=0.3).start(self)






# ----------------------------
# Clase Principal de la Aplicación
# ----------------------------
class MyApp(MDApp):
    
    dialog = None
    match_seleccionado = None
    selected_envio_countries = []
    selected_recepcion_countries = []
    operacion_seleccionada = None
    current_matches = []
    current_main_match = None
    title = "Gestor de Matches Oficina"
    icon = "assets/62838.png"

    def build(self):
        # ————————————————————————————————————————————
        # 0) Asegurarnos de que Python pueda importar custom_widgets
        #    (añadimos la carpeta base al inicio de sys.path)
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        if base_path not in sys.path:
            sys.path.insert(0, base_path)
        # ————————————————————————————————————————————

        self.theme_cls.primary_palette = "Blue"
        sm = ScreenManager()

        # 1) Carpeta de KV empaquetados
        kv_dir = os.path.join(base_path, "kv")

        # 2) Lista de nombres de KV
        kv_names = [
            "main_menu.kv",
            "add_envio.kv",
            "add_recepcion.kv",
            "manage_matches.kv",
            "pdf_report.kv",
            "modify_operacion.kv",
            "swipe_matches.kv",
        ]

        # 3) Carga dinámica de cada KV
        for name in kv_names:
            kv_path = os.path.join(kv_dir, name)
            if os.path.exists(kv_path):
                Builder.load_file(kv_path)
            else:
                logger.warning(f"KV no encontrado: {kv_path}")

        # 4) Registrar pantallas
        sm.add_widget(MainMenu(name="main_menu"))
        sm.add_widget(AddEnvio(name="add_envio"))
        sm.add_widget(AddRecepcion(name="add_recepcion"))
        sm.add_widget(ManageMatches(name="manage_matches"))
        sm.add_widget(PDFReport(name="pdf_report"))
        sm.add_widget(ModifyOperacion(name="modify_operacion"))
        sm.add_widget(SwipeMatches(name="swipe_matches"))

        return sm

    def on_start(self):
        self.update_badge_matches()

    def set_focus(self, field_id):
        def focus_callback(dt):
            screen = self.root.current_screen
            if hasattr(screen.ids, field_id):
                screen.ids[field_id].focus = True
        Clock.schedule_once(focus_callback, 0.1)
        
    def marcar_como_pendiente(self, envio_id: int, recepcion_id: int):
        """
        Llamada desde el swipe: mueve el par a pendientes y refresca pantallas.
        """
        from backend.operations import marcar_pendiente
        marcar_pendiente(envio_id, recepcion_id)
        # Recarga matches y actualiza badge
        self.cargar_matches()
        self.update_badge_matches()


    # Funciones de dropdown para envío, recepción y modificación
    def open_dropdown_envio(self):
        from backend.file_manager import load_available_countries
        available = load_available_countries()
        menu_items = [{"text": country} for country in available]
        # Agregamos la opción de Nuevo País
        menu_items.append({"text": "Nuevo País"})
        caller = self.root.get_screen("add_envio").ids.btn_agregar_pais

        # Crear el dropdown con auto_open=True para que se abra inmediatamente
        self.menu_envio = crear_dropdown_menu(caller, menu_items, auto_open=True, hor_growth="left", ver_growth="up")
        
        # Asignamos la acción para cada ítem
        def set_item(name_item):
            if name_item == "Nuevo País":
                self.open_new_country_dialog(context="envio")
            else:
                if name_item in self.selected_envio_countries:
                    self.confirm_deselect_country(name_item, "envio")
                else:
                    self.selected_envio_countries.append(name_item)
                    self.update_selected_label("envio")
            # Cerramos el dropdown de Agregar País
            self.menu_envio.dismiss()
    
        for item in menu_items:
            text_item = item["text"]
            item["on_release"] = lambda text_item=text_item: set_item(text_item)


    def open_dropdown_recepcion(self):
        from backend.file_manager import load_available_countries
        available = load_available_countries()
        menu_items = [{"text": country} for country in available]
        menu_items.append({"text": "Nuevo País"})
        caller = self.root.get_screen("add_recepcion").ids.btn_agregar_pais
        self.menu_recepcion = crear_dropdown_menu(caller, menu_items, auto_open=True, hor_growth="left", ver_growth="up")
        def set_item(name_item):
            if name_item == "Nuevo País":
                self.open_new_country_dialog(context="recepcion")
            else:
                if name_item in self.selected_recepcion_countries:
                    self.confirm_deselect_country(name_item, "recepcion")
                else:
                    self.selected_recepcion_countries.append(name_item)
                    self.update_selected_label("recepcion")
            self.menu_recepcion.dismiss()
        for item in menu_items:
            text_item = item["text"]
            item["on_release"] = lambda text_item=text_item: set_item(text_item)

    def open_dropdown_modificacion(self):
        from backend.file_manager import load_available_countries
        available = load_available_countries()
        menu_items = [{"text": country} for country in available]
        menu_items.append({"text": "Nuevo País"})
        caller = self.root.get_screen("modify_operacion").ids.btn_agregar_pais
        self.menu_paises = crear_dropdown_menu(caller, menu_items, auto_open=True, hor_growth="left", ver_growth="up")
        def set_item(name_item):
            if name_item == "Nuevo País":
                self.open_new_country_dialog(context="modificacion")
            else:
                if not hasattr(self, "selected_modificacion_countries"):
                    self.selected_modificacion_countries = []
                if name_item in self.selected_modificacion_countries:
                    self.confirm_deselect_country(name_item, "modificacion")
                else:
                    self.selected_modificacion_countries.append(name_item)
                    self.update_selected_label("modificacion")
            self.menu_paises.dismiss()
        for item in menu_items:
            text_item = item["text"]
            item["on_release"] = lambda text_item=text_item: set_item(text_item)

    def update_selected_label(self, context="envio"):
        if context == "envio":
            container = self.root.get_screen("add_envio").ids.chips_container_envio
            container.clear_widgets()
            for country in self.selected_envio_countries:
                chip = MyChip(text=country)
                chip.unbind(on_release=chip.eliminar_chip)
                chip.bind(on_release=lambda instance, c=country: self.confirm_deselect_country(c, "envio"))
                container.add_widget(chip)
        elif context == "recepcion":
            container = self.root.get_screen("add_recepcion").ids.chips_container_recepcion
            container.clear_widgets()
            for country in self.selected_recepcion_countries:
                chip = MyChip(text=country)
                chip.unbind(on_release=chip.eliminar_chip)
                chip.bind(on_release=lambda instance, c=country: self.confirm_deselect_country(c, "recepcion"))
                container.add_widget(chip)
        elif context == "modificacion":
            container = self.root.get_screen("modify_operacion").ids.chips_container_modificacion
            container.clear_widgets()
            if hasattr(self, "selected_modificacion_countries"):
                for country in self.selected_modificacion_countries:
                    chip = MyChip(text=country)
                    chip.unbind(on_release=chip.eliminar_chip)
                    chip.bind(on_release=lambda instance, c=country: self.confirm_deselect_country(c, "modificacion"))
                    container.add_widget(chip)
            else:
                self.selected_modificacion_countries = []

    def confirm_deselect_country(self, country, context):
        def remove_country(instance):
            if context == "envio":
                if country in self.selected_envio_countries:
                    self.selected_envio_countries.remove(country)
                    self.update_selected_label("envio")
            elif context == "recepcion":
                if country in self.selected_recepcion_countries:
                    self.selected_recepcion_countries.remove(country)
                    self.update_selected_label("recepcion")
            elif context == "modificacion":
                if country in self.selected_modificacion_countries:
                    self.selected_modificacion_countries.remove(country)
                    self.update_selected_label("modificacion")
            dialog.dismiss()
        dialog = MDDialog(
            title="Deseleccionar país",
            text=f"¿Deseas deseleccionar el país {country}?",
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: dialog.dismiss()),
                MDFlatButton(text="CONFIRMAR", on_release=remove_country),
            ],
        )
        dialog.open()

    def open_new_country_dialog(self, context="envio"):
        dialog_content = Builder.load_string(
            """
BoxLayout:
    orientation: 'vertical'
    size_hint_y: None
    height: dp(60)
    MDTextField:
        id: input_new_country
        hint_text: "Ingrese el nuevo país"
        size_hint_x: None
        width: dp(200)
        pos_hint: {"center_x": 0.5}
        multiline: False
"""
        )
        self.dialog = MDDialog(
            title="Agregar Nuevo País",
            type="custom",
            content_cls=dialog_content,
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda x: self.dialog.dismiss()),
                MDFlatButton(
                    text="AGREGAR",
                    on_release=lambda x: self.agregar_nuevo_pais(context, dialog_content.ids.input_new_country.text),
                ),
            ],
        )
        self.dialog.open()
        Clock.schedule_once(lambda dt: setattr(dialog_content.ids.input_new_country, "focus", True), 0.2)

    def agregar_nuevo_pais(self, context, new_country):
        new_country = new_country.strip().upper()
        if new_country:
            from backend.file_manager import add_new_country
            add_new_country(new_country)
            if context == "envio":
                if new_country not in self.selected_envio_countries:
                    self.selected_envio_countries.append(new_country)
                self.update_selected_label("envio")
            elif context == "recepcion":
                if new_country not in self.selected_recepcion_countries:
                    self.selected_recepcion_countries.append(new_country)
                self.update_selected_label("recepcion")
            elif context == "modificacion":
                if not hasattr(self, "selected_modificacion_countries"):
                    self.selected_modificacion_countries = []
                if new_country not in self.selected_modificacion_countries:
                    self.selected_modificacion_countries.append(new_country)
                self.update_selected_label("modificacion")
        self.dialog.dismiss()

    def guardar_envio(self, monto, paises_widgets):
        try:
            monto_str = monto.replace(",", "")
            monto_float = float(monto_str)
            paises_formateados = ", ".join([chip.text for chip in paises_widgets])
        except Exception as e:
            self.mostrar_dialogo("Error", "Datos ingresados no válidos")
            return
        from backend.operations import check_duplicate_operation, add_envio_ui
        if check_duplicate_operation(monto_float, paises_formateados, "envio"):
            self._finalizar_guardado_envio(monto_float, paises_formateados)
        else:
            self._finalizar_guardado_envio(monto_float, paises_formateados)

    def _finalizar_guardado_envio(self, monto, paises):
        from backend.operations import add_envio_ui
        resultado = add_envio_ui(monto, paises)
        self.mostrar_dialogo("¡Listo!", resultado)
        self.reset_screen("add_envio")
        self.root.current = "main_menu"

    def guardar_recepcion(self, monto, paises_widgets):
        try:
            monto_str = monto.replace(",", "")
            monto_float = float(monto_str)
            paises_formateados = ", ".join([chip.text for chip in paises_widgets])
        except Exception as e:
            self.mostrar_dialogo("Error", "Datos ingresados no válidos")
            return
        from backend.operations import check_duplicate_operation, add_recepcion_ui
        if check_duplicate_operation(monto_float, paises_formateados, "recepcion"):
            self._finalizar_guardado_recepcion(monto_float, paises_formateados)
        else:
            self._finalizar_guardado_recepcion(monto_float, paises_formateados)

    def _finalizar_guardado_recepcion(self, monto, paises):
        from backend.operations import add_recepcion_ui
        resultado = add_recepcion_ui(monto, paises)
        self.mostrar_dialogo("¡Listo!", resultado)
        self.reset_screen("add_recepcion")
        self.root.current = "main_menu"

    def reset_screen(self, screen_name):
        screen = self.root.get_screen(screen_name)
        if screen_name == "add_envio":
            screen.ids.envio_monto.text = ""
            screen.ids.chips_container_envio.clear_widgets()
            self.selected_envio_countries = []
        elif screen_name == "add_recepcion":
            screen.ids.recepcion_monto.text = ""
            screen.ids.chips_container_recepcion.clear_widgets()
            self.selected_recepcion_countries = []
        screen.dispatch("on_enter")

    def mostrar_dialogo(self, title, text):
        if self.dialog:
            self.dialog.dismiss()
        self.dialog = MDDialog(
            title=title,
            text=text,
            buttons=[MDFlatButton(text="CERRAR", on_release=lambda x: self.dialog.dismiss())],
        )
        self.dialog.open()

    def go_to_matches(self):
        """
        Cambia a la pantalla swipe_matches, carga los envíos con sus recepciones candidatas,
        rota las tarjetas y actualiza el badge.
        """
        from backend.operations import get_available_matches

        # 1) Cambiar pantalla
        self.root.current = "swipe_matches"
        # 2) Obtener lista de bloques {envio, candidatas}
        self.current_matches = get_available_matches()
        # 3) Mostrar en tarjetas
        self.rotar_cartas()
        # 4) Actualizar indicador
        self.update_badge_matches()


    def cargar_matches(self):
        from backend.operations import get_available_matches
        self.current_matches = get_available_matches()
        self.rotar_cartas()

    def actualizar_matches(self):
        swipe_screen = self.root.get_screen("swipe_matches")
        if not self.current_matches:
            from kivymd.uix.label import MDLabel
            swipe_screen.ids.card_container.clear_widgets()
            swipe_screen.ids.card_container.add_widget(
                MDLabel(text="No hay matches disponibles", halign="center")
            )
            return

        # Tarjeta Central: Mostrar información de la contraparte
        base_match = self.current_matches[0]
        central_text = (
            f"Match Principal\n"
            f"Tipo: {base_match.get('TipoContraparte', 'N/A')}\n"  # Tipo opuesto
            f"ID: {base_match.get('MatchID', 'N/A')}\n"
            f"Monto: ${base_match.get('SumaTotal', 0):.2f}\n"       # Monto de la contraparte
            f"País: {base_match.get('Pais', 'N/A')}"
        )
        swipe_screen.ids.label_central_card.text = central_text
        swipe_screen.ids.central_card.opacity = 1

        # Tarjeta Superior: Mostrar la información de origen
        candidates = self.current_matches[1:]
        if len(candidates) >= 1:
            candidate_top = candidates[0]
            top_text = (
                f"Match Superior\n"
                f"Tipo: {candidate_top.get('Tipo', 'N/A')}\n"
                f"ID: {candidate_top.get('MatchID', 'N/A')}\n"
                f"Monto: ${candidate_top.get('MontoObjetivo', 0):.2f}\n"
                f"País: {candidate_top.get('Pais', 'N/A')}"
            )
            swipe_screen.ids.label_top_card.text = top_text
            swipe_screen.ids.top_card.opacity = 1
        else:
            swipe_screen.ids.top_card.opacity = 0

        # Tarjeta Inferior: Mostrar la información de origen del siguiente candidato, si existe
        if len(candidates) >= 2:
            candidate_bottom = candidates[1]
            bottom_text = (
                f"Match Inferior\n"
                f"Tipo: {candidate_bottom.get('Tipo', 'N/A')}\n"
                f"ID: {candidate_bottom.get('MatchID', 'N/A')}\n"
                f"Monto: ${candidate_bottom.get('MontoObjetivo', 0):.2f}\n"
                f"País: {candidate_bottom.get('Pais', 'N/A')}"
            )
            swipe_screen.ids.label_bottom_card.text = bottom_text
            swipe_screen.ids.bottom_card.opacity = 1
        else:
            swipe_screen.ids.bottom_card.opacity = 0



    def rotar_cartas(self):
        """
        Actualiza las tarjetas de swipe_matches:
        - Central: datos del envío (ID, monto, países del envío)
        - Superior/Inferior: hasta 2 recepciones candidatas, mostrando
        sólo el/los país(es) en común.
        """
        swipe = self.root.get_screen("swipe_matches")
        bloques = self.current_matches

        if not bloques:
            swipe.ids.label_central_card.text = "No hay envíos con candidatas 🎀"
            swipe.ids.central_card.opacity = 1
            swipe.ids.top_card.opacity = swipe.ids.bottom_card.opacity = 0
            return

        bloque = bloques[0]
        envio = bloque["envio"]
        recs  = bloque["candidatas"]
        paises_e = fetch_paises_envio(envio["id"])

        # — Central (envío) —
        swipe.ids.central_card.match_data = {"envio": envio}
        swipe.ids.label_central_card.text = (
            f"Envío ID: {envio['id']}\n"
            f"Monto: ${envio['monto']:.2f}\n"
            f"Paises: {', '.join(sorted(paises_e))}"
        )
        swipe.ids.central_card.opacity = 1

        # — Superior (recepción 1) —
        if len(recs) >= 1:
            r1 = recs[0]
            comunes = paises_e & fetch_paises_recepcion(r1["id"])
            swipe.ids.top_card.match_data = {"recepcion": r1}
            swipe.ids.label_top_card.text = (
                f"Recep. ID: {r1['id']}\n"
                f"Monto: ${r1['monto']:.2f}\n"
                f"Paises: {', '.join(sorted(comunes)) or 'N/A'}"
            )
            swipe.ids.top_card.opacity = 1
        else:
            swipe.ids.top_card.opacity = 0

        # — Inferior (recepción 2) —
        if len(recs) >= 2:
            r2 = recs[1]
            comunes = paises_e & fetch_paises_recepcion(r2["id"])
            swipe.ids.bottom_card.match_data = {"recepcion": r2}
            swipe.ids.label_bottom_card.text = (
                f"Recep. ID: {r2['id']}\n"
                f"Monto: ${r2['monto']:.2f}\n"
                f"Paises: {', '.join(sorted(comunes)) or 'N/A'}"
            )
            swipe.ids.bottom_card.opacity = 1
        else:
            swipe.ids.bottom_card.opacity = 0






    def mostrar_seleccion_mes(self):
        from kivymd.uix.menu import MDDropdownMenu
        spanish_months = [
            "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ]
        meses = [{"text": f"{i:02d} - {spanish_months[i-1]}", "on_release": lambda x=i: self.generar_pdf_seleccionado(x)}
                 for i in range(1, 13)]
        caller = self.root.get_screen("main_menu").ids.btn_pdf
        self.menu_meses = crear_dropdown_menu(caller, meses)
        Clock.schedule_once(lambda dt: setattr(self.menu_meses, "pos", ((Window.width - self.menu_meses.width) / 2,
                                                                         (Window.height - self.menu_meses.height) / 2)), 0.1)

    def generar_pdf_seleccionado(self, mes):
        from backend.operations import generate_pdf_report_ui
        resultado = generate_pdf_report_ui(mes)
        self.mostrar_dialogo("Resultado", resultado)
        self.menu_meses.dismiss()

    def seleccionar_operacion(self, oper, tipo):
        """
        Muestra los datos de la operación (envio/recepcion) y carga sus chips.
        """
        self.operacion_seleccionada = oper
        screen = self.root.get_screen("modify_operacion")

        # Identificar ID y países según tipo
        if tipo == "envio":
            op_id   = oper["NumeroOperacion"]
            op_pais = oper.get("PaisEnvio", "")
        else:
            op_id   = oper["NumeroOperacion"]
            op_pais = oper.get("PaisRecepcion", "")

        # Texto informativo
        screen.ids.lbl_operacion_info.text = (
            f"Operación {tipo.capitalize()} ID {op_id} | Monto ${oper['Monto']:.2f}"
            + (f" | Países: {op_pais}" if op_pais else "")
        )

        # Reiniciar campo monto
        screen.ids.nuevo_monto.hint_text = f"Monto Original: {oper['Monto']:.2f}"
        screen.ids.nuevo_monto.text = ""

        # Cargar países en la lista interna
        self.selected_modificacion_countries = [p.strip() for p in op_pais.split(",") if p.strip()]

        # ¡Mostrar chips en pantalla!
        self.update_selected_label("modificacion")


    def crear_contenido_operaciones(self, items):
        from kivy.uix.boxlayout import BoxLayout
        from kivymd.uix.list import MDList
        layout = BoxLayout(orientation="vertical", size_hint_y=None)
        layout.bind(minimum_height=layout.setter("height"))
        lista = MDList()
        for item in items:
            lista.add_widget(item)
        layout.add_widget(lista)
        return layout

    def reset_modify_screen(self):
        """
        Limpia completamente la pantalla de modificar operación:
        - Resetea textos e inputs
        - Elimina todos los chips de países
        - Cierra dropdowns si están abiertos
        - Limpia la selección interna de países
        """
        screen = self.root.get_screen("modify_operacion")

        # 1) Reset de labels e inputs
        if "lbl_operacion_info" in screen.ids:
            screen.ids.lbl_operacion_info.text = "No se ha seleccionado ninguna operación."
        if "nuevo_monto" in screen.ids:
            screen.ids.nuevo_monto.text = ""
            screen.ids.nuevo_monto.hint_text = "Monto orig."

        # 2) Limpiar chips de modificación
        if "chips_container_modificacion" in screen.ids:
            screen.ids.chips_container_modificacion.clear_widgets()

        # 3) Reiniciar lista interna de países
        self.selected_modificacion_countries = []

        # 4) Cerrar menús si quedaron abiertos
        if hasattr(self, "menu_operaciones") and self.menu_operaciones:
            try: self.menu_operaciones.dismiss()
            except: pass
            self.menu_operaciones = None
        if hasattr(self, "menu_tipo_operaciones") and self.menu_tipo_operaciones:
            try: self.menu_tipo_operaciones.dismiss()
            except: pass
            self.menu_tipo_operaciones = None


    def crear_boton_dialogo(self, texto, on_release):
        return MDFlatButton(text=texto, on_release=on_release)
    
    def modificar_operacion(self):
        if not self.operacion_seleccionada:
            self.mostrar_dialogo("Error", "No se ha seleccionado ninguna operación.")
            return
        screen = self.root.get_screen("modify_operacion")
        nuevo_monto = screen.ids.nuevo_monto.text
        nuevos_paises = ", ".join(self.selected_modificacion_countries) if hasattr(self, "selected_modificacion_countries") and self.selected_modificacion_countries else ""
        from backend.operations import modify_operacion_ui
        op_id = self.operacion_seleccionada.get("NumeroOperacion")
        if op_id is None:
            self.mostrar_dialogo("Error", "La operación seleccionada no tiene un ID válido.")
            return
        resultado = modify_operacion_ui(op_id, nuevo_monto, nuevos_paises)
        self.mostrar_dialogo("Resultado", resultado)
        self.reset_modify_screen()
        self.root.current = "main_menu"
        
    def update_badge_matches(self):
        try:
            from backend.operations import get_available_matches
            matches = get_available_matches()
            count = len(matches)
            if not self.root or "main_menu" not in self.root.screen_names:
                logger.warning("La pantalla 'main_menu' aún no está disponible para actualizar el badge.")
                return
            screen = self.root.get_screen("main_menu")
            if "badge_matches" in screen.ids:
                screen.ids.badge_matches.text = str(count) if count > 0 else ""
        except Exception as e:
            logger.exception("Error al actualizar badge de matches.")
            
   
        
    def mostrar_menu_operaciones(self):
        # menú de tipo
        from kivymd.uix.menu import MDDropdownMenu
        items = [
            {"text": "Envíos",      "on_release": lambda: self.mostrar_operaciones_dropdown("envio")},
            {"text": "Recepciones", "on_release": lambda: self.mostrar_operaciones_dropdown("recepcion")},
        ]
        caller = self.root.get_screen("modify_operacion").ids.btn_seleccionar_operacion
        self.menu_tipo_operaciones = crear_dropdown_menu(caller, items, hor_growth="right", ver_growth="down", width_mult=5)




    def mostrar_operaciones_dropdown(self, tipo):
        """
        Muestra un dropdown con las últimas operaciones de tipo 'envio' o 'recepcion'.
        Descarta cualquier menú previo para evitar WidgetException.
        """
        from backend.operations import get_last_operations
        from kivymd.uix.menu import MDDropdownMenu
        # Si ya hay un menú abierto, ciérralo antes
        if hasattr(self, "menu_operaciones") and self.menu_operaciones:
            try:
                self.menu_operaciones.dismiss()
            except Exception:
                pass
            self.menu_operaciones = None
        if hasattr(self, "menu_tipo_operaciones") and self.menu_tipo_operaciones:
            try:
                self.menu_tipo_operaciones.dismiss()
            except Exception:
                pass
            self.menu_tipo_operaciones = None

        operaciones = get_last_operations(tipo, limit=10)
        if not operaciones:
            self.mostrar_dialogo("Info", f"No hay operaciones de {tipo} disponibles.")
            return

        items = []
        for op in operaciones:
            pais = op["PaisEnvio"] if tipo == "envio" else op["PaisRecepcion"]
            txt  = f"ID: {op['NumeroOperacion']} - Monto: ${op['Monto']:.2f} - País: {pais}"
            items.append({
                "text": txt,
                "viewclass": "OneLineListItem",
                "on_release": lambda op=op, tp=tipo: self.seleccionar_operacion_dropdown(op, tp)
            })

        caller = self.root.get_screen("modify_operacion").ids.btn_seleccionar_operacion
        self.menu_operaciones = MDDropdownMenu(
            caller=caller,
            items=items,
            width_mult=5,
            position="center",
            hor_growth="right",
            ver_growth="down",
            max_height=300,
        )
        self.menu_operaciones.open()





    def seleccionar_operacion_dropdown(self, oper, tipo):
        """
        Cierra menús y pasa a modificar operación con contexto 'envio' o 'recepcion'.
        """
        # Cerrar dropdowns
        if self.menu_operaciones and self.menu_operaciones.parent:
            self.menu_operaciones.dismiss()
        if self.menu_tipo_operaciones and self.menu_tipo_operaciones.parent:
            self.menu_tipo_operaciones.dismiss()

        # Guardar contexto
        self.operacion_tipo = tipo
        self.seleccionar_operacion(oper, tipo)
        self.root.current = "modify_operacion"


    # Método para cargar los matches en la pantalla ManageMatches
    def cargar_matches_manage(self):
        screen = self.root.get_screen("manage_matches")
        lista = screen.ids.lista_matches
        lista.clear_widgets()
        matches = operations.get_available_matches()
        for match in matches:
            # Crear un item con los detalles del match
            item = OneLineListItem(
                text=f"Match ID: {match['MatchID']} - Monto: ${match['MontoObjetivo']:.2f} - País: {match['Pais']}",
                on_release=self.seleccionar_match  # Asigna la función para seleccionar el match
            )
            # Guardamos la data del match en el propio item
            item.match_data = match
            lista.add_widget(item)

    # Función para almacenar el match seleccionado cuando se toca un item
    def seleccionar_match(self, instance):
        self.match_seleccionado = instance.match_data
        # Aquí puedes cambiar el aspecto del item para resaltar la selección
        for item in instance.parent.children:
            item.bg_color = (1, 1, 1, 1)  # Color por defecto (blanco)
        instance.bg_color = (0.7, 0.9, 1, 1)  # Color de selección (un azul clarito kawaii)
        self.mostrar_dialogo("¡Match seleccionado!", f"Seleccionaste el match ID: {instance.match_data['MatchID']}")

    # Función que se llama desde el botón "Confirmar Match Seleccionado"
    def confirmar_match(self):
        if not self.match_seleccionado:
            self.mostrar_dialogo("¡Uy, Onii-Chan!", "Por favor, selecciona un match primero.")
            return
        # Llamar a la función del backend para confirmar el match
        result = operations.confirm_match_ui(self.match_seleccionado["MatchID"])
        self.mostrar_dialogo("Confirmación", result)
        # Limpiar la selección y actualizar la lista de matches
        self.match_seleccionado = None
        self.cargar_matches_manage()
        self.update_badge_matches()
        
    def mostrar_matches_pendientes(self):
        """
        Diálogo con lista detallada de matches pendientes.
        Permite 'Reactivar' o 'Concluir' sin salir de este diálogo.
        """
        from backend.operations import get_pending_matches
        from kivymd.uix.boxlayout import MDBoxLayout
        from kivymd.uix.scrollview import MDScrollView
        from kivymd.uix.list import ThreeLineIconListItem
        from kivymd.uix.list import IconLeftWidget
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton

        pending = get_pending_matches()
        if not pending:
            self.mostrar_dialogo("Información", "No hay matches pendientes por cerrar.")
            return

        content = MDBoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None)
        content.bind(minimum_height=content.setter("height"))
        scroll = MDScrollView(size_hint=(1, None), size=(dp(300), dp(300)))
        lista = MDBoxLayout(orientation="vertical", spacing=dp(5), size_hint_y=None)
        lista.bind(minimum_height=lista.setter("height"))

        for m in pending:
            item = ThreeLineIconListItem(
                text=f"PENDIENTE ID {m['pending_id']}",
                secondary_text=f"Env {m['envio_id']} ({m['paises_envio']}) → Rec {m['recepcion_id']} ({m['paises_recepcion']})",
                tertiary_text=f"Monto Env: ${m['monto_envio']:.2f} | Monto Rec: ${m['monto_recepcion']:.2f}"
            )
            item.match = m
            icon = IconLeftWidget(icon="refresh")
            item.add_widget(icon)
            item.bind(on_release=lambda inst, mm=m: self._dialog_pendiente_action(mm))
            lista.add_widget(item)

        scroll.add_widget(lista)
        content.add_widget(scroll)

        self.dialog = MDDialog(
            title="Matches Pendientes",
            type="custom",
            content_cls=content,
            buttons=[MDFlatButton(text="CERRAR", on_release=lambda x: self.dialog.dismiss())]
        )
        self.dialog.open()


    def _dialog_pendiente_action(self, match):
        from kivymd.uix.dialog import MDDialog
        from kivymd.uix.button import MDFlatButton

        texto = (
            f"Pendiente ID {match['pending_id']}\n\n"
            f"Envío {match['envio_id']} (${match['monto_envio']:.2f}) | "
            f"Paises: {match['paises_envio']}\n\n"
            f"Recepción {match['recepcion_id']} (${match['monto_recepcion']:.2f}) | "
            f"Paises: {match['paises_recepcion']}\n\n"
            "¿Qué deseas hacer?"
        )
        dlg = MDDialog(
            title="Acción sobre Match Pendiente",
            text=texto,
            buttons=[
                MDFlatButton(text="REACTIVAR", on_release=lambda x: self._reactivar(match, dlg)),
                MDFlatButton(text="CONCLUIR",   on_release=lambda x: self._concluir(match, dlg))
            ],
        )
        dlg.open()


    def _reactivar(self, match, dialog):
        from backend.operations import reactivate_pending
        reactivate_pending(match['envio_id'], match['recepcion_id'])
        dialog.dismiss()
        self.dialog.dismiss()
        # Refresca badge y tarjetas de swipe automáticamente
        self.update_badge_matches()
        self.cargar_matches()
        self.rotar_cartas()
        self.mostrar_dialogo("¡Listo!", "Match reactivado a utilizables.")

    def _concluir(self, match, dialog):
        from backend.operations import cerrar_match_ui
        cerrar_match_ui(match['pending_id'])
        dialog.dismiss()
        self.dialog.dismiss()
        # Refresca badge y tarjetas de swipe automáticamente
        self.update_badge_matches()
        self.cargar_matches()
        self.rotar_cartas()
        self.mostrar_dialogo("¡Listo!", "Match concluido y movido a concluidas.")




    def confirmar_cierre_match(self, match):
        # Se puede agregar aquí un diálogo de confirmación si lo deseas
        result = operations.cerrar_match_ui(match["MatchID"])
        self.mostrar_dialogo("Resultado", result)
        # Actualiza el listado de pending, refrescando el diálogo o la pantalla
        self.dialog.dismiss()
        
    def show_match_confirmation(self, match_data):
        dialog = MDDialog(
            title="Confirmar Match",
            text=f"Onii-Chan, ¿confirmas el match con ID {match_data['MatchID']}?\n"
                 f"Monto: ${match_data.get('MontoObjetivo', 0):.2f}\n"
                 f"País: {match_data.get('Pais', 'N/A')}",
            buttons=[
                MDFlatButton(text="CANCELAR", on_release=lambda btn: dialog.dismiss()),
                MDFlatButton(text="CONFIRMAR", on_release=lambda btn: self.confirm_match(match_data, dialog))
            ],
        )
        dialog.open()
    
    def confirm_match(self, match_data, dialog):
        from backend.operations import confirm_match_ui
        result = confirm_match_ui(match_data["MatchID"])
        self.mostrar_dialogo("Confirmación", result)  # Método ya definido para mostrar diálogos
        dialog.dismiss()
        self.cargar_matches()          # Recarga los matches si tienes ese método
        self.update_badge_matches()    # Actualiza el badge de matches


    

if __name__ == "__main__":
    MyApp().run()
