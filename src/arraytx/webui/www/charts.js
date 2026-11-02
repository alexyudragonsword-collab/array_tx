/* Small SVG charts for the array_tx page: lines (with an optional pattern
 * panel on top), scatter, and a cell grid.  No library: the page must run
 * inside a WebView with no network.  Everything is drawn in a viewBox and
 * scales with its box; a tooltip element (#tip) follows the nearest x. */
"use strict";
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, text) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] !== undefined && attrs[k] !== null) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const nice = (lo, hi, n) => {           // tick positions
    const span = hi - lo; if (!(span > 0)) return [lo];
    const raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * p).find(s => s >= raw) || p * 10;
    const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  };
  const fmt = v => (Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));
  const tip = document.getElementById("tip");
  const showTip = (x, y, text) => { if (!tip) return; tip.textContent = text; tip.hidden = false;
    tip.style.left = (x + 12) + "px"; tip.style.top = (y + 12) + "px"; };
  const hideTip = () => { if (tip) tip.hidden = true; };

  /* opts: {series:[{x,y,color,dash,width,label}], xlab, ylab, xlim, ylim, bands:[{x0,x1,fill}],
   *        vlines:[{x,color,label,dash}], nulls:[{x0,x1}], top:{y,ylab,ylim,color} (pattern panel),
   *        W,H, legend:true, tooltip:(i,s)=>text} */
  function lines(box, o) {
    box.innerHTML = "";
    const W = o.W || 560, H = o.H || 260, topH = o.top ? 62 : 0;
    const L = 42, R = 10, T = 10 + topH, B = 28;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    const xs = o.series.flatMap(s => s.x), ys = o.series.flatMap(s => s.y.filter(v => v !== null && isFinite(v)));
    const x0 = o.xlim ? o.xlim[0] : Math.min(...xs), x1 = o.xlim ? o.xlim[1] : Math.max(...xs);
    let y0 = o.ylim ? o.ylim[0] : Math.min(...ys), y1 = o.ylim ? o.ylim[1] : Math.max(...ys);
    if (!(y1 > y0)) { y0 -= 1; y1 += 1; }
    const X = x => L + (x - x0) / (x1 - x0) * (W - L - R), Y = y => T + (y1 - y) / (y1 - y0) * (H - T - B);
    (o.bands || []).forEach(b => svg.appendChild(el("rect", { x: X(b.x0), y: T, width: Math.max(0, X(b.x1) - X(b.x0)), height: H - T - B, fill: b.fill })));
    (o.nulls || []).forEach(n => svg.appendChild(el("rect", { x: X(n.x0), y: T, width: Math.max(0.5, X(n.x1) - X(n.x0)), height: H - T - B, fill: "#ececea" })));
    nice(y0, y1, 5).forEach(v => { svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), stroke: "#e3e2dd" }));
      svg.appendChild(el("text", { x: L - 4, y: Y(v) + 3, "text-anchor": "end", class: "tk" }, fmt(v))); });
    nice(x0, x1, 7).forEach(v => { if (v < x0 - 1e-9 || v > x1 + 1e-9) return;
      svg.appendChild(el("text", { x: X(v), y: H - B + 13, "text-anchor": "middle", class: "tk" }, fmt(v))); });
    svg.appendChild(el("text", { x: (L + W - R) / 2, y: H - 2, "text-anchor": "middle", class: "al" }, o.xlab || ""));
    svg.appendChild(el("text", { transform: `translate(11,${(T + H - B) / 2}) rotate(-90)`, "text-anchor": "middle", class: "al" }, o.ylab || ""));
    if (o.top) {                                       // the pattern panel, same x axis
      const t = o.top, ty0 = t.ylim[0], ty1 = t.ylim[1], TY = y => 8 + (ty1 - y) / (ty1 - ty0) * (topH - 14);
      svg.appendChild(el("text", { x: L - 4, y: TY(ty1) + 3, "text-anchor": "end", class: "tk" }, fmt(ty1)));
      svg.appendChild(el("text", { x: L - 4, y: TY(ty0) + 3, "text-anchor": "end", class: "tk" }, fmt(ty0)));
      svg.appendChild(el("line", { x1: L, y1: TY(ty0), x2: W - R, y2: TY(ty0), stroke: "#e3e2dd" }));
      let d = ""; t.x.forEach((x, i) => { const y = Math.max(ty0, t.y[i]); d += (d ? " L" : "M") + X(x).toFixed(1) + "," + TY(y).toFixed(1); });
      svg.appendChild(el("path", { d, fill: "none", stroke: t.color || "#8a8a85", "stroke-width": 1.2 }));
      svg.appendChild(el("text", { x: W - R - 2, y: 16, "text-anchor": "end", class: "tk" }, t.ylab || ""));
    }
    (o.vlines || []).forEach(v => { svg.appendChild(el("line", { x1: X(v.x), y1: T, x2: X(v.x), y2: H - B, stroke: v.color || "#8a8a85", "stroke-dasharray": v.dash || "4 3" }));
      if (v.label) svg.appendChild(el("text", { x: X(v.x) + 3, y: T + 11, class: "tk", fill: v.color || "#8a8a85" }, v.label)); });
    o.series.forEach(s => { let d = "", pen = false;
      s.x.forEach((x, i) => { const y = s.y[i]; if (y === null || y === undefined || !isFinite(y)) { pen = false; return; }
        d += (pen ? " L" : " M") + X(x).toFixed(1) + "," + Y(Math.max(y0, Math.min(y1, y))).toFixed(1); pen = true; });
      svg.appendChild(el("path", { d, fill: "none", stroke: s.color, "stroke-width": s.width || 1.6, "stroke-dasharray": s.dash || null })); });
    if (o.legend !== false) { let lx = L + 6; o.series.forEach(s => { if (!s.label) return;
      svg.appendChild(el("line", { x1: lx, y1: T + 8, x2: lx + 14, y2: T + 8, stroke: s.color, "stroke-width": 2, "stroke-dasharray": s.dash || null }));
      const t = el("text", { x: lx + 17, y: T + 11, class: "lg", fill: s.color }, s.label); svg.appendChild(t); lx += 24 + s.label.length * 6.2; }); }
    const cur = el("line", { x1: 0, y1: T, x2: 0, y2: H - B, stroke: "#555", "stroke-dasharray": "2 2", visibility: "hidden" }); svg.appendChild(cur);
    svg.addEventListener("mousemove", ev => { const r = svg.getBoundingClientRect(); const px = (ev.clientX - r.left) / r.width * W;
      const x = x0 + (px - L) / (W - L - R) * (x1 - x0); if (x < x0 || x > x1) { hideTip(); cur.setAttribute("visibility", "hidden"); return; }
      const s0 = o.series[0]; let best = 0, bd = Infinity; s0.x.forEach((v, i) => { const d = Math.abs(v - x); if (d < bd) { bd = d; best = i; } });
      cur.setAttribute("x1", X(s0.x[best])); cur.setAttribute("x2", X(s0.x[best])); cur.setAttribute("visibility", "visible");
      const text = o.tooltip ? o.tooltip(best) : o.series.map(s => `${s.label || ""} ${s.y[best] === null ? "—" : fmt(s.y[best])}`).join("\n");
      showTip(ev.clientX, ev.clientY, `${o.xlab ? o.xlab.split(" ")[0] : "x"} = ${fmt(s0.x[best])}\n${text}`); });
    svg.addEventListener("mouseleave", () => { hideTip(); cur.setAttribute("visibility", "hidden"); });
    box.appendChild(svg);
  }

  function scatter(box, o) {
    box.innerHTML = "";
    const W = o.W || 260, H = o.H || 260, L = 28, R = 8, T = 8, B = 24;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
    const m = o.lim || Math.max(...o.x.map(Math.abs), ...o.y.map(Math.abs)) * 1.05;
    const X = x => L + (x + m) / (2 * m) * (W - L - R), Y = y => T + (m - y) / (2 * m) * (H - T - B);
    nice(-m, m, 6).forEach(v => { svg.appendChild(el("line", { x1: X(v), y1: T, x2: X(v), y2: H - B, stroke: "#eeeeea" }));
      svg.appendChild(el("line", { x1: L, y1: Y(v), x2: W - R, y2: Y(v), stroke: "#eeeeea" })); });
    const g = el("g", { fill: o.color || "#1baf7a", "fill-opacity": 0.55 });
    o.x.forEach((x, i) => g.appendChild(el("circle", { cx: X(x).toFixed(1), cy: Y(o.y[i]).toFixed(1), r: 1.3 })));
    svg.appendChild(g);
    svg.appendChild(el("text", { x: (L + W - R) / 2, y: H - 4, "text-anchor": "middle", class: "al" }, o.xlab || "I"));
    svg.appendChild(el("text", { transform: `translate(10,${(T + H - B) / 2}) rotate(-90)`, "text-anchor": "middle", class: "al" }, o.ylab || "Q"));
    if (o.note) svg.appendChild(el("text", { x: W - R - 2, y: T + 10, "text-anchor": "end", class: "tk" }, o.note));
    box.appendChild(svg);
  }

  /* o: {rows:[label], cols:[label], cells:[[{v,text,sub,sel,base,bad}]], onclick(r,c), lo, hi} lower = better, deeper = better */
  function grid(box, o) {
    box.innerHTML = "";
    const cw = 92, ch = 44, L = 46, T = 20, W = L + o.cols.length * cw + 8, H = T + o.rows.length * ch + 8;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H });
    svg.style.width = "auto"; svg.style.maxWidth = "100%";             // a 1x1 grid must not fill the box
    const span = o.hi - o.lo;
    o.cols.forEach((c, j) => svg.appendChild(el("text", { x: L + j * cw + cw / 2, y: 13, "text-anchor": "middle", class: "al" }, c)));
    o.rows.forEach((r, i) => { svg.appendChild(el("text", { x: L - 6, y: T + i * ch + ch / 2 + 3, "text-anchor": "end", class: "al" }, r));
      o.cols.forEach((c, j) => { const cell = o.cells[i][j]; const x = L + j * cw + 2, y = T + i * ch + 2;
        const g = el("g", { cursor: cell ? "pointer" : "default" });
        let fill = "#f6f6f3"; if (cell && cell.v !== null && cell.v !== undefined) { const t = span > 0 ? Math.max(0, Math.min(1, (o.hi - cell.v) / span)) : 0.5; fill = `rgba(42,120,214,${(0.12 + 0.55 * t).toFixed(2)})`; }
        g.appendChild(el("rect", { x, y, width: cw - 4, height: ch - 4, rx: 5, fill, stroke: cell && cell.sel ? "#1d1d1b" : (cell && cell.base ? "#2a78d6" : "none"), "stroke-width": 1.5, "stroke-dasharray": cell && cell.base && !cell.sel ? "3 2" : null }));
        g.appendChild(el("text", { x: x + (cw - 4) / 2, y: y + 18, "text-anchor": "middle", class: "al", "font-weight": 600 }, cell ? cell.text : "—"));
        if (cell && cell.sub) g.appendChild(el("text", { x: x + (cw - 4) / 2, y: y + 31, "text-anchor": "middle", class: "tk", fill: cell.bad ? "#eb6834" : "#555" }, cell.sub));
        if (cell && o.onclick) g.addEventListener("click", () => o.onclick(i, j));
        svg.appendChild(g); }); });
    box.appendChild(svg);
  }
  return { lines, scatter, grid, fmt };
})();
