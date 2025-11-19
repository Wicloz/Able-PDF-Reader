import fitz
import pyray as pr
import numpy as np
from kokoro import KPipeline as KokoroPipeline
import threading
from transformers import pipeline
from enum import Enum, auto


# magic numbers
SCROLL_SPEED = 20
PAGE_GAP = 10
TOPBAR_HEIGHT = 50
AUDIOBAR_HEIGHT = 50

# models and their properties
TTS_SAMPLE_RATE = 24000
LL_MODEL_ID = 'meta-llama/Llama-3.2-3B-Instruct'


class FitMode(Enum):
    WIDTH = auto()
    HEIGHT = auto()
    NONE = auto()
    BOTH = auto()


class WidgetTTS:
    def __init__(self):
        # fixed widget bounds
        self.height = AUDIOBAR_HEIGHT
        self.left = 0

        self.editing_speed = False
        self.speed_ptr = pr.ffi.new('int *')

    def set_manager(self, manager):
        self.manager = manager

    def start(self, mouse_position, screen_width, screen_height):
        # variable widget bounds
        self.top = screen_height - AUDIOBAR_HEIGHT
        self.width = screen_width

        # determine mouse position in widget
        self.mouse_position = None
        if mouse_position.y > self.top:
            self.mouse_position = mouse_position

    def update(self):
        self.manager.narration_continue()

        if not self.editing_speed:
            self.speed_ptr[0] = int(round(self.manager.tts_speed * 100))

    def render(self):
        pr.draw_rectangle(self.left, self.top, self.width, self.height, pr.BLACK)
        pr.gui_set_style(pr.DEFAULT, pr.TEXT_SIZE, int(round(self.height / 2)))

        if pr.gui_button(pr.Rectangle(0, self.top, 100, self.height), 'PLAY'):
            self.manager.narration_play()

        if pr.gui_button(pr.Rectangle(100, self.top, 100, self.height), 'PAUSE'):
            self.manager.narration_pause()

        if pr.gui_value_box(
            pr.Rectangle(400, self.top, 100, self.height),
            'Speed % ',
            self.speed_ptr,
            50,
            200,
            self.editing_speed,
        ):
            if self.editing_speed:
                self.manager.change_tts_speed(self.speed_ptr[0] / 100)
            self.editing_speed = not self.editing_speed

        if pr.gui_button(pr.Rectangle(600, self.top, 100, self.height), 'REPLAY'):
            self.manager.narration_rewind()

        if pr.gui_button(pr.Rectangle(700, self.top, 100, self.height), 'NEXT'):
            self.manager.narration_jump_to_paragraph(self.manager.tts_next_paragraph)


