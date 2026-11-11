// Progressive enhancements for forms and AI pages. Every page works without this script.
(function () {
    // 1. Loading state: <form data-loading="Working…"> disables its submit button after submit.
    document.querySelectorAll("form[data-loading]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            var btn = e.submitter || form.querySelector('button[type="submit"], button:not([type])');
            form.setAttribute("aria-busy", "true");
            if (!btn) return;
            // Let the browser read the button's name/value before it is disabled.
            setTimeout(function () {
                btn.disabled = true;
                btn.classList.add("is-loading");
                btn.dataset.label = btn.textContent;
                btn.textContent = form.dataset.loading;
            }, 0);
        });
    });
    // Restore buttons if the page comes back from the back/forward cache.
    window.addEventListener("pageshow", function (e) {
        if (!e.persisted) return;
        document.querySelectorAll("button.is-loading").forEach(function (btn) {
            btn.disabled = false;
            btn.classList.remove("is-loading");
            if (btn.dataset.label) btn.textContent = btn.dataset.label;
        });
    });

    // 2. Example question chips fill the question box instead of reloading the page.
    var question = document.getElementById("question");
    document.querySelectorAll("[data-fill-question]").forEach(function (chip) {
        chip.addEventListener("click", function (e) {
            if (!question) return;
            e.preventDefault();
            question.value = chip.dataset.fillQuestion;
            question.focus();
            updateCount();
        });
    });

    // 3. Character counter for the question box.
    var counter = document.querySelector('[data-char-count-for="question"]');
    function updateCount() {
        if (!counter || !question) return;
        var max = parseInt(question.getAttribute("maxlength"), 10);
        counter.textContent = question.value.length + " / " + max + " characters";
    }
    if (question && counter) { question.addEventListener("input", updateCount); if (question.value) updateCount(); }

    // 4. Appeal selection count on the AI review page.
    var boxes = document.querySelectorAll("[data-appeal-item]");
    var count = document.querySelector("[data-appeal-count]");
    function updateAppeal() {
        var n = Array.prototype.filter.call(boxes, function (b) { return b.checked; }).length;
        if (count) count.textContent = n + " charge" + (n === 1 ? "" : "s") + " selected";
        boxes.forEach(function (b) { b.closest(".charge-card").classList.toggle("is-selected", b.checked); });
    }
    if (boxes.length) { boxes.forEach(function (b) { b.addEventListener("change", updateAppeal); }); updateAppeal(); }

    // 5. Tables that scroll sideways must be reachable by keyboard (WCAG 2.1.1).
    function labelFor(wrap) {
        var cap = wrap.querySelector("caption");
        if (cap) return cap.textContent.trim();
        var el = wrap.previousElementSibling;
        while (el && !/^H[1-6]$/.test(el.tagName)) el = el.previousElementSibling;
        return el ? el.textContent.trim() : "Table";
    }
    function markScrollable() {
        document.querySelectorAll(".table-wrap").forEach(function (wrap) {
            if (wrap.scrollWidth > wrap.clientWidth + 1) {
                wrap.setAttribute("tabindex", "0");
                wrap.setAttribute("role", "region");
                wrap.setAttribute("aria-label", labelFor(wrap) + " (scrolls sideways)");
            } else if (wrap.getAttribute("role") === "region") {
                wrap.removeAttribute("tabindex"); wrap.removeAttribute("role"); wrap.removeAttribute("aria-label");
            }
        });
    }
    markScrollable();
    window.addEventListener("resize", function () { clearTimeout(markScrollable.t); markScrollable.t = setTimeout(markScrollable, 150); });

    // 6. Copy / download the appeal letter.
    function textOf(sel) { var el = document.querySelector(sel); return el ? el.textContent : ""; }
    document.querySelectorAll("[data-copy-target]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var done = function () { var t = btn.textContent; btn.textContent = "Copied"; setTimeout(function () { btn.textContent = t; }, 1500); };
            if (navigator.clipboard) navigator.clipboard.writeText(textOf(btn.dataset.copyTarget)).then(done, function () {});
        });
    });
    document.querySelectorAll("[data-download-target]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var blob = new Blob([textOf(btn.dataset.downloadTarget)], { type: "text/plain" });
            var a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = btn.dataset.filename || "appeal.txt";
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
        });
    });
})();
