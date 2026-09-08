# coding: utf-8

import builtins

from logHandler import log


def _identity(message):
    return message


def setup_translation():
    fallback_translate = builtins.__dict__.get("_", _identity)
    try:
        import addonHandler

        addonHandler.initTranslation()
    except Exception as error:
        log.debug(
            "Chessboard translation is unavailable in this context; using existing translation fallback: %s",
            error,
        )
        return fallback_translate
    return builtins.__dict__.get("_", fallback_translate)


_ = setup_translation()
