import pyray as pr
from sys import argv
from classes import SessionManager, WidgetPDF, WidgetTopbar, WidgetTTS
from rayui import set_ui_font
import torch
from os import environ


def load_dotenv():
    with open('.env', 'r') as fp:
        for line in fp:
            line = line.split('#', 1)[0]
            if '=' in line:
                key, value = line.split('=', 1)
                environ[key.strip()] = value.strip()


if __name__ == '__main__':
    # load environment variables
    load_dotenv()

    # initialize PR window
    pr.set_config_flags(pr.FLAG_WINDOW_RESIZABLE | pr.FLAG_VSYNC_HINT)
    pr.set_target_fps(0)
    pr.init_window(1280, 1280, 'PDF Reader')
    pr.set_exit_key(pr.KEY_NULL)

    # check and show capabilities
    print('CUDA:', torch.cuda.is_available())

    # load custom font
    set_ui_font('assets/Inter-VariableFont_opsz,wght.ttf', 2)

    # open PDF and keep it open
    pdf_manager = SessionManager(argv[1])

    # create widget instances
    pdf_widget = WidgetPDF()
    pdf_widget.set_manager(pdf_manager)
    topbar_widget = WidgetTopbar()
    topbar_widget.set_manager(pdf_manager)
    tts_widget = WidgetTTS()
    tts_widget.set_manager(pdf_manager)

    while not pr.window_should_close():
        screen_width = pr.get_screen_width()
        screen_height = pr.get_screen_height()

        # widget starts
        pdf_widget.start(screen_width, screen_height)
        topbar_widget.start(screen_width, screen_height)
        tts_widget.start(screen_width, screen_height)

        # widget updates
        pdf_widget.update()
        topbar_widget.update()
        tts_widget.update()

        # start drawing
        pr.begin_drawing()
        pr.clear_background(pr.BLACK)

        # render widgets
        pdf_widget.render()
        topbar_widget.render()
        tts_widget.render()

        # end drawing
        pr.end_drawing()

    # cleanup after close is requested
    pr.close_window()
