import pyray as pr
from abc import ABC, abstractmethod


FONT = None
SPACING = None


def set_ui_font(path, spacing):
    global FONT, SPACING

    SPACING = spacing

    if FONT is not None:
        pr.unload_font(FONT)
    FONT = load_font(path)


class InlineWidget(ABC):
    @abstractmethod
    def get_desired_width(self, height):
        pass

    @abstractmethod
    def update(self, top, bottom, left, right):
        pass

    @abstractmethod
    def render(self, top, bottom, left, right):
        pass


def load_font(path):
    font = pr.load_font_ex(path, 256, None, 0)
    pr.gen_texture_mipmaps(font.texture)
    pr.set_texture_filter(font.texture, pr.TEXTURE_FILTER_TRILINEAR)
    return font


def get_text_width(text, font_size):
    return int(round(pr.measure_text_ex(FONT, text, font_size, SPACING).x))


def draw_text(text, posX, posY, font_size, color):
    pr.draw_text_ex(
        FONT,
        text,
        pr.Vector2(posX, posY),
        font_size,
        SPACING,
        color,
    )


class Padding(InlineWidget):
    def __init__(self, width):
        self.width = width

    def get_desired_width(self, height):
        return self.width

    def update(self, top, bottom, left, right):
        pass

    def render(self, top, bottom, left, right):
        pass


class Label(InlineWidget):
    def __init__(self, text):
        self.text = text

    def get_desired_width(self, height):
        font_size = int(round(height * 0.6))
        return int(round(get_text_width(self.text, font_size) + (height - font_size)))

    def update(self, top, bottom, left, right):
        pass

    def render(self, top, bottom, left, right):
        font_size = int(round((bottom - top) * 0.6))
        text_width = get_text_width(self.text, font_size)
        draw_text(
            self.text,
            left + (right - left - text_width) // 2,
            top + (bottom - top - font_size) // 2,
            font_size,
            pr.WHITE,
        )


class Button(InlineWidget):
    BG_COLOR_DEFAULT = pr.Color(68, 70, 74, 255)
    BORDER_COLOR_DEFAULT = pr.Color(255, 255, 255, 255)
    BG_COLOR_PRESSED = pr.Color(47, 87, 109, 255)
    BORDER_COLOR_HOVER = pr.Color(61, 174, 233, 255)

    def __init__(self, label, callback):
        self.label = label
        self.callback = callback

    def get_desired_width(self, height):
        font_size = int(round(height * 0.6))
        return int(round(get_text_width(self.label, font_size) + (height - font_size)))

    def update(self, top, bottom, left, right):
        if pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT):
            mouse_pos_x = pr.get_mouse_x()
            mouse_pos_y = pr.get_mouse_y()

            if left <= mouse_pos_x <= right and top <= mouse_pos_y <= bottom and self.callback:
                self.callback()

    def render(self, top, bottom, left, right):
        mouse_pos_x = pr.get_mouse_x()
        mouse_pos_y = pr.get_mouse_y()

        # draw background
        if left <= mouse_pos_x <= right and top <= mouse_pos_y <= bottom and pr.is_mouse_button_down(pr.MOUSE_BUTTON_LEFT):
            pr.draw_rectangle(left, top, right - left, bottom - top, self.BG_COLOR_PRESSED)
        else:
            pr.draw_rectangle(left, top, right - left, bottom - top, self.BG_COLOR_DEFAULT)

        # draw border
        if left <= mouse_pos_x <= right and top <= mouse_pos_y <= bottom:
            pr.draw_rectangle_lines(left, top, right - left - 1, bottom - top - 1, self.BORDER_COLOR_HOVER)
        else:
            pr.draw_rectangle_lines(left, top, right - left - 1, bottom - top - 1, self.BORDER_COLOR_DEFAULT)

        # draw label
        font_size = int(round((bottom - top) * 0.6))
        text_width = get_text_width(self.label, font_size)
        draw_text(
            self.label,
            left + (right - left - text_width) // 2,
            top + (bottom - top - font_size) // 2,
            font_size,
            pr.WHITE,
        )


