"""生成简单的 ICO 图标文件（不依赖 Pillow）"""
import struct, zlib, os

# 16x16 RGBA 像素数据（红底白叉）
def make_icon():
    size = 16
    # 创建红色背景 + 白色 X 形状
    pixels = []
    for y in range(size):
        row = []
        for x in range(size):
            # 白色 X：对角线±2px
            on_diag1 = abs(x - y) <= 1
            on_diag2 = abs(x - (size - 1 - y)) <= 1
            border = x < 2 or x >= size-2 or y < 2 or y >= size-2
            if on_diag1 or on_diag2:
                row.extend([255, 255, 255, 255])   # 白
            elif border:
                row.extend([180, 0, 0, 255])       # 深红边框
            else:
                row.extend([220, 30, 30, 255])     # 红
        pixels.extend(row)

    # 写 PNG（内嵌进 ICO）
    def png_chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    raw = b""
    for y in range(size):
        raw += b"\x00"  # filter type
        raw += bytes(pixels[y*size*4:(y+1)*size*4])

    compressed = zlib.compress(raw, 9)

    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
    # IHDR: bit depth=8, color type=2 (RGB) — use RGB not RGBA for simplicity
    # Redo with proper RGBA
    png = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">II", size, size) + bytes([8, 6, 0, 0, 0])  # 8-bit RGBA
    png += png_chunk(b"IHDR", ihdr)
    png += png_chunk(b"IDAT", compressed)
    png += png_chunk(b"IEND", b"")

    # ICO format: header + directory + PNG data
    ico_header = struct.pack("<HHH", 0, 1, 1)  # reserved, type=1(ICO), count=1
    # Directory entry: width, height, colors, reserved, planes, bit_count, size, offset
    png_size = len(png)
    ico_dir = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, png_size, 22)
    ico = ico_header + ico_dir + png

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    with open(out, "wb") as f:
        f.write(ico)
    print(f"图标已生成：{out}")

if __name__ == "__main__":
    make_icon()
