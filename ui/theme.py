"""Dark window, soft muted card colors (dark text sits on all of them)."""

THEME = {
    "bg_window": "#14161D",
    "output_bg": "#D5E4EA",
    "output_text": "#0F4C5C",
}

# Eight clearly different, low-saturation colors
CARD_PALETTE = [
    "#9FBCD6",  # dusty blue
    "#A8CDB0",  # sage green
    "#E3C7A1",  # soft peach
    "#C3B1D9",  # lavender
    "#E3B3C0",  # dusty pink
    "#9ED0CC",  # soft teal
    "#D9D49E",  # butter
    "#B7BFCB",  # slate grey
]

BACK_COLOR = "#D6A595"      # muted clay for BACK buttons
NEXT_COLOR = "#B7BFCB"      # "next page" card
UTILITY_COLOR = "#4F5B6E"   # small footer buttons
UTILITY_TEXT = "#DDE3EA"

CARD_TEXT = "#1F2933"       # dark text on pastel cards
BORDER_IDLE = "#2C3240"
BORDER_FOCUS = "#F4F1E8"    # soft off-white outline while looking at a card
BORDER_SELECTED = "#E6C86E" # soft gold for the selected "I / me" card
RING_COLOR = "#2B3A4A"      # dwell progress ring

# Font stack with Telugu + Devanagari support (Windows has Nirmala UI)
UI_FONT = '"Nirmala UI", "Noto Sans Telugu", "Noto Sans Devanagari", "Segoe UI", sans-serif'