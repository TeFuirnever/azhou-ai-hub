// R10 SOURCE-COPY EXPERIMENT ONLY. Never a production ZCode page adapter.
export function createR10Diagnostics(configuration) {
  const config = Object.freeze({ ...configuration });
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  if (!uuid.test(config.owner) || !uuid.test(config.token)
      || config.id !== 'agent-skin-zcode-probe-' + config.owner
      || !['mount', 'clean'].includes(config.action)
      || (config.action === 'mount' && config.token !== config.owner)
      || !Number.isFinite(config.timeOrigin) || config.timeOrigin <= 0
      || !/^[a-f0-9]{64}$/.test(config.generationSHA256)) throw new Error('invalid-r10-config');
  return Object.freeze({
    inspect(host) {
      try {
        const url = new URL(host.location.href);
        return { matched: host === host.top && url.protocol === 'file:' && url.hostname === ''
          && decodeURIComponent(url.pathname) === '/Applications/ZCode.app/Contents/Resources/app.asar/out/renderer/index.html'
          && host.performance.timeOrigin === config.timeOrigin };
      } catch { return { matched: false }; }
    },
    run(host) {
      const document = host.document;
      let style;
      try {
        style = document.getElementById(config.id);
        if (style && (style.dataset.documentGeneration !== config.generationSHA256
            || style.dataset.timeOrigin !== String(config.timeOrigin))) {
          return { state: 'document-generation-mismatch', count: document.querySelectorAll('#' + config.id).length };
        }
        if (config.action === 'mount') {
          if (style) return { state: style.dataset.owner === config.token ? 'reused' : 'collision',
            count: document.querySelectorAll('#' + config.id).length };
          style = document.createElement('style');
          style.id = config.id;
          style.dataset.owner = config.token;
          style.dataset.documentGeneration = config.generationSHA256;
          style.dataset.timeOrigin = String(config.timeOrigin);
          style.textContent = ':root{--agent-skin-zcode-probe:' + config.token + ';}';
          document.head.appendChild(style);
          return { state: 'mounted', readback: host.getComputedStyle(document.documentElement)
            .getPropertyValue('--agent-skin-zcode-probe').trim(), count: document.querySelectorAll('#' + config.id).length };
        }
        if (!style) return { state: 'already-disposed', count: 0 };
        if (style.dataset.owner !== config.token) return { state: 'ownership-mismatch',
          count: document.querySelectorAll('#' + config.id).length };
        style.remove();
        return { state: 'disposed', count: document.querySelectorAll('#' + config.id).length };
      } catch (error) {
        return { state: config.action === 'clean' ? 'cleanup-unknown' : 'mount-unknown',
          count: null, errorType: error?.name ?? 'unknown' };
      }
    },
  });
}
