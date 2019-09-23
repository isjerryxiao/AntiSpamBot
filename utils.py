import logging
import sys
import traceback
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
