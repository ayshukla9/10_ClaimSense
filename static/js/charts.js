// Embeds the existing Vega-Lite spec files with the ClaimSense look: system font, muted axes,
// responsive width. The spec files themselves stay unchanged (the /vega-lite/*.png routes use them too).
window.ClaimSenseCharts = (function () {
    var css = getComputedStyle(document.documentElement);
    function token(name, fallback) { return (css.getPropertyValue(name) || fallback).trim(); }
    var font = token("--font", "system-ui, sans-serif");
    var config = {
        font: font,
        background: null,
        view: { stroke: null },
        axis: { labelColor: token("--muted", "#64748b"), titleColor: token("--muted", "#64748b"), labelFontSize: 11,
                titleFontSize: 11, titleFontWeight: 600, gridColor: token("--border", "#e5e7eb"), domainColor: token("--border-strong", "#cbd5e1"), tickColor: token("--border-strong", "#cbd5e1") },
        legend: { labelColor: token("--ink", "#0f172a"), titleColor: token("--muted", "#64748b"), labelFontSize: 12, titleFontSize: 11, orient: "bottom" },
        title: { fontSize: 0 },  // the card shows its own title
        bar: { cornerRadiusTopLeft: 4, cornerRadiusTopRight: 4 },
        line: { strokeWidth: 2.5 },
        point: { size: 50, filled: true }
    };
    // Colors from the design tokens, replacing the spec's original gold, which has low contrast on white.
    var colors = {
        "In Network": token("--brand", "#13294b"), "Out of Network": token("--danger", "#b91c1c"),
        "Charged": token("--brand", "#13294b"), "Covered by plan": token("--ok", "#15803d"), "Patient owes": token("--warn", "#b45309")
    };
    function embed(target, specUrl) {
        var el = document.querySelector(target);
        if (!el || !window.vegaEmbed) return;
        fetch(specUrl).then(function (r) { return r.json(); }).then(function (spec) {
            spec.width = "container";
            spec.autosize = { type: "fit", contains: "padding" };
            var narrow = el.clientWidth < 480;
            if (narrow) {
                // phones: steeper, shorter axis labels and a wrapped legend so nothing is clipped
                spec.padding = { left: 28, right: 12, top: 5, bottom: 5 };
                var x = spec.encoding && spec.encoding.x;
                if (x && x.type === "nominal") x.axis = Object.assign({}, x.axis, { labelAngle: -40, labelLimit: 110 });
            }
            var color = spec.encoding && spec.encoding.color;
            if (color && color.scale && color.scale.domain) {
                color.scale.range = color.scale.domain.map(function (d, i) { return colors[d] || color.scale.range[i]; });
            }
            var cfg = Object.assign({}, config, { legend: Object.assign({}, config.legend, narrow ? { columns: 1 } : {}) });
            return vegaEmbed(target, spec, { actions: false, config: cfg, renderer: "svg" });
        }).catch(function (err) {
            el.innerHTML = '<div class="empty-state">Chart failed to load. ' + (err && err.message ? err.message : "") + "</div>";
        });
    }
    return { embed: embed };
})();
