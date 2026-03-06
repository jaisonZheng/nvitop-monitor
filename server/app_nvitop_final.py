#!/usr/bin/env python3
"""
nvitop web mirror - pixel-perfect terminal UI in the browser.

Data flow:
  HPC client  →  POST /update_ansi (raw ANSI text)
  Server      →  converts ANSI escape codes → HTML spans
  Browser     →  polls GET /data_html every 1s, renders <pre> on black bg
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import html
import re
from datetime import datetime

app = FastAPI()

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
state = {
    "html_output": "",      # pre-rendered HTML from last ANSI push
    "raw_ansi": "",         # raw ANSI text (for debugging)
    "timestamp": "",
    "hostname": "",
    "username": "",
    # Dimensions requested by the browser (cols × rows).
    # The client reads these and passes them to nvitop via pty/COLUMNS/LINES.
    "cols": 200,
    "rows": 50,
}

# ---------------------------------------------------------------------------
# ANSI → HTML converter (supports 16-color, 256-color, bold, dim, italic)
# ---------------------------------------------------------------------------

# xterm 256-color palette
def _build_xterm256():
    """Return list of 256 hex-color strings for xterm-256color."""
    palette = []
    # 0-15: system colors
    system = [
        "#000000", "#800000", "#008000", "#808000",
        "#000080", "#800080", "#008080", "#c0c0c0",
        "#808080", "#ff0000", "#00ff00", "#ffff00",
        "#0000ff", "#ff00ff", "#00ffff", "#ffffff",
    ]
    palette.extend(system)
    # 16-231: 6×6×6 color cube
    for r in range(6):
        for g in range(6):
            for b in range(6):
                rv = 0 if r == 0 else 55 + r * 40
                gv = 0 if g == 0 else 55 + g * 40
                bv = 0 if b == 0 else 55 + b * 40
                palette.append(f"#{rv:02x}{gv:02x}{bv:02x}")
    # 232-255: grayscale
    for i in range(24):
        v = 8 + i * 10
        palette.append(f"#{v:02x}{v:02x}{v:02x}")
    return palette

XTERM256 = _build_xterm256()


def ansi_to_html(text: str) -> str:
    """
    Convert ANSI-escaped terminal text to HTML.

    Handles:
    - ESC[0m  reset
    - ESC[1m  bold
    - ESC[2m  dim
    - ESC[3m  italic
    - ESC[4m  underline
    - ESC[7m  reverse (swaps fg/bg)
    - ESC[30-37, 90-97m  standard/bright fg colors
    - ESC[40-47, 100-107m  standard/bright bg colors
    - ESC[38;5;Nm  256-color fg
    - ESC[48;5;Nm  256-color bg
    - ESC[38;2;R;G;Bm  truecolor fg
    - ESC[48;2;R;G;Bm  truecolor bg
    - ESC[?…h / ESC[?…l  private modes (ignored)
    - ESC[…A/B/C/D  cursor movement (ignored; nvitop -1 doesn't use these)
    - Other ESC sequences stripped silently
    """
    # Standard 16-color fg/bg
    STD_FG = {
        30: "#2e3436", 31: "#cc0000", 32: "#4e9a06", 33: "#c4a000",
        34: "#3465a4", 35: "#75507b", 36: "#06989a", 37: "#d3d7cf",
        90: "#555753", 91: "#ef2929", 92: "#8ae234", 93: "#fce94f",
        94: "#729fcf", 95: "#ad7fa8", 96: "#34e2e2", 97: "#eeeeec",
    }
    STD_BG = {
        40: "#2e3436", 41: "#cc0000", 42: "#4e9a06", 43: "#c4a000",
        44: "#3465a4", 45: "#75507b", 46: "#06989a", 47: "#d3d7cf",
        100: "#555753", 101: "#ef2929", 102: "#8ae234", 103: "#fce94f",
        104: "#729fcf", 105: "#ad7fa8", 106: "#34e2e2", 107: "#eeeeec",
    }

    # Current style state
    class Style:
        def __init__(self):
            self.reset()
        def reset(self):
            self.fg = None
            self.bg = None
            self.bold = False
            self.dim = False
            self.italic = False
            self.underline = False
            self.reverse = False
        def css(self):
            parts = []
            fg = self.fg
            bg = self.bg
            if self.reverse:
                fg, bg = (bg or "#e5e5e5"), (fg or "#000000")
            if fg:
                parts.append(f"color:{fg}")
            if bg:
                parts.append(f"background:{bg}")
            if self.bold:
                parts.append("font-weight:bold")
            if self.dim:
                parts.append("opacity:0.6")
            if self.italic:
                parts.append("font-style:italic")
            if self.underline:
                parts.append("text-decoration:underline")
            return ";".join(parts)

    style = Style()
    result = []

    # Tokenize: split on ESC sequences
    # We'll process char by char via regex
    ESC = r'\x1b'
    # Match any ESC sequence: CSI (ESC[...m etc), OSC, or bare ESC
    TOKEN_RE = re.compile(
        r'\x1b\[([0-9;:<=>?]*)([A-Za-z])'   # CSI sequence
        r'|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)'  # OSC sequence
        r'|\x1b[^[\]]'                           # other ESC + 1 char
    )

    def apply_sgr(params_str: str):
        if not params_str:
            params_str = "0"
        codes = params_str.split(";")
        i = 0
        while i < len(codes):
            c = codes[i].strip() or "0"
            n = int(c) if c.isdigit() else 0
            if n == 0:
                style.reset()
            elif n == 1:
                style.bold = True
            elif n == 2:
                style.dim = True
            elif n == 3:
                style.italic = True
            elif n == 4:
                style.underline = True
            elif n == 7:
                style.reverse = True
            elif n == 22:
                style.bold = False; style.dim = False
            elif n == 23:
                style.italic = False
            elif n == 24:
                style.underline = False
            elif n == 27:
                style.reverse = False
            elif n == 39:
                style.fg = None
            elif n == 49:
                style.bg = None
            elif n in STD_FG:
                style.fg = STD_FG[n]
            elif n in STD_BG:
                style.bg = STD_BG[n]
            elif n == 38 and i + 1 < len(codes):
                mode = codes[i+1].strip()
                if mode == "5" and i + 2 < len(codes):
                    idx = int(codes[i+2]) if codes[i+2].isdigit() else 0
                    style.fg = XTERM256[min(idx, 255)]
                    i += 2
                elif mode == "2" and i + 4 < len(codes):
                    r, g, b = codes[i+2], codes[i+3], codes[i+4]
                    style.fg = f"#{int(r):02x}{int(g):02x}{int(b):02x}"
                    i += 4
            elif n == 48 and i + 1 < len(codes):
                mode = codes[i+1].strip()
                if mode == "5" and i + 2 < len(codes):
                    idx = int(codes[i+2]) if codes[i+2].isdigit() else 0
                    style.bg = XTERM256[min(idx, 255)]
                    i += 2
                elif mode == "2" and i + 4 < len(codes):
                    r, g, b = codes[i+2], codes[i+3], codes[i+4]
                    style.bg = f"#{int(r):02x}{int(g):02x}{int(b):02x}"
                    i += 4
            i += 1

    pos = 0
    open_span = False
    pending_text = []

    def flush_text():
        nonlocal open_span
        if not pending_text:
            return
        t = html.escape("".join(pending_text), quote=False)
        pending_text.clear()
        css = style.css()
        if css:
            result.append(f'<span style="{css}">{t}</span>')
        else:
            result.append(t)

    for m in TOKEN_RE.finditer(text):
        # Flush literal text before this match
        literal = text[pos:m.start()]
        if literal:
            pending_text.append(literal)

        pos = m.end()

        seq = m.group(0)
        if seq.startswith('\x1b['):
            params = m.group(1)
            cmd = m.group(2)
            if cmd == 'm':
                flush_text()
                apply_sgr(params)
            # All other CSI commands (cursor movement etc) are silently ignored
        # OSC and other ESC sequences: silently ignored

    # Remaining literal text
    literal = text[pos:]
    if literal:
        pending_text.append(literal)
    flush_text()

    return "".join(result)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class AnsiData(BaseModel):
    timestamp: str = ""
    raw_ansi: str
    hostname: str = ""
    username: str = ""


class RawData(BaseModel):
    timestamp: str = ""
    raw_output: str = ""
    hostname: str = ""
    username: str = ""


class Dimensions(BaseModel):
    cols: int
    rows: int


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.post("/update_ansi")
async def update_ansi(data: AnsiData):
    """Primary endpoint: receive raw ANSI text, convert to HTML."""
    converted = ansi_to_html(data.raw_ansi)
    state["html_output"] = converted
    state["raw_ansi"] = data.raw_ansi
    state["timestamp"] = data.timestamp or datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    state["hostname"] = data.hostname
    state["username"] = data.username
    return {"status": "ok", "html_length": len(converted)}


@app.post("/update_raw")
async def update_raw(data: RawData):
    """Legacy endpoint: plain text (no ANSI). Render as-is."""
    state["html_output"] = html.escape(data.raw_output)
    state["raw_ansi"] = data.raw_output
    state["timestamp"] = data.timestamp or datetime.now().strftime("%a %b %d %H:%M:%S %Y")
    state["hostname"] = data.hostname
    state["username"] = data.username
    return {"status": "ok"}


@app.get("/data_html")
async def data_html():
    return JSONResponse({
        "html": state["html_output"],
        "timestamp": state["timestamp"],
        "hostname": state["hostname"],
        "username": state["username"],
    })


@app.get("/dimensions")
async def get_dimensions():
    """Client polls this to learn the desired terminal size."""
    return JSONResponse({"cols": state["cols"], "rows": state["rows"]})


@app.post("/set_dimensions")
async def set_dimensions(dim: Dimensions):
    """Browser posts its computed cols/rows whenever the window is resized."""
    cols = max(80, min(512, dim.cols))
    rows = max(24, min(200, dim.rows))
    state["cols"] = cols
    state["rows"] = rows
    return {"status": "ok", "cols": cols, "rows": rows}


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(PAGE_HTML)


# ---------------------------------------------------------------------------
# Frontend HTML - pixel-perfect nvitop terminal clone
# ---------------------------------------------------------------------------

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>nvitop — GPU Monitor</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  html, body {
    width: 100%;
    height: 100%;
    background: #000;
    /* Font is set dynamically by JS to fill the viewport */
    font-family: 'Courier New', 'Lucida Console', 'DejaVu Sans Mono', Consolas, monospace;
    color: #d3d7cf;
    overflow: hidden;
  }

  /* Status bar at very top */
  #statusbar {
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 20px;
    background: #111;
    border-bottom: 1px solid #333;
    display: flex;
    align-items: center;
    padding: 0 8px;
    font-size: 11px;
    color: #888;
    z-index: 10;
    gap: 16px;
    flex-shrink: 0;
  }
  #statusbar .dot {
    display: inline-block;
    width: 8px; height: 8px;
    border-radius: 50%;
    background: #555;
    transition: background 0.3s;
  }
  #statusbar .dot.live  { background: #4e9a06; }
  #statusbar .dot.stale { background: #c4a000; animation: blink-stale 1s infinite; }
  #statusbar .dot.dead  { background: #cc0000; }
  @keyframes blink-stale { 0%,100%{opacity:1} 50%{opacity:0.3} }

  #status-dims { margin-left: auto; font-size: 10px; color: #555; }

  /* Terminal viewport — fills the space below the status bar */
  #viewport {
    position: fixed;
    top: 20px; bottom: 0; left: 0; right: 0;
    overflow: hidden;           /* no scrollbar — content is sized to fit exactly */
    display: flex;
    align-items: flex-start;
  }

  /* The <pre> that holds nvitop output.
     font-size / line-height are set by JS each time the window is resized
     so the content fills the viewport without scrolling. */
  #terminal {
    white-space: pre;
    color: #d3d7cf;
    /* JS overwrites font-size and line-height */
    font-size: 13px;
    line-height: 1.0;
    -webkit-user-select: text;
    user-select: text;
    padding: 0 4px;
  }

  /* Placeholder while waiting for first data */
  #placeholder { color: #555; font-size: 13px; }
  #placeholder .spinner { display: inline-block; animation: spin 1.2s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>

<div id="statusbar">
  <span class="dot" id="dot"></span>
  <span id="status-text">Connecting…</span>
  <span id="status-host"></span>
  <span id="status-time"></span>
  <span id="status-dims"></span>
</div>

<div id="viewport">
  <pre id="terminal"><span id="placeholder"><span class="spinner">◐</span>  Waiting for nvitop data from HPC…

Make sure the client is running on the HPC:
  python3 ~/hpc-gpu-monitor/client/nvitop_ansi_client.py
</span></pre>
</div>

<script>
(function () {
  'use strict';

  const terminal    = document.getElementById('terminal');
  const viewport    = document.getElementById('viewport');
  const dot         = document.getElementById('dot');
  const statusText  = document.getElementById('status-text');
  const statusHost  = document.getElementById('status-host');
  const statusTime  = document.getElementById('status-time');
  const statusDims  = document.getElementById('status-dims');

  let lastUpdate = 0;
  let consecutiveErrors = 0;
  const STALE_MS = 5000;
  const DEAD_MS  = 15000;

  const SPINNER = ['◐','◓','◑','◒'];
  let spinIdx = 0;

  // ── Responsive sizing ───────────────────────────────────────────────────
  // We measure the monospace character size at a reference font-size, then
  // compute the font-size that makes exactly `cols` chars fit horizontally
  // and `rows` lines fit vertically in the viewport.

  // Hidden ruler to measure one character
  const ruler = document.createElement('pre');
  ruler.style.cssText = [
    'position:absolute', 'visibility:hidden', 'pointer-events:none',
    'top:-9999px', 'left:-9999px', 'margin:0', 'padding:0',
    'white-space:pre', 'font-family:inherit',
  ].join(';');
  ruler.textContent = 'M';
  document.body.appendChild(ruler);

  let pendingResize = null;
  let lastSentCols = 0, lastSentRows = 0;

  function measureCharAt(fontSize, lineHeight) {
    ruler.style.fontSize   = fontSize + 'px';
    ruler.style.lineHeight = lineHeight;
    const r = ruler.getBoundingClientRect();
    return { w: r.width, h: r.height };
  }

  function applySize(cols, rows) {
    // Viewport area available for the terminal
    const vw = window.innerWidth;
    const vh = window.innerHeight - 20;   // minus status bar

    // Binary-search the font-size that fits `cols` chars in `vw` pixels.
    // We target line-height = 1.0 so rows fit in vh as well.
    let lo = 6, hi = 32, fs = 13;
    for (let i = 0; i < 12; i++) {
      const mid = (lo + hi) / 2;
      const { w, h } = measureCharAt(mid, '1.0');
      const fitCols = Math.floor(vw / w);
      const fitRows = Math.floor(vh / h);
      if (fitCols >= cols && fitRows >= rows) {
        lo = mid;
        fs = mid;
      } else {
        hi = mid;
      }
    }

    terminal.style.fontSize   = fs.toFixed(2) + 'px';
    terminal.style.lineHeight = '1.0';

    // Report actual terminal dimensions that fit at this font size
    const { w, h } = measureCharAt(fs, '1.0');
    const actualCols = Math.floor(vw / w);
    const actualRows = Math.floor(vh / h);
    statusDims.textContent = actualCols + '×' + actualRows;
    return { cols: actualCols, rows: actualRows };
  }

  function sendDimensions(cols, rows) {
    if (cols === lastSentCols && rows === lastSentRows) return;
    lastSentCols = cols;
    lastSentRows = rows;
    fetch('/set_dimensions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cols, rows }),
    }).catch(() => {});
  }

  function onResize() {
    // Debounce: wait 200 ms after the last resize event before acting
    clearTimeout(pendingResize);
    pendingResize = setTimeout(() => {
      // Ask server what cols/rows it's currently using
      fetch('/dimensions', { cache: 'no-store' })
        .then(r => r.json())
        .then(d => {
          const { cols, rows } = applySize(d.cols, d.rows);
          sendDimensions(cols, rows);
        })
        .catch(() => {
          // Fallback: compute cols/rows ourselves from viewport
          const vw = window.innerWidth;
          const vh = window.innerHeight - 20;
          const { w, h } = measureCharAt(13, '1.0');
          const cols = Math.floor(vw / w);
          const rows = Math.floor(vh / h);
          applySize(cols, rows);
          sendDimensions(cols, rows);
        });
    }, 200);
  }

  window.addEventListener('resize', onResize);

  // Initial sizing: fetch current server dims and fit to window
  function initialSize() {
    fetch('/dimensions', { cache: 'no-store' })
      .then(r => r.json())
      .then(d => {
        const { cols, rows } = applySize(d.cols, d.rows);
        sendDimensions(cols, rows);
      })
      .catch(() => {
        const vw = window.innerWidth;
        const vh = window.innerHeight - 20;
        const { w, h } = measureCharAt(13, '1.0');
        sendDimensions(Math.floor(vw / w), Math.floor(vh / h));
      });
  }
  initialSize();

  // ── Data polling ──────────────────────────────────────────────────────────
  function setStatus(cls, text) {
    dot.className = 'dot ' + cls;
    statusText.textContent = text;
  }

  async function fetchData() {
    try {
      const resp = await fetch('/data_html', { cache: 'no-store' });
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const data = await resp.json();
      consecutiveErrors = 0;

      if (data.html && data.html.trim()) {
        terminal.innerHTML = data.html;
        lastUpdate = Date.now();
        statusHost.textContent = data.hostname ? '@ ' + data.hostname : '';
        statusTime.textContent = data.timestamp;
        setStatus('live', 'Live');
      } else {
        const age = Date.now() - lastUpdate;
        if (lastUpdate === 0) {
          spinIdx = (spinIdx + 1) % SPINNER.length;
          terminal.innerHTML =
            '<span style="color:#555"><span>' + SPINNER[spinIdx] + '</span>' +
            '  Waiting for nvitop data from HPC…\n\n' +
            'Make sure the client is running on the HPC:\n' +
            '  python3 ~/hpc-gpu-monitor/client/nvitop_ansi_client.py\n</span>';
          setStatus('', 'Waiting for data…');
        } else if (age > DEAD_MS) {
          setStatus('dead', 'No data for ' + Math.round(age/1000) + 's');
        } else if (age > STALE_MS) {
          setStatus('stale', 'Stale (' + Math.round(age/1000) + 's)');
        }
      }
    } catch (e) {
      consecutiveErrors++;
      setStatus(consecutiveErrors > 5 ? 'dead' : 'stale', 'Error: ' + e.message);
    }
  }

  fetchData();
  setInterval(fetchData, 1000);
})();
</script>

</body>
</html>
"""

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
