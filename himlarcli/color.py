import sys

class Color:

    if sys.stdout.isatty():
        TTY = True
    else:
        TTY = False

    # General effects
    reset = '\033[0m' if TTY else ''   # Default color and effects
    bold  = '\033[1m' if TTY else ''   # Bold/brighter
    dim   = '\033[2m' if TTY else ''   # Dim/darker
    cur   = '\033[3m' if TTY else ''   # Italic font
    und   = '\033[4m' if TTY else ''   # Underline
    rev   = '\033[7m' if TTY else ''   # Reverse/Inverted
    cof   = '\033[?25l' if TTY else '' # Cursor Off
    con   = '\033[?25h' if TTY else '' # Cursor On
    stk   = '\033[09m' if TTY else ''  # Strikethrough
    inv   = '\033[08m' if TTY else ''  # Invisible

    class fg(Color):
        # Foreground colors

        # Base color
        BLK = '\033[30m' if Color.TTY else ''
        RED = '\033[31m' if TTY else ''
        GRN = '\033[32m' if TTY else ''
        YLW = '\033[33m' if TTY else ''
        BLU = '\033[34m' if TTY else ''
        MGN = '\033[35m' if TTY else ''
        CYN = '\033[36m' if TTY else ''
        WHT = '\033[37m' if TTY else ''

        # Lighter shade
        blk = '\033[90m' if TTY else ''
        red = '\033[91m' if TTY else ''
        grn = '\033[92m' if TTY else ''
        ylw = '\033[93m' if TTY else ''
        blu = '\033[94m' if TTY else ''
        mgn = '\033[95m' if TTY else ''
        cyn = '\033[96m' if TTY else ''
        wht = '\033[97m' if TTY else ''

    class bg:
        # Background color

        # Base color
        BLK = '\033[40m' if TTY else '' # Black
        RED = '\033[41m' if TTY else '' # Red
        GRN = '\033[42m' if TTY else '' # Green
        YLW = '\033[43m' if TTY else '' # Yellow
        BLU = '\033[44m' if TTY else '' # Blue
        MGN = '\033[45m' if TTY else '' # Magenta
        CYN = '\033[46m' if TTY else '' # Cyan
        WHT = '\033[47m' if TTY else '' # White

        # Lighter shade
        blk = '\033[100m' if TTY else '' # Black
        red = '\033[101m' if TTY else '' # Red
        grn = '\033[102m' if TTY else '' # Green
        ylw = '\033[103m' if TTY else '' # Yellow
        blu = '\033[104m' if TTY else '' # Blue
        mgn = '\033[105m' if TTY else '' # Magenta
        cyn = '\033[106m' if TTY else '' # Cyan
        wht = '\033[107m' if TTY else '' # White
