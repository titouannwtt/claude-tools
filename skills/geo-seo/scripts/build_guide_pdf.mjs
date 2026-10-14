#!/usr/bin/env node
// Assembles references/*.md into a single PDF guide (cover, table of contents, page numbers).
//
//   MARKED_MODULE=/path/to/node_modules/marked/lib/marked.esm.js \
//   PLAYWRIGHT_MODULE=/path/to/node_modules/playwright/index.mjs \
//   node build_guide_pdf.mjs [output.pdf]
//
// The module paths are local values (local.env), never versioned.
// Prerequisite: Playwright's Chromium installed (`npx playwright install chromium`).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const refs = path.join(here, '..', 'references');
const out = path.resolve(process.argv[2] || path.join(here, '..', 'references', 'COMPLETE-GUIDE.pdf'));
const need = (name) => { if (!process.env[name]) { console.error(`${name} missing (see the script header)`); process.exit(2); } return process.env[name]; };
const { marked } = await import(pathToFileURL(need('MARKED_MODULE')).href);
const { chromium } = await import(pathToFileURL(need('PLAYWRIGHT_MODULE')).href);

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const slug = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

const files = fs.readdirSync(refs).filter((f) => /^\d\d-.*\.md$/.test(f)).sort();
const templates = fs.existsSync(path.join(refs, 'templates'))
  ? fs.readdirSync(path.join(refs, 'templates')).sort() : [];

const toc = [];
let body = '';
for (const f of files) {
  const md = fs.readFileSync(path.join(refs, f), 'utf8');
  const renderer = new marked.Renderer();
  let first = true;
  renderer.heading = ({ tokens, depth }) => {
    const text = tokens.map((t) => t.raw ?? t.text ?? '').join('');
    const plain = text.replace(/[*`]/g, '');
    const id = `${f.slice(0, 2)}-${slug(plain)}`;
    if (depth === 1 && first) { first = false; toc.push({ d: 1, id, t: plain }); return `<h1 id="${id}" class="chapter">${esc(plain)}</h1>`; }
    if (depth === 2) toc.push({ d: 2, id, t: plain });
    return `<h${depth} id="${id}">${marked.parseInline(text)}</h${depth}>`;
  };
  body += `<section class="chap">${marked.parse(md, { renderer, gfm: true })}</section>\n`;
}

let annex = '<section class="chap"><h1 class="chapter" id="annexes">Appendices: ready-to-adapt templates</h1>';
toc.push({ d: 1, id: 'annexes', t: 'Appendices: ready-to-adapt templates' });
for (const t of templates) {
  const raw = fs.readFileSync(path.join(refs, 'templates', t), 'utf8');
  const id = `appendix-${slug(t)}`;
  toc.push({ d: 2, id, t });
  annex += `<h2 id="${id}">${esc(t)}</h2>` + (t.endsWith('.md')
    ? marked.parse(raw, { gfm: true }) : `<pre><code>${esc(raw)}</code></pre>`);
}
annex += '</section>';

const tocHtml = toc.map((e) => `<li class="t${e.d}"><a href="#${e.id}">${esc(e.t)}</a></li>`).join('\n');
const today = new Date().toISOString().slice(0, 10);
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Complete GEO and SEO guide</title><style>
@page { size: A4; margin: 20mm 17mm 20mm 17mm; }
body { font: 10.5pt/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1c1c1c; }
.cover { height: 235mm; display: flex; flex-direction: column; justify-content: center; page-break-after: always; }
.cover h1 { font-size: 30pt; line-height: 1.15; margin: 0 0 10mm; border: 0; }
.cover p { font-size: 13pt; color: #444; max-width: 140mm; }
.cover small { color: #777; margin-top: 12mm; }
.toc { page-break-after: always; } .toc h1 { font-size: 20pt; }
.toc ul { list-style: none; padding: 0; } .toc li { margin: 1.2mm 0; } .toc li.t1 { font-weight: 700; margin-top: 4mm; }
.toc li.t2 { margin-left: 6mm; font-size: 9.5pt; } .toc a { color: inherit; text-decoration: none; }
.chap { page-break-before: always; }
h1.chapter { font-size: 21pt; border-bottom: 2px solid #2f6f5e; padding-bottom: 3mm; margin-top: 0; }
h2 { font-size: 14pt; margin-top: 8mm; color: #1e4d41; page-break-after: avoid; } h3 { font-size: 11.5pt; page-break-after: avoid; }
p, li { orphans: 3; widows: 3; }
table { border-collapse: collapse; width: 100%; margin: 4mm 0; font-size: 9pt; page-break-inside: auto; }
tr { page-break-inside: avoid; } th, td { border: 1px solid #c9c9c9; padding: 1.6mm 2.2mm; vertical-align: top; text-align: left; }
th { background: #eef3f1; }
code { font: 8.6pt/1.4 "SFMono-Regular", Menlo, Consolas, monospace; background: #f3f3f3; padding: 0 1mm; border-radius: 1mm; word-break: break-word; }
pre { background: #f6f6f6; border: 1px solid #ddd; border-radius: 2mm; padding: 3mm; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: none; padding: 0; }
blockquote { margin: 3mm 0; padding: 1mm 4mm; border-left: 3px solid #2f6f5e; color: #444; background: #f7faf9; }
a { color: #1d5d92; }
</style></head><body>
<section class="cover"><h1>Complete guide to Google and AI assistant search visibility</h1>
<p>Method, practices, adjustments and examples drawn from a real overhaul of 700 pages in 10 languages: measured audit, technical work, content, translations, submission, measurement, off-site actions, pitfalls met and autonomous procedure.</p>
<small>Version of ${today}. Worked example: jam-jam.org. Generated from the geo-seo skill knowledge base.</small></section>
<section class="toc"><h1>Table of contents</h1><ul>${tocHtml}</ul></section>
${body}
${annex}
</body></html>`;

const tmp = path.join(refs, '.guide.html');
fs.writeFileSync(tmp, html);
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(tmp).href, { waitUntil: 'load' });
await page.pdf({
  path: out, format: 'A4', printBackground: true, displayHeaderFooter: true,
  headerTemplate: '<span></span>',
  footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#777"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
  margin: { top: '20mm', bottom: '20mm', left: '17mm', right: '17mm' },
});
await browser.close();
if (!process.env.KEEP_HTML) fs.unlinkSync(tmp);
console.log(JSON.stringify({ pdf: out, bytes: fs.statSync(out).size, chapters: files.length, annexes: templates.length }));
