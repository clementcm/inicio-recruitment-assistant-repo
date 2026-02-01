#!/usr/bin/env python3
from PIL import Image
import sys

# Open the image
img = Image.open('/Volumes/Extreme Pro/Projects/anti G project/Unipile chatbot/frontend/logo.jpg')

# Convert to RGBA if not already
img = img.convert('RGBA')

# Get pixel data
data = img.getdata()

# Create new image data with white pixels made transparent
new_data = []
for item in data:
    # If pixel is mostly white (R, G, B all > 240), make it transparent
    if item[0] > 240 and item[1] > 240 and item[2] > 240:
        new_data.append((255, 255, 255, 0))  # Transparent
    else:
        new_data.append(item)

# Update image data
img.putdata(new_data)

# Save as PNG (supports transparency)
img.save('/Volumes/Extreme Pro/Projects/anti G project/Unipile chatbot/frontend/logo.png')
print("Logo saved with transparent background as logo.png")
