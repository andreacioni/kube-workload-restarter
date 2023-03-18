import logging
import sys


def get_console_handler():
    FORMATTER = logging.Formatter(
        "%(asctime)s — %(name)s — %(levelname)s — %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler


log = logging.getLogger('restarter')
log.setLevel(logging.DEBUG)
log.addHandler(get_console_handler())
