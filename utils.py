import logging
import sys
import traceback
from threading import Thread
from re import compile as re_compile
logger = logging.getLogger('antispambot.utils')

def print_traceback(debug: bool = False) -> None:
    if debug is True:
        logger.critical("[debug on] Exception caught.\nPrinting stack traceback\n" + format_exc_plus())
    else:
        logger.critical("Exception caught.\nPrinting stack traceback\n" + traceback.format_exc())

def format_exc_plus():
    """
    Print the usual traceback information, followed by a listing of all the
    local variables in each frame.
    from Python Cookbook by David Ascher, Alex Martelli
    """
    ret = str()
    tb = sys.exc_info()[2]
    while True:
        if not tb.tb_next:
            break
        tb = tb.tb_next
    stack = []
    f = tb.tb_frame
    while f:
        stack.append(f)
        f = f.f_back
    stack.reverse()
    ret += traceback.format_exc()
    ret += "\nLocals by frame, innermost last\n"
    for frame in stack:
        ret += "Frame %s in %s at line %s\n" % (frame.f_code.co_name,
                                                frame.f_code.co_filename,
                                                frame.f_lineno)
        for key, value in frame.f_locals.items(  ):
            ret += "\t%20s = " % key
            # We have to be VERY careful not to cause a new error in our error
            # printer! Calling str(  ) on an unknown object could cause an
            # error we don't want, so we must use try/except to catch it --
            # we can't stop it from happening, but we can and should
            # stop it from propagating if it does happen!
            try:
                ret += str(value)
            except:
                ret += "<ERROR WHILE PRINTING VALUE>"
            ret += '\n'
    return ret

def background(func):
    def wrapped(*args, **kwargs):
        tr = Thread(target=func, args=args, kwargs=kwargs)
        tr.daemon = True
        tr.start()
        return tr
    return wrapped

__Ha = [[0x2E80, 0x2E99],    # Han # So  [26] CJK RADICAL REPEAT, CJK RADICAL RAP
        [0x2E9B, 0x2EF3],    # Han # So  [89] CJK RADICAL CHOKE, CJK RADICAL C-SIMPLIFIED TURTLE
        [0x2F00, 0x2FD5],    # Han # So [214] KANGXI RADICAL ONE, KANGXI RADICAL FLUTE
        0x3005,              # Han # Lm       IDEOGRAPHIC ITERATION MARK
        0x3007,              # Han # Nl       IDEOGRAPHIC NUMBER ZERO
        [0x3021, 0x3029],    # Han # Nl   [9] HANGZHOU NUMERAL ONE, HANGZHOU NUMERAL NINE
        [0x3038, 0x303A],    # Han # Nl   [3] HANGZHOU NUMERAL TEN, HANGZHOU NUMERAL THIRTY
        0x303B,              # Han # Lm       VERTICAL IDEOGRAPHIC ITERATION MARK
        [0x3400, 0x4DB5],    # Han # Lo [6582] CJK UNIFIED IDEOGRAPH-3400, CJK UNIFIED IDEOGRAPH-4DB5
        [0x4E00, 0x9FC3],    # Han # Lo [20932] CJK UNIFIED IDEOGRAPH-4E00, CJK UNIFIED IDEOGRAPH-9FC3
        [0xF900, 0xFA2D],    # Han # Lo [302] CJK COMPATIBILITY IDEOGRAPH-F900, CJK COMPATIBILITY IDEOGRAPH-FA2D
        [0xFA30, 0xFA6A],    # Han # Lo  [59] CJK COMPATIBILITY IDEOGRAPH-FA30, CJK COMPATIBILITY IDEOGRAPH-FA6A
        [0xFA70, 0xFAD9],    # Han # Lo [106] CJK COMPATIBILITY IDEOGRAPH-FA70, CJK COMPATIBILITY IDEOGRAPH-FAD9
        [0x20000, 0x2A6D6],  # Han # Lo [42711] CJK UNIFIED IDEOGRAPH-20000, CJK UNIFIED IDEOGRAPH-2A6D6
        [0x2F800, 0x2FA1D],  # Han # Lo [542] CJK COMPATIBILITY IDEOGRAPH-2F800, CJK COMPATIBILITY IDEOGRAPH-2FA1D
        [0xFF00, 0xFFEF]]    # Halfwidth and Fullwidth Forms - added
def __build_re():
    # https://stackoverflow.com/questions/34587346/python-check-if-a-string-contains-chinese-character/34587468
    L = []
    for i in __Ha:
        if isinstance(i, list):
            f, t = i
            try:
                f = chr(f)
                t = chr(t)
                L.append(f'{f}-{t}')
            except Exception:
                print_traceback(debug=True)
                # A narrow python build, so can't use chars > 65535 without surrogate pairs!
        else:
            try:
                L.append(chr(i))
            except Exception:
                print_traceback(debug=True)

    RE = f"[{''.join(L)}]"
    return re_compile(RE)

_CJKRE = __build_re()

def find_cjk_letters(text: str) -> list:
    return _CJKRE.findall(text)
