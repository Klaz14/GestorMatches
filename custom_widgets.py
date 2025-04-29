# custom_widgets.py
from kivymd.uix.textfield import MDTextField

class FormattedMDTextField(MDTextField):
    def __init__(self, **kwargs):
        super(FormattedMDTextField, self).__init__(**kwargs)
        self._is_updating = False
        self.bind(text=self.on_text_internal)
        self.bind(focus=self.on_focus_internal)

    def insert_text(self, substring, from_undo=False):
        # Permite solo dígitos
        filtered = ''.join([c for c in substring if c.isdigit()])
        return super(FormattedMDTextField, self).insert_text(filtered, from_undo=from_undo)

    def on_text_internal(self, instance, value):
        if self._is_updating:
            return
        # Solo formatea mientras está en foco
        if self.focus:
            raw = value.replace(",", "")
            if raw:
                try:
                    number = int(raw)
                    formatted = "{:,}".format(number)
                except ValueError:
                    formatted = value
            else:
                formatted = value

            if formatted != value:
                cursor_index = self.cursor_index()
                self._is_updating = True
                self.text = formatted
                new_cursor = min(len(formatted), cursor_index)
                self.cursor = self.get_cursor_from_index(new_cursor)
                self._is_updating = False

    def on_focus_internal(self, instance, value):
        if value:
            # Al ganar foco, se vuelve a formatear para mostrar separadores
            raw = self.text.replace(",", "")
            if raw:
                try:
                    number = int(raw)
                    formatted = "{:,}".format(number)
                except ValueError:
                    formatted = self.text
            else:
                formatted = self.text
            self._is_updating = True
            self.text = formatted
            self._is_updating = False
        else:
            # Al perder el foco, elimina los separadores para tener el número "juntito"
            self._is_updating = True
            self.text = self.text.replace(",", "")
            self._is_updating = False
