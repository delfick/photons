from PIL import ImageFont, ImageDraw, Image
import argparse
import os

this_dir = os.path.dirname(__file__)


chars = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789,.:!?@#$%^&*(){}[]-_'\""

parser = argparse.ArgumentParser()
parser.add_argument(
    "font_file",
    help="Path to amstrad-cpc-extended.ttf, (see https://fontstruct.com/fontstructions/show/25590/amstrad_cpc_extended)",
)
args = parser.parse_args()

for w in (8, 16):
    font = ImageFont.truetype(args.font_file, w)
    with open(os.path.join(this_dir, f"alphabet_{w}.py"), "w") as fle:
        print("from photons_canvas.animations.font.base import Character, Space", file=fle)
        print("", file=fle)
        print("characters = {", file=fle)

        for ch in list(chars):
            image = Image.new("L", (w, w))
            draw = ImageDraw.Draw(image)
            draw.text((0, 0), ch, fill="white", font=font)

            nxt = []
            for i in range(w):
                row = []
                for j in range(w):
                    pixel = image.getpixel((j, i))
                    if pixel == 0:
                        row.append("_")
                    else:
                        row.append("#")
                nxt.append("".join(row))

            if ch == " ":
                print(f'    " ": Space({w // 2}, {w}),', file=fle)
                continue

            if ch == "z":
                nxt.insert(0, nxt.pop())

            if ch == '"':
                ch = "'\"'"
            else:
                ch = f'"{ch}"'

            print(f'    {ch}: Character(\n        """', file=fle)

            for row in nxt:
                print(f"      {''.join(row)}", file=fle)
            print('      """\n    ),', file=fle)

        print("}", file=fle)
