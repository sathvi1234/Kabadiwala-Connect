export async function compressImage(file: Blob, maxBytes = 200 * 1024, quality = 0.7): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  let width = bitmap.width;
  let height = bitmap.height;
  let q = quality;
  let blob = file;
  for (let i = 0; i < 8; i += 1) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, width);
    canvas.height = Math.max(1, height);
    const ctx = canvas.getContext("2d");
    if (!ctx) break;
    ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const next = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/webp", q));
    if (!next) break;
    blob = next;
    if (blob.size <= maxBytes) break;
    q = Math.max(0.35, q - 0.1);
    width = Math.round(width * 0.85);
    height = Math.round(height * 0.85);
  }
  bitmap.close();
  return blob;
}

export function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}
