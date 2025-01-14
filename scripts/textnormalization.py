import regex as re

def normalize_text(text):
    """
    Normalize the input text by removing unnecessary whitespace,
    replacing common symbols with readable alternatives, and ensuring proper formatting.
    """
    text = re.sub(r'\s+', ' ', text.strip())

    replacements = {
        '−': '-',  # Replace Unicode minus with standard hyphen
        '×': '\times',  # Replace multiplication symbol with LaTeX command
        '÷': '\div',  # Replace division symbol with LaTeX command
        '=': ' = ',  # Add spacing around equals for clarity
        '∞': '\infty',  # Replace infinity symbol
        '∑': '\sum',  # Replace summation symbol
        '√': '\sqrt',  # Replace square root symbol
        'π': '\pi',  # Replace pi symbol
        '^': '**',  # Replace caret with exponentiation for Python
    }
    for symbol, replacement in replacements.items():
        text = text.replace(symbol, replacement)

    text = re.sub(r'(\d+)\s*/\s*(\d+)', r'\frac{\1}{\2}', text)  # Fractions
    text = re.sub(r'_(\w+)', r'_{\1}', text)  # Subscripts
    text = re.sub(r'\^(\w+)', r'^{\1}', text)  # Superscripts

    text = re.sub(r'(?<!\\)([+\-*/^=()])', r' \1 ', text)  # Space around operators
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize spaces again

    return text
