"""Integrity suite for the super-archify canonical skill.

Pins the vendored upstream baseline (tt-a1i/archify v3.3.0), the hub wrapper
layer (frontmatter contract, carved coexistence boundary, brand protocol,
receipt) and the deterministic CLI surfaces the receipt depends on.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_repository import INVOCATION_CLASSES, SKILL_BRAND_CONTRACTS


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / "skills" / "super-archify"
SKILL = SKILL_DIR / "SKILL.md"

UPSTREAM_TAG = "v3.3.0"
UPSTREAM_COMMIT = "af3aaf3c36762f2afb62a4a09533f6c7273b07e5"
UPSTREAM_URL = "https://github.com/tt-a1i/archify"
UPSTREAM_SKILL_SHA256 = "e5c49b1c3e1b5b46ffb044aa676c46a58715cb34b459cbabd7f48e5887fed808"
VENDORED_FILE_COUNT = 598
VENDOR_MANIFEST = ROOT / "tests" / "archify-vendor-manifest.json"


def run_cli(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["node", str(SKILL_DIR / "bin" / "archify.mjs"), *args],
        cwd=SKILL_DIR, capture_output=True, check=False,
    )


class ArchifyPackageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL.read_text(encoding="utf-8")
        match = re.match(r"^---\n(?P<frontmatter>.*?)\n---\n", self.text, re.DOTALL)
        self.assertIsNotNone(match)
        self.frontmatter = match.group("frontmatter")

    def test_frontmatter_matches_the_hub_contract(self) -> None:
        keys = {line.split(":", 1)[0] for line in self.frontmatter.splitlines()}
        self.assertEqual({"name", "description"}, keys - {"invocation"})
        name = re.search(r"^name:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertEqual("super-archify", name.group(1).strip())
        invocation = re.search(r"^invocation:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(invocation)
        self.assertIn(invocation.group(1).strip(), INVOCATION_CLASSES)
        description = re.search(r"^description:\s*([^\n]+)$", self.frontmatter, re.MULTILINE)
        self.assertIsNotNone(description)
        self.assertLessEqual(len(description.group(1).strip()), 1024)

    def test_upstream_description_baseline_and_carve_are_retained(self) -> None:
        self.assertIn(
            "Create validated architecture, workflow, sequence, data-flow, lifecycle/state",
            self.text,
        )
        self.assertIn("Not for dashboards", self.text)
        self.assertIn("belong to super-excalidraw-diagram", self.text)

    def test_excalidraw_diagram_records_the_other_side_of_the_carve(self) -> None:
        excalidraw = (ROOT / "skills" / "super-excalidraw-diagram" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("belong to super-archify", excalidraw)

    def test_brand_contract_is_present(self) -> None:
        contract = SKILL_BRAND_CONTRACTS["skills/super-archify/SKILL.md"]
        self.assertIn(f"🦊 阿舟 · {contract['display_name']}", self.text)
        self.assertIn(contract["motto"], self.text)
        self.assertIn(contract["startup"], self.text)
        for marker in ("✅ 验证通过", "❌ 验证失败", "🔒 阿舟暂停这一项"):
            self.assertIn(marker, self.text)
        self.assertIn("A host without Unicode", self.text)
        self.assertIn("raw evidence", self.text)
        self.assertIn("super-archify.receipt.v1", self.text)

    def test_provenance_pins_the_locked_upstream(self) -> None:
        provenance = (SKILL_DIR / "references" / "provenance.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_TAG, provenance)
        self.assertIn(UPSTREAM_COMMIT, provenance)
        self.assertIn(UPSTREAM_URL, provenance)
        self.assertIsNotNone(re.search(r"^Classification: `faithful`", provenance, re.MULTILINE))
        self.assertIn("Skill-standard §2.3", provenance)

    def test_compatibility_map_records_the_trim_and_the_carve(self) -> None:
        compat = (SKILL_DIR / "references" / "upstream-compatibility.md").read_text(encoding="utf-8")
        self.assertIn(UPSTREAM_COMMIT, compat)
        self.assertIn("intentionally omitted", compat)
        self.assertIn("condensed to the 1024-character hub frontmatter ceiling", compat)
        self.assertIn("A future removal or replacement needs", compat)

    def test_setup_documents_the_node_runtime(self) -> None:
        setup = (SKILL_DIR / "references" / "setup.md").read_text(encoding="utf-8")
        self.assertIn("Node.js 18", setup)
        self.assertIn("fail closed", setup.lower())
        self.assertIn("doctor", setup)

    def test_vendored_tree_matches_the_complete_manifest(self) -> None:
        manifest = json.loads(VENDOR_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("azhou-hub.archify-vendor-manifest.v1", manifest["schema"])
        self.assertEqual(UPSTREAM_TAG, manifest["tag"])
        self.assertEqual(UPSTREAM_COMMIT, manifest["commit"])
        self.assertEqual(UPSTREAM_SKILL_SHA256, manifest["source_files"]["SKILL.md"])
        self.assertEqual(596, len(manifest["source_files"]))
        self.assertEqual(1, sum(row["disposition"] == "retain_documented_exclusion" for row in manifest["migration"]))
        actual = {
            path.relative_to(SKILL_DIR).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(SKILL_DIR.rglob("*")) if path.is_file()
        }
        self.assertEqual(VENDORED_FILE_COUNT, len(manifest["files"]))
        self.assertEqual(set(manifest["files"]), set(actual))
        for relative, expected in manifest["files"].items():
            self.assertEqual(expected, actual[relative], relative)

    def test_vendored_tree_size_is_stable(self) -> None:
        files = [path for path in SKILL_DIR.rglob("*") if path.is_file()]
        self.assertEqual(VENDORED_FILE_COUNT, len(files))

    def test_license_copy_and_notices_are_retained(self) -> None:
        license_text = (ROOT / "LICENSES" / "archify-MIT.txt").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 tt-a1i (Archify)", license_text)
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("tt-a1i (Archify)", notices)
        self.assertIn("archify-MIT.txt", notices)
        self.assertIn("JetBrains Mono", notices)
        package_notices = (SKILL_DIR / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("JetBrains Mono", package_notices)
        self.assertIn("Pele 1.3.0", package_notices)
        pele_license = (SKILL_DIR / "explainer/vendor/pele/LICENSE").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 kepano", pele_license)
        self.assertIn("ISC License", pele_license)


@unittest.skipIf(shutil.which("node") is None, "node is not available")
class ArchifyCliSmokeTest(unittest.TestCase):
    def test_doctor_passes_on_the_trimmed_package(self) -> None:
        result = run_cli("doctor")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(b"Archify is ready", result.stdout)

    def test_guide_router_loads(self) -> None:
        result = run_cli("guide", "user requests an order status timeline", "--json")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertTrue(payload["ok"])

    def test_validate_passes_on_a_shipped_example(self) -> None:
        result = run_cli(
            "validate", "workflow", "examples/agent-tool-call.workflow.json",
            "--quality", "showcase", "--json",
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout.decode("utf-8"))
        self.assertTrue(payload["ok"])


@unittest.skipIf(shutil.which("node") is None, "node is not available")
class ArchifyRuntimeRegressionTest(unittest.TestCase):
    def test_preview_delivers_through_the_actual_internal_cli(self) -> None:
        program = r'''
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root,input,output] = process.argv.slice(1);
const { startPreview } = await import(pathToFileURL(path.join(root,'bin/preview.mjs')));
const preview = await startPreview({type:'workflow',input,output,open:false,pollMs:100,debounceMs:20});
try {
  const deadline=Date.now()+15000;
  while (preview.state().status==='checking' && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,50));
  console.log(JSON.stringify(preview.state()));
} finally { await preview.stop(); await preview.closed; }
'''
        with tempfile.TemporaryDirectory(prefix="hub-archify-preview-") as directory:
            root = Path(directory)
            source = json.loads((SKILL_DIR / "examples/agent-tool-call.workflow.json").read_text())
            source["meta"]["output"] = "artifact.html"
            input_path, output_path = root / "input.json", root / "artifact.html"
            input_path.write_text(json.dumps(source))
            result = subprocess.run(
                ["node", "--input-type=module", "-e", program, str(SKILL_DIR), str(input_path), str(output_path)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=25,
                env={**os.environ, "ARCHIFY_UPDATE_CHECK_DISABLED": "1"},
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            state = json.loads(result.stdout)
            self.assertEqual("verified", state["status"], state)
            self.assertTrue(output_path.is_file(), state)
            self.assertEqual(hashlib.sha256(output_path.read_bytes()).hexdigest(), state["lastVerified"]["sha256"])
            self.assertEqual(state["lastVerified"]["checkCount"], state["lastVerified"]["checksPassed"])

    def test_official_update_identity_is_distinct_from_canonical_name(self) -> None:
        # Exact official v3.1.0 stable manifest archived at the v3.2.0 source tag.
        # This checks protocol compatibility, not whether that historical version is newer.
        manifest = {
            "schemaVersion": 1, "skillId": "archify", "channel": "stable", "version": "3.1.0",
            "publishedAt": "2026-10-13T17:01:11Z",
            "source": {"repository": UPSTREAM_URL, "ref": "v3.1.0", "treeSha": "7e1de2b2cf3a9a91823ee5dcc2089c1d96a7e4f1"},
            "artifact": {"sha256": "ffedc53390c9da6e859f41e432c5d2d0615a23cf00a503181f07efbba88a7ce8"},
            "summary": "Adds five diagram types for ten total, default Live motion, clearer layouts and verified delivery, with export and Windows portability fixes.",
            "releaseNotes": UPSTREAM_URL + "/releases/tag/v3.1.0", "severity": "normal",
        }
        program = r'''
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const [root,text]=process.argv.slice(1);
const {validateLocalRelease,validateStableUpdateManifest}=await import(pathToFileURL(path.join(root,'scripts/update-contract.mjs')));
const source=JSON.parse(text);
const local=validateLocalRelease(JSON.parse(fs.readFileSync(path.join(root,'skill-release.json'),'utf8')));
const official=validateStableUpdateManifest(source);
let renamedRejected=false;
try { validateStableUpdateManifest({...source,skillId:'super-archify'}); } catch { renamedRejected=true; }
console.log(JSON.stringify({local,official,renamedRejected}));
'''
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR), json.dumps(manifest)],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("archify", payload["local"]["skillId"])
        self.assertEqual("3.3.0", payload["local"]["version"])
        self.assertEqual(manifest, payload["official"])
        self.assertTrue(payload["renamedRejected"])

    def test_explainer_delivery_keeps_unrequested_browser_not_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="hub-archify-explainer-") as directory:
            output = Path(directory) / "answer.html"
            result = subprocess.run(
                ["node", str(SKILL_DIR / "bin/archify.mjs"), "finalize", "explainer",
                 str(SKILL_DIR / "examples/delivery.explainer.json"), str(output), "--json"],
                cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=20,
                env={**os.environ, "ARCHIFY_UPDATE_CHECK_DISABLED": "1"},
            )
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            receipt = json.loads(result.stdout)
            self.assertEqual({"validate":"pass", "deliver":"pass", "check":"pass", "browser-check":"not-run"}, receipt["gates"])
            self.assertFalse(receipt["browserCheck"]["requested"])
            self.assertFalse(receipt["browserCheck"]["ran"])
            self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), receipt["artifact"]["sha256"])


    def test_copy_handlers_keep_manual_fallback_when_clipboard_is_unavailable(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const source=fs.readFileSync(path.join(process.argv[1],'explainer/reader.js'),'utf8');
const lineByPrefix=prefix=>{const i=source.indexOf(prefix);assert.ok(i>=0,prefix);return source.slice(i,source.indexOf('\n',i)+1);};
// The vendored file defines copyText and escapeText at the top level; the regression
// slices the handlers and prepends those two single-line definitions unchanged.
const preamble=lineByPrefix('  async function copyText(')+lineByPrefix('  const escapeText = value => String(value');
let start=source.indexOf("  all('[data-copy]')");
const end=source.indexOf('  // Source cards:',start);
assert.ok(start>=0&&end>start);
const handlers=preamble+source.slice(start,end);
for(const handler of ['snippet','ask'])for(const mode of ['missing','reject','success']){
  const writes=[],notices=[];
  const element=()=>({textContent:'',value:'',style:{},events:{},children:[],setAttribute(){},focus(){},addEventListener(event,fn){this.events[event]=fn;},append(child){this.children.push(child);},click(){this.events.click?.();},select(){this.selected=this.value;}});
  const area=element(),quote=element(),where=element(),form=element(),head=element(),note=element(),dialog=element(),copy=element();
  copy.textContent='Copy';copy.closest=()=>({querySelector:()=>({textContent:'Original snippet'})});
  form.requestSubmit=()=>form.events.submit({preventDefault(){}});
  dialog.querySelector=selector=>({'textarea':area,'blockquote':quote,'.ask-where':where,'.ask-note':note,'form':form}[selector]);
  dialog.querySelectorAll=()=>[];dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;};
  const panel={id:'panel',dataset:{title:'Panel title'},querySelector:selector=>selector==='.panel-id'?{textContent:'1'}:head};
  const document={body:{append(){}},createElement:tag=>tag==='dialog'?dialog:element(),querySelector:selector=>selector==='.masthead'?{dataset:{title:'Page title'}}:{textContent:'Page title'},addEventListener(){}};
  const clipboard=mode==='missing'?undefined:{writeText(text){assert.equal(this,clipboard);writes.push(text);return mode==='reject'?Promise.reject(new Error('Denied')):Promise.resolve();}};
  const words=new Proxy({askChips:['Explain this'],copy:'Copy',copied:'Copied',askCopied:'Question copied'},{get:(target,key)=>target[key]??String(key)});
  vm.runInNewContext(handlers+'\nsetupAsk();',{
    document,navigator:{clipboard,platform:'',userAgent:''},location:{protocol:'https:',href:'https://example.invalid/reader'},
    all:selector=>selector==='[data-copy]'?[copy]:selector==='.panel'?[panel]:[],
    words,english:true,say:en=>en,escapeText:String,notify:text=>notices.push(text),setTimeout(){},
  });
  if(handler==='snippet')copy.click();
  else {head.children[0].click();area.value='Why?';form.requestSubmit();}
  await new Promise(setImmediate);
  assert.equal(writes.length,mode==='missing'?0:1,handler+' '+mode);
  if(handler==='snippet'){
    if(mode==='success'){assert.equal(writes[0],'Original snippet');assert.equal(copy.textContent,'Copied');assert.deepEqual(notices,[]);}
    else {assert.equal(copy.textContent,'Copy');assert.deepEqual(notices,['Copy failed. Select the code and copy it manually.']);}
  }else{
    const text=mode==='success'?writes[0]:area.value;
    for(const context of ['Page title','ID: panel','Why?','https://example.invalid/reader'])assert.ok(text.includes(context),context);
    if(mode==='success'){assert.equal(dialog.open,false);assert.deepEqual(notices,['Question copied']);}
    else {assert.equal(dialog.open,true);assert.equal(area.selected,area.value);assert.deepEqual(notices,[]);}
  }
}
console.log(JSON.stringify({checks:6,passed:true}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"checks": 6, "passed": True}, json.loads(result.stdout))


@unittest.skipIf(shutil.which("node") is None, "node is not available")
class ArchifyExplainerSecurityRegressionTest(unittest.TestCase):
    def test_citation_revision_is_never_silently_replaced(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const [root,repo] = process.argv.slice(1);
const {resolveExplainerSources}=await import(pathToFileURL(path.join(root,'explainer/sources.mjs')));
const git=(...args)=>execFileSync('git',['-C',repo,...args],{encoding:'utf8'}).trim();
git('init','--quiet');
git('config','remote.origin.url','https://github.com/example/revision-regression');
const commit=text=>{fs.writeFileSync(path.join(repo,'evidence.txt'),text+'\n');git('add','evidence.txt');git('-c','user.name=Regression','-c','user.email=regression@example.invalid','-c','commit.gpgsign=false','commit','--quiet','-m','Fixture');return git('rev-parse','HEAD');};
const old=commit('Original evidence'), latest=commit('Later evidence');
const make=(pin,revision=latest,code=false)=>({sources:[{id:'ref',path:'evidence.txt',lines:[1,1],...(pin===undefined?{}:{revision:pin})}],panels:[{id:'panel',blocks:code?[{id:'code',type:'code',source:'ref'}]:[]}],...(revision===null?{}:{meta:{repository:{url:'https://github.com/example/revision-regression',revision}}})});
for(const doc of [make(old),make(old,null),make(old,latest,true)]){
  const before=JSON.stringify(doc);
  await assert.rejects(resolveExplainerSources(doc,{repoRoot:repo}),error=>error.archifyDiagnostics?.[0]?.code==='explainer/source-revision'&&error.archifyDiagnostics[0].subject.path==='/sources/0/revision');
  assert.equal(JSON.stringify(doc),before);
}
for(const [doc,revision,text] of [[make(latest),latest,'Later evidence'],[make(undefined),latest,'Later evidence'],[make(old,old),old,'Original evidence']]){
  const before=JSON.stringify(doc), result=await resolveExplainerSources(doc,{repoRoot:repo});
  assert.equal(result.sources.ref.revision,revision);assert.equal(result.sources.ref.text,text);assert.ok(result.sources.ref.url.includes('/blob/'+revision+'/'));assert.equal(JSON.stringify(doc),before);
}
const plain=await resolveExplainerSources(make(old),{});
assert.equal(plain.sources.ref.revision,old);assert.equal(plain.sources.ref.text,undefined);assert.deepEqual(plain.dependencies,[]);
console.log(JSON.stringify({checks:7,passed:true}));
"""
        with tempfile.TemporaryDirectory(prefix="archify-revision-regression-") as directory:
            result = subprocess.run(
                ["node", "--input-type=module", "-e", program, str(SKILL_DIR), directory],
                capture_output=True, text=True, encoding="utf-8", timeout=20,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"checks": 7, "passed": True}, json.loads(result.stdout))

    def test_native_css_cannot_close_the_preview_style_element(self) -> None:
        from html.parser import HTMLParser

        program = r"""
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const {renderExplainer}=await import(pathToFileURL(path.join(process.argv[1],'explainer/render.mjs')));
const doc={schema_version:1,diagram_type:'explainer',meta:{id:'css-regression',title:'CSS containment',locale:'en'},answer:{summary:'Keep native styles contained.'},panels:[{id:'panel',title:'Preview',blocks:[{id:'native',type:'diagram',diagramType:'architecture',spec:{}}]}],sources:[]};
const styles='<style>.node{--sample:"</sty/**/le><img id=style-breakout src=x onerror=globalThis.injected=1><style>"}@media (width < 900px){.node{fill:rgb(1,2,3)}}</style>';
const diagram={diagramType:'architecture',html:'<!doctype html><html><body><svg></svg></body></html>',svg:'<svg viewBox="0 0 100 100"><rect class="node" width="10" height="10"/></svg>',styles,semantic:{nodes:[],edges:[]}};
console.log(renderExplainer(doc,{preparedDiagrams:{diagrams:{native:diagram},dependencies:[]}}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

        class Page(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.breakouts = []
                self.styles = []
                self.in_style = False

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                if dict(attrs).get("id") == "style-breakout":
                    self.breakouts.append(tag)
                self.in_style = tag == "style" or self.in_style

            def handle_endtag(self, tag: str) -> None:
                if tag == "style":
                    self.in_style = False

            def handle_data(self, data: str) -> None:
                if self.in_style:
                    self.styles.append(data)

        page = Page()
        page.feed(result.stdout)
        self.assertEqual([], page.breakouts)
        preview_css = next(css for css in page.styles if "--sample" in css)
        self.assertIn("@media (width < 900px)", preview_css)
        self.assertIn(".preview-native .node{fill:rgb(1,2,3)}", preview_css)
        self.assertNotIn("</style", preview_css.lower())

    def test_browser_argument_transport_preserves_data_and_releases_context(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const source=fs.readFileSync(path.join(process.argv[1],'explainer/browser-check.mjs'),'utf8');
const start=source.indexOf('async function call('), end=source.indexOf('function measureNativePreviews()',start);
assert.ok(start>=0&&end>start);
const call=vm.runInNewContext(source.slice(start,end)+'\ncall');
const payload='[data-value="</script>\\\'\u2028<literal>"]';
const sent=[];let failure=false;
const browser={sessionPromise:Promise.resolve('session'),cdp:{async send(method,params,session){
  sent.push({method,params,session});
  if(method==='Runtime.evaluate'){assert.equal(params.expression,'globalThis');return {result:{objectId:'context'}};}
  if(method==='Runtime.callFunctionOn'){
    assert.equal(params.arguments[0].value,payload);assert.ok(!params.functionDeclaration.includes(payload));
    return failure?{exceptionDetails:{text:'Expected browser failure'}}:{result:{value:payload}};
  }
  assert.equal(method,'Runtime.releaseObject');assert.equal(params.objectId,'context');return {};
}}};
assert.equal(await call(browser,function(value){return value;},[payload]),payload);
assert.equal(sent.at(-1).method,'Runtime.releaseObject');
failure=true;
await assert.rejects(call(browser,function(value){return value;},[payload]),/Expected browser failure/);
assert.equal(sent.at(-1).method,'Runtime.releaseObject');
console.log(JSON.stringify({argumentPreserved:true,errorPropagated:true,contextReleased:true}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            {"argumentPreserved": True, "errorPropagated": True, "contextReleased": True},
            json.loads(result.stdout),
        )


@unittest.skipIf(shutil.which("node") is None, "node is not available")
class ArchifyLocalHardeningRegressionTest(unittest.TestCase):
    def test_drilldown_navigation_refuses_unsafe_schemes(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const source=fs.readFileSync(path.join(process.argv[1],'assets/template.html'),'utf8');
const start=source.indexOf('      function isSafeRelativeHtmlHref(value) {'),end=source.indexOf('      function relationshipsFor(id, byId) {',start);
assert.ok(start>=0&&end>start,'drilldown navigation block');
const page=({search='',parentHref=null}={})=>{
  const navigations=[],links=[];
  const element=()=>{const node={attributes:{},children:[],setAttribute(name,value){this.attributes[name]=String(value);},appendChild(child){this.children.push(child);}};Object.defineProperty(node,'href',{set(value){links.push(String(value));}});return node;};
  const context={location:{pathname:'/docs/parent.html',search,assign:url=>navigations.push(url)},svg:{getAttribute:name=>name==='data-parent-href'?parentHref:null},
    document:{createElement:element},URLSearchParams,viewerText:key=>key,drilldownsSection:{},drilldownsList:element()};
  vm.runInNewContext(source.slice(start,end)+'\nthis.navigation={navigateToRelativeHtml,navigateToParent,renderDrilldowns};',context);
  return {...context.navigation,navigations,links,guard:context.safeNavigationHref};
};
const drilldowns=href=>({getAttribute:name=>name==='data-node-drilldowns'?JSON.stringify([{href,label:'Drilldown'}]):null});
// The three sinks keep their documented behavior: a sibling page navigates with ?from=, the parent
// link comes from ?from= or data-parent-href, and the passport list links to the sibling.
for(const [options,run,expected,navigations,links] of [
  [{},view=>view.navigateToRelativeHtml('child.html'),true,['child.html?from=parent.html'],[]],
  [{search:'?from=parent.html&theme=dark'},view=>view.navigateToParent(),true,['parent.html?theme=dark'],[]],
  [{parentHref:'up.html#top'},view=>view.navigateToParent(),true,['up.html#top'],[]],
  [{},view=>view.renderDrilldowns(drilldowns('child.html')),undefined,[],['child.html?from=parent.html']],
]){
  const view=page(options);
  assert.equal(run(view),expected);
  assert.deepEqual(view.navigations,navigations);
  assert.deepEqual(view.links,links);
}
const hostile=['javascript:alert(1)','JavaScript:alert(1)',' javascript:alert(1)','jav\tascript:alert(1)','\u0001javascript:alert(1)','java\nscript:alert(1)',
  'data:text/html,<script>alert(1)</script>','vbscript:msgbox(1)','blob:https://example.invalid/x','mailto:a@example.invalid','//example.invalid/x.html','\\\\example.invalid\\x.html',''];
for(const href of hostile){
  const view=page({search:'?from='+encodeURIComponent(href),parentHref:href});
  assert.equal(view.navigateToRelativeHtml(href),false,JSON.stringify(href));
  assert.equal(view.navigateToParent(),false,JSON.stringify(href));
  assert.deepEqual(view.navigations,[],JSON.stringify(href));
  view.renderDrilldowns(drilldowns(href));
  assert.deepEqual(view.links,[],JSON.stringify(href));
}
// One shared guard backs the sinks: it normalizes what a browser ignores before the scheme check.
assert.equal(typeof page().guard,'function','template ships the shared safe-URL guard');
const guard=page().guard;
for(const href of hostile) assert.equal(guard(href),null,JSON.stringify(href));
for(const value of [null,undefined,42,{}]) assert.equal(guard(value),null);
for(const [href,expected] of [
  ['child.html','child.html'],['child.html?from=parent.html#top','child.html?from=parent.html#top'],['../dir/child.html','../dir/child.html'],
  ['/docs/child.html','/docs/child.html'],['#fragment','#fragment'],['?theme=dark','?theme=dark'],['  child.html\t\n','child.html'],
  ['/example.invalid/x.html','/example.invalid/x.html'],
  ['https://example.invalid/a b.html','https://example.invalid/a b.html'],['HTTP://EXAMPLE.INVALID/x.html','HTTP://EXAMPLE.INVALID/x.html'],
  ['file:///abs/path/x.html','file:///abs/path/x.html'],['\u0001 file:///abs/path/x.html ','file:///abs/path/x.html'],
]) assert.equal(guard(href),expected,JSON.stringify(href));
console.log(JSON.stringify({sites:4,hostile:hostile.length,allowed:12,passed:true}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"sites": 4, "hostile": 13, "allowed": 12, "passed": True}, json.loads(result.stdout))

    def test_analysis_client_renders_repository_payloads_as_text(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const CLIENT = path.join(process.argv[1], 'modules/code-analysis/overlay/client');
const IMG = '<img src=x onerror=alert(1)>';
const FILE = `deep/${IMG}/a.py`;
const MSG = `msg ${IMG} tail`;
const NUM = `9>${IMG}`;
let captured = { html: [] };
const rowValues = {};
const ctxProxy = () => new Proxy({}, {
  get(target, key) {
    if (key in target) return target[key];
    if (key === 'measureText') return () => ({ width: 12 });
    if (key === 'createLinearGradient' || key === 'createRadialGradient' || key === 'createPattern') return () => ({ addColorStop() {} });
    if (key === 'canvas') return null;
    return (...a) => {};
  },
  set(target, key, value) { target[key] = value; return true; },
});
class El {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.attributes = {}; this.dataset = {};
    this.style = { setProperty() {}, removeProperty() {} };
    this._listeners = {};
    this.classList = { add() {}, remove() {}, toggle() {}, contains: () => false };
    this.hidden = false; this.textContent = ''; this.scrollTop = 0; this.disabled = false;
    this._html = ''; this.parentNode = null; this.clientWidth = 640; this.clientHeight = 480;
  }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v); captured.html.push(this._html); }
  appendChild(c) { this.children.push(c); c.parentNode = this; return c; }
  prepend(c) { this.children.unshift(c); c.parentNode = this; return c; }
  insertBefore(c) { this.children.push(c); c.parentNode = this; return c; }
  append(c) { this.children.push(c); c.parentNode = this; return c; }
  before() {} after() {} remove() {} focus() {} select() {} click() {}
  setAttribute(k, v) { this.attributes[k] = String(v); }
  getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; }
  removeAttribute(k) { delete this.attributes[k]; }
  hasAttribute(k) { return k in this.attributes; }
  addEventListener(t, fn) { (this._listeners[t] = this._listeners[t] || []).push(fn); }
  fire(t, ev) { (this._listeners[t] || []).slice().forEach((fn) => fn.call(this, ev)); }
  fireClick() { this.fire('click', { preventDefault() {}, stopPropagation() {}, target: this, key: 'Enter', clientX: 0, clientY: 0 }); }
  getClientRects() { return [{}]; }
  getBoundingClientRect() { return { left: 0, top: 0, right: 640, bottom: 480, width: 640, height: 480, x: 0, y: 0 }; }
  querySelector(sel) { this._q = this._q || {}; if (!this._q[sel]) { const el = new El(sel); el.parentElement = this; this._q[sel] = el; } return this._q[sel]; }
  querySelectorAll(sel) {
    this._qa = this._qa || {};
    if (!this._qa[sel]) {
      const row = new El('row');
      row.getAttribute = (name) => (rowValues[name] !== undefined ? rowValues[name] : '');
      row.hasAttribute = (name) => name === 'data-finding' || name === 'data-ind' || name === 'data-edge';
      row.closest = () => row;
      this._qa[sel] = [row];
    }
    return this._qa[sel];
  }
  contains() { return false; }
  getContext() { return ctxProxy(); }
}
function makeEnv({ analysis, atlas, atlas3dData }) {
  captured = { html: [] };
  const allEls = [];
  const root = new El('html');
  const toolbar = new El('div');
  const container = new El('div');
  container.getAttribute = (k) => (k === 'data-just-panned' ? 'false' : null);
  const docStubs = { '.toolbar': toolbar, '.header': new El('div'), '.diagram-container': container, '.analysis-stage': new El('div') };
  const rafQueue = [];
  const windowObj = {
    innerWidth: 1400, innerHeight: 900, devicePixelRatio: 1,
    addEventListener() {}, removeEventListener() {},
    __archifyMakeAnalysisTranslator: () => (key, params) => String(key).replace(/\{(\w+)\}/g, (m, k) => (params && k in params ? String(params[k]) : m)),
    __archifyWireVerification: () => {},
  };
  const doc = {
    documentElement: root,
    body: new El('body'),
    hidden: false,
    activeElement: null,
    getElementById(id) {
      if (id === 'bauify-analysis') return { textContent: JSON.stringify(analysis) };
      if (id === 'bauify-atlas-data') return { textContent: JSON.stringify(atlas) };
      if (id === 'bauify-atlas3d-data') return { textContent: JSON.stringify(atlas3dData || {}) };
      return null;
    },
    createElement(tag) { const el = new El(tag); allEls.push(el); return el; },
    createElementNS(ns, tag) { const el = new El(tag); allEls.push(el); return el; },
    querySelector(sel) { return docStubs[sel] || new El(sel); },
    querySelectorAll() { return []; },
    addEventListener() {},
  };
  const sandbox = {
    document: doc, window: windowObj, root,
    innerHeight: 900, innerWidth: 1400,
    navigator: { clipboard: undefined, platform: 'test', userAgent: 'test' },
    location: { pathname: '/reports/x.html', search: '', assign() {}, replace() {} },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    matchMedia: () => ({ matches: false }),
    MutationObserver: class { observe() {} },
    ResizeObserver: class { observe() {} },
    requestAnimationFrame(fn) { rafQueue.push(fn); return rafQueue.length; },
    cancelAnimationFrame() {},
    performance,
    getComputedStyle: () => ({ getPropertyValue: () => '' }),
    Float32Array, Float64Array, JSON, Math, Object, Array, Number, String, Set, Map, URL, URLSearchParams, Blob, Proxy,
    setTimeout, clearTimeout,
    console,
    Option: class { constructor(label, value) { this.text = label; this.value = value; } },
  };
  sandbox.globalThis = sandbox;
  windowObj.matchMedia = sandbox.matchMedia;
  return { sandbox, windowObj, doc, root, toolbar, container, rafQueue, captured, allEls, flush: () => { const q = rafQueue.splice(0); q.forEach((fn) => fn(performance.now())); } };
}
function runScript(env, file) {
  const source = fs.readFileSync(path.join(CLIENT, file), 'utf8');
  vm.runInNewContext(source, env.sandbox, { filename: file, timeout: 20000 });
}
function findEl(list, pred) {
  for (const el of list || []) {
    if (pred(el)) return el;
    const inner = findEl(el.children, pred);
    if (inner) return inner;
  }
  return null;
}
const overlayAnalysis = {
  ui: { locale: 'en', messages: {} },
  repository: { url: 'https://example.invalid/x', language: 'py', root: '.', revision: 'abcdef123456', sourceKind: 'commit' },
  totals: { modules: NUM, edges: 2 },
  unmapped: [{ id: 'U1', label: `unmapped ${IMG}`, path: 'u<img>', files: 2, loc: 10, fanIn: 1, fanOut: 1, fileList: [] }],
  components: [
    {
      id: 'C1', label: `comp ${IMG}`,
      modules: [{ id: 'M1', label: `mod ${IMG}`, path: 'm<img>', files: 1, loc: 5, fanIn: 1, fanOut: 0 }],
      indicators: { status: 'amber', items: [{ key: 'instability', label: 'Instability', status: 'neutral', findings: ['FHUB', 'FIMP'], detail: [], value: '0.5', fanIn: NUM, fanOut: 1, instability: NUM }] },
      ambiguousModules: [], files: NUM, loc: NUM, internalImports: 1,
      incoming: [],
      outgoing: [{ component: 'C2', weight: NUM, evidence: [{ file: 'a.py', line: 2, to: 'b.py' }] }],
      fileList: [{ path: FILE, module: 'M1', findings: [{ id: 'FIMP' }], loc: NUM, importsOut: NUM, importedBy: NUM }],
      findings: [{ id: 'FHUB' }, { id: 'FIMP' }],
    },
    { id: 'C2', label: 'C2', modules: [], indicators: { status: 'grey', items: [] }, ambiguousModules: [], files: 1, loc: 1, internalImports: 0, incoming: [{ component: 'C1', weight: 2, evidence: [{ file: 'a.py', line: 2, to: 'b.py' }] }], outgoing: [], fileList: [], findings: [] },
  ],
  edges: [{ from: 'C1', to: 'C2', weight: 2, declared: true, evidence: [{ file: FILE, line: NUM, to: 'x' }] }],
  findings: [
    { id: 'FHUB', code: 'coupling/hub', dimension: 'coupling', severity: 'warning', message: MSG, subject: { module: 'M1' }, componentIds: ['C1'], moduleIds: ['M1'], evidence: { fanIn: 1, fanOut: 1, dependents: ['M2'], dependencies: ['M3'], threshold: { fanIn: NUM, fanOut: 1 } } },
    { id: 'FIMP', code: 'architecture/boundary', dimension: 'architecture', severity: 'warning', message: `b ${IMG}`, subject: { file: FILE, line: 2, boundary: { from: 'ui', to: 'db' } }, componentIds: ['C1'], moduleIds: ['M1'], evidence: { imports: [{ file: FILE, line: NUM, to: `to ${IMG}` }], rule: { reason: 'r' }, totalImports: 1, files: ['x'] } },
  ],
  overview: {
    counts: { error: 1, warning: 2, info: 0, findings: 2, acceptedErrors: 0, accepted: 0 },
    priorities: ['FHUB'],
    groups: [{ code: 'coupling/hub', severity: 'warning', count: 1, ids: ['FHUB'] }, { code: 'architecture/boundary', severity: 'warning', count: 1, ids: ['FIMP'] }],
    coverage: { language: 'py', files: { analyzed: 2, excludedByRole: 0, excludedRoles: [], parseErrors: [] }, rules: { run: ['coupling/hub'], suppressed: [] }, unresolved: {}, boundaries: { layers: [], rules: 1 } },
    review: null, investigation: null,
  },
  snippets: { [FILE]: { lines: ['line one', `line ${IMG} two`], changes: { status: 'modified', added: [2], modified: [], deleted: [{ after: 1, count: NUM }] } } },
};
function runOverlay() {
  Object.assign(rowValues, {
    'data-finding': 'FHUB', 'data-ind': 'instability', 'data-edge': 'C1>C2',
    'data-file': FILE, 'data-line': '3', 'data-range-start': NUM, 'data-range-end': '6',
    'data-match': JSON.stringify({ kind: 'external', line: 2, endLine: 2, column: NUM, endColumn: '5' }),
    'data-why': 'why', 'data-tone': 'amber',
  });
  const env = makeEnv({ analysis: overlayAnalysis });
  const g = new El('g');
  g.getBBox = () => ({ x: 0, y: 0, width: 10, height: 10 });
  g.getAttribute = (k) => (k === 'data-node-id' ? 'C1' : null);
  const svg = new El('svg');
  svg.appendChild(g);
  svg.querySelector = (sel) => { svg._q = svg._q || {}; if (!svg._q[sel]) svg._q[sel] = sel.indexOf('data-node-id') !== -1 ? g : new El(sel); return svg._q[sel]; };
  svg.querySelectorAll = (sel) => (sel.indexOf('data-node-id') !== -1 ? [g] : []);
  const baseQuery = env.doc.querySelector.bind(env.doc);
  env.doc.querySelector = (sel) => (sel === 'svg' ? svg : baseQuery(sel));
  runScript(env, 'overlay.js');
  const btn = env.toolbar.children.find((c) => c.tagName === 'button');
  btn.fireClick();
  env.flush();
  env.windowObj.__archifyShowFinding('FHUB');
  env.flush();
  const detailEl = findEl(env.allEls, (el) => el.id === 'bauify-detail');
  assert.ok(detailEl, 'overlay detail element exists');
  detailEl.querySelectorAll('.ref')[0].fireClick();
  env.flush();
  const panelEl = findEl(env.allEls, (el) => el.id === 'bauify-panel');
  const stageEl = findEl(env.allEls, (el) => el.id === 'bauify-stage');
  svg.fire('click', { preventDefault() {}, stopPropagation() {}, target: { closest: (sel) => (sel && sel.indexOf('g[data-node-id]') !== -1 ? g : null) } }, true);
  env.flush();
  panelEl.querySelectorAll('.ind.link')[0].fireClick();
  env.flush();
  panelEl.querySelectorAll('.fly-rel[data-edge]')[0].fireClick();
  env.flush();
  const offRow = new El('button');
  offRow.dataset.go = 'off:U1';
  offRow.closest = (sel) => (sel === 'button' ? offRow : null);
  if (stageEl) stageEl.fire('click', { stopPropagation() {}, target: offRow });
  env.flush();
  return captured.html;
}
function atlasPayload(mode) {
  return {
    ui: { locale: 'en', messages: {}, mode },
    components: [{ id: 'C1', label: `c ${IMG}`, modules: [{ id: 'm1', label: `m ${IMG}`, path: 'p<img>' }] }],
    findings: [{ id: 'F1', code: 'complexity/function', dimension: 'complexity', severity: 'warning', message: MSG, subject: { file: FILE, line: 3 }, componentIds: ['C1'], moduleIds: ['m1'] }],
  };
}
function atlasData() {
  return {
    modules: [{ id: 'm1', label: `mod ${IMG}`, path: 'p<img>', fanIn: NUM, fanOut: NUM }],
    files: [[FILE, 0, 40]],
    edges: [],
    functions: [[0, `fn ${IMG}`, 7, NUM, 2, 10, 0, null]],
    findings: [
      { id: 'F1', code: 'complexity/function', severity: 'warning', kind: 'function', fn: 0, file: 0, accepted: false, title: `t ${IMG}` },
      { id: 'F2', code: 'coupling/hub', severity: 'warning', kind: 'module', module: 0, accepted: false, title: `h ${IMG}` },
    ],
    coverage: { records: 1, resolved: 1, external: 0, unknown: 0, outside: 0, parseErrors: 0, notCompiled: 0 },
    measured: true,
  };
}
function runAtlas(mode) {
  Object.assign(rowValues, { 'data-finding': '0', 'data-module': '0' });
  const env = makeEnv({ analysis: atlasPayload(mode), atlas: atlasData() });
  env.root.setAttribute('data-bauify', 'on');
  runScript(env, 'atlas.js');
  env.flush();
  const panel = findEl(env.allEls, (el) => el.id === 'bauify-atlas');
  assert.ok(panel, 'atlas panel exists');
  if (mode === 'standalone') {
    const canvas = panel.querySelector('canvas');
    const tip = panel.querySelector('.atlas-tip');
    let hitAny = false;
    outer: for (let y = 6; y < 470; y += 3) {
      for (let x = 6; x < 630; x += 3) {
        canvas.fire('mousemove', { clientX: x, clientY: y });
        if (!tip.hidden && tip._html) { hitAny = true; break outer; }
      }
    }
    assert.ok(hitAny, 'atlas hover tip rendered');
  } else {
    const side = panel.querySelector('.atlas-side');
    side.querySelectorAll('[data-finding]')[0].fireClick();
    env.flush();
  }
  return captured.html;
}
function runAtlas3d() {
  const env = makeEnv({ analysis: atlasPayload('diagram'), atlas: atlasData(), atlas3dData: { detail: { F1: { message: MSG, fix: `fix ${IMG}` } }, run: { summary: { errors: 1, warnings: 0, info: 0 } } } });
  class V3 {
    constructor(x, y, z) { this.x = x || 0; this.y = y || 0; this.z = z || 0; }
    clone() { return new V3(this.x, this.y, this.z); }
    add(v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
    multiplyScalar(s) { this.x *= s; this.y *= s; this.z *= s; return this; }
    copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
    normalize() { const l = Math.hypot(this.x, this.y, this.z) || 1; return this.multiplyScalar(1 / l); }
    project() { this.x = 0; this.y = 0; this.z = 0.5; return this; }
    set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
    setXYZ() { return this; }
  }
  class Attr {
    constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; this.count = Math.ceil(array.length / itemSize); }
    getX(i) { return this.array[i * this.itemSize]; }
    getY(i) { return this.array[i * this.itemSize + 1]; }
    getZ(i) { return this.array[i * this.itemSize + 2]; }
    setXYZ(i, x, y, z) { const o = i * this.itemSize; this.array[o] = x; this.array[o + 1] = y; this.array[o + 2] = z; return this; }
  }
  class Geometry { constructor() { this._a = {}; } setAttribute(n, a) { this._a[n] = a; } getAttribute(n) { return this._a[n] || new Attr([], 3); } }
  class Color { constructor() { this.r = 0.5; this.g = 0.4; this.b = 0.6; } }
  class Box3 {
    constructor() { this.min = new V3(Infinity, Infinity, Infinity); this.max = new V3(-Infinity, -Infinity, -Infinity); }
    setFromBufferAttribute(a) { for (let i = 0; i < a.count; i += 1) { this.min.x = Math.min(this.min.x, a.getX(i)); this.min.y = Math.min(this.min.y, a.getY(i)); this.min.z = Math.min(this.min.z, a.getZ(i)); this.max.x = Math.max(this.max.x, a.getX(i)); this.max.y = Math.max(this.max.y, a.getY(i)); this.max.z = Math.max(this.max.z, a.getZ(i)); } return this; }
    expandByScalar(s) { this.min.x -= s; this.min.y -= s; this.min.z -= s; this.max.x += s; this.max.y += s; this.max.z += s; return this; }
    getSize(v) { return v.set(this.max.x - this.min.x, this.max.y - this.min.y, this.max.z - this.min.z); }
    getCenter(v) { return v.set((this.min.x + this.max.x) / 2, (this.min.y + this.max.y) / 2, (this.min.z + this.max.z) / 2); }
  }
  class Curve { constructor() {} getPoints(n) { return Array.from({ length: n }, () => new V3()); } }
  const canvas = new El('canvas');
  env.sandbox.window.THREE = {
    Vector3: V3, Color, Box3,
    BufferAttribute: Attr, Float32BufferAttribute: Attr, BufferGeometry: Geometry,
    WebGLRenderer: class { constructor() { this.domElement = canvas; } setPixelRatio() {} setClearColor() {} setSize() {} getPixelRatio() { return 1; } render() {} },
    Scene: class { add() {} },
    PerspectiveCamera: class { constructor() { this.position = new V3(); this.aspect = 1; } lookAt() {} updateProjectionMatrix() {} },
    Points: class { constructor() { this.position = new V3(); } },
    LineSegments: class { constructor() { this.position = new V3(); } },
    ShaderMaterial: class {}, LineBasicMaterial: class {},
    EdgesGeometry: class {}, BoxGeometry: class {}, CubicBezierCurve3: Curve, QuadraticBezierCurve3: Curve,
    AdditiveBlending: 0,
  };
  const host = new El('section');
  runScript(env, 'atlas3d.js');
  const view = env.windowObj.__archifyAtlas3d.mount(host);
  assert.ok(view && view.select, 'atlas3d mounted');
  view.select({ type: 'finding', index: 0 });
  return captured.html;
}
const overlayHtml = runOverlay();
const atlasPageHtml = runAtlas('diagram');
const atlasStandaloneHtml = runAtlas('standalone');
const atlas3dHtml = runAtlas3d();
const all = [...overlayHtml, ...atlasPageHtml, ...atlasStandaloneHtml, ...atlas3dHtml];
const sinks = all.length;
assert.ok(sinks >= 20, `collected ${sinks} innerHTML writes`);
for (const html of all) assert.doesNotMatch(html, /<img\b/i, `raw payload in sink: ${html.slice(0, 200)}`);
const escaped = all.filter((h) => h.includes('&lt;img'));
assert.ok(escaped.length >= 10, `escaped payload present in only ${escaped.length} sinks`);
console.log(JSON.stringify({ sinks, withEscapedPayload: escaped.length, passed: true }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"sinks": 21, "withEscapedPayload": 14, "passed": True}, json.loads(result.stdout))

    def test_static_bake_cannot_reconstitute_embedded_style_elements(self) -> None:
        program = r"""
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const {bakeSvg} = await import(pathToFileURL(path.join(process.argv[1], 'renderers/shared/svg-bake.mjs')));
const wrap = (body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">${body}</svg>`;
const legit = bakeSvg(wrap('<style>.c-n{fill:#102030}</style><rect class="c-n" width="4" height="4"/>'), { theme: 'dark', preset: 'classic' });
const styleCount = (text) => (text.match(/<\/?style\b/g) || []).length;
if (styleCount(legit) !== 4) throw new Error('legit bake: expected baker + body style tags, got ' + styleCount(legit));
if (!legit.includes('fill: #102030') || !legit.includes('<rect class="c-n"')) throw new Error('legit bake lost declarations');
const empty = bakeSvg(wrap('<style></style><rect width="4" height="4"/>'), { theme: 'dark', preset: 'classic' });
if (styleCount(empty) !== 2) throw new Error('empty body style should only keep the baker style');
const hostile = [
  '<sty<style></style>le>.n{fill:red}</style><rect class="n" width="4" height="4"/>',
  '<style>.n{fill:red}<rect class="n" width="4" height="4"/>',
  '<rect width="4" height="4"/></style>',
  '<style><style>.n{fill:red}</style></style><rect width="4" height="4"/>',
  '<style x="<s>a</s y=">.n{fill:red}</style><rect width="4" height="4"/>',
];
let threw = 0;
for (const body of hostile) {
  try { bakeSvg(wrap(body), { theme: 'dark', preset: 'classic' }); } catch (_) { threw += 1; }
}
console.log(JSON.stringify({ styles: styleCount(legit), empty: styleCount(empty), threw, expected: hostile.length, passed: threw === hostile.length }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"styles": 4, "empty": 2, "threw": 5, "expected": 5, "passed": True}, json.loads(result.stdout))

    def test_story_scoping_rejects_style_reconstitution_and_terminators(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {pathToFileURL} from 'node:url';
const root = process.argv[1];
const {parseStylesheet} = await import(pathToFileURL(path.join(root, 'renderers/shared/svg-bake.mjs')));
const source = fs.readFileSync(path.join(root, 'pr/story-svg.mjs'), 'utf8');
const start = source.indexOf('function scopeEmbeddedStyles(svg, key) {'), end = source.indexOf('function annotateEdgePaths(svg) {', start);
assert.ok(start >= 0 && end > start);
const scopeEmbeddedStyles = vm.runInNewContext('(' + source.slice(start, end) + ')', { parseStylesheet });
const cases = [
  ['<svg><style>.c-n{fill:var(--x)}</style><rect class="c-n"/></svg>', '<svg><style><![CDATA[[data-native-key="native-1"] :is(.c-n){fill:var(--x)}]]></style><rect class="c-n"/></svg>'],
  ['<svg><style></style><rect/></svg>', '<svg><rect/></svg>'],
  ['<svg><style><![CDATA[.c-node{fill:red}]]></style><rect class="c-node"/></svg>', '<svg><style><![CDATA[[data-native-key="native-1"] :is(.c-node){fill:red}]]></style><rect class="c-node"/></svg>'],
];
for (const [input, expected] of cases) assert.equal(scopeEmbeddedStyles(input, 'native-1'), expected);
const hostile = [
  '<svg><sty<style></style>le><rect/></svg>',
  '<svg><style>a]]><img src=x onerror=alert(1)>{fill:red}</style><rect/></svg>',
  '<svg><style>.a{fill:red}]]><script>alert(1)</script>.b{fill:blue}</style><rect/></svg>',
  '<svg><style>.a{fill:red}</style y="1"><rect/></svg>',
];
let threw = 0;
for (const svg of hostile) {
  try { scopeEmbeddedStyles(svg, 'native-1'); } catch (_) { threw += 1; }
}
assert.equal(threw, hostile.length);
console.log(JSON.stringify({ cases: cases.length, threw, expected: hostile.length, passed: true }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"cases": 3, "threw": 4, "expected": 4, "passed": True}, json.loads(result.stdout))

    def test_render_tag_tokenizer_is_equivalent_and_linear(self) -> None:
        program = r"""
import fs from 'node:fs';
import path from 'node:path';
const source = fs.readFileSync(path.join(process.argv[1], 'scripts/check-render-output.mjs'), 'utf8');
const marker = 'const SVG_TAG_TOKEN = ';
const at = source.indexOf(marker);
const lineEnd = source.indexOf('\n', at);
const NEW = new Function('return ' + source.slice(at + marker.length, lineEnd).replace(/;$/, ''))();
const OLD = /<!--[\s\S]*?(?:-->|$)|<!\[CDATA\[[\s\S]*?(?:\]\]>|$)|<(\/?)([A-Za-z][\w:-]*)(?=[\s/>])(?:=\s*"[^"]*"|=\s*'[^']*'|[^>"']|["'])*>/g;
if (NEW.source === OLD.source) throw new Error('the tag tokenizer alternation was not restructured');
const tokenize = (re, text) => Array.from(text.matchAll(re), (m) => [m.index, m[0], m[1] || '', m[2] || '']);
// The one documented degenerate corner where the old alternation fell back to a
// shorter tag: '=' followed by a complete quoted value that contains '>' with no
// '>' after the closing quote. Archify output XML-escapes attribute values, so
// this shape never reaches the tokenizer in generated artifacts.
const divergent = (text) => {
  const m = /=(?=\s*(?:"[^"]*>[^"]*"|'[^']*>'[^']*'))/.exec(text);
  if (!m) return false;
  const open = text.indexOf('"', m.index) !== -1 ? '"' : "'";
  const closeStart = text.indexOf(open, m.index + 1);
  const closeEnd = text.indexOf(open, closeStart + 1);
  return !text.slice(closeEnd + 1).includes('>');
};
const corpus = [
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">',
  '<g class="n" data-node-id="a1">', "<g data-note=it's>",
  '<path d="M0,0 L10,10"/>', '<rect x=1 y=2 width=3 height=4/>',
  '<!-- a <style> comment -->', '<![CDATA[ raw <ctx > data ]]>',
  '<title>Text with <img> inside</title>', "<a href='x'>",
  '<b = "unclosed', "<c ='x", "<d data-note=it's x=1>",
  '<e "quoted" literal>', '<f = >', '<g ==>', "<h ='='>",
  '<text>plain > text</text>', '</closing-tag>', '<k a="1" b=\'2\' c=3 d/>',
];
let mismatches = 0;
const check = (text) => {
  const a = tokenize(OLD, text), b = tokenize(NEW, text);
  if (JSON.stringify(a) !== JSON.stringify(b) && !divergent(text)) mismatches += 1;
};
corpus.forEach(check);
let seed = 0x12345678;
const rnd = () => { seed = (Math.imul(seed ^ (seed >>> 15), 1 | seed) + 0x6d2b79f5) >>> 0; return seed / 0xffffffff; };
const alpha = ['<', '>', 'a', 'b', '=', '"', "'", ' ', '/', ':', '\n'];
for (let i = 0; i < 40000; i += 1) {
  let text = '';
  const len = 1 + Math.floor(rnd() * 20);
  for (let j = 0; j < len; j += 1) text += alpha[Math.floor(rnd() * alpha.length)];
  check(text);
}
if (mismatches) throw new Error(`tokenizer language mismatch on ${mismatches} inputs`);
const pathological = '<a ' + '=""'.repeat(20000);
const t0 = performance.now();
Array.from(pathological.matchAll(NEW));
const ms = performance.now() - t0;
if (ms > 2000) throw new Error(`tokenizer still slow on pathological input: ${ms}ms`);
console.log(JSON.stringify({ mismatches: 0, ms: Math.round(ms), passed: true }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({"mismatches": 0, "passed": True}, {k: payload[k] for k in ("mismatches", "passed")})
        self.assertLess(payload["ms"], 2000)

    def test_strip_tags_cannot_leave_a_complete_tag(self) -> None:
        program = r"""
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
const source = fs.readFileSync(path.join(process.argv[1], 'scripts/check-render-output.mjs'), 'utf8');
const start = source.indexOf('function stripTags(value) {');
const end = source.indexOf('\n}', start) + 2;
assert.ok(start >= 0);
const stripTags = vm.runInNewContext('(' + source.slice(start, end) + ')', {});
const TAG = /<[A-Za-z/][^>]*>/;
const alphabet = ['<', '>', 'a', 'b', '"', '/'];
let cases = 0;
const check = (value) => {
  cases += 1;
  const out = stripTags(value);
  assert.doesNotMatch(out, TAG, JSON.stringify(value) + ' -> ' + JSON.stringify(out));
};
for (let len = 0; len <= 6; len += 1) {
  const total = alphabet.length ** len;
  for (let i = 0; i < total; i += 1) {
    let value = '', n = i;
    for (let j = 0; j < len; j += 1) { value += alphabet[n % alphabet.length]; n = Math.floor(n / alphabet.length); }
    check(value);
  }
}
for (const payload of [
  '<scr<script>ipt>alert(1)</scr</script>ipt>',
  '<img<img src=x onerror=alert(1)> src=y>',
  '<<script>script>alert(1)<</script>/script>',
  '<img src="a>b" onerror=alert(1)>',
  '<a b="</script>x">',
  '<b<c>old</c>ad>',
  '<<in>img src=x onerror=alert(1)>',
  'i<3<t>ag>',
]) check(payload);
console.log(JSON.stringify({ cases, passed: true }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["passed"])
        self.assertGreater(payload["cases"], 50000)


if __name__ == "__main__":
    unittest.main()
