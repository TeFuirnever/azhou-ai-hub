import { TextDecoder } from 'node:util';

const schema = 'azhou-agent-skin.reference-official-theme.v1';
const contract = 'codex-dream-official-theme/6fc42df4';
let result = {schema, contract, status: 'blocked', reasons: ['validator_unavailable']};
try {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 1048576) throw new Error();
    chunks.push(chunk);
  }
  const source = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(Buffer.concat(chunks));
  const {validateOfficialTheme} = await import('../vendor/dream-theme-validator.mjs');
  try {
    validateOfficialTheme(JSON.parse(source));
    result = {schema, contract, status: 'passed', reasons: []};
  } catch {
    result = {schema, contract, status: 'blocked', reasons: ['theme_schema']};
  }
} catch {}
process.stdout.write(JSON.stringify(result) + '\n');
