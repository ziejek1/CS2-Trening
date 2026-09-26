from PIL import Image, ImageDraw

sizes = (16, 24, 32, 48, 64, 128, 256)
images = []
for size in sizes:
    image = Image.new("RGBA", (size, size), "#0B1220")
    draw = ImageDraw.Draw(image)
    margin = max(1, size // 10)
    draw.rounded_rectangle((margin, margin, size - margin, size - margin), radius=max(2, size // 6), fill="#111827", outline="#2563EB", width=max(1, size // 24))
    center = size // 2
    radius = max(3, size // 4)
    line = max(1, size // 18)
    green = "#34D399"
    draw.ellipse((center - radius, center - radius, center + radius, center + radius), outline=green, width=line)
    draw.line((center - radius - line, center, center + radius + line, center), fill=green, width=line)
    draw.line((center, center - radius - line, center, center + radius + line), fill=green, width=line)
    draw.ellipse((center - max(1, size // 24), center - max(1, size // 24), center + max(1, size // 24), center + max(1, size // 24)), fill="#FBBF24")
    images.append(image)
images[-1].save("app_icon.ico", format="ICO", sizes=[(size, size) for size in sizes])
