import sys
import subprocess
from xml.etree import ElementTree as ET

# Usage: python3 tex-to-svg.py "a^2+b^2=c^2" output.svg
equation = sys.argv[1]
output_fn = "optut.svg" #sys.argv[2]
PADDING = 200  # Adjust this value for more/less space

try:
    # 1. Get raw SVG from MathJax
    raw_svg = subprocess.check_output(['tex2svg', equation], text=True)

    # 2. Parse XML
    ET.register_namespace('', "http://w3.org")
    root = ET.fromstring(raw_svg)

    # 3. Double the display size
    def double_dim(val):
        num = float(''.join(c for c in val if c.isdigit() or c == '.'))
        unit = ''.join(c for c in val if c.isalpha())
        return f"{num * 2}{unit}"

    root.set('width', double_dim(root.get('width')))
    root.set('height', double_dim(root.get('height')))

    # 4. Modify ViewBox for Padding
    vbox = [float(x) for x in root.get('viewBox').split()]
    # vbox is [min-x, min-y, width, height]
    vbox[0] -= PADDING  # Move left edge further left
    vbox[1] -= PADDING  # Move top edge further up
    vbox[2] += PADDING * 2  # Make total width wider
    vbox[3] += PADDING * 2  # Make total height taller

    new_vbox_str = " ".join(map(str, vbox))
    root.set('viewBox', new_vbox_str)

    # 5. Inject White Background (matching the new expanded viewBox)
    rect = ET.Element('rect', {
        'x': str(vbox[0]),
        'y': str(vbox[1]),
        'width': str(vbox[2]),
        'height': str(vbox[3]),
        'fill': 'white'
    })
    root.insert(0, rect)

    # 6. Save and Open
    with open(output_fn, 'wb') as f:
        f.write(ET.tostring(root))

    subprocess.call(['open', output_fn])

except Exception as e:
    print(f"Error: {e}")
