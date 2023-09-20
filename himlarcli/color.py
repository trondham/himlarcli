import sys

class Color:

    TTY = True if sys.stdout.isatty() else False

    # General effects
    reset = '\033[0m' if self.TTY else ''   # Default color and effects
    bold  = '\033[1m' if self.TTY else ''   # Bold/brighter
    dim   = '\033[2m' if self.TTY else ''   # Dim/darker
    cur   = '\033[3m' if self.TTY else ''   # Italic font
    und   = '\033[4m' if self.TTY else ''   # Underline
    rev   = '\033[7m' if self.TTY else ''   # Reverse/Inverted
    cof   = '\033[?25l' if self.TTY else '' # Cursor Off
    con   = '\033[?25h' if self.TTY else '' # Cursor On
    stk   = '\033[09m' if self.TTY else ''  # Strikethrough
    inv   = '\033[08m' if self.TTY else ''  # Invisible

    class fg:
        # Foreground colors

        # Base color
        BLK = '\033[30m' if self.TTY else ''
        RED = '\033[31m' if self.TTY else ''
        GRN = '\033[32m' if self.TTY else ''
        YLW = '\033[33m' if self.TTY else ''
        BLU = '\033[34m' if self.TTY else ''
        MGN = '\033[35m' if self.TTY else ''
        CYN = '\033[36m' if self.TTY else ''
        WHT = '\033[37m' if self.TTY else ''

        # Lighter shade
        blk = '\033[90m' if self.TTY else ''
        red = '\033[91m' if self.TTY else ''
        grn = '\033[92m' if self.TTY else ''
        ylw = '\033[93m' if self.TTY else ''
        blu = '\033[94m' if self.TTY else ''
        mgn = '\033[95m' if self.TTY else ''
        cyn = '\033[96m' if self.TTY else ''
        wht = '\033[97m' if self.TTY else ''

    class bg:
        # Background color

        # Base color
        BLK = '\033[40m' if self.TTY else '' # Black
        RED = '\033[41m' if self.TTY else '' # Red
        GRN = '\033[42m' if self.TTY else '' # Green
        YLW = '\033[43m' if self.TTY else '' # Yellow
        BLU = '\033[44m' if self.TTY else '' # Blue
        MGN = '\033[45m' if self.TTY else '' # Magenta
        CYN = '\033[46m' if self.TTY else '' # Cyan
        WHT = '\033[47m' if self.TTY else '' # White

        # Lighter shade
        blk = '\033[100m' if self.TTY else '' # Black
        red = '\033[101m' if self.TTY else '' # Red
        grn = '\033[102m' if self.TTY else '' # Green
        ylw = '\033[103m' if self.TTY else '' # Yellow
        blu = '\033[104m' if self.TTY else '' # Blue
        mgn = '\033[105m' if self.TTY else '' # Magenta
        cyn = '\033[106m' if self.TTY else '' # Cyan
        wht = '\033[107m' if self.TTY else '' # White
