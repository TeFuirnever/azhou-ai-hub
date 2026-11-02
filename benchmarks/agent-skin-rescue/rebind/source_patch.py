"""Patch only new evidence source copies. Existing C0/verifier semantics remain."""
import json
MODULE='extension/r10-diagnostics.mjs'
def one(source, before, after):
    if source.count(before)!=1: raise ValueError('source boundary drift: '+before[:80])
    return source.replace(before,after,1)
def patch_sources(original, diagnostic_source):
    result=dict(original)
    builder=result['tools/build-startup.py']
    builder=one(builder,'        controller = _module_function(\n','''        r10_diagnostics_source = _module_function(
            (root / 'extension/r10-diagnostics.mjs').read_text(encoding='utf-8'),
            'export function createR10Diagnostics(', 'function createR10Diagnostics(', 'R10 diagnostics',
        ).strip()
        controller = _module_function(
''')
    builder=one(builder,'        image_metadata,\n','        image_metadata,\n        r10_diagnostics_source,\n')
    builder=one(builder,'def _build_script(root: Path, assets: dict, wallpaper_css: str, artifacts) -> str:',
      'def _build_script(root: Path, assets: dict, wallpaper_css: str, artifacts, *, r10_diagnostics: bool = False) -> str:')
    builder=one(builder,"    if len(payload.encode('utf-8')) >= MAX_STARTUP_BYTES:\n",
      "    if r10_diagnostics:\n        anchor = '    installStartup,\\n'\n        if payload.count(anchor) != 1: raise RuntimeError('R10 bootstrap boundary drift')\n        payload = payload.replace(anchor, anchor + '    diagnostics: createR10Diagnostics(R10_CONFIG),\\n', 1)\n    if len(payload.encode('utf-8')) >= MAX_STARTUP_BYTES:\n")
    builder=one(builder,'def build_startup(bundle: Path, *, root: Path = ROOT) -> dict:',
      'def build_startup(bundle: Path, *, root: Path = ROOT, r10_diagnostics: bool = False) -> dict:')
    builder=one(builder,'    install_script = _build_script(root, assets, wallpaper_css, artifacts)',
      '    install_script = _build_script(root, assets, wallpaper_css, artifacts, r10_diagnostics=r10_diagnostics)')
    result['tools/build-startup.py']=builder
    bootstrap=result['extension/bootstrap.mjs']
    bootstrap=one(bootstrap,'  installStartup,\n','  installStartup,\n  diagnostics = null,\n')
    bootstrap=one(bootstrap,'  return installStartup(installAnimation, host, pageAdapter);',
      '  if (diagnostics) return installStartup(installAnimation, host, pageAdapter, diagnostics);\n  return installStartup(installAnimation, host, pageAdapter);')
    result['extension/bootstrap.mjs']=bootstrap
    renderer=result['extension/renderer.mjs']
    renderer=one(renderer,'export function installStartup(payload, host = globalThis, pageAdapter) {',
      '''export function installStartup(payload, host = globalThis, pageAdapter, diagnostics = null) {
  // R10 source-copy experiment only. The formal third parameter remains pageAdapter.
  if (diagnostics) {
    if (!pageAdapter || typeof pageAdapter.identify !== 'function')
      return { installed: false, alreadyActive: false, reason: 'page-unsupported' };
    const admission = diagnostics.inspect(host);
    if (!admission.matched) return { installed: false, alreadyActive: false, reason: 'probe-target-mismatch' };
    return { installed: false, alreadyActive: false, reason: 'probe-only', assemblyObservation: diagnostics.run(host) };
  }''')
    result['extension/renderer.mjs']=renderer
    verifier=result['tools/verify-artifacts.py']
    for field in ['INPUT_FILES','STARTUP_REQUIRED_INPUTS']:
        verifier=one(verifier,'\n'+field+' = (\n','\n'+field+" = (\n    '"+MODULE+"',\n")
    # Entry predicates, legacy sets, old-build bounds remain byte-for-byte.
    result['tools/verify-artifacts.py']=verifier
    package=json.loads(result['hub-package.json'])
    for field in ['build_inputs','runtime_paths']:
        if MODULE in package[field]:raise ValueError('diagnostics already registered')
        package[field].append(MODULE)
    result['hub-package.json']=json.dumps(package,ensure_ascii=False,indent=2)+'\n'
    result[MODULE]=diagnostic_source
    return result
