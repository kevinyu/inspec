import logging


try:
    unicode
    _unicode = True
except NameError:
    _unicode = False


class CursesHandler(logging.Handler):
    """Handling logging in curses window

    from https://stackoverflow.com/a/28102809
    """

    def __init__(self):
        logging.Handler.__init__(self)
        self.screen = None

    def set_screen(self, screen):
        screen.refresh()
        screen.scrollok(True)
        screen.idlok(True)
        screen.leaveok(True)
        self.screen = screen

    def emit(self, record):
        try:
            msg = self.format(record)
            screen = self.screen
            fs = "\n%s"
            if not _unicode: #if no unicode support...
                screen.addstr(fs % msg)
                screen.refresh()
            else:
                try:
                    if (isinstance(msg, unicode) ):
                        ufs = u'\n%s'
                        try:
                            screen.addstr(ufs % msg)
                            screen.refresh()
                        except UnicodeEncodeError:
                            screen.addstr((ufs % msg).encode(code))
                            screen.refresh()
                    else:
                        screen.addstr(fs % msg)
                        screen.refresh()
                except UnicodeError:
                    screen.addstr(fs % msg.encode("UTF-8"))
                    screen.refresh()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)
