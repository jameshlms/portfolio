// Replaces the page's native scrollbar with an overlay one (OverlayScrollbars)
// that sits on top of the content and only shows while the page is scrolling.
// Scrolling itself stays native, so wheel, keyboard, touch and anchors behave
// as normal. The theme lives in style.css under .os-theme-site.
const { OverlayScrollbars } = OverlayScrollbarsGlobal;

OverlayScrollbars(document.body, {
    scrollbars: {
        theme: "os-theme-site",
        autoHide: "scroll",
        autoHideDelay: 800,
        clickScroll: "instant",
    },
});
