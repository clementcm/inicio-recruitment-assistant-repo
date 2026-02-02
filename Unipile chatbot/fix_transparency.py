from PIL import Image
import numpy as np

def make_transparent(image_path, output_path, tolerance=30):
    img = Image.open(image_path).convert("RGBA")
    data = np.array(img)
    
    # Assume top-left pixel is the background color to remove
    r, g, b, a = data[0, 0]
    
    # Create mask for pixels close to the background color
    red, green, blue, alpha = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    mask = (
        (np.abs(red - r) <= tolerance) & 
        (np.abs(green - g) <= tolerance) & 
        (np.abs(blue - b) <= tolerance)
    )
    
    # Set alpha to 0 for matching pixels
    data[:,:,3][mask] = 0
    
    new_img = Image.fromarray(data)
    new_img.save(output_path, "PNG")
    print(f"Saved transparent image to {output_path}")

try:
    make_transparent(
        "/Volumes/Extreme Pro/Projects/anti G project/Unipile chatbot/frontend/logo.jpg",
        "/Volumes/Extreme Pro/Projects/anti G project/Unipile chatbot/frontend/logo.png"
    )
except Exception as e:
    print(f"Error: {e}")
