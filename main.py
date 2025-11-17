import pyray as pr
from sys import argv
from classes import SessionManager, WidgetPDF, WidgetTopbar, WidgetTTS
import torch


if __name__ == '__main__':
    # initialize PR window
    pr.set_config_flags(pr.FLAG_WINDOW_RESIZABLE | pr.FLAG_VSYNC_HINT)
    pr.set_target_fps(0)
    pr.init_window(1280, 1280, 'PDF Reader')

    # check and show capabilities
    print('CUDA:', torch.cuda.is_available())

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
        mouse_position = pr.get_mouse_position()
        screen_width = pr.get_screen_width()
        screen_height = pr.get_screen_height()

        # widget starts
        pdf_widget.start(mouse_position, screen_width, screen_height)
        topbar_widget.start(mouse_position, screen_width, screen_height)
        tts_widget.start(mouse_position, screen_width, screen_height)

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

    pr.close_window()
