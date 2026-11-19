import { TextDecoder } from 'node:util';

const schema = 'azhou-agent-skin.reference-safe-css.v1';
const contract = 'dreamskin-safe-css/1';
let result = { schema, contract, status: 'blocked', reasons: ['validator_unavailable'] };
try {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 262144) throw new Error();
    chunks.push(chunk);
  }
  let source;
  try {
    source = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(Buffer.concat(chunks));
  } catch {
    result = { schema, contract, status: 'blocked', reasons: ['css_utf8_invalid'] };
  }
  if (source !== undefined) {
    const { validateSafeCss, SafeCssValidationError, SAFE_CSS_CONTRACT } =
      await import('../vendor/dream-safe-css-validator.mjs');
    if (SAFE_CSS_CONTRACT.contract !== contract) throw new Error();
    try {
      validateSafeCss(source);
      result = { schema, contract, status: 'passed', reasons: [] };
    } catch (error) {
      if (!(error instanceof SafeCssValidationError)) throw error;
      result = { schema, contract, status: 'blocked', reasons: ['safe_css_invalid'] };
    }
  }
} catch {
  result = { schema, contract, status: 'blocked', reasons: ['validator_unavailable'] };
}
process.stdout.write(JSON.stringify(result) + '\n');
