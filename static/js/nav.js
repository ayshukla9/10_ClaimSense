// Mobile menu toggle and "More" dropdown dismissal. The nav works without this script.
(function () {
    var toggle = document.querySelector(".nav-toggle");
    var nav = document.getElementById("site-nav");
    if (toggle && nav) {
        toggle.addEventListener("click", function () {
            var open = nav.classList.toggle("is-open");
            toggle.setAttribute("aria-expanded", open ? "true" : "false");
        });
    }
    var more = document.querySelector(".nav-more");
    if (more) {
        document.addEventListener("click", function (e) {
            if (more.open && !more.contains(e.target)) more.open = false;
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape" && more.open) { more.open = false; more.querySelector("summary").focus(); }
        });
    }
})();
