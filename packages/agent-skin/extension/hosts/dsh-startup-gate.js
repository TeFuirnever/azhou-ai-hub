(() => {
  const host = globalThis;
  const document = host.document;
  const name = '__azhouDshStartupGate';
  const latchName = '__azhouDshStartupGateDocumentLatch';
  const owner = 'azhou-dsh-startup-gate-v1';
  if (!document || Object.getOwnPropertyDescriptor(document, latchName)) return;
  try {
    Object.defineProperty(document, latchName, {
      value: Object.freeze({ owner }), configurable: false, enumerable: false, writable: false,
    });
  } catch { return; }
  if (!document.documentElement || typeof document.createElement !== 'function'
      || document.hidden === true || document.visibilityState === 'hidden'
      || Object.getOwnPropertyDescriptor(host, name)) return;

  const opaqueAlpha = value => {
    const alpha = String(value ?? '').trim().toLowerCase();
    return alpha === '100%' || Number(alpha) === 1;
  };
  const opaqueColor = value => {
    const color = String(value ?? '').trim();
    if (!color || /^(?:transparent|currentcolor)$/i.test(color)
        || /\bvar\s*\(/i.test(color)) return false;
    const hex = /^#([\da-f]+)$/i.exec(color);
    if (hex) {
      if (hex[1].length === 4) return hex[1].at(-1).toLowerCase() === 'f';
      if (hex[1].length === 8) return hex[1].slice(-2).toLowerCase() === 'ff';
      return hex[1].length === 3 || hex[1].length === 6;
    }
    const functional = /^([a-z-]+)\((.*)\)$/i.exec(color);
    if (functional) {
      const name = functional[1].toLowerCase();
      if (!['rgb', 'rgba', 'hsl', 'hsla', 'color', 'lab', 'lch', 'oklab', 'oklch', 'hwb'].includes(name)) {
        return false;
      }
      const body = functional[2];
      const slash = body.lastIndexOf('/');
      if (slash >= 0) return opaqueAlpha(body.slice(slash + 1).replace(/\)\s*$/, '').trim());
      const components = body.split(',');
      return components.length !== 4 || opaqueAlpha(components[3]);
    }
    return true;
  };
  const safeColor = value => {
    try {
      const color = typeof value === 'string' ? value.trim() : '';
      return color && color.length < 100 && !/[;{}]/.test(color)
        && opaqueColor(color) && host.CSS?.supports?.('color', color) === true ? color : '';
    } catch {}
    return '';
  };
  const computedColorIsOpaque = value => {
    const color = String(value ?? '').trim();
    const rgb = /^rgba?\((.*)\)$/i.exec(color);
    if (rgb) {
      const channels = rgb[1].split(/[\s,/]+/).filter(Boolean);
      return channels.length === 3 || (channels.length === 4 && opaqueAlpha(channels[3]));
    }
    return safeColor(color) !== '';
  };
  const coverBackground = () => {
    const body = document.body;
    try {
      const surface = host.getComputedStyle?.(body)?.getPropertyValue?.('--dsw-alias-bg-base');
      const color = safeColor(surface);
      if (color) return color;
    } catch {}
    try {
      if (typeof body?.hasAttribute === 'function') {
        return body.hasAttribute('data-ds-dark-theme') ? '#10121c' : '#f8f8f8';
      }
      const style = host.getComputedStyle?.(body ?? document.documentElement);
      const scheme = String(style?.colorScheme ?? style?.getPropertyValue?.('color-scheme') ?? '')
        .trim().toLowerCase().split(/\s+/);
      if (scheme.includes('dark') && !scheme.includes('light')) return '#10121c';
      if (scheme.includes('light') && !scheme.includes('dark')) return '#f8f8f8';
      const preferredDark = host.matchMedia?.('(prefers-color-scheme: dark)')?.matches;
      if (typeof preferredDark === 'boolean') return preferredDark ? '#10121c' : '#f8f8f8';
    } catch {}
    return '#10121c';
  };

  let phase = 'waiting';
  let timer = null;
  let frame = null;
  let element = null;
  const expirationListeners = new Set();
  const remove = () => {
    if (timer !== null) host.clearTimeout(timer);
    timer = null;
    if (frame !== null) {
      if (typeof host.cancelAnimationFrame === 'function') host.cancelAnimationFrame(frame);
      else host.clearTimeout(frame);
    }
    frame = null;
    host.removeEventListener?.('pagehide', expire);
    try { element?.remove(); } catch {}
    element = null;
  };
  const expire = () => {
    if (phase === 'released' || phase === 'expired') return false;
    phase = 'expired';
    remove();
    const listeners = [...expirationListeners];
    expirationListeners.clear();
    for (const listener of listeners) {
      try { listener(); } catch {}
    }
    return true;
  };
  const arm = milliseconds => {
    if (timer !== null) host.clearTimeout(timer);
    timer = host.setTimeout(expire, milliseconds);
  };
  const gate = Object.freeze({
    owner,
    claim() {
      if (phase !== 'waiting') return false;
      phase = 'claimed';
      arm(12_000);
      return true;
    },
    ready() {
      if (phase !== 'claimed') return false;
      phase = 'revealing';
      arm(250);
      const reveal = () => {
        frame = null;
        if (phase !== 'revealing') return;
        phase = 'released';
        expirationListeners.clear();
        remove();
      };
      if (typeof host.requestAnimationFrame === 'function') frame = host.requestAnimationFrame(reveal);
      else frame = host.setTimeout(reveal, 0);
      return true;
    },
    release: expire,
    onExpire(listener) {
      if (typeof listener !== 'function') return () => false;
      if (phase === 'expired') {
        try { listener(); } catch {}
        return () => false;
      }
      if (phase === 'released') return () => false;
      expirationListeners.add(listener);
      let active = true;
      return () => {
        if (!active) return false;
        active = false;
        return expirationListeners.delete(listener);
      };
    },
    status: () => phase,
  });

  try {
    element = document.createElement('div');
    element.setAttribute('data-azhou-dsh-startup-gate', '');
    element.setAttribute('aria-hidden', 'true');
    Object.assign(element.style, {
      position: 'fixed', inset: '0', width: '100vw', height: '100vh', zIndex: '2147483647',
      backgroundColor: coverBackground(), pointerEvents: 'auto',
    });
    document.documentElement.appendChild(element);
    const rect = element.getBoundingClientRect();
    const style = host.getComputedStyle(element);
    const opacity = Number.parseFloat(style.opacity);
    const viewportWidth = Number(host.innerWidth);
    const viewportHeight = Number(host.innerHeight);
    const hitTest = document.elementFromPoint;
    const hitPoints = [[1, 1], [viewportWidth / 2, viewportHeight / 2],
      [viewportWidth - 1, 1], [1, viewportHeight - 1], [viewportWidth - 1, viewportHeight - 1]];
    if (style.position !== 'fixed' || style.display === 'none' || style.visibility !== 'visible'
        || style.pointerEvents !== 'auto' || Number(style.zIndex) < 2_147_483_647
        || opacity !== 1 || !computedColorIsOpaque(style.backgroundColor)
        || !Number.isFinite(viewportWidth) || viewportWidth <= 0
        || !Number.isFinite(viewportHeight) || viewportHeight <= 0
        || !Number.isFinite(rect.left) || !Number.isFinite(rect.top)
        || !Number.isFinite(rect.right) || !Number.isFinite(rect.bottom)
        || rect.left > 0 || rect.top > 0 || rect.right < viewportWidth || rect.bottom < viewportHeight
        || typeof hitTest !== 'function'
        || hitPoints.some(([x, y]) => {
          const top = hitTest.call(document, x, y);
          return top !== element && !element.contains?.(top);
        })) {
      expire();
      return;
    }
    Object.defineProperty(host, name, { value: gate, configurable: false, enumerable: false, writable: false });
    host.addEventListener?.('pagehide', expire, { once: true });
    arm(8_000);
  } catch {
    expire();
  }
})();
