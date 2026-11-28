const zh = document.documentElement.lang === "zh-CN";

for (const button of document.querySelectorAll(".copy-actions [data-copy]")) {
  const source = document.getElementById(button.dataset.copy);
  const fallback = source?.closest("[data-copy-fallback]");
  if (!navigator.clipboard?.writeText) {
    fallback?.setAttribute("open", "");
    continue;
  }
  const actions = button.parentElement;
  const status = (button.closest(".term-bar") ?? actions).querySelector('[role="status"]');
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
  let acknowledgment;
  let retiring = false;
  function showStatus(text, state) {
    retiring = false;
    fade?.cancel();
    acknowledgment?.cancel();
    status.dataset.state = state;
    if (message.textContent !== text) message.textContent = text;
  }
  function acknowledge(firstConfirmation) {
    if (!animatable() || !firstConfirmation) return;
    acknowledgment = check.animate([{ opacity: .7 }, { opacity: 1 }], { duration: feedback, easing });
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
    if (!motion.matches) return;
    acknowledgment?.cancel();
    if (retiring) showStatus("", "");
  });
  button.addEventListener("click", async () => {
    const current = ++attempt;
    clearTimeout(reset);
    clearTimeout(pending);
    fade?.cancel();
    if (status.dataset.state !== "pending") {
      pending = setTimeout(() => showStatus(pendingText, "pending"), 120);
    }
    try {
      await navigator.clipboard.writeText(source.textContent);
      if (current !== attempt) return;
      const firstConfirmation = status.dataset.state !== "success";
      showStatus(copiedText, "success");
      acknowledge(firstConfirmation);
      reset = setTimeout(retire, 3500);
    } catch {
      if (current !== attempt) return;
      fallback?.setAttribute("open", "");
      showStatus(failedText, "error");
    } finally {
      if (current === attempt) clearTimeout(pending);
    }
  });
}
