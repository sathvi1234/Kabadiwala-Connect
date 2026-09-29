import io

from PIL import Image


def dhash(data: bytes, hash_size: int = 8) -> str:
    image = Image.open(io.BytesIO(data)).convert("L").resize((hash_size + 1, hash_size))
    pixels = list(image.getdata())
    bits = []
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            bits.append("1" if left > right else "0")
    return "".join(bits)


def hamming(a: str, b: str) -> int:
    if not a or not b or len(a) != len(b):
        return 64
    return sum(x != y for x, y in zip(a, b))


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return round(1 - hamming(a, b) / len(a), 3)