class TextField(InlineWidget):
    BG_COLOR_DEFAULT = pr.Color(20, 22, 24, 255)
    BORDER_COLOR_DEFAULT = pr.Color(255, 255, 255, 255)
    BORDER_COLOR_ACTIVE = pr.Color(61, 174, 233, 255)

    def __init__(self, type, value, width, callback):
        self.editing = False
        self.type = type
        self.has_valid_characters = False
        self.insert_mode = False
        self.callback = callback
        self.width_in_characters = width

        if self.type is int:
            self.has_valid_characters = True
            self.valid_characters = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-', '+'}

        if self.type is float:
            self.has_valid_characters = True
            self.valid_characters = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '-', '+', '.', ','}

        self.set_value(value)

    def set_value(self, value):
        self.value = value
        if not self.editing:
            self.content = str(self.value)
            self.cursor = len(self.content)

    def _parse(self):
        old_value = self.value

        if self.type is str:
            self.value = self.content

        if self.type is int:
            try:
                self.value = int(self.content)
            except ValueError:
                pass
            self.content = str(self.value)

        if self.type is float:
            try:
                self.value = float(self.content.replace(',', '.'))
            except ValueError:
                pass
            self.content = str(self.value)

        self.cursor = len(self.content)
        self.editing = False

        if old_value != self.value and self.callback:
            self.callback(self.value)

    def _insert_text_at_cursor(self, text):
        continue_idx = self.cursor
        if self.insert_mode:
            continue_idx += len(text)

        if continue_idx < len(self.content):
            self.content = self.content[:self.cursor] + text + self.content[continue_idx:]
        else:
            self.content = self.content[:self.cursor] + text

        self.cursor += len(text)

    def get_desired_width(self, height):
        return int(round(get_text_width('0' * self.width_in_characters, int(round(height * 0.6))) * 1.4))

    def update(self, top, bottom, left, right):
        if pr.is_mouse_button_released(pr.MOUSE_BUTTON_LEFT):
            mouse_pos_x = pr.get_mouse_x()
            mouse_pos_y = pr.get_mouse_y()

            # clicks inside start editing and move cursor
            if left <= mouse_pos_x <= right and top <= mouse_pos_y <= bottom:
                self.editing = True

                font_size = int(round((bottom - top) * 0.6))
                relative_x = mouse_pos_x - (left + 5)

                for idx in range(len(self.content) + 1):
                    if relative_x < get_text_width(self.content[:idx], font_size):
                        break
                    self.cursor = idx

            # clicks outside will end editing
            elif self.editing:
                self._parse()

        if not self.editing:
            return

        # arrow keys move the cursor one position
        if pr.is_key_pressed(pr.KEY_LEFT):
            if self.cursor > 0:
                self.cursor -= 1
        if pr.is_key_pressed(pr.KEY_RIGHT):
            if self.cursor < len(self.content):
                self.cursor += 1

        # some keys move the cursor all the way
        if pr.is_key_pressed(pr.KEY_HOME) or pr.is_key_pressed(pr.KEY_UP) or pr.is_key_pressed(pr.KEY_PAGE_UP):
            self.cursor = 0
        if pr.is_key_pressed(pr.KEY_END) or pr.is_key_pressed(pr.KEY_DOWN) or pr.is_key_pressed(pr.KEY_PAGE_DOWN):
            self.cursor = len(self.content)

        # insert key toggles insert mode
        if pr.is_key_pressed(pr.KEY_INSERT):
            self.insert_mode = not self.insert_mode

        # backspace removes one character if possible
        if pr.is_key_pressed(pr.KEY_BACKSPACE):
            if self.cursor > 0:
                self.content = self.content[:self.cursor - 1] + self.content[self.cursor:]
                self.cursor -= 1

        # delete removes one character if possible
        if pr.is_key_pressed(pr.KEY_DELETE):
            if self.cursor < len(self.content):
                self.content = self.content[:self.cursor] + self.content[self.cursor + 1:]

        # press enter to finish editing
        if pr.is_key_pressed(pr.KEY_ENTER):
            self._parse()

        # press escape to cancel editing
        if pr.is_key_pressed(pr.KEY_ESCAPE):
            self.content = str(self.value)
            self.cursor = len(self.content)
            self.editing = False

        # user can also undo but keep editing
        if (pr.is_key_down(pr.KEY_LEFT_CONTROL) or pr.is_key_down(pr.KEY_RIGHT_CONTROL)) and pr.is_key_pressed(pr.KEY_Z):
            self.content = str(self.value)
            self.cursor = len(self.content)

        # handle regular typing
        text = ''

        character = pr.get_char_pressed()
        while character > 0:
            character = chr(character)
            if not self.has_valid_characters or character in self.valid_characters:
                text += character
            character = pr.get_char_pressed()

        if text:
            self._insert_text_at_cursor(text)

        # pasting from clipboard
        if (pr.is_key_down(pr.KEY_LEFT_CONTROL) or pr.is_key_down(pr.KEY_RIGHT_CONTROL)) and pr.is_key_pressed(pr.KEY_V):
            paste = pr.get_clipboard_text()

            if self.has_valid_characters:
                paste = ''.join(character for character in paste if character in self.valid_characters)

            if paste:
                self._insert_text_at_cursor(paste)

    def render(self, top, bottom, left, right):
        # draw background
        pr.draw_rectangle(left, top, right - left, bottom - top, self.BG_COLOR_DEFAULT)

        # draw text
        font_size = int(round((bottom - top) * 0.6))
        draw_text(
            self.content,
            left + 5,
            top + (bottom - top - font_size) // 2,
            font_size,
            pr.WHITE,
        )

        # draw cursor
        if self.editing:
            if self.insert_mode and self.cursor < len(self.content):
                current_character = self.content[self.cursor]
                current_character_width = get_text_width(current_character, font_size)
                curr_char_start = left + 5 + get_text_width(self.content[:self.cursor + 1], font_size) - current_character_width
                pr.draw_rectangle(
                    curr_char_start - 1,
                    top + 5,
                    current_character_width + 2,
                    bottom - top - 10,
                    pr.WHITE,
                )
                draw_text(
                    current_character,
                    curr_char_start,
                    top + (bottom - top - font_size) // 2,
                    font_size,
                    pr.BLACK,
                )

            else:
                pre_char_end = left + 5 + get_text_width(self.content[:self.cursor], font_size)
                pr.draw_line(pre_char_end + 2, top + 5, pre_char_end + 2, bottom - 5, pr.WHITE)

        # draw border
        if self.editing or (left <= pr.get_mouse_x() <= right and top <= pr.get_mouse_y() <= bottom):
            pr.draw_rectangle_lines(left, top, right - left - 1, bottom - top - 1, self.BORDER_COLOR_ACTIVE)
        else:
            pr.draw_rectangle_lines(left, top, right - left - 1, bottom - top - 1, self.BORDER_COLOR_DEFAULT)
