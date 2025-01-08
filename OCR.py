import os
import math
from collections import Counter
from google.cloud import vision
import re

os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'ocracle-8ab6e49a7b54.json'

def detect_text(path):
    """Detects text in the file."""
    client = vision.ImageAnnotatorClient()

    with open(path, 'rb') as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if response.error.message:
        raise Exception(f'{response.error.message}')

    return texts[0].description if texts else ''

print(detect_text('image.png'))
#