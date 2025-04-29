from kivy.uix.screenmanager import Screen
from kivy.clock import Clock
from kivy.animation import Animation

class SwipeMatches(Screen):
    def on_enter(self):
        # Al ingresar a la pantalla, guarda los colores originales de las tarjetas superior e inferior:
        self.original_top_color = [0.8, 1, 0.8, 1]      # mismo color que usaste en el KV
        self.original_bottom_color = [0.8, 1, 0.8, 1]   # mismo color que usaste en el KV
        # Inicia la verificación de colisiones cada 0.1 segundos:
        self._collision_event = Clock.schedule_interval(self.check_card_collision, 0.1)

    def on_leave(self):
        # Cuando salgas de la pantalla, cancela la función de verificación periódica
        if hasattr(self, "_collision_event"):
            self._collision_event.cancel()

    def check_card_collision(self, dt):
        # Obtenemos los widgets usando sus IDs definidos en el KV:
        central = self.ids.central_card
        top = self.ids.top_card
        bottom = self.ids.bottom_card

        # Tomamos el color de fondo actual de la tarjeta central:
        central_color = central.md_bg_color

        # --- Para la tarjeta superior ---
        if central.collide_widget(top):
            # Anima el cambio de color del fondo a la tarjeta superior al color central
            Animation(md_bg_color=central_color, duration=0.15).start(top)
        else:
            # Si no hay colisión, regresa al color original
            Animation(md_bg_color=self.original_top_color, duration=0.15).start(top)

        # --- Para la tarjeta inferior ---
        if central.collide_widget(bottom):
            Animation(md_bg_color=central_color, duration=0.15).start(bottom)
        else:
            Animation(md_bg_color=self.original_bottom_color, duration=0.15).start(bottom)