class WidgetTopbar:
    def __init__(self):
        # fixed widget bounds
        self.top = 0
        self.height = TOPBAR_HEIGHT
        self.left = 0

        self.editing_zoom = False
        self.zoom_ptr = pr.ffi.new('int *')

        self.editing_page = False
        self.page_ptr = pr.ffi.new('int *')

    def set_manager(self, manager):
        self.manager = manager

    def start(self, mouse_position, screen_width, screen_height):
        # variable widget bounds
        self.width = screen_width

        # determine mouse position in widget
        self.mouse_position = None
        if mouse_position.y < self.height:
            self.mouse_position = mouse_position

    def update(self):
        if not self.editing_zoom:
            self.zoom_ptr[0] = int(round(self.manager.zoom * 100))

        if not self.editing_page:
            self.page_ptr[0] = self.manager.current_page + 1

    def render(self):
        pr.draw_rectangle(self.left, self.top, self.width, self.height, pr.BLACK)

        pr.gui_set_style(pr.DEFAULT, pr.TEXT_SIZE, int(round(self.height / 2)))
        occupied = self.left + 100

        if pr.gui_value_box(
            pr.Rectangle(occupied, self.top, 100, self.height),
            'Zoom % ',
            self.zoom_ptr,
            10,
            800,
            self.editing_zoom,
        ):
            if self.editing_zoom:
                self.manager.zoom = self.zoom_ptr[0] / 100
            self.editing_zoom = not self.editing_zoom

        occupied += 200

        if pr.gui_button(pr.Rectangle(occupied, self.top, self.height, self.height), '<'):
            self.manager.go_to_page = self.manager.current_page - 1

        occupied += self.height

        if pr.gui_value_box(
            pr.Rectangle(occupied, self.top, 100, self.height),
            '',
            self.page_ptr,
            1,
            self.manager.page_count,
            self.editing_page,
        ):
            if self.editing_page:
                self.manager.go_to_page = self.page_ptr[0] - 1
            self.editing_page = not self.editing_page

        occupied += 100

        pr.draw_text_ex(
            pr.get_font_default(),
            f'/ {self.manager.page_count}',
            pr.Vector2(occupied, self.top + self.height / 4),
            int(round(self.height / 2)),
            1,
            pr.WHITE,
        )

        occupied += pr.measure_text(f'/ {self.manager.page_count}', int(round(self.height / 2)))

        if pr.gui_button(pr.Rectangle(occupied, self.top, self.height, self.height), '>'):
            self.manager.go_to_page = self.manager.current_page + 1

        occupied += self.height + 100

        if pr.gui_button(pr.Rectangle(occupied, self.top, 150, self.height), 'Fit Width'):
            self.manager.fit_mode = FitMode.WIDTH

        occupied += 150

        if pr.gui_button(pr.Rectangle(occupied, self.top, 150, self.height), 'Fit Height'):
            self.manager.fit_mode = FitMode.HEIGHT

        occupied += 150

        if pr.gui_button(pr.Rectangle(occupied, self.top, 150, self.height), 'Fit Page'):
            self.manager.fit_mode = FitMode.BOTH

        occupied += 150

        if pr.gui_button(pr.Rectangle(occupied, self.top, 150, self.height), 'Original Size'):
            self.manager.fit_mode = FitMode.NONE


