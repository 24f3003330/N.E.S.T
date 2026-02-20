/* ═══════════════════════════════════════════
   N.E.S.T – Base JavaScript
   ═══════════════════════════════════════════ */

document.addEventListener("DOMContentLoaded", () => {
    console.log("N.E.S.T loaded ✓");

    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll(".alert-dismissible").forEach((alert) => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            bsAlert.close();
        }, 5000);
    });
});
