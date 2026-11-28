(() => {
  const grid = document.querySelector('.cursor-demo-grid');
  const toggle = document.querySelector('[data-cursor-pendant-toggle]');
  const pendant = document.querySelector('[data-cursor-pendant]');
  if (!grid || !toggle || !pendant) return;

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

  function hide() {
    if (pendant.hidden) return;
    pendant.hidden = true;
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    previousX = null;
    angle = 0;
    velocity = 0;
    lastTime = 0;
    pendant.style.setProperty('--pendant-angle', '0deg');
  }

  function syncAvailability() {
    enabled = false;
    toggle.setAttribute('aria-pressed', 'false');
    toggle.hidden = !availability.every(query => query.matches);
    hide();
  }

  function animate(time) {
    const elapsed = lastTime ? Math.min((time - lastTime) / 1000, 0.032) : 0;
    lastTime = time;
    velocity += -angle * 55 * elapsed;
    velocity *= Math.exp(-9 * elapsed);
    angle = Math.max(-25, Math.min(25, angle + velocity * elapsed));
    pendant.style.setProperty('--pendant-angle', `${angle}deg`);
    if (Math.abs(angle) < 0.08 && Math.abs(velocity) < 0.08) {
      angle = 0;
      velocity = 0;
      lastTime = 0;
      frame = 0;
      pendant.style.setProperty('--pendant-angle', '0deg');
    } else {
      frame = requestAnimationFrame(animate);
    }
  }

  function follow(event) {
    if (!enabled || event.pointerType !== 'mouse') return;
    const bounds = grid.getBoundingClientRect();
    const x = event.clientX - bounds.left - grid.clientLeft;
    const y = event.clientY - bounds.top - grid.clientTop;
    const gridWidth = grid.clientWidth;
    const gridHeight = grid.clientHeight;
    pendant.hidden = false;
    const width = pendant.offsetWidth;
    const height = pendant.offsetHeight;
    const offsetX = 22;
    const offsetY = 18;
    const left = x + offsetX + width + 18 <= gridWidth ? x + offsetX : x - offsetX - width;
    const top = y + offsetY + height + 4 <= gridHeight ? y + offsetY : y - offsetY - height;
    const fittedX = Math.max(0, Math.min(gridWidth - width, left));
    const fittedY = Math.max(0, Math.min(gridHeight - height, top));
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
