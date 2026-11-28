(() => {
  const grid = document.querySelector('.cursor-demo-grid');
  const toggle = document.querySelector('[data-cursor-pendant-toggle]');
  const pendant = document.querySelector('[data-cursor-pendant]');
  const swing = pendant?.querySelector('.cursor-pendant-swing');
  if (!grid || !toggle || !pendant || !swing) return;

  const followTransition = 'transform 40ms ease-out';
  const maxSwing = 20;
  const settleSpeed = 1.2;
  const springLimit = 25;
  const maxStep = 0.032;
  const availability = [
    matchMedia('(hover: hover) and (pointer: fine)'),
    matchMedia('(prefers-reduced-motion: no-preference)'),
    matchMedia('(forced-colors: none)'),
  ];
  let enabled = false;
  let previousX = null;
  let angle = 0;
  let velocity = 0;
  let frame = 0;
  let lastTime = 0;

  function drawAngle() {
    swing.style.transform = `rotate(${angle * maxSwing / springLimit}deg)`;
  }

  function hide() {
    if (pendant.hidden) return;
    pendant.hidden = true;
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    previousX = null;
    angle = 0;
    velocity = 0;
    lastTime = 0;
    drawAngle();
  }

  function syncAvailability() {
    enabled = false;
    toggle.setAttribute('aria-pressed', 'false');
    toggle.hidden = !availability.every(query => query.matches);
    hide();
  }

  function animate(time) {
    const elapsed = lastTime ? Math.min((time - lastTime) / 1000, maxStep) : 0;
    lastTime = time;
    const scaledTime = elapsed * settleSpeed;
    const steps = Math.max(1, Math.ceil(scaledTime / maxStep));
    const step = scaledTime / steps;
    for (let index = 0; index < steps; index++) {
      velocity = (velocity - angle * 55 * step) * Math.exp(-9 * step);
      angle = Math.max(-springLimit, Math.min(springLimit, angle + velocity * step));
    }
    if (Math.abs(angle) < 0.08 && Math.abs(velocity) < 0.08) {
      angle = 0;
      velocity = 0;
      lastTime = 0;
      frame = 0;
    } else {
      frame = requestAnimationFrame(animate);
    }
    drawAngle();
  }

  function follow(event) {
    if (!enabled || event.pointerType !== 'mouse') return;
    const bounds = grid.getBoundingClientRect();
    const x = event.clientX - bounds.left - grid.clientLeft;
    const y = event.clientY - bounds.top - grid.clientTop;
    const gridWidth = grid.clientWidth;
    const gridHeight = grid.clientHeight;
    const arriving = pendant.hidden;
    pendant.hidden = false;
    const width = pendant.offsetWidth;
    const height = pendant.offsetHeight;
    const offsetX = 22;
    const offsetY = 18;
    const left = x + offsetX + width + 18 <= gridWidth ? x + offsetX : x - offsetX - width;
    const top = y + offsetY + height + 4 <= gridHeight ? y + offsetY : y - offsetY - height;
    const fittedX = Math.max(0, Math.min(gridWidth - width, left));
    const fittedY = Math.max(0, Math.min(gridHeight - height, top));
    pendant.style.transition = arriving ? 'none' : followTransition;
    pendant.style.transform = `translate(${fittedX}px, ${fittedY}px)`;
    if (previousX !== null) {
      velocity = Math.max(-180, Math.min(180, velocity - (x - previousX) * 3));
      if (!frame && Math.abs(velocity) > 0.08) frame = requestAnimationFrame(animate);
    }
    previousX = x;
  }

  toggle.addEventListener('click', () => {
    enabled = !enabled;
    toggle.setAttribute('aria-pressed', String(enabled));
    hide();
  });
  grid.addEventListener('pointerenter', follow);
  grid.addEventListener('pointermove', follow);
  grid.addEventListener('pointerleave', hide);
  grid.addEventListener('pointercancel', hide);
  window.addEventListener('scroll', hide, { passive: true, capture: true });
  window.addEventListener('blur', hide);
  window.addEventListener('resize', hide);
  for (const query of availability) query.addEventListener('change', syncAvailability);
  syncAvailability();
})();
