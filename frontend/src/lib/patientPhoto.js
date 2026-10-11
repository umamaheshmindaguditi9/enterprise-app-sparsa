export const jpegBlob = canvas => new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.82));

export const fitPhotoCanvas = (source, width, height) => {
  const canvas = document.createElement("canvas"), ratio = Math.min(1, 800 / Math.max(width, height));
  canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  return canvas;
};

export const preparePhotoFile = async file => {
  let image, temporaryUrl;
  try {
    if (typeof createImageBitmap === "function") image = await createImageBitmap(file);
    else { temporaryUrl = URL.createObjectURL(file); image = new Image(); image.src = temporaryUrl; await image.decode(); }
    const photo = await jpegBlob(fitPhotoCanvas(image, image.width, image.height));
    if (!photo) throw new Error("Photo conversion failed");
    return photo;
  } finally { image?.close?.(); if (temporaryUrl) URL.revokeObjectURL(temporaryUrl); }
};