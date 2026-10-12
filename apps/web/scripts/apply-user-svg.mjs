import fs from "fs";
import path from "path";
import sharp from "sharp";
import pngToIco from "png-to-ico";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..", "public", "brand");
const srcSvg = "D:\\knowledge-library-full-mascot.svg";
const brandSvg = path.join(root, "mascot", "knowledge-library-full-mascot.svg");
const antFullSvg = path.join(root, "mascot", "ant-full.svg");
const sourcePng = path.join(root, "mascot", "_source-full.png");

fs.copyFileSync(srcSvg, brandSvg);
fs.copyFileSync(srcSvg, antFullSvg);

const svg = fs.readFileSync(srcSvg);
console.log("svg bytes", svg.length);

// Rasterize SVG → high-res PNG source
await sharp(svg, { density: 300 })
  .resize(1024, 1024, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
  .png()
  .toFile(sourcePng);
console.log("wrote source png", fs.statSync(sourcePng).size);

async function removeDarkBg(input, threshold = 28) {
  const { data, info } = await sharp(input).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  for (let i = 0; i < data.length; i += 4) {
    const r = data[i];
    const g = data[i + 1];
    const b = data[i + 2];
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    if (max < threshold && max - min < 14) data[i + 3] = 0;
  }
  return sharp(data, { raw: { width: info.width, height: info.height, channels: 4 } }).png().toBuffer();
}

async function appIcon(cutout, size, out) {
  const pad = Math.round(size * 0.12);
  const inner = size - pad * 2;
  const mascot = await sharp(cutout)
    .resize(inner, inner, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
    .png()
    .toBuffer();
  const radius = Math.round(size * 0.22);
  const bg = Buffer.from(
    `<svg width="${size}" height="${size}"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0B1A4A"/><stop offset="1" stop-color="#102A6A"/></linearGradient></defs><rect width="${size}" height="${size}" rx="${radius}" fill="url(#g)"/></svg>`,
  );
  await sharp(bg)
    .composite([{ input: mascot, top: pad, left: pad }])
    .png()
    .toFile(out);
  console.log("wrote", path.basename(out));
}

// Keep exact raster of SVG for full mascot
fs.copyFileSync(sourcePng, path.join(root, "mascot", "ant-full.png"));
fs.copyFileSync(sourcePng, path.join(root, "mascot", "ant-search.png"));
fs.copyFileSync(sourcePng, path.join(root, "mascot", "ant-empty.png"));
fs.copyFileSync(sourcePng, path.join(root, "mascot", "knowledge-library-mascot-source.png"));

const cutout = await removeDarkBg(sourcePng, 28);
const meta = await sharp(cutout).metadata();
const w = meta.width;
const h = meta.height;

const markBuf = await sharp(cutout)
  .extract({
    left: Math.round(w * 0.06),
    top: Math.round(h * 0.02),
    width: Math.round(w * 0.88),
    height: Math.round(h * 0.72),
  })
  .resize(512, 512, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
  .png()
  .toBuffer();

await sharp(markBuf).toFile(path.join(root, "mascot", "ant-mark.png"));
await sharp(markBuf).resize(256, 256).toFile(path.join(root, "mascot", "ant-loading.png"));
await sharp(markBuf).toFile(path.join(root, "logo", "logo-mark.png"));
await sharp(markBuf).toFile(path.join(root, "logo", "logo-mark-dark.png"));

// Prefer SVG mark wrappers pointing at original SVG where useful
fs.writeFileSync(
  path.join(root, "logo", "logo-mark.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="Knowledge Library"><image href="../mascot/knowledge-library-full-mascot.svg" width="512" height="512" preserveAspectRatio="xMidYMid meet"/></svg>\n`,
);
fs.copyFileSync(path.join(root, "logo", "logo-mark.svg"), path.join(root, "logo", "logo-mark-dark.svg"));
fs.writeFileSync(
  path.join(root, "mascot", "ant-mark.svg"),
  `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="Knowledge Library"><image href="knowledge-library-full-mascot.svg" width="512" height="512" preserveAspectRatio="xMidYMid meet"/></svg>\n`,
);

for (const size of [16, 32, 48, 64, 128, 180, 192, 256, 512, 1024]) {
  await appIcon(cutout, size, path.join(root, "app-icons", `icon-${size}.png`));
}
await appIcon(cutout, 512, path.join(root, "app-icons", "icon.png"));

await sharp(markBuf).resize(16, 16).png().toFile(path.join(root, "favicon", "favicon-16x16.png"));
await sharp(markBuf).resize(32, 32).png().toFile(path.join(root, "favicon", "favicon-32x32.png"));
const ico = await pngToIco([
  path.join(root, "favicon", "favicon-16x16.png"),
  path.join(root, "favicon", "favicon-32x32.png"),
]);
fs.writeFileSync(path.join(root, "favicon", "favicon.ico"), ico);
fs.copyFileSync(path.join(root, "favicon", "favicon.ico"), path.join(__dirname, "..", "public", "favicon.ico"));

const ogBg = Buffer.from(
  `<svg width="1200" height="630"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#F8FAFF"/><stop offset="1" stop-color="#E4E8FF"/></linearGradient><linearGradient id="lib" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#2F5BEA"/><stop offset="1" stop-color="#6C3EF0"/></linearGradient></defs><rect width="1200" height="630" fill="url(#bg)"/><text x="88" y="250" font-family="Segoe UI, Arial" font-size="64" font-weight="700" fill="#102A6A">Knowledge</text><text x="88" y="330" font-family="Segoe UI, Arial" font-size="64" font-weight="500" fill="url(#lib)">Library</text><text x="88" y="390" font-family="Segoe UI, Arial" font-size="26" fill="#667085">Explore • Understand • Grow</text></svg>`,
);
const ogMascot = await sharp(cutout)
  .resize(440, 440, { fit: "contain", background: { r: 0, g: 0, b: 0, alpha: 0 } })
  .png()
  .toBuffer();
await sharp(ogBg)
  .composite([{ input: ogMascot, top: 95, left: 700 }])
  .png()
  .toFile(path.join(root, "social", "og-image.png"));

console.log("done from D:\\knowledge-library-full-mascot.svg");
