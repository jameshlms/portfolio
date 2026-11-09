// Renders Cloudflare Turnstile into every empty .turnstile slot: on load, and
// again after htmx swaps the contact form back in (each token is single-use,
// so a re-rendered form needs a fresh widget).
function renderTurnstile() {
    for (const slot of document.querySelectorAll(".turnstile:not([data-rendered])")) {
        slot.dataset.rendered = "";
        window.turnstile.render(slot, { sitekey: slot.dataset.sitekey, theme: "light" });
    }
}

window.onTurnstileLoad = () => {
    renderTurnstile();
    document.addEventListener("htmx:after:swap", renderTurnstile);
};
