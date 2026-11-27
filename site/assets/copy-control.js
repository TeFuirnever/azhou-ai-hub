const zh = document.documentElement.lang === "zh-CN";

for (const button of document.querySelectorAll("[data-copy]")) {
  if (!navigator.clipboard?.writeText) continue;
  const actions = button.parentElement;
  const status = actions.querySelector('[role="status"]');
  const message = status.querySelector("[data-copy-message]");
  const check = status.querySelector(".copy-check");
  actions.hidden = false;
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const tokens = getComputedStyle(document.documentElement);
  const easing = tokens.getPropertyValue("--motion-ease").trim();
  const feedback = parseFloat(tokens.getPropertyValue("--motion-feedback"));
  const change = parseFloat(tokens.getPropertyValue("--motion-change"));
  const animatable = () => !motion.matches && typeof status.animate === "function";
  const pendingText = zh ? "正在复制…" : "Copying…";
  const copiedText = zh ? "已复制" : "Copied";
  const failedText = zh ? "复制失败。请手动复制下方内容。" : "Copy failed. Select and copy the text below.";
  let attempt = 0;
  let reset;
  let pending;
  let fade;
  let retiring = false;
  function showStatus(text, state) {
    retiring = false;
    fade?.cancel();
    status.dataset.state = state;
    if (message.textContent !== text) message.textContent = text;
  }
  // Each confirmed attempt answers, including a repeat tap while "Copied" is showing.
  function acknowledge(confirmed) {
    if (!animatable()) return;
    retiring = false;
    fade?.cancel();
    message.animate([{ opacity: .65 }, { opacity: 1 }], { duration: feedback, easing });
    if (confirmed) {
      check.animate([{ opacity: 0, transform: "scale(.6)" }, { opacity: 1, transform: "none" }], { duration: feedback, easing });
    }
  }
  function retire() {
    if (!animatable()) {
      showStatus("", "");
      return;
    }
    retiring = true;
    fade = status.animate([{ opacity: 1 }, { opacity: 0 }], { duration: change, easing, fill: "forwards" });
    fade.finished.then(() => { if (retiring) showStatus("", ""); }, () => {});
  }
  motion.addEventListener("change", () => {
    if (motion.matches && retiring) showStatus("", "");
  });
  button.addEventListener("click", async () => {
    const current = ++attempt;
    clearTimeout(reset);
    clearTimeout(pending);
    fade?.cancel();
    if (status.dataset.state !== "pending") {
      pending = setTimeout(() => showStatus(pendingText, "pending"), 120);
    }
    const source = document.getElementById(button.dataset.copy);
    try {
      await navigator.clipboard.writeText(source.textContent);
      if (current !== attempt) return;
      showStatus(copiedText, "success");
      acknowledge(true);
      reset = setTimeout(retire, 3500);
    } catch {
      if (current !== attempt) return;
      showStatus(failedText, "error");
      acknowledge(false);
    } finally {
      if (current === attempt) clearTimeout(pending);
    }
  });
}
