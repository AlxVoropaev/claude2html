(function () {
  var DEFAULT = "github-light";
  var VALID = ["github-light", "github-dark", "monokai-pro-light", "monokai-pro-dark"];
  try {
    var stored = localStorage.getItem("theme");
    if (stored && VALID.indexOf(stored) !== -1) {
      document.documentElement.setAttribute("data-theme", stored);
    } else {
      document.documentElement.setAttribute("data-theme", DEFAULT);
    }
  } catch (e) {
    document.documentElement.setAttribute("data-theme", DEFAULT);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var sel = document.getElementById("theme-select");
    if (!sel) return;
    sel.value = document.documentElement.getAttribute("data-theme") || DEFAULT;
    sel.addEventListener("change", function () {
      document.documentElement.setAttribute("data-theme", sel.value);
      try { localStorage.setItem("theme", sel.value); } catch (e) {}
    });
  });
})();
