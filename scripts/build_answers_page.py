"""Build answers.html (GitHub Pages) from lab_answers.md. Handles the subset that file uses:
headings with {#anchor}, paragraphs, **bold**, `code`, fenced code (with a copy button), tables, numbered lists.
Usage: build_answers_page.py lab_answers.md answers.html
"""
import html, re, sys

src, dst = sys.argv[1], sys.argv[2]
lines = open(src).read().splitlines()

def inline(t):
    t = html.escape(t, quote=False)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    return re.sub(r"(https?://[^\s<*]+)", r'<a href="\1">\1</a>', t)

out, i, n_code = [], 0, 0
while i < len(lines):
    l = lines[i]
    if l.startswith("```"):
        j = i + 1
        while not lines[j].startswith("```"): j += 1
        n_code += 1
        body = html.escape("\n".join(lines[i + 1:j]), quote=False)
        out.append(f'<div class="code"><button class="mini" data-target="c{n_code}">Copy</button><pre><code id="c{n_code}">{body}</code></pre></div>')
        i = j + 1; continue
    m = re.match(r"^(#{1,3}) (.*?)(?: \{#([\w-]+)\})?$", l)
    if m:
        lvl, text, anchor = len(m.group(1)), m.group(2), m.group(3)
        out.append(f'<h{lvl}{f" id={chr(34)}{anchor}{chr(34)}" if anchor else ""}>{inline(text)}</h{lvl}>'); i += 1; continue
    if l.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            if not all(re.fullmatch(r"-+", c) for c in cells): rows.append(cells)
            i += 1
        head, *body = rows
        out.append("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                   + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
        continue
    if re.match(r"^\d+\. ", l):
        items = []
        while i < len(lines) and re.match(r"^\d+\. ", lines[i]):
            items.append(re.sub(r"^\d+\. ", "", lines[i])); i += 1
        out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in items) + "</ol>"); continue
    if l.strip():
        para = [l]; i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|```|\||\d+\. )", lines[i]):
            para.append(lines[i]); i += 1
        out.append(f"<p>{inline(' '.join(para))}</p>"); continue
    i += 1

page = open("index.html").read()
style = page[page.index("<style>"):page.index("</style>") + 8]
style = style.replace("</style>", """  .code { position:relative; }
  .code pre { padding-top:46px; }
  table { border-collapse:collapse; width:100%; margin:8px 0 16px; font-size:15px; }
  th, td { border:1px solid var(--line); padding:7px 10px; text-align:left; vertical-align:top; }
  th { background:var(--card); }
  .note { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:8px; padding:10px 14px; }
  h2 { padding-top:8px; }
</style>""")
doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Lab Answers</title>
{style}
</head>
<body>
<main>
<p class="small"><a href="./">← Lab setup</a></p>
{chr(10).join(out)}
<p class="note small">Known answers are for <b>10/21/2026</b>. Risk tiers use days since last login, so counts drift a little each day after that.</p>
</main>
<script>
  document.querySelectorAll('button.mini').forEach(b => b.addEventListener('click', async () => {{
    const text = document.getElementById(b.dataset.target).textContent;
    try {{ await navigator.clipboard.writeText(text); }}
    catch {{ const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); }}
    b.textContent = 'Copied ✓'; setTimeout(() => b.textContent = 'Copy', 2000);
  }}));
</script>
</body>
</html>
"""
open(dst, "w").write(doc)
anchors = re.findall(r'id="([\w-]+)"', doc)
print(f"wrote {dst}: {n_code} code blocks, anchors: {anchors}")
