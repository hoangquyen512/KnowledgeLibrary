/**
 * Rasterize brand SVGs → PNG/ICO for favicon, PWA, and OG.
 * Run: node scripts/rasterize-brand.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { Resvg } from "@resvg/resvg-js";
import pngToIco from "png-to-ico";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function render(svgPath, outPath, width) {
  const svg = fs.readFileSync(svgPath);
  const resvg = new Resvg(svg, {
    fitTo: { mode: "width", value: width },
    font: { loadSystemFonts: true },
  });
  const png = resvg.render().asPng();
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, png);
  console.log("wrote", path.relative(process.cwd(), outPath), `(${width}px)`);
  return outPath;
}

const root = path.join(__dirname, "..", "public", "brand");
const mark = path.join(root, "logo", "logo-mark.svg");
const appIcon = path.join(root, "app-icons", "icon.svg");
const og = path.join(root, "social", "og-image.svg");
const full = path.join(root, "mascot", "ant-full.svg");
const antMark = path.join(root, "mascot", "ant-mark.svg");
const search = path.join(root, "mascot", "ant-search.svg");
const empty = path.join(root, "mascot", "ant-empty.svg");
const loading = path.join(root, "mascot", "ant-loading.svg");

render(mark, path.join(root, "favicon", "favicon-16x16.png"), 16);
render(mark, path.join(root, "favicon", "favicon-32x32.png"), 32);

for (const size of [16, 32, 48, 64, 128, 180, 192, 256, 512, 1024]) {
  render(appIcon, path.join(root, "app-icons", `icon-${size}.png`), size);
}

render(og, path.join(root, "social", "og-image.png"), 1200);
render(full, path.join(root, "mascot", "ant-full.png"), 512);
render(antMark, path.join(root, "mascot", "ant-mark.png"), 256);
render(search, path.join(root, "mascot", "ant-search.png"), 512);
render(empty, path.join(root, "mascot", "ant-empty.png"), 512);
render(loading, path.join(root, "mascot", "ant-loading.png"), 256);

const ico = await pngToIco([
  path.join(root, "favicon", "favicon-16x16.png"),
  path.join(root, "favicon", "favicon-32x32.png"),
]);
fs.writeFileSync(path.join(root, "favicon", "favicon.ico"), ico);
fs.copyFileSync(
  path.join(root, "favicon", "favicon.ico"),
  path.join(__dirname, "..", "public", "favicon.ico"),
);
console.log("wrote favicon.ico");