class WidgetPDF:
    def __init__(self):
        # fixed widget bounds
        self.left = 0
        self.top = TOPBAR_HEIGHT

        # keep relevant previous state
        self.prev_width = None
        self.prev_zoom = None
        self.prev_fit_mode = None

        # track references to page textures
        self.texture_cache = {}

    def set_manager(self, manager):
        self.manager = manager

    def _rebuild_page_cache(self):
        content_width = self.width * self.manager.zoom
        content_height = self.height * self.manager.zoom

        match self.manager.fit_mode:
            case FitMode.BOTH:
                self.pdf_page_scales = np.minimum(
                    content_width / self.manager.page_widths,
                    content_height / self.manager.page_heights,
                )

            case FitMode.WIDTH:
                self.pdf_page_scales = content_width / self.manager.page_widths

            case FitMode.HEIGHT:
                self.pdf_page_scales = content_height / self.manager.page_heights

            case _:
                self.pdf_page_scales = np.ones(self.manager.page_count, dtype=float)

        self.pdf_page_scaled_y = self.manager.page_heights * self.pdf_page_scales
        self.pdf_page_scaled_x = self.manager.page_widths * self.pdf_page_scales

        self.pdf_page_y_offsets = np.cumsum(self.pdf_page_scaled_y) - self.pdf_page_scaled_y + PAGE_GAP * np.arange(self.manager.page_count)
        self.content_y_offset = self.top
        self.pdf_page_x_offsets = (content_width - self.pdf_page_scaled_x) / 2
        self.content_x_offset = (self.width - content_width) / 2 + self.left

        self.paragraph_offsets = self.pdf_page_scales[self.manager.para_pages][:, np.newaxis] * self.manager.para_rects
        self.paragraph_offsets[:, 0] += self.pdf_page_x_offsets[self.manager.para_pages]
        self.paragraph_offsets[:, 1] += self.pdf_page_y_offsets[self.manager.para_pages]

        # unload and reset texture cache
        for texture in self.texture_cache.values():
            pr.unload_texture(texture)
        self.texture_cache = {}

    def start(self, mouse_position, screen_width, screen_height):
        # variable widget bounds
        self.width = screen_width
        self.height = screen_height - TOPBAR_HEIGHT - AUDIOBAR_HEIGHT

        # determine mouse position in widget
        self.mouse_position = None
        if mouse_position.y > self.top and mouse_position.y < self.top + self.height:
            self.mouse_position = pr.Vector2(mouse_position.x - self.left, mouse_position.y - self.top)

    def update(self):
        if len(self.texture_cache) > 0:
            self.manager.current_page = list(self.texture_cache.keys())[-1]

        if self.mouse_position:
            # handle mouse scrolling
            if pr.is_key_down(pr.KEY_LEFT_CONTROL) or pr.is_key_down(pr.KEY_RIGHT_CONTROL):
                self.manager.zoom *= np.exp(pr.get_mouse_wheel_move() * 0.1)

            elif pr.is_key_down(pr.KEY_LEFT_SHIFT) or pr.is_key_down(pr.KEY_RIGHT_SHIFT):
                self.manager.scroll_offset_x -= pr.get_mouse_wheel_move() * (SCROLL_SPEED / self.manager.zoom)
            else:
                self.manager.scroll_offset_y -= pr.get_mouse_wheel_move() * (SCROLL_SPEED / self.manager.zoom)

            # handle mouse dragging
            if pr.is_mouse_button_down(pr.MOUSE_BUTTON_LEFT):
                self.manager.scroll_offset_x -= pr.get_mouse_delta().x / self.manager.zoom
                self.manager.scroll_offset_y -= pr.get_mouse_delta().y / self.manager.zoom

            # handle arrow keys
            if pr.is_key_down(pr.KEY_UP):
                self.manager.scroll_offset_y -= SCROLL_SPEED / self.manager.zoom
            if pr.is_key_down(pr.KEY_DOWN):
                self.manager.scroll_offset_y += SCROLL_SPEED / self.manager.zoom
            if pr.is_key_down(pr.KEY_LEFT):
                self.manager.scroll_offset_x -= SCROLL_SPEED / self.manager.zoom
            if pr.is_key_down(pr.KEY_RIGHT):
                self.manager.scroll_offset_x += SCROLL_SPEED / self.manager.zoom

        if self.width != self.prev_width or self.manager.zoom != self.prev_zoom or self.manager.fit_mode != self.prev_fit_mode:
            self.prev_width = self.width
            self.prev_zoom = self.manager.zoom
            self.prev_fit_mode = self.manager.fit_mode
            self._rebuild_page_cache()

        if self.manager.go_to_page is not None:
            self.manager.scroll_offset_y = self.pdf_page_y_offsets[self.manager.go_to_page] / self.manager.zoom
            self.manager.go_to_page = None

    def render(self):
        for page_num in range(self.manager.page_count):
            page_top_relative_to_window = self.pdf_page_y_offsets[page_num] + self.content_y_offset - self.manager.scroll_offset_y * self.manager.zoom
            page_height = self.pdf_page_scaled_y[page_num]
            page_left_relative_to_window = self.pdf_page_x_offsets[page_num] + self.content_x_offset - self.manager.scroll_offset_x * self.manager.zoom
            page_width = self.pdf_page_scaled_x[page_num]

            if (
                page_top_relative_to_window + page_height < self.top
                or
                page_top_relative_to_window > self.top + self.height
                or
                page_left_relative_to_window + page_width < self.left
                or
                page_left_relative_to_window > self.left + self.width
            ):
                if page_num in self.texture_cache:
                    pr.unload_texture(self.texture_cache[page_num])
                    del self.texture_cache[page_num]
                continue

            pr.draw_rectangle(
                int(page_left_relative_to_window),
                int(page_top_relative_to_window),
                int(page_width),
                int(page_height),
                pr.WHITE,
            )

            if page_num not in self.texture_cache:
                self.texture_cache[page_num] = self.manager.rasterize_page(page_num, self.pdf_page_scales[page_num])

            texture = self.texture_cache[page_num]
            pr.draw_texture(texture, int(page_left_relative_to_window), int(page_top_relative_to_window), pr.WHITE)

        for para_num in range(len(self.manager.paragraphs)):
            highlight_left = self.paragraph_offsets[para_num][0] + self.content_x_offset - self.manager.scroll_offset_x * self.manager.zoom
            highlight_top = self.paragraph_offsets[para_num][1] + self.content_y_offset - self.manager.scroll_offset_y * self.manager.zoom
            highlight_width = self.paragraph_offsets[para_num][2]
            highlight_height = self.paragraph_offsets[para_num][3]

            if (
                highlight_top + highlight_height < self.top
                or
                highlight_top > self.top + self.height
                or
                highlight_left + highlight_width < self.left
                or
                highlight_left > self.left + self.width
            ):
                continue

            if para_num == self.manager.tts_current_paragraph:
                pr.draw_rectangle(
                    int(highlight_left),
                    int(highlight_top),
                    int(highlight_width),
                    int(highlight_height),
                    pr.Color(255, 0, 0, 50),
                )

            elif self.mouse_position and (
                self.mouse_position.x >= highlight_left
                and
                self.mouse_position.x <= highlight_left + highlight_width
                and
                self.mouse_position.y + self.top >= highlight_top
                and
                self.mouse_position.y + self.top <= highlight_top + highlight_height
            ):
                pr.draw_rectangle(
                    int(highlight_left),
                    int(highlight_top),
                    int(highlight_width),
                    int(highlight_height),
                    pr.Color(0, 0, 255, 50),
                )

                if pr.is_mouse_button_pressed(pr.MOUSE_BUTTON_LEFT):
                    self.manager.narration_jump_to_paragraph(para_num)
                    self.manager.narration_play()


