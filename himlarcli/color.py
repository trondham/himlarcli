
class Color:
    # General effects

    reset = '\033[0m'   # Default color and effects
    bold  = '\033[1m'   # Bold/brighter
    dim   = '\033[2m'   # Dim/darker
    cur   = '\033[3m'   # Italic font
    und   = '\033[4m'   # Underline
    rev   = '\033[7m'   # Reverse/Inverted
    cof   = '\033[?25l' # Cursor Off
    con   = '\033[?25h' # Cursor On
    stk   = '\033[09m'  # Strikethrough
    inv   = '\033[08m'  # Invisible

    class fg:
        # Foreground colors

        # Base color
        BLK = '\033[30m'
        RED = '\033[31m'
        GRN = '\033[32m'
        YLW = '\033[33m'
        BLU = '\033[34m'
        MGN = '\033[35m'
        CYN = '\033[36m'
        WHT = '\033[37m'

        # Lighter shade
        blk = '\033[90m'
        red = '\033[91m'
        grn = '\033[92m'
        ylw = '\033[93m'
        blu = '\033[94m'
        mgn = '\033[95m'
        cyn = '\033[96m'
        wht = '\033[97m'

    class bg:
        # Background color

        # Base color
        BLK = '\033[40m' # Black
        RED = '\033[41m' # Red
        GRN = '\033[42m' # Green
        YLW = '\033[43m' # Yellow
        BLU = '\033[44m' # Blue
        MGN = '\033[45m' # Magenta
        CYN = '\033[46m' # Cyan
        WHT = '\033[47m' # White

        # Lighter shade
        blk = '\033[100m' # Black
        red = '\033[101m' # Red
        grn = '\033[102m' # Green
        ylw = '\033[103m' # Yellow
        blu = '\033[104m' # Blue
        mgn = '\033[105m' # Magenta
        cyn = '\033[106m' # Cyan
        wht = '\033[107m' # White