class SessionManager:
    def __init__(self, path):
        self.pdf = fitz.open(path)

        # extract page count
        self.page_count = self.pdf.page_count

        # extract page dimensions
        self.page_heights = np.empty(self.page_count, dtype=float)
        self.page_widths = np.empty(self.page_count, dtype=float)

        for page_num in range(self.page_count):
            page = self.pdf.load_page(page_num)
            self.page_heights[page_num] = page.rect.height
            self.page_widths[page_num] = page.rect.width

        # extract PDF text as paragraphs
        self.paragraphs = []
        self.para_pages = []
        self.para_rects = []

        for page_num in range(self.page_count):
            page = self.pdf.load_page(page_num)
            blocks = page.get_text('blocks')
            for block in blocks:
                self.para_pages.append(page_num)
                self.para_rects.append((block[0], block[1], block[2] - block[0], block[3] - block[1]))
                self.paragraphs.append(block[4])

        self.para_pages = np.array(self.para_pages, dtype=int)
        self.para_rects = np.array(self.para_rects, dtype=float)

        # keep track of scroll and zoom
        self.scroll_offset_y = 0
        self.scroll_offset_x = 0
        self.zoom = 1
        self.fit_mode = FitMode.BOTH

        # keep track of the current page
        self.current_page = 0
        self.go_to_page = None

        # TTS stuff
        self.tts_cache = {}
        self.tts_lock = threading.Lock()
        self.tts_thread = None
        self.tts_pipeline = None
        self.tts_playing = False
        self.tts_sound = None
        self.tts_speed = 1
        self.tts_current_paragraph = None
        self.tts_next_paragraph = 0
        self.llm_pipeline = None

        prompt = (
            "Your job is to normalize text extracted from a PDF to be suitable for processing by text-to-speech software. "
            "This includes correcting any OCR errors, removing line breaks and word breaks, expanding abbreviations, converting LaTeX math into spoken form, and cleaning up citations and footnotes. "
            "Consider everything in the context of 'this will be read aloud'. "
            "This text could be a paragraph, (section) title, author list, table fragment, figure caption, footnote, or some meta content. "
            "The text is extracted from the PDF as is. It might be short or truncated. Do not correct for this, some other piece of text will have the rest. "
            "Consider your role as an automated tool and never try to talk to the user. Your output will be used without any further review. "
            "Don't change the meaning of the text or add any explanations. "
            "Output only the fully normalized text. "
            "If no normalization is needed, return the text as is. "
        )

        self.tts_context = [
            {'role': 'system', 'content': prompt},
        ]

    def _cache_tts_paragraph(self, pnum):
        text = self.paragraphs[pnum]

        print()
        print(f'Caching TTS for paragraph {pnum}:')
        print(text)

        self.tts_context.append({'role': 'user', 'content': text})

        self.tts_context = self.llm_pipeline(
            self.tts_context,
            max_new_tokens=int(round(len(self.llm_pipeline.tokenizer(text)['input_ids']) * 1.2)),
            do_sample=False,
        )[0]['generated_text']

        text = self.tts_context[-1]['content']
        print(text)
        print()

        chunks = []
        for _, _, chunk in self.tts_pipeline(text, voice='af_heart', speed=self.tts_speed):
            chunks.append(chunk)

        audio = np.concatenate(chunks, axis=0)
        with self.tts_lock:
            self.tts_cache[pnum] = audio

    def _tts_thread_run(self):
        while True:
            pnum = self.tts_next_paragraph
            duration = 0

            while duration < 60:
                if pnum not in self.tts_cache:
                    self._cache_tts_paragraph(pnum)
                    break

                duration += len(self.tts_cache[pnum]) / TTS_SAMPLE_RATE
                pnum += 1

    def rasterize_page(self, page_num, scale):
        page = self.pdf.load_page(page_num)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True)

        image = pr.Image()
        image.width = pixmap.width
        image.height = pixmap.height
        image.mipmaps = 1
        image.format = pr.PIXELFORMAT_UNCOMPRESSED_R8G8B8A8
        image.data = pr.ffi.cast('void *', pixmap.samples_ptr)

        texture = pr.load_texture_from_image(image)
        return texture

    def narration_play(self):
        if not pr.is_audio_device_ready():
            pr.init_audio_device()

        if not self.tts_playing:
            if self.tts_sound is not None:
                pr.resume_sound(self.tts_sound)
            self.tts_playing = True

        if self.tts_pipeline is None:
            self.tts_pipeline = KokoroPipeline(lang_code='a')

        if self.llm_pipeline is None:
            self.llm_pipeline = pipeline(
                task='text-generation',
                model=LL_MODEL_ID,
                torch_dtype='auto',
                device_map='auto',
            )

        if self.tts_thread is None or not self.tts_thread.is_alive():
            self.tts_thread = threading.Thread(target=self._tts_thread_run, daemon=True)
            self.tts_thread.start()

    def narration_pause(self):
        if self.tts_playing:
            if self.tts_sound is not None:
                pr.pause_sound(self.tts_sound)
            self.tts_playing = False

    def narration_continue(self):
        # wait until the user wants playback
        if not self.tts_playing:
            return

        # wait until the audio stream is done playing
        if self.tts_sound is not None and pr.is_sound_playing(self.tts_sound):
            return

        # go to the next paragraph
        self.tts_current_paragraph = self.tts_next_paragraph

        # wait until the current paragraph has TTS
        if self.tts_current_paragraph not in self.tts_cache:
            return

        # obtain audio for the current paragraph
        with self.tts_lock:
            audio = self.tts_cache[self.tts_current_paragraph]
        current_paragraph_samples = len(audio)

        # prepare audio for raylib consumption
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        audio_ptr = pr.ffi.cast('float *', audio.ctypes.data)

        # clean up old audio stream
        if self.tts_sound is not None:
            pr.unload_sound(self.tts_sound)

        # create and fill new audio stream
        self.tts_sound = pr.load_sound_from_wave(pr.Wave(
            current_paragraph_samples,
            TTS_SAMPLE_RATE,
            32,
            1,
            audio_ptr,
        ))
        pr.play_sound(self.tts_sound)

        # jump to the paragraph
        self.go_to_page = self.para_pages[self.tts_current_paragraph]

        # prepare the next paragraph
        self.tts_next_paragraph = self.tts_current_paragraph + 1

    def change_tts_speed(self, speed):
        if speed == self.tts_speed:
            return
        self.tts_speed = speed

        with self.tts_lock:
            self.tts_cache = {}

        self.narration_rewind()

    def narration_rewind(self):
        if self.tts_sound is not None:
            pr.stop_sound(self.tts_sound)
        if self.tts_current_paragraph is not None:
            self.tts_next_paragraph = self.tts_current_paragraph

    def narration_jump_to_paragraph(self, pnum):
        if self.tts_sound is not None:
            pr.stop_sound(self.tts_sound)
        self.tts_next_paragraph = pnum
