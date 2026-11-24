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
from xml.dom import minidom

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
const cases=[
  [{},view=>view.navigateToRelativeHtml('child.html'),true,['child.html?from=parent.html'],[]],
  [{search:'?from=parent.html&theme=dark'},view=>view.navigateToParent(),true,['parent.html?theme=dark'],[]],
  [{parentHref:'up.html#top'},view=>view.navigateToParent(),true,['up.html#top'],[]],
  [{},view=>view.renderDrilldowns(drilldowns('child.html')),undefined,[],['child.html?from=parent.html']],
];
for(const [options,run,expected,navigations,links] of cases){
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
const allowed=[
  ['child.html','child.html'],['child.html?from=parent.html#top','child.html?from=parent.html#top'],['../dir/child.html','../dir/child.html'],
  ['/docs/child.html','/docs/child.html'],['#fragment','#fragment'],['?theme=dark','?theme=dark'],['  child.html\t\n','child.html'],
  ['/example.invalid/x.html','/example.invalid/x.html'],
  ['https://example.invalid/a b.html','https://example.invalid/a b.html'],['HTTP://EXAMPLE.INVALID/x.html','HTTP://EXAMPLE.INVALID/x.html'],
  ['file:///abs/path/x.html','file:///abs/path/x.html'],['\u0001 file:///abs/path/x.html ','file:///abs/path/x.html'],
];
for(const [href,expected] of allowed) assert.equal(guard(href),expected,JSON.stringify(href));
console.log(JSON.stringify({sites:cases.length,hostile:hostile.length,allowed:allowed.length,passed:true}));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"sites": 4, "hostile": 13, "allowed": 12, "passed": True}, json.loads(result.stdout))

    def test_drilldown_anchor_emission_refuses_unsafe_schemes(self) -> None:
        program = r"""
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const {wrapSingleChildAnchor} = await import(pathToFileURL(path.join(process.argv[1], 'renderers/shared/cli.mjs')));
const markup = '<g id="n"><rect width="4" height="4"/></g>';
const wrapped = wrapSingleChildAnchor(markup, [{ href: 'child.html#focus=n', label: 'Child' }]);
if (!wrapped.includes('class="archify-drilldown-link"') || !wrapped.includes('href="child.html#focus=n"')) throw new Error('legal sibling target must keep its anchor');
const hostile = ['javascript:alert(1)', 'JavaScript:alert(1)', 'data:text/html,<script>alert(1)</script>', 'vbscript:msgbox(1)', '//example.invalid/x.html', 'https://example.invalid/x.html', 'sub/dir.html', '../up.html'];
let rejected = 0;
for (const href of hostile) {
  if (wrapSingleChildAnchor(markup, [{ href, label: 'X' }]) === markup) rejected += 1;
}
console.log(JSON.stringify({ wrapped: true, rejected, expected: hostile.length, passed: rejected === hostile.length }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"wrapped": True, "rejected": 8, "expected": 8, "passed": True}, json.loads(result.stdout))

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

    def test_analysis_client_helpers_escape_every_payload_field(self) -> None:
        program = r"""
        import assert from 'node:assert/strict';
        import fs from 'node:fs';
        import path from 'node:path';
        import vm from 'node:vm';

        // Every markup helper of overlay.js, atlas.js and atlas3d.js is driven with a
        // document in which each value it reads is hostile: a quote that breaks out of
        // a quoted attribute and an <img> that fires a handler. A small DOM parses what
        // each innerHTML / outerHTML write receives, so rendered rows can be clicked
        // the way a reader would, and the run fails while any write still carries a
        // raw payload or an event-handler attribute.
        const CLIENT = path.join(process.argv[1], 'modules/code-analysis/overlay/client');

        // Each hostile value starts with its field number, so a value cut short by
        // slice() still names its field. P() breaks out of a quoted attribute and
        // opens an element; PID() has no quote, so it also serves as an identifier.
        const FIELDS = [];
        const P = (name) => { FIELDS.push(name); return `P.F${FIELDS.length}"><img src=x onerror=P.F${FIELDS.length}>`; };
        const PID = (name) => { FIELDS.push(name); return `P.F${FIELDS.length}<img src=x onerror=P.F${FIELDS.length}>`; };
        const fieldName = (n) => FIELDS[Number(n) - 1];
        // A field number followed by a raw quote or angle bracket was not escaped.
        const RAW = /p\.f(\d+)(?=["'><])/gi;

        // ---- a small DOM: one tree, parsed markup, selectors, bubbling events ----
        const VOID = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr']);
        const RAWTEXT = new Set(['script', 'style', 'textarea', 'title']);
        const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: '\u00a0' };
        const decode = (s) => s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => e[0] === '#' ? String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)) : (Object.hasOwn(ENTITIES, e) ? ENTITIES[e] : m));
        const textNode = (data, parent) => ({ nodeType: 3, data, parentNode: parent });

        function parseHtml(html, doc) {
          const holder = doc.createElement('#fragment');
          const stack = [holder];
          const text = (data) => { if (data) stack[stack.length - 1].childNodes.push(textNode(decode(data), stack[stack.length - 1])); };
          let i = 0;
          while (i < html.length) {
            const lt = html.indexOf('<', i);
            if (lt < 0) { text(html.slice(i)); break; }
            if (lt > i) text(html.slice(i, lt));
            if (html.startsWith('<!--', lt)) { const end = html.indexOf('-->', lt + 4); i = end < 0 ? html.length : end + 3; continue; }
            if (html.startsWith('</', lt)) {
              const end = html.indexOf('>', lt + 2) < 0 ? html.length : html.indexOf('>', lt + 2);
              const name = html.slice(lt + 2, end).trim().toLowerCase();
              for (let k = stack.length - 1; k > 0; k -= 1) if (stack[k].localName === name) { stack.length = k; break; }
              i = end + 1;
              continue;
            }
            let j = lt + 1, quote = null;
            while (j < html.length) { const ch = html[j]; if (quote) { if (ch === quote) quote = null; } else if (ch === '"' || ch === "'") quote = ch; else if (ch === '>') break; j += 1; }
            const raw = html.slice(lt + 1, j);
            i = j + 1;
            const selfClose = raw.endsWith('/');
            const body = selfClose ? raw.slice(0, -1) : raw;
            const nameMatch = body.match(/^[^\s/>]+/);
            const name = nameMatch ? nameMatch[0].toLowerCase() : '';
            if (!name) continue;
            const el = doc.createElement(name);
            const attrRe = /([^\s=/>]+)(?:\s*=\s*("([^"]*)"|'([^']*)'|[^\s>]*))?/g;
            attrRe.lastIndex = nameMatch[0].length;
            let m;
            while ((m = attrRe.exec(body))) el.attributes[m[1].toLowerCase()] = decode(m[3] !== undefined ? m[3] : m[4] !== undefined ? m[4] : (m[2] || ''));
            const top = stack[stack.length - 1];
            el.parentNode = top; top.childNodes.push(el);
            if (RAWTEXT.has(name)) {
              const close = html.toLowerCase().indexOf('</' + name, i);
              const rawText = html.slice(i, close < 0 ? html.length : close);
              if (rawText) el.childNodes.push(textNode(rawText, el));
              i = close < 0 ? html.length : html.indexOf('>', close) + 1;
            } else if (!selfClose && !VOID.has(name)) stack.push(el);
          }
          return holder;
        }

        // Selectors: comma lists of compounds joined by a descendant or ">" combinator.
        function parseCompound(token) {
          const compound = { tag: null, id: null, classes: [], attrs: [] };
          const rest = token.replace(/^([a-zA-Z][\w-]*)/, (t) => { compound.tag = t.toLowerCase(); return ''; });
          const re = /#([\w-]+)|\.([\w-]+)|\[([\w:-]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\]\s]*))?\]/g;
          let m;
          while ((m = re.exec(rest))) {
            if (m[1]) compound.id = m[1];
            else if (m[2]) compound.classes.push(m[2]);
            else compound.attrs.push([m[3].toLowerCase(), (m[4] ?? '').replace(/^["']|["']$/g, '')]);
          }
          if (rest.replace(re, '').trim()) throw new SyntaxError('unsupported selector ' + token);
          return compound;
        }
        function parseSelector(selector) {
          return selector.split(',').map((one) => {
            const parts = [];
            let current = '', depth = 0, quote = null;
            for (const ch of one) {
              if (quote) { current += ch; if (ch === quote) quote = null; continue; }
              if (ch === '"' || ch === "'") { quote = ch; current += ch; continue; }
              if (ch === '[') depth += 1; else if (ch === ']') depth -= 1;
              if (!depth && /[>+~]/.test(ch)) { if (current.trim()) parts.push([' ', current.trim()]); parts.push([ch, '']); current = ''; continue; }
              if (!depth && /\s/.test(ch)) { if (current.trim()) parts.push([' ', current.trim()]); current = ''; continue; }
              current += ch;
            }
            if (current.trim()) parts.push([' ', current.trim()]);
            const complexes = [];
            let combinator = ' ';
            for (const [joiner, token] of parts) { if (!token) { combinator = joiner; continue; } complexes.push({ compound: parseCompound(token), combinator }); combinator = ' '; }
            return complexes;
          });
        }
        function matchCompound(el, c) {
          if (c.tag && el.localName !== c.tag) return false;
          if (c.id && el.id !== c.id) return false;
          if (!c.classes.every((k) => el.classList.contains(k))) return false;
          return c.attrs.every(([name, value]) => el.hasAttribute(name) && (value === '' || el.getAttribute(name) === value));
        }
        function matchComplex(el, complexes, i = complexes.length - 1) {
          if (!matchCompound(el, complexes[i].compound)) return false;
          if (i === 0) return true;
          const { combinator } = complexes[i];
          for (let p = el.parentNode; p && p.nodeType === 1; p = combinator === '>' ? null : p.parentNode) if (matchComplex(p, complexes, i - 1)) return true;
          return false;
        }
        const matches = (el, selector) => parseSelector(selector).some((complexes) => matchComplex(el, complexes));

        const captured = [];
        let runLabel = '';
        const ctxProxy = () => new Proxy({}, {
          get(target, key) {
            if (key in target) return target[key];
            if (key === 'measureText') return () => ({ width: 12 });
            if (key === 'createLinearGradient' || key === 'createRadialGradient' || key === 'createPattern') return () => ({ addColorStop() {} });
            if (key === 'canvas') return null;
            return () => {};
          },
          set(target, key, value) { target[key] = value; return true; },
        });

        class El {
          constructor(doc, tag) {
            this.ownerDocument = doc; this.localName = tag; this.tagName = tag.toUpperCase(); this.nodeType = 1;
            this.childNodes = []; this.attributes = Object.create(null); this._listeners = {};
            this.style = { setProperty() {}, removeProperty() {} };
            this.value = ''; this.scrollTop = 0; this.tabIndex = 0; this.lang = '';
            this.offsetWidth = 60; this.offsetHeight = 18; this.offsetTop = 0; this.offsetLeft = 0;
            this.clientWidth = 640; this.clientHeight = 480;
          }
          get parentNode() { return this._parent; }
          set parentNode(v) { this._parent = v; }
          get parentElement() { return this._parent && this._parent.nodeType === 1 ? this._parent : null; }
          get children() { return this.childNodes.filter((n) => n.nodeType === 1); }
          get firstElementChild() { return this.children[0] || null; }
          get isConnected() { for (let p = this; p; p = p.parentNode) if (p === p.ownerDocument.documentElement) return true; return false; }
          get id() { return this.getAttribute('id') || ''; }
          set id(v) { this.setAttribute('id', v); }
          get className() { return this.getAttribute('class') || ''; }
          set className(v) { this.setAttribute('class', v); }
          get title() { return this.getAttribute('title') || ''; }
          set title(v) { this.setAttribute('title', v); }
          get type() { return this.getAttribute('type') || ''; }
          set type(v) { this.setAttribute('type', v); }
          get classList() {
            const el = this;
            const list = () => (el.className || '').split(/\s+/).filter(Boolean);
            const add = (...names) => { const all = list(); names.forEach((n) => { if (!all.includes(n)) all.push(n); }); el.className = all.join(' '); };
            const remove = (...names) => { el.className = list().filter((n) => !names.includes(n)).join(' '); };
            const contains = (n) => list().includes(n);
            const toggle = (n, force) => { const on = force === undefined ? !contains(n) : !!force; if (on) add(n); else remove(n); return on; };
            return { add, remove, contains, toggle };
          }
          get dataset() {
            const el = this;
            const name = (k) => 'data-' + String(k).replace(/[A-Z]/g, (c) => '-' + c.toLowerCase());
            return new Proxy({}, {
              get: (_, k) => el.getAttribute(name(k)),
              set: (_, k, v) => { el.setAttribute(name(k), v == null ? '' : String(v)); return true; },
              has: (_, k) => el.hasAttribute(name(k)),
            });
          }
          setAttribute(k, v) { this.attributes[String(k).toLowerCase()] = String(v); }
          getAttribute(k) { const key = String(k).toLowerCase(); return Object.hasOwn(this.attributes, key) ? this.attributes[key] : null; }
          hasAttribute(k) { return Object.hasOwn(this.attributes, String(k).toLowerCase()); }
          removeAttribute(k) { delete this.attributes[String(k).toLowerCase()]; }
          _adopt(child) { if (child.parentNode) child.parentNode.childNodes = child.parentNode.childNodes.filter((n) => n !== child); child.parentNode = this; }
          appendChild(child) { this._adopt(child); this.childNodes.push(child); return child; }
          append(...nodes) { nodes.forEach((n) => this.appendChild(n)); }
          prepend(...nodes) { nodes.forEach((n) => { this._adopt(n); }); this.childNodes.unshift(...nodes); }
          insertBefore(child, ref) { this._adopt(child); const at = ref ? this.childNodes.indexOf(ref) : -1; if (at < 0) this.childNodes.push(child); else this.childNodes.splice(at, 0, child); return child; }
          _sibling(nodes, offset) { const parent = this.parentNode; if (!parent) return; const at = parent.childNodes.indexOf(this) + offset; nodes.forEach((n, i) => { n.parentNode = parent; parent.childNodes.splice(at + i, 0, n); }); }
          before(...nodes) { this._sibling(nodes, 0); }
          after(...nodes) { this._sibling(nodes, 1); }
          remove() { if (this.parentNode) this.parentNode.childNodes = this.parentNode.childNodes.filter((n) => n !== this); this.parentNode = null; }
          add(option) { this.appendChild(option); if (this.value === '' && option.value !== undefined) this.value = option.value; }
          get textContent() { return this.childNodes.map((n) => (n.nodeType === 3 ? n.data : n.textContent)).join(''); }
          set textContent(v) { this.childNodes = v ? [textNode(String(v), this)] : []; }
          set innerHTML(v) {
            const html = String(v);
            this.childNodes = parseHtml(html, this.ownerDocument).childNodes;
            this.childNodes.forEach((n) => { n.parentNode = this; });
            captured.push({ el: this, html, run: runLabel });
          }
          set outerHTML(v) { const html = String(v); const nodes = parseHtml(html, this.ownerDocument).childNodes; this._sibling(nodes, 0); this.remove(); captured.push({ el: this, html, run: runLabel }); }
          querySelectorAll(selector) {
            const out = [];
            const visit = (node) => { for (const child of node.childNodes) { if (child.nodeType !== 1) continue; if (matches(child, selector)) out.push(child); visit(child); } };
            visit(this);
            return out;
          }
          querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
          closest(selector) { for (let p = this; p && p.nodeType === 1; p = p.parentNode) if (matches(p, selector)) return p; return null; }
          contains(node) { for (let p = node; p; p = p.parentNode) if (p === this) return true; return false; }
          addEventListener(type, fn, options) { const capture = options === true || !!(options && options.capture); const list = (this._listeners[type] = this._listeners[type] || { bubble: [], capture: [] }); list[capture ? 'capture' : 'bubble'].push(fn); }
          removeEventListener() {}
          dispatchEvent(type, init = {}) {
            const chain = []; for (let p = this; p && p.nodeType === 1; p = p.parentNode) chain.unshift(p);
            let stopped = false;
            const event = { type, target: this, defaultPrevented: false, key: '', ...init, preventDefault() { this.defaultPrevented = true; }, stopPropagation() { stopped = true; }, stopImmediatePropagation() { stopped = true; this._immediate = true; } };
            const run = (node, phase) => { const list = (node._listeners[type] || {})[phase] || []; for (const fn of list.slice()) { event.currentTarget = node; fn.call(node, event); if (event._immediate) break; } };
            for (let k = 0; k < chain.length - 1 && !stopped; k += 1) run(chain[k], 'capture');
            if (!stopped) run(this, 'capture');
            if (!stopped) run(this, 'bubble');
            for (let k = chain.length - 2; k >= 0 && !stopped; k -= 1) run(chain[k], 'bubble');
            return !event.defaultPrevented;
          }
          click() { return this.dispatchEvent('click', {}); }
          focus() { this.ownerDocument.activeElement = this; }
          blur() { if (this.ownerDocument.activeElement === this) this.ownerDocument.activeElement = null; }
          select() {}
          scrollIntoView() {}
          getBoundingClientRect() { return { left: 0, top: 0, right: 640, bottom: 480, width: 640, height: 480, x: 0, y: 0 }; }
          getClientRects() { return [{}]; }
          getBBox() { return { x: 0, y: 0, width: 10, height: 10 }; }
          getTotalLength() { return 100; }
          getPointAtLength() { return { x: 50, y: 50 }; }
          getContext() { return ctxProxy(); }
        }

        const pathOf = (el) => {
          const names = [];
          for (let p = el; p && p.localName !== '#fragment' && p.localName !== 'html'; p = p.parentNode) {
            names.unshift(p.localName + (p.id ? '#' + p.id : p.className ? '.' + p.className.trim().split(/\s+/).slice(0, 2).join('.') : ''));
            if (!p.parentNode) break;
          }
          return names.join(' > ') || '(detached)';
        };

        function makeDocument({ analysis, atlas, atlas3dData, standalone }) {
          const doc = { activeElement: null, hidden: false, addEventListener() {}, removeEventListener() {} };
          doc.createElement = (tag) => new El(doc, tag);
          doc.createElementNS = (ns, tag) => new El(doc, tag);
          const html = doc.createElement('html'), body = doc.createElement('body');
          doc.documentElement = html; doc.body = body; html.appendChild(body);
          const header = doc.createElement('div'); header.className = 'header'; body.appendChild(header);
          const toolbar = doc.createElement('div'); toolbar.className = 'toolbar'; body.appendChild(toolbar);
          toolbar.appendChild(doc.createElement('div')).className = 'export-wrap';
          if (standalone) body.appendChild(doc.createElement('div')).className = 'analysis-stage';
          else {
            const svg = doc.createElement('svg'); body.appendChild(svg);
            for (const id of ['C1', 'C3']) {
              const g = svg.appendChild(doc.createElement('g'));
              g.setAttribute('data-node-id', id); g.setAttribute('data-node-sublabel', analysis.sub || '');
              const path = g.appendChild(doc.createElement('path')); path.setAttribute('data-edge-from', id); path.setAttribute('data-edge-to', 'C2'); path.setAttribute('d', 'M0,0 L10,10');
            }
            const container = doc.createElement('div'); container.className = 'diagram-container'; body.appendChild(container);
          }
          doc.querySelector = (sel) => html.querySelector(sel);
          doc.querySelectorAll = (sel) => html.querySelectorAll(sel);
          doc.getElementById = (id) => {
            if (id === 'bauify-analysis') return { textContent: JSON.stringify(analysis) };
            if (id === 'bauify-atlas-data') return { textContent: JSON.stringify(atlas) };
            if (id === 'bauify-atlas3d-data') return { textContent: JSON.stringify(atlas3dData || {}) };
            return html.querySelector('#' + id);
          };
          return doc;
        }

        // The shipped translator: a bundled-table lookup, then raw {key} substitution.
        const translate = () => (key, values = {}) => String(key).replace(/\{([A-Za-z][A-Za-z0-9]*)\}/g, (m, k) => (Object.hasOwn(values, k) ? String(values[k]) : m));

        function makeEnv(options) {
          const doc = makeDocument(options);
          const sandbox = {
            document: doc, console: { log() {}, info() {}, warn() {}, error() {} }, performance, URL, Blob,
            setTimeout: () => 1, clearTimeout() {},
            requestAnimationFrame: () => 1, cancelAnimationFrame() {},
            innerWidth: 1400, innerHeight: 900, devicePixelRatio: 1,
            addEventListener() {}, removeEventListener() {},
            matchMedia: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }),
            getComputedStyle: () => ({ getPropertyValue: () => '' }),
            navigator: { clipboard: undefined, platform: 'test', userAgent: 'test' },
            location: { pathname: '/reports/x.html', search: '', hash: '', assign() {}, replace() {}, reload() {} },
            sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
            MutationObserver: class { observe() {} disconnect() {} },
            ResizeObserver: class { observe() {} disconnect() {} },
            MouseEvent: class { constructor(type, init) { this.type = type; Object.assign(this, init || {}); } },
            Option: class { constructor(label, value) { this.text = label; this.value = value; } },
            __archifyMakeAnalysisTranslator: () => translate({}),
            __archifyWireVerification: () => {},
          };
          sandbox.window = sandbox; sandbox.globalThis = sandbox; sandbox.self = sandbox;
          return { doc, sandbox };
        }

        // Loads one client script the way the page does.
        const run = (env, file) => vm.runInNewContext(fs.readFileSync(path.join(CLIENT, file), 'utf8'), env.sandbox, { filename: file, timeout: 20000 });

        // ---- the hostile documents the clients read -------------------------
        const FILE_A = 'pkg/' + P('path FILE_A') + '/a.py';
        const FILE_B = 'pkg/b' + P('path FILE_B') + '.py';
        const FILE_D = 'src/' + P('path FILE_D') + '.d.ts';
        // Captured source: hostile text on every line, under each kind of change marker.
        const snippet = (tag, changes, count) => ({
          lines: Array.from({ length: count }, (_, i) => (i % 2 ? `  return ${P(`${tag}.lines[${i}]`)} # ` : `def f${i}():  # ${P(`${tag}.lines[${i}]`)}`)),
          changes,
        });
        const SNIPPETS = {
          [FILE_A]: snippet('snippets[FILE_A]', { status: 'modified', added: [2], modified: [], deleted: [{ after: 1, count: P('snippets[FILE_A].changes.deleted[0].count') }] }, 14),
          [FILE_B]: snippet('snippets[FILE_B]', { status: 'added', added: [1], modified: [], deleted: [] }, 5),
          [FILE_D]: snippet('snippets[FILE_D]', { status: 'unavailable', added: [], modified: [], deleted: [] }, 3),
        };
        // Finding identifiers: hostile, yet still usable as object keys and in selectors.
        const F_HUB = PID('finding FHUB id'), F_BND = PID('finding FBND id'), F_CYC = PID('finding FCYC id'), F_MOD = PID('finding FMOD id');
        const F_LEAK = PID('finding FLEAK id'), F_CONC = PID('finding FCONC id'), F_CX = PID('finding FCX id'), F_CXA = PID('finding FCXA id');
        const F_DUP = PID('finding FDUP id'), F_EXT = PID('finding FEXT id'), F_EXT2 = PID('finding FEXT2 id'), F_EXT3 = PID('finding FEXT3 id');
        const F_ODD = PID('finding FODD id'), F_NEW = PID('finding FNEW id'), F_CHG = PID('finding FCHG id'), F_OFF = PID('finding FOFF id');
        const IDS = [F_HUB, F_BND, F_CYC, F_MOD, F_LEAK, F_CONC, F_CX, F_CXA, F_DUP, F_EXT, F_EXT2, F_EXT3, F_ODD, F_NEW, F_CHG, F_OFF];

        // One analysis document. Every value a markup helper reads is hostile, except
        // the few that select a branch (rule and indicator keys, component and module
        // identifiers, finding identifiers), which keep their shape.
        function overlayAnalysis(tweak = () => {}) {
          const finding = (id, code, extra) => ({
            id, code,
            dimension: P(`finding ${id} dimension`), severity: P(`finding ${id} severity`), message: P(`finding ${id} message`),
            componentIds: ['C1'], moduleIds: ['M1', 'M2'], reviewTarget: P(`finding ${id} reviewTarget`),
            ...extra,
          });
          const place = (file, tag) => ({ file, line: P(`${tag}.line`), to: P(`${tag}.to`) });
          const measures = (tag) => ({ complexity: P(`${tag}.complexity`), nesting: P(`${tag}.nesting`), length: P(`${tag}.evidence.length`) });
          const analysis = {
            ui: { locale: 'en', messages: {}, resume: { command: P('ui.resume.command') } },
            repository: {
              url: P('repository.url'), language: P('repository.language'), root: P('repository.root'), revision: P('repository.revision'),
              baseRevision: P('repository.baseRevision'), sourceKind: 'working-tree', snapshotId: P('repository.snapshotId'),
            },
            sub: P('diagram node sublabel'),
            totals: { modules: P('totals.modules'), edges: P('totals.edges') },
            architectureBrief: P('architectureBrief'),
            verification: null,
            unmapped: [{
              id: 'U1', label: P('unmapped[0].label'), path: P('unmapped[0].path'), files: P('unmapped[0].files'), loc: P('unmapped[0].loc'),
              fanIn: P('unmapped[0].fanIn'), fanOut: P('unmapped[0].fanOut'),
              fileList: [{ path: FILE_D, module: 'U1', findings: [], loc: P('unmapped[0].fileList[0].loc'), importsOut: P('unmapped[0].fileList[0].importsOut'), importedBy: P('unmapped[0].fileList[0].importedBy') }],
            }],
            components: [
              {
                id: 'C1', label: P('components[C1].label'),
                modules: [
                  { id: 'M1', label: P('components[C1].modules[M1].label'), path: P('components[C1].modules[M1].path'), files: P('components[C1].modules[M1].files'), loc: P('components[C1].modules[M1].loc'), fanIn: P('components[C1].modules[M1].fanIn'), fanOut: P('components[C1].modules[M1].fanOut') },
                  { id: 'M2', label: P('components[C1].modules[M2].label'), path: P('components[C1].modules[M2].path'), files: 1, loc: 3, fanIn: 1, fanOut: 1 },
                ],
                indicators: { status: 'amber', items: [
                  { key: 'instability', label: P('indicators[instability].label'), status: P('indicators[instability].status'), findings: [F_HUB, F_BND], detail: [], value: P('indicators[instability].value'), fanIn: P('indicators[instability].fanIn'), fanOut: P('indicators[instability].fanOut'), instability: P('indicators[instability].instability') },
                  { key: 'cycle', label: P('indicators[cycle].label'), status: P('indicators[cycle].status'), findings: [F_CYC, F_MOD], detail: [P('indicators[cycle].detail[0]'), 'component:C2', P('indicators[cycle].detail[2]')], value: P('indicators[cycle].value') },
                  { key: 'hub', label: P('indicators[hub].label'), status: P('indicators[hub].status'), findings: [F_HUB, F_CONC], detail: [], value: P('indicators[hub].value') },
                  { key: 'boundary', label: P('indicators[boundary].label'), status: P('indicators[boundary].status'), findings: [F_BND, F_LEAK], detail: [], value: P('indicators[boundary].value') },
                  { key: 'complexity', label: P('indicators[complexity].label'), status: P('indicators[complexity].status'), findings: [F_CX, F_CXA, F_NEW, F_CHG], detail: [], value: P('indicators[complexity].value') },
                  { key: PID('indicators[external].key'), label: P('indicators[external].label'), status: P('indicators[external].status'), findings: [F_EXT, F_EXT2, F_EXT3], detail: [], value: P('indicators[external].value') },
                  { key: 'dup', label: P('indicators[dup].label'), status: P('indicators[dup].status'), findings: [F_DUP, F_ODD], detail: [], value: P('indicators[dup].value') },
                ] },
                ambiguousModules: [P('components[C1].ambiguousModules[0]'), P('components[C1].ambiguousModules[1]')],
                files: P('components[C1].files'), loc: P('components[C1].loc'), internalImports: P('components[C1].internalImports'),
                incoming: [
                  { component: 'C3', weight: P('components[C1].incoming[0].weight'), evidence: [place(FILE_A, 'components[C1].incoming[0].evidence[0]'), place(FILE_B, 'components[C1].incoming[0].evidence[1]')] },
                  { module: 'M9', ambiguous: true, weight: P('components[C1].incoming[1].weight'), evidence: [place(FILE_D, 'components[C1].incoming[1].evidence[0]')] },
                ],
                outgoing: [
                  { component: 'C2', weight: P('components[C1].outgoing[0].weight'), evidence: [place(FILE_A, 'components[C1].outgoing[0].evidence[0]')] },
                  { module: 'M9', weight: P('components[C1].outgoing[1].weight'), evidence: [place(FILE_B, 'components[C1].outgoing[1].evidence[0]')] },
                ],
                fileList: [
                  { path: FILE_A, module: 'M1', findings: [{ id: F_CX }], loc: P('fileList[FILE_A].loc'), importsOut: P('fileList[FILE_A].importsOut'), importedBy: P('fileList[FILE_A].importedBy') },
                  { path: FILE_B, module: 'M2', findings: [], loc: P('fileList[FILE_B].loc'), importsOut: P('fileList[FILE_B].importsOut'), importedBy: P('fileList[FILE_B].importedBy') },
                ],
                findings: [{ id: F_HUB }, { id: F_BND }],
              },
              // Never opened itself: its status is not a level, and it is the target of C1's dependency row.
              {
                id: 'C2', label: P('components[C2].label'), modules: [], indicators: { status: P('components[C2].indicators.status'), items: [] }, ambiguousModules: [],
                files: P('components[C2].files'), loc: P('components[C2].loc'), internalImports: P('components[C2].internalImports'), incoming: [], outgoing: [], fileList: [], findings: [],
              },
              {
                id: 'C3', label: P('components[C3].label'),
                modules: [{ id: 'M3', label: P('components[C3].modules[M3].label'), path: P('components[C3].modules[M3].path'), files: P('components[C3].modules[M3].files'), loc: P('components[C3].modules[M3].loc'), fanIn: P('components[C3].modules[M3].fanIn'), fanOut: P('components[C3].modules[M3].fanOut') }],
                // `findings` is an object with a `length`, not an array: a count that is really a string.
                indicators: { status: 'green', items: [{ key: PID('indicators[k3].key'), label: P('indicators[k3].label'), status: P('indicators[k3].status'), findings: { length: P('indicators[k3].findings.length (object, not array)') }, detail: [], value: P('indicators[k3].value'), fanIn: P('indicators[k3].fanIn'), fanOut: P('indicators[k3].fanOut'), instability: P('indicators[k3].instability') }] },
                ambiguousModules: [], files: P('components[C3].files'), loc: P('components[C3].loc'), internalImports: P('components[C3].internalImports'),
                incoming: [], outgoing: [{ component: 'C2', weight: P('components[C3].outgoing[0].weight'), evidence: [place(FILE_A, 'components[C3].outgoing[0].evidence[0]')] }],
                fileList: [{ path: FILE_D, module: 'M3', findings: [{ id: F_ODD }], loc: P('fileList[FILE_D].loc'), importsOut: P('fileList[FILE_D].importsOut'), importedBy: P('fileList[FILE_D].importedBy') }],
                findings: [],
              },
            ],
            edges: [
              { from: 'C1', to: 'C2', weight: P('edges[0].weight'), declared: true, evidence: [place(FILE_A, 'edges[0].evidence[0]'), place(FILE_B, 'edges[0].evidence[1]')] },
              { from: 'C1', to: 'C3', weight: P('edges[1].weight'), declared: false, evidence: [place(FILE_D, 'edges[1].evidence[0]')] },
              { from: 'C3', to: 'C1', weight: P('edges[2].weight'), declared: false, evidence: [place(FILE_A, 'edges[2].evidence[0]')] },
            ],
            // One finding for each rule shape the reader distinguishes.
            findings: [
              finding(F_HUB, 'coupling/hub', {
                severity: 'error', subject: { module: 'M1' }, review: { status: 'accepted', reason: P('finding FHUB review.reason') },
                supportedFixes: [P('finding FHUB supportedFixes[0]'), P('finding FHUB supportedFixes[1]')],
                evidence: {
                  fanIn: P('finding FHUB evidence.fanIn'), fanOut: P('finding FHUB evidence.fanOut'),
                  dependents: [PID('finding FHUB dependents[0]'), PID('finding FHUB dependents[1]')], dependencies: [P('finding FHUB dependencies[0]')],
                  threshold: { fanIn: P('finding FHUB threshold.fanIn'), fanOut: P('finding FHUB threshold.fanOut') },
                },
              }),
              finding(F_BND, 'architecture/boundary', {
                subject: { file: FILE_A, line: P('finding FBND subject.line'), boundary: { from: P('finding FBND boundary.from'), to: P('finding FBND boundary.to') } },
                evidence: {
                  imports: [
                    { ...place(FILE_A, 'finding FBND imports[0]'), typeOnly: true },
                    { ...place(FILE_B, 'finding FBND imports[1]'), lazy: true },
                    place(FILE_D, 'finding FBND imports[2]'),
                  ],
                  rule: { reason: P('finding FBND rule.reason') }, totalImports: P('finding FBND totalImports'), files: [P('finding FBND files[0]')], kind: 'eager',
                },
              }),
              finding(F_CYC, 'coupling/import-cycle', {
                subject: { files: [P('finding FCYC subject.files[0]'), P('finding FCYC subject.files[1]'), P('finding FCYC subject.files[2]'), P('finding FCYC subject.files[3]')], file: FILE_A, line: P('finding FCYC subject.line') },
                evidence: {
                  path: [FILE_A, FILE_B], imports: [place(FILE_A, 'finding FCYC imports[0]')],
                  pathImports: [{ file: FILE_A, to: FILE_B, deferred: true, line: P('finding FCYC pathImports[0].line') }], kind: 'structural',
                },
              }),
              finding(F_MOD, 'coupling/cycle', {
                subject: { modules: [P('finding FMOD subject.modules[0]'), 'M2'], module: 'M2' },
                evidence: { path: ['M1', 'M2'], edges: [{ from: 'M1', to: 'M2', weight: P('finding FMOD edges[0].weight'), lazy: P('finding FMOD edges[0].lazy'), deferred: true }], kind: P('finding FMOD evidence.kind') },
              }),
              finding(F_LEAK, 'coupling/internal-leak', {
                subject: { module: 'M2', file: FILE_B, line: P('finding FLEAK subject.line') },
                evidence: {
                  imports: [place(FILE_A, 'finding FLEAK imports[0]'), place(FILE_D, 'finding FLEAK imports[1]')],
                  entries: [P('finding FLEAK entries[0]'), P('finding FLEAK entries[1]')], totalImports: P('finding FLEAK totalImports'),
                  consumers: [P('finding FLEAK consumers[0]')], internalFiles: [P('finding FLEAK internalFiles[0]')], moduleFiles: P('finding FLEAK moduleFiles'), kind: 'eager', entrySource: 'config',
                },
              }),
              finding(F_CONC, 'coupling/concentration', {
                subject: { file: FILE_A },
                evidence: {
                  reach: { dependents: P('finding FCONC reach.dependents'), modules: P('finding FCONC reach.modules'), share: P('finding FCONC reach.share') },
                  size: { share: P('finding FCONC size.share'), loc: P('finding FCONC size.loc'), totalLoc: P('finding FCONC size.totalLoc') },
                  loc: P('finding FCONC loc'), threshold: { fileLines: P('finding FCONC threshold.fileLines') },
                },
              }),
              finding(F_CX, 'complexity/function', {
                subject: { file: FILE_A, line: 7, endLine: P('finding FCX subject.endLine'), function: P('finding FCX subject.function') },
                evidence: { ...measures('finding FCX'), deepestLine: 9, threshold: { complexity: P('finding FCX threshold.complexity'), nesting: P('finding FCX threshold.nesting') } },
              }),
              finding(F_CXA, 'complexity/function', {
                subject: { file: FILE_A, line: P('finding FCXA subject.line'), endLine: P('finding FCXA subject.endLine'), function: P('finding FCXA subject.function') },
                evidence: {
                  risk: { loading: P('finding FCXA risk.loading'), loadingNote: P('finding FCXA risk.loadingNote') },
                  partialInitCandidate: {
                    entry: FILE_A, viaLine: P('finding FCXA viaLine'), importer: FILE_B, line: P('finding FCXA line'),
                    chain: [PID('finding FCXA chain[0]'), PID('finding FCXA chain[1]'), PID('finding FCXA chain[2]')], name: P('finding FCXA name'), boundAt: P('finding FCXA boundAt'),
                  },
                  ...measures('finding FCXA'), threshold: { complexity: P('finding FCXA threshold.complexity'), nesting: P('finding FCXA threshold.nesting') },
                  imports: [
                    { ...place(FILE_D, 'finding FCXA imports[0]'), typeOnly: true },
                    { ...place(FILE_A, 'finding FCXA imports[1]'), lazy: true },
                    place(FILE_B, 'finding FCXA imports[2]'),
                  ],
                },
              }),
              finding(F_DUP, 'redundancy/duplicate-block', {
                subject: { locations: [
                  { file: FILE_A, line: 2, endLine: P('finding FDUP locations[0].endLine'), column: P('finding FDUP locations[0].column'), endColumn: P('finding FDUP locations[0].endColumn') },
                  { file: FILE_B, line: P('finding FDUP locations[1].line'), endLine: P('finding FDUP locations[1].endLine'), column: P('finding FDUP locations[1].column'), endColumn: P('finding FDUP locations[1].endColumn') },
                  { file: FILE_D, line: P('finding FDUP locations[2].line'), endLine: 3, column: 2, endColumn: 5 },
                ] },
                evidence: { tokens: P('finding FDUP tokens'), lines: P('finding FDUP lines'), kind: 'renamed' },
              }),
              finding(F_EXT, P('finding FEXT code'), {
                external: {
                  tool: P('finding FEXT external.tool'), ruleId: P('finding FEXT external.ruleId'), sourceId: 'S1', binding: 'verified',
                  originalSeverity: P('finding FEXT external.originalSeverity'), reportPointer: P('finding FEXT external.reportPointer'),
                  helpUri: 'https://example.invalid/' + P('finding FEXT external.helpUri'),
                  locations: [
                    { file: FILE_A, line: 3, endLine: P('finding FEXT locations[0].endLine'), column: P('finding FEXT locations[0].column'), endColumn: P('finding FEXT locations[0].endColumn'), role: P('finding FEXT locations[0].role') },
                    { file: FILE_B, line: P('finding FEXT locations[1].line'), endLine: P('finding FEXT locations[1].endLine'), column: P('finding FEXT locations[1].column'), endColumn: P('finding FEXT locations[1].endColumn'), role: 'related' },
                    { file: FILE_D, line: P('finding FEXT locations[2].line'), endLine: P('finding FEXT locations[2].endLine'), column: P('finding FEXT locations[2].column'), endColumn: P('finding FEXT locations[2].endColumn') },
                  ],
                },
              }),
              finding(F_EXT2, 'external/review', {
                external: { tool: P('finding FEXT2 external.tool'), ruleId: P('finding FEXT2 external.ruleId'), sourceId: 'S1', binding: 'changed', helpUri: 'javascript:alert(1)', locations: [] },
                review: { status: 'accepted-changed', reason: P('finding FEXT2 review.reason') },
              }),
              finding(F_EXT3, 'external/other', {
                external: { tool: P('finding FEXT3 external.tool'), sourceId: 'S2', binding: P('finding FEXT3 external.binding'), locations: [{ file: P('finding FEXT3 locations[0].file'), line: P('finding FEXT3 locations[0].line') }] },
              }),
              finding(F_ODD, P('finding FODD code'), {
                componentIds: ['C3', 'C9'], moduleIds: ['M3', 'M9', 'M10'], review: { status: 'new' },
                evidence: { imports: [place(FILE_D, 'finding FODD imports[0]')] }, message: P('finding FODD message') + '\n\n' + P('finding FODD message line 3'),
              }),
              finding(F_NEW, 'complexity/function', {
                subject: { file: FILE_B, line: P('finding FNEW subject.line'), endLine: P('finding FNEW subject.endLine'), function: P('finding FNEW subject.function') },
                evidence: { ...measures('finding FNEW'), threshold: {} }, review: { status: 'new' },
              }),
              finding(F_OFF, 'coupling/concentration', {
                componentIds: [], moduleIds: ['U1', 'M9', 'M10'], subject: { module: 'U1' },
                evidence: { reach: { dependents: P('finding FOFF reach.dependents'), modules: P('finding FOFF reach.modules'), share: P('finding FOFF reach.share') } },
              }),
              finding(F_CHG, 'complexity/function', {
                subject: { file: FILE_D, line: P('finding FCHG subject.line'), endLine: P('finding FCHG subject.endLine'), function: P('finding FCHG subject.function') },
                evidence: { ...measures('finding FCHG'), deepestLine: P('finding FCHG deepestLine') }, review: { status: 'accepted-changed', reason: P('finding FCHG review.reason') },
              }),
            ],
            overview: {
              counts: { error: P('overview.counts.error'), warning: P('overview.counts.warning'), info: P('overview.counts.info'), findings: P('overview.counts.findings'), acceptedErrors: P('overview.counts.acceptedErrors'), accepted: P('overview.counts.accepted') },
              priorities: [F_HUB, F_CX, F_EXT, F_ODD],
              groups: [
                { code: 'coupling/hub', severity: P('overview.groups[0].severity'), count: P('overview.groups[0].count'), ids: [F_HUB, F_CONC] },
                { code: P('overview.groups[1].code'), severity: 'error', count: P('overview.groups[1].count'), ids: [F_ODD, F_NEW, F_CHG] },
              ],
              investigation: { architecture: { structuralSignals: [{ id: F_LEAK }, { id: F_MOD }] } },
              coverage: {
                language: P('overview.coverage.language'),
                files: {
                  analyzed: P('coverage.files.analyzed'), excludedByRole: P('coverage.files.excludedByRole'), excludedRoles: [P('coverage.files.excludedRoles[0]'), P('coverage.files.excludedRoles[1]')],
                  translationUnits: P('coverage.files.translationUnits'), notCompiled: P('coverage.files.notCompiled'),
                  parseErrors: [P('coverage.files.parseErrors[0]'), P('coverage.files.parseErrors[1]'), P('coverage.files.parseErrors[2]'), P('coverage.files.parseErrors[3]')],
                },
                otherLanguages: [{ adapter: P('coverage.otherLanguages[0].adapter'), files: P('coverage.otherLanguages[0].files') }],
                unresolved: { unknown: P('coverage.unresolved.unknown'), opaque: P('coverage.unresolved.opaque') },
                unmappedModules: [P('coverage.unmappedModules[0]')], ambiguousModules: [P('coverage.ambiguousModules[0]')],
                rules: { run: ['coupling/hub', P('coverage.rules.run[1]'), 'redundancy/duplicate-block', 'conventions/x'], suppressed: [P('coverage.rules.suppressed[0]'), P('coverage.rules.suppressed[1]')] },
                duplicates: { complete: P('coverage.duplicates.complete'), analyzed: P('coverage.duplicates.analyzed'), selected: P('coverage.duplicates.selected') },
                boundaries: { layers: [{ name: P('coverage.boundaries.layers[0].name') }, { name: P('coverage.boundaries.layers[1].name'), files: ['a'] }], rules: P('coverage.boundaries.rules') },
                external: [
                  {
                    id: 'S1', code: P('coverage.external[S1].code'), tool: P('coverage.external[S1].tool'), toolVersion: P('coverage.external[S1].toolVersion'), format: P('coverage.external[S1].format'),
                    status: 'partial', binding: 'changed', suppressed: P('coverage.external[S1].suppressed'), reportFile: P('coverage.external[S1].reportFile'),
                    notices: [{ message: P('coverage.external[S1].notices[0].message') }, { message: P('coverage.external[S1].notices[1].message') }],
                    // Again a `length` that is not a count.
                    coverage: { complete: 'yes', files: { length: P('coverage.external[S1].coverage.files.length (object, not array)') } },
                  },
                  {
                    id: 'S2', code: P('coverage.external[S2].code'), tool: P('coverage.external[S2].tool'), format: P('coverage.external[S2].format'),
                    status: 'imported', binding: 'verified', suppressed: 0, reportFile: P('coverage.external[S2].reportFile'), notices: [], coverage: { complete: false, files: [] },
                  },
                ],
              },
              review: {
                comparison: {
                  comparable: 'yes',
                  notDetected: [
                    { code: P('review.comparison.notDetected[0].code'), message: P('review.comparison.notDetected[0].message'), likelyCause: P('review.comparison.notDetected[0].likelyCause') },
                    { code: 'coupling/hub', message: P('review.comparison.notDetected[1].message') },
                  ],
                  fixed: [], new: [P('review.comparison.new[0]')], evidenceChanged: [P('review.comparison.evidenceChanged[0]')],
                  reasons: [P('review.comparison.reasons[0]'), { message: P('review.comparison.reasons[1].message'), code: P('review.comparison.reasons[1].code') }],
                },
                baseline: {
                  accepted: P('review.baseline.accepted'), changed: { length: P('review.baseline.changed.length (object, not array)') },
                  stale: [{ id: P('review.baseline.stale[0].id'), code: P('review.baseline.stale[0].code'), reason: P('review.baseline.stale[0].reason') }],
                },
              },
            },
            snippets: SNIPPETS,
            tasks: Object.fromEntries(IDS.map((id) => [id, {
              markdown: P(`tasks[${id}].markdown`),
              task: {
                taskId: P(`tasks[${id}].task.taskId`), source: { snapshotId: P(`tasks[${id}].task.source.snapshotId`) },
                evidence: { status: P(`tasks[${id}].task.evidence.status`), reason: P(`tasks[${id}].task.evidence.reason`), checkedAt: P(`tasks[${id}].task.evidence.checkedAt`) },
                locations: [{ file: FILE_A, startLine: 2, endLine: P(`tasks[${id}].task.locations[0].endLine`) }, { file: FILE_B, startLine: P(`tasks[${id}].task.locations[1].startLine`), endLine: P(`tasks[${id}].task.locations[1].endLine`) }],
              },
            }])),
          };
          // More findings than one page of the list holds.
          analysis.findings.push(...Array.from({ length: 30 }, (_, i) => finding(PID(`list finding ${i} id`), 'coupling/hub', { componentIds: [], moduleIds: [] })));
          tweak(analysis);
          return analysis;
        }
        // A pull-request analysis: one impact record of every kind.
        const WITH_PR = (analysis) => {
          const measure = (tag) => ({ complexity: P(`${tag}.complexity`), nesting: P(`${tag}.nesting`), length: P(`${tag}.length`), fanIn: P(`${tag}.fanIn`), fanOut: P(`${tag}.fanOut`), forms: [P(`${tag}.forms[0]`), P(`${tag}.forms[1]`)] });
          const kinds = ['dependency-added', 'dependency-removed', 'dependency-changed', 'structural-measures', 'module-coupling', 'module-added', 'module-removed', 'known-users', 'known-importers', 'file-source', 'function-metrics', 'definition-text', 'definition-added', 'definition-removed', 'structural-finding-added', P('impact.records[15].kind')];
          analysis.pullRequest = {
            simulation: true, number: P('pullRequest.number'), title: P('pullRequest.title'), scope: P('pullRequest.scope'), repository: P('pullRequest.repository'),
            baseSHA: P('pullRequest.baseSHA'), headSHA: P('pullRequest.headSHA'),
            beforeSources: { [FILE_A]: snippet('pullRequest.beforeSources[FILE_A]', { status: 'unchanged', added: [], modified: [], deleted: [] }, 12) },
            impact: {
              status: 'partial', basis: P('pullRequest.impact.basis'), total: P('pullRequest.impact.total'), comparison: { comparable: 'no' },
              coverage: { work: { parsedFiles: P('pullRequest.impact.coverage.work.parsedFiles') } },
              categories: { architecture: { total: P('impact.categories.architecture.total'), priorities: [] }, complexity: { total: 0, priorities: [] } },
              records: kinds.map((kind, i) => {
                const tag = `impact.records[${i}]`;
                return {
                  id: PID(`${tag}.id`), category: i % 2 ? 'complexity' : 'architecture', kind, findingId: i === 0 ? F_BND : P(`${tag}.findingId (unknown)`),
                  module: P(`${tag}.module`), path: P(`${tag}.path`), name: P(`${tag}.name`), from: P(`${tag}.from`), to: P(`${tag}.to`),
                  before: measure(`${tag}.before`), after: measure(`${tag}.after`),
                  changes: [{ field: P(`${tag}.changes[0].field`), before: P(`${tag}.changes[0].before`), after: P(`${tag}.changes[0].after`) }, { field: 'size.lines', before: null, after: P(`${tag}.changes[1].after`) }],
                  callers: { coverage: P(`${tag}.callers.coverage`), total: P(`${tag}.callers.total`) }, importers: P(`${tag}.importers`), unchangedCallers: P(`${tag}.unchangedCallers`),
                  locations: [
                    { side: 'base', file: P(`${tag}.locations[0].file`), line: P(`${tag}.locations[0].line`), relation: P(`${tag}.locations[0].relation`), unchanged: P(`${tag}.locations[0].unchanged`) },
                    { side: 'head', file: FILE_A, line: P(`${tag}.locations[1].line`), relation: 'bound-call' },
                  ],
                  contexts: [{ id: F_HUB, code: 'coupling/hub' }, { id: F_ODD, code: P(`${tag}.contexts[1].code`) }],
                };
              }),
            },
          };
        };

        // ---- driving every render path ---------------------------------------
        const failures = [];
        let stepCount = 0;
        // One named render step; an exception is reported, never hidden.
        const step = async (name, fn) => {
          stepCount += 1;
          try { await fn(); } catch (error) { failures.push(`${runLabel} / ${name}: ${String(error && error.message || error).slice(0, 160)}`); }
        };
        const settle = () => new Promise((resolve) => setImmediate(resolve));
        const enter = (name, env) => { runLabel = name; env.sandbox.__archifyShowFinding = () => {}; return env; };

        async function overlayRun(label, analysis, standalone, bare = false) {
          const env = enter(label, makeEnv({ analysis, atlas: null, standalone }));
          const w = env.sandbox, doc = env.doc;
          const q = (sel) => doc.querySelector(sel);
          const need = (sel) => { const el = q(sel); assert.ok(el, `missing ${sel}`); return el; };
          w.__archifySaveReview = async () => ({ saved: false });
          await step('load', () => run(env, 'overlay.js'));
          if (!standalone) await step('toggle layer on', () => need('.toolbar button').click());
          for (const id of IDS) await step(`show finding ${id}`, () => w.__archifyShowFinding(id));
          if (!standalone) {
            await step('show component C1', () => q('svg g[data-node-id="C1"] path').dispatchEvent('click', {}));
            for (const key of ['instability', 'cycle', 'hub', 'boundary', 'complexity', 'dup']) await step(`indicator ${key}`, () => need(`#bauify-panel .ind.link[data-ind="${key}"]`).click());
            await step('indicator (hostile key)', () => doc.querySelectorAll('#bauify-panel .ind.link')[6].click());
            await step('component C3', () => q('svg g[data-node-id="C3"] path').dispatchEvent('click', {}));
            await step('finding rows of the detail page', () => { for (const el of doc.querySelectorAll('#bauify-detail [data-finding]').slice(0, 4)) el.click(); });
            await step('component C1 again', () => q('svg g[data-node-id="C1"] path').dispatchEvent('click', {}));
            await step('dependency row', () => need('#bauify-panel .fly-rel[data-edge]').click());
            await step('dependency evidence', () => need('#bauify-panel .fly-ev').click());
            await step('code dependency from the start card', () => need('#bauify-stage .first-row[data-go="code"]').click());
            await step('code dependency hit path', () => { for (const el of doc.querySelectorAll('svg .bauify-hit')) el.click(); });
            await step('off-diagram module from the start card', () => need('#bauify-stage .first-row[data-go="off:U1"]').click());
            await step('off-diagram file', () => need('#bauify-panel .fly-ev').click());
            await step('off-diagram finding', () => need('#bauify-panel .fly-find').click());
            await step('component from the start card', () => need('#bauify-stage .first-row[data-go="component:C1"]').click());
            await step('source link of an edge', () => need('#bauify-panel .source-file').click());
          }
          await step('show source from the atlas', () => w.__archifyShowSource(FILE_A, 3, 'base', { base: FILE_A, head: FILE_B }, () => {}));
          await step('show source without a pair', () => w.__archifyShowSource(FILE_B, P('showSource line'), 'head'));
          await step('open the code pane from every finding page', () => {
            for (const id of IDS) {
              w.__archifyShowFinding(id);
              for (const el of doc.querySelectorAll('#bauify-detail .ref').slice(0, 3)) el.click();
            }
          });
          // The code pane reads its highlight tone back from a data-* attribute, which this query counts as a DOM source.
          await step('source link carrying a hostile tone attribute', () => {
            w.__archifyShowFinding(F_CX);
            const ref = need('#bauify-detail .ref');
            ref.setAttribute('data-tone', P('data-tone attribute on a source link'));
            ref.click();
          });
          if (bare) { await settle(); return; }
          await step('show overview', () => { w.__archifyShowFinding(F_HUB); need('#bauify-detail .back').click(); });
          await step('structural signals', () => { for (const el of doc.querySelectorAll('#bauify-overview .structural-signals [data-finding]').slice(0, 2)) el.click(); need('#bauify-detail .back').click(); });
          await step('priority cards', () => { for (const el of doc.querySelectorAll('#bauify-overview .priority-card [data-finding]').slice(0, 3)) el.click(); need('#bauify-detail .back').click(); });
          await step('all finding groups', () => { for (const el of doc.querySelectorAll('#bauify-overview .all-finding-groups [data-finding]').slice(0, 2)) el.click(); need('#bauify-detail .back').click(); });
          await step('findings list', () => need('#bauify-overview .browse-findings').click());
          await step('findings page 2', () => need('#bauify-overview [data-page="1"]').click());
          await step('findings page 1', () => need('#bauify-overview [data-page="-1"]').click());
          await step('findings search', () => { const search = need('#finding-search'); search.value = P('filters.search'); search.dispatchEvent('input', {}); });
          await step('findings without a match', () => { const search = need('#finding-search'); search.value = P('filters.search (no match)'); search.dispatchEvent('input', {}); });
          await step('reset filters', () => need('#bauify-overview .reset-filters').click());
          await step('sources from the list', () => need('#bauify-overview .view-sources').click());
          await step('findings of one source', () => need('#bauify-overview .source-findings').click());
          await step('back to the overview', () => need('#bauify-overview .findings-back').click());
          await step('sources from the overview', () => need('#bauify-overview .overview-sources').click());
          await step('external diagnostics', () => { need('#bauify-overview .sources-back').click(); need('#bauify-overview .external-findings').click(); need('#bauify-overview .findings-back').click(); });
          await step('copy the architecture brief', () => need('#bauify-overview .brief-copy').click());
          await step('copy the start command', () => { const el = q('#bauify-overview .start-copy'); if (el) el.click(); });
          if (analysis.pullRequest) {
            await step('PR impact locations', () => {
              for (const el of doc.querySelectorAll('#bauify-overview [data-impact-location]').slice(0, 4)) el.click();
              need('#bauify-code .source-back').click();
            });
            await step('PR impact related finding', () => need('#bauify-overview .pr-impact-evidence [data-finding]').click());
          }
          await step('review form', () => { w.__archifyShowFinding(F_HUB); const action = need('#bauify-detail .review-action'); action.click(); need('#bauify-detail .review-form').dispatchEvent('submit', {}); });
          await step('task preview', async () => {
            w.__archifyShowFinding(F_HUB);
            need('#bauify-detail .task-refresh').click();
            await settle();
            need('#bauify-detail .task-copy').click();
            await settle();
          });
          await settle();
        }

        // The Atlas payload: every finding kind, each measured value hostile.
        function atlasData(pr) {
          const functions = [
            [0, P('functions[0].name'), 7, P('functions[0].complexity'), P('functions[0].nesting'), P('functions[0].lines'), 0, { column: P('functions[0].range.column'), endLine: P('functions[0].range.endLine'), endColumn: P('functions[0].range.endColumn') }],
            [1, P('functions[1].name'), P('functions[1].line'), P('functions[1].complexity'), P('functions[1].nesting'), P('functions[1].lines'), -1, null],
            [0, P('functions[2].name'), P('functions[2].line'), P('functions[2].complexity'), P('functions[2].nesting'), P('functions[2].lines'), 2, null],
            [1, P('functions[3].name'), P('functions[3].line'), P('functions[3].complexity'), P('functions[3].nesting'), P('functions[3].lines'), -1, null],
            [1, P('functions[4].name'), P('functions[4].line'), P('functions[4].complexity'), P('functions[4].nesting'), P('functions[4].lines'), -1, null],
          ];
          return {
            modules: [
              { id: 'm1', label: P('atlas.modules[0].label'), path: P('atlas.modules[0].path'), fanIn: P('atlas.modules[0].fanIn'), fanOut: P('atlas.modules[0].fanOut') },
              { id: 'm2', label: P('atlas.modules[1].label'), path: P('atlas.modules[1].path'), fanIn: P('atlas.modules[1].fanIn'), fanOut: P('atlas.modules[1].fanOut') },
            ],
            files: [[FILE_A, 0, P('atlas.files[0].lines')], [FILE_B, 0, P('atlas.files[1].lines')], [FILE_D, 1, P('atlas.files[2].lines')]],
            edges: [[0, 2], [2, 1]],
            functions,
            findings: [
              // Atlas 3D looks severities up in a colour table, so the two it reads keep a real one.
              { id: F_CX, code: 'complexity/function', severity: 'warning', kind: 'function', fn: 0, file: 0, accepted: P('atlas.findings[0].accepted'), title: P('atlas.findings[0].title') },
              { id: F_HUB, code: 'coupling/hub', severity: 'error', kind: 'module', module: 0, accepted: false, title: P('atlas.findings[1].title') },
              { id: F_MOD, code: P('atlas.findings[2].code'), severity: 'info', kind: 'cycle', path: [0, 2, 1], files: [0, 2], accepted: false, title: P('atlas.findings[2].title') },
              { id: F_LEAK, code: 'coupling/internal-leak', severity: P('atlas.findings[3].severity'), kind: 'edges', edges: [[0, 2], [2, 1]], module: 1, entries: [2], accepted: false, title: P('atlas.findings[3].title') },
              { id: F_ODD, code: P('atlas.findings[4].code'), severity: P('atlas.findings[4].severity'), kind: P('atlas.findings[4].kind (unknown)'), modules: [0, 1], file: 1, accepted: P('atlas.findings[4].accepted'), title: P('atlas.findings[4].title') },
            ],
            coverage: Object.fromEntries(['records', 'resolved', 'external', 'unknown', 'outside', 'parseErrors', 'notCompiled'].map((k) => [k, P(`atlas.coverage.${k}`)])),
            measured: true,
          };
        }

        // The analysis the Atlas scripts read next to their own payload.
        function atlasAnalysis(mode, pr) {
          const analysis = {
            ui: { locale: 'en', messages: {}, mode },
            components: [{ id: 'C1', label: P('analysis.components[0].label'), modules: [{ id: 'm1', label: P('analysis.components[0].modules[0].label') }, { id: 'm2', label: P('analysis.components[0].modules[1].label') }] }],
            findings: [{ id: F_CX, message: P('analysis.findings[0].message'), supportedFixes: [P('analysis.findings[0].supportedFixes[0]'), P('analysis.findings[0].supportedFixes[1]')] }, { id: F_HUB, message: P('analysis.findings[1].message'), supportedFixes: [P('analysis.findings[1].supportedFixes[0]')] }],
            snippets: SNIPPETS,
          };
          if (pr) {
            analysis.pullRequest = {
              simulation: false, number: P('pr.number'), repository: P('pr.repository'), scope: P('pr.scope'),
              baseSHA: P('pr.baseSHA'), headSHA: P('pr.headSHA'),
              before: Object.fromEntries(['files', 'dependencies', 'functions', 'modules'].map((k) => [k, P(`pr.before.${k}`)])),
              after: Object.fromEntries(['files', 'dependencies', 'functions', 'modules'].map((k) => [k, P(`pr.after.${k}`)])),
              distribution: {
                labels: [P('pr.distribution.labels[0]'), P('pr.distribution.labels[1]'), P('pr.distribution.labels[2]')],
                before: [P('pr.distribution.before[0]'), P('pr.distribution.before[1]'), P('pr.distribution.before[2]')],
                after: [P('pr.distribution.after[0]'), P('pr.distribution.after[1]'), P('pr.distribution.after[2]')],
              },
              ambiguousFunctions: P('pr.ambiguousFunctions'),
              omitted: { base: [P('pr.omitted.base[0]')], head: [P('pr.omitted.head[0]'), P('pr.omitted.head[1]')] },
              beforeSources: { [FILE_A]: snippet('pr.beforeSources[FILE_A]', { status: 'modified', added: [], modified: [3], deleted: [] }, 12) },
              moduleChanges: [{
                id: 'm1',
                files: { added: P('pr.moduleChanges[0].files.added'), removed: P('pr.moduleChanges[0].files.removed'), modified: P('pr.moduleChanges[0].files.modified') },
                functions: { added: 0, removed: P('pr.moduleChanges[0].functions.removed'), modified: 0 },
              }],
              changes: [
                { kind: 'edge', from: FILE_A, to: FILE_B, status: P('pr.changes[0].status'), path: P('pr.changes[0].path') },
                { kind: 'function', name: P('pr.changes[1].name'), path: FILE_A, status: P('pr.changes[1].status'), before: { complexity: P('pr.changes[1].before.complexity') }, after: { complexity: P('pr.changes[1].after.complexity') } },
                { kind: 'file', path: FILE_D, status: P('pr.changes[2].status') },
              ],
              changedFiles: [
                { path: FILE_A, previousPath: P('pr.changedFiles[0].previousPath'), status: P('pr.changedFiles[0].status'), kind: 'file' },
                { path: 'gone.py', previousPath: P('pr.changedFiles[1].previousPath'), status: P('pr.changedFiles[1].status'), kind: 'file' },
                { path: FILE_D, status: P('pr.changedFiles[2].status'), kind: 'file' },
              ],
            };
            Object.assign(analysis.snippets, { [FILE_D]: snippet('analysis.snippets[FILE_D]', { status: 'added', added: [1], modified: [], deleted: [] }, 8) });
          }
            return analysis;
        }

        async function atlasRun(label, mode, pr) {
          const env = enter(label, makeEnv({ analysis: atlasAnalysis(mode, pr), atlas: atlasData(pr), standalone: mode === 'standalone' }));
          const w = env.sandbox, doc = env.doc;
          const q = (sel) => doc.querySelector(sel);
          const need = (sel) => { const el = q(sel); assert.ok(el, `missing ${sel}`); return el; };
          doc.documentElement.setAttribute('data-bauify', 'on');
          await step('load', () => run(env, 'atlas.js'));
          const page = mode !== 'standalone';
          if (page) {
            await step('switch to the atlas view', () => need('.views-option[data-view="atlas"]').click());
            await step('all findings page', () => need('.atlas-all').click());
            await step('module row', () => need('.atlas-side-content [data-module]').click());
            for (const id of [F_CX, F_MOD, F_LEAK, F_ODD, F_HUB]) await step(`focus finding ${id}`, () => w.__archifyAtlas.focusFinding(id));
            await step('module of a finding', () => need('.atlas-selection [data-module]').click());
            await step('finding row of a module', () => need('.atlas-selection [data-finding]').click());
            await step('evidence button', () => need('.atlas-selection .atlas-evidence').click());
            await step('back through the crumbs', () => { const crumb = q('.atlas-crumbs [data-go]'); if (crumb) crumb.click(); else need('.atlas-fly-x').click(); });
            await step('focus a module by id', () => w.__archifyAtlas.focusModule('m2'));
            await step('clear the selection', () => need('.atlas-clear').click());
          }
          for (const id of [F_CX, F_MOD, F_LEAK, F_ODD, F_HUB]) await step(`select finding ${id}`, () => need('.atlas-side-content [data-finding]').click());
          await step('select a module row', () => need('.atlas-side-content [data-module]').click());
          await step('files tab', () => need('.atlas-tab#atlas-tab-files').click());
          if (pr) {
            await step('changed files scope', () => { const scope = need('select.atlas-file-scope'); scope.value = 'changed'; scope.dispatchEvent('change', {}); });
            await step('pick a changed file', () => need('.atlas-file-list [data-changed-file]').click());
            await step('changed file actions', () => {
              for (const el of doc.querySelectorAll('.atlas-selection [data-atlas-change-source]')) el.click();
              need('.atlas-selection .atlas-change-download').click();
            });
            await step('changed file search', () => { const input = need('.atlas-file-query'); input.value = P('changed file query'); input.dispatchEvent('input', {}); });
            await step('clear the changed file search', () => { const input = need('.atlas-file-query'); input.value = ''; input.dispatchEvent('input', {}); });
            await step('all files scope', () => { const scope = need('select.atlas-file-scope'); scope.value = 'all'; scope.dispatchEvent('change', {}); });
          }
          await step('open a captured file', () => need('.atlas-file-list [data-file]').click());
          await step('open every captured file', () => { for (const row of doc.querySelectorAll('.atlas-file-list [data-file]')) row.click(); });
          await step('type in the file search', () => { const input = need('.atlas-file-query'); input.value = P('atlas file query'); input.dispatchEvent('input', {}); });
          await step('clear the file search', () => { const input = need('.atlas-file-query'); input.value = 'zz-no-match'; input.dispatchEvent('input', {}); });
          if (pr) {
            await step('download the file markdown', () => need('.atlas-selection .atlas-file-download').click());
            if (page) await step('copy a module for AI', () => {
              // A module row toggles: click rows until one leaves a module panel open.
              for (const row of doc.querySelectorAll('.atlas-side-content [data-module]')) {
                row.click();
                const act = q('.atlas-selection [data-act="copy-module"]');
                if (act) { act.click(); return; }
              }
              assert.fail('no module panel with the copy action');
            });
            await step('PR change rows', () => { for (const el of doc.querySelectorAll('.atlas-side-content [data-pr-change]')) el.click(); });
          }
          if (page) await step('search suggestions', () => { const input = need('.atlas-q'); input.value = 'e'; input.dispatchEvent('input', {}); input.value = P('atlas search'); input.dispatchEvent('input', {}); });
          await step('hover tips', () => {
            const canvas = need('.atlas-stage canvas'), tip = need('.atlas-tip');
            let seen = 0;
            for (let y = 6; y < 470 && seen < 6; y += 3) for (let x = 6; x < 630; x += 3) { canvas.dispatchEvent('mousemove', { clientX: x, clientY: y }); if (!tip.hidden && tip.childNodes.length) seen += 1; }
          });
          await step('restore a selection', () => w.__archifyAtlas.restoreSelection({
            module: 0, finding: 1, file: -1, changedFile: null, scope: 'all', tab: 'files', query: '', zoom: 1, view: { scroll: 0, modules: 0, groups: new Set() },
          }));
          await step('close and reopen', () => { w.__archifyAtlas.close(); w.__archifyAtlas.open(); });
          return env;
        }

        // Atlas 3D runs against a stand-in for the inert three.js the page carries.
        async function atlas3dRun(label, data) {
          class V3 {
            constructor(x, y, z) { this.x = x || 0; this.y = y || 0; this.z = z || 0; }
            clone() { return new V3(this.x, this.y, this.z); }
            add(v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
            distanceTo(v) { return Math.hypot(this.x - v.x, this.y - v.y, this.z - v.z); }
            multiplyScalar(s) { this.x *= s; this.y *= s; this.z *= s; return this; }
            copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
            normalize() { const l = Math.hypot(this.x, this.y, this.z) || 1; return this.multiplyScalar(1 / l); }
            project() { this.x = 0; this.y = 0; this.z = 0.5; return this; }
            set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
          }
          class Attr {
            constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; this.count = Math.ceil(array.length / itemSize); }
            setXYZ() { return this; }
            getX(i) { return this.array[i * this.itemSize]; }
            getY(i) { return this.array[i * this.itemSize + 1]; }
            getZ(i) { return this.array[i * this.itemSize + 2]; }
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
          class Curve { getPoints(n) { return Array.from({ length: n }, () => new V3()); } getPoint() { return new V3(); } }
          const renderer = { domElement: null };
          const THREE = {
            Vector3: V3, Color, Box3, BufferAttribute: Attr, Float32BufferAttribute: Attr, BufferGeometry: Geometry,
            WebGLRenderer: class { constructor() { this.domElement = renderer.domElement; } setPixelRatio() {} setClearColor() {} setSize() {} getPixelRatio() { return 1; } render() {} },
            Scene: class { add() {} }, PerspectiveCamera: class { constructor() { this.position = new V3(); this.aspect = 1; } lookAt() {} updateProjectionMatrix() {} },
            Points: class { constructor() { this.position = new V3(); } }, LineSegments: class { constructor() { this.position = new V3(); } },
            ShaderMaterial: class {}, LineBasicMaterial: class {}, EdgesGeometry: class {}, BoxGeometry: class {}, CubicBezierCurve3: Curve, QuadraticBezierCurve3: Curve, AdditiveBlending: 0,
          };
          const env = enter(label, makeEnv({ analysis: atlasAnalysis('diagram'), atlas: data.atlas, atlas3dData: data.more }));
          const w = env.sandbox, doc = env.doc;
          const need = (sel) => { const el = doc.querySelector(sel); assert.ok(el, `missing ${sel}`); return el; };
          w.THREE = THREE;
          const host = doc.createElement('section'); host.id = 'atlas3d-host'; doc.body.appendChild(host);
          const canvas = doc.createElement('canvas'); renderer.domElement = canvas;
          await step('load', () => run(env, 'atlas3d.js'));
          let view = null;
          await step('mount', () => { view = w.__archifyAtlas3d.mount(host); assert.ok(view && view.select, 'atlas3d mounted'); });
          await step('start card', () => { for (const el of doc.querySelectorAll('#atlas3d-host .a3d-lead')) el.click(); });
          await step('directory chips', () => { for (const el of doc.querySelectorAll('#atlas3d-host .a3d-chips [data-module]')) el.click(); });
          await step('directory finding rows', () => { for (const el of doc.querySelectorAll('#atlas3d-host .a3d-row[data-finding]')) el.click(); });
          for (let i = 0; i < 2; i += 1) await step(`module ${i}`, () => view.select({ type: 'module', index: i }));
          for (let i = 0; i < 5; i += 1) await step(`finding ${i}`, () => view.select({ type: 'finding', index: i }));
          for (let i = 0; i < 3; i += 1) await step(`file ${i}`, () => view.select({ type: 'file', index: i }));
          for (let i = 0; i < 4; i += 1) await step(`function ${i}`, () => view.select({ type: 'function', index: i }));
          await step('hover tip', () => canvas.dispatchEvent('pointermove', { clientX: 320, clientY: 240 }));
          await step('clear the selection', () => need('#atlas3d-host .a3d-reset').click());
          return env;
        }

        // Standalone reports carry no diagram, so they list no components.
        const isStandalone = (analysis) => { analysis.ui.mode = 'standalone'; analysis.components = []; return analysis; };
        const findingsOfOneSource = (a) => a.findings.map((f) => ({ id: f.id, relatedIds: [P(`overview.findings[${f.id}].relatedIds`)] }));
        await overlayRun('overlay diagram en', overlayAnalysis());
        await overlayRun('overlay standalone en', overlayAnalysis(isStandalone), true);
        await overlayRun('overlay diagram zh-CN', overlayAnalysis((a) => {
          a.ui.locale = 'zh-CN';
          a.overview.review.comparison.comparable = 'no';
          a.overview.priorities = [];
          a.components[2].indicators.items[0].findings = [];
        }));
        await overlayRun('overlay standalone zh-CN PR', overlayAnalysis((a) => { isStandalone(a); a.ui.locale = 'zh-CN'; WITH_PR(a); delete a.ui.resume; }), true);
        await overlayRun('overlay standalone without overview', overlayAnalysis((a) => { isStandalone(a); delete a.overview; a.ui.openByDefault = true; }), true, true);
        await overlayRun('overlay diagram without external sources', overlayAnalysis((a) => {
          a.overview.coverage.external = [];
          a.overview.review.comparison.comparable = undefined;
          a.overview.coverage.rules = { run: [], suppressed: [] };
          a.overview.coverage.duplicates = null;
          a.overview.coverage.boundaries = null;
          a.overview.coverage.otherLanguages = [];
          a.overview.coverage.files.parseErrors = [];
        }), false, true);
        await overlayRun('overlay diagram PR', overlayAnalysis((a) => { WITH_PR(a); a.overview.investigation = null; a.overview.review = null; a.overview.groups = []; }));
        await overlayRun('overlay diagram partial comparison', overlayAnalysis((a) => {
          a.overview.review.comparison.comparable = undefined;
          a.overview.review.baseline = null;
          a.overview.coverage.duplicates = { complete: true, analyzed: 1, selected: 1 };
          a.overview.coverage.language = 'java';
          a.components[0].incoming[1].component = 'C9';
          a.components[0].outgoing[1].component = 'C9';
          a.overview.findings = findingsOfOneSource(a);
        }));
        await atlasRun('atlas page', 'diagram', false);
        await atlasRun('atlas standalone', 'standalone', false);
        await atlasRun('atlas page PR', 'diagram', true);
        await atlasRun('atlas standalone PR', 'standalone', true);
        await atlas3dRun('atlas3d', {
          atlas: atlasData(false),
          more: {
            detail: Object.fromEntries(IDS.map((id) => [id, { message: P(`atlas3d.detail[${id}].message`), fix: P(`atlas3d.detail[${id}].fix`) }])),
            run: { summary: { errors: P('atlas3d.run.summary.errors'), warnings: P('atlas3d.run.summary.warnings'), info: P('atlas3d.run.summary.info') } },
          },
        });

        // ---- verdict ----------------------------------------------------------
        // A write leaks when a field number is followed by a raw quote or bracket, or
        // when what it built parses to a blocked element or an event-handler attribute.
        const BLOCKED = new Set(['img', 'script', 'iframe', 'object', 'embed', 'style', 'link', 'meta', 'base']);
        const leaks = [];
        for (const { el, html, run } of captured) {
          const found = new Set();
          for (const m of html.matchAll(RAW)) found.add(fieldName(m[1]));
          const visit = (n) => {
            if (n.nodeType !== 1) return;
            if (BLOCKED.has(n.localName)) found.add(`<${n.localName}> element`);
            for (const name of Object.keys(n.attributes)) if (/^on/i.test(name)) found.add(`${name}= attribute`);
            n.childNodes.forEach(visit);
          };
          parseHtml(html, el.ownerDocument).childNodes.forEach(visit);
          if (found.size) leaks.push({ run, sink: pathOf(el), fields: [...found] });
        }
        const paths = new Set(captured.map((c) => pathOf(c.el)));
        // Each family of markup helpers writes to its own container; all must have rendered.
        const required = ['#bauify-reader', '#bauify-overview', '#bauify-panel', '#bauify-detail', '#bauify-code', '#bauify-stage', '.atlas-first', '.atlas-side-content', '.atlas-selection', '.atlas-crumbs', '.atlas-tip', '.atlas-file-list', '#atlas-sug', '.a3d-first', '.a3d-dir', '.a3d-fly-body', '.a3d-tip'];
        const missing = required.filter((part) => ![...paths].some((p) => p.includes(part)));
        console.log(JSON.stringify({ fields: FIELDS.length, steps: stepCount, failedSteps: failures, sinks: captured.length, sinkPaths: paths.size, withEscapedPayload: captured.filter((c) => /&lt;img\b/.test(c.html)).length, leaks, missingSinks: missing }));
        assert.deepEqual(failures, [], 'every render step ran');
        assert.deepEqual(missing, [], 'every helper family rendered');
        assert.equal(leaks.length, 0, 'no sink received a raw payload');
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(
            {"fields": 7228, "steps": 519, "failedSteps": [], "sinks": 1396, "sinkPaths": 34,
             "withEscapedPayload": 1265, "leaks": [], "missingSinks": []},
            json.loads(result.stdout),
        )

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
const attrsKept = bakeSvg(wrap('<style id="c-n" type="text/css">.c-n{fill:#102030}</style><rect class="c-n" width="4" height="4"/>'), { theme: 'dark', preset: 'classic' });
if (!attrsKept.includes('<style id="c-n" type="text/css">') || !attrsKept.includes('fill: #102030')) throw new Error('well-formed style attributes must survive baking');
const mixed = bakeSvg(wrap('<style media="screen and (min-width: 600px)" id=\'c-m\'>.c-m{fill:#102030}</style><rect width="4" height="4"/>'), { theme: 'dark', preset: 'classic' });
if (!mixed.includes('media="screen and (min-width: 600px)"') || !mixed.includes('id="c-m"') || !mixed.includes('fill: #102030')) throw new Error('mixed-quote style attributes must survive baking');
const quoted = bakeSvg(wrap('<style data-x=\'a"b\' data-y="c&amp;d">.c-n{fill:#102030}</style><rect width="4" height="4"/>'), { theme: 'dark', preset: 'classic' });
if (!quoted.includes("data-x='a\"b'") || !quoted.includes('data-y="c&amp;d"')) throw new Error('quoted style attribute values must survive baking');
const spaced = bakeSvg(wrap('<style  >.c-n{fill:#102030}</style><rect width="4" height="4"/>'), { theme: 'dark', preset: 'classic' });
if (!spaced.includes('<style>.c-n { fill: #102030; }')) throw new Error('whitespace-only style attributes must bake to a plain tag');
const hostile = [
  '<sty<style></style>le>.n{fill:red}</style><rect class="n" width="4" height="4"/>',
  '<style>.n{fill:red}<rect class="n" width="4" height="4"/>',
  '<rect width="4" height="4"/></style>',
  '<style><style>.n{fill:red}</style></style><rect width="4" height="4"/>',
  '<style x="<s>a</s y=">.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x="a>.n{fill:red}</style><rect class="n" width="4" height="4"/>',
  "<style x='a>.n{fill:red}</style><rect class='n' width='4' height='4'/>",
  '<style/>.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x="1"/>.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x="1"/ y="2">.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x=1>.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x="1"y="2">.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x="1" x="2">.n{fill:red}</style><rect width="4" height="4"/>',
  '<style media>.n{fill:red}</style><rect width="4" height="4"/>',
  '<style x="a&b">.n{fill:red}</style><rect width="4" height="4"/>',
  '<STYLE/>.n{fill:red}</STYLE><rect width="4" height="4"/>',
  '<style//>.n{fill:red}</style><rect width="4" height="4"/>',
];
let threw = 0;
for (const body of hostile) {
  try { bakeSvg(wrap(body), { theme: 'dark', preset: 'classic' }); } catch (_) { threw += 1; }
}
const variantBody = '<STYLE><script xmlns="http://www.w3.org/2000/svg">alert(1)</script></STYLE><rect width="4" height="4"/>';
let variantOut = null;
try { variantOut = bakeSvg(wrap(variantBody), { theme: 'dark', preset: 'classic' }); } catch (_) {}
if (variantOut !== null && (/<script/i.test(variantOut) || ![...variantOut.matchAll(/<\/?[sS][tT][yY][lL][eE]\b/g)].every((m) => m[0] === '<style' || m[0] === '</style'))) {
  throw new Error('case-variant style payload survived baking: ' + variantOut);
}
console.log(JSON.stringify({ styles: styleCount(legit), empty: styleCount(empty), threw, expected: hostile.length, caseVariant: variantOut === null ? 'threw' : 'neutralized', passed: threw === hostile.length }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"styles": 4, "empty": 2, "threw": 17, "expected": 17, "caseVariant": "neutralized", "passed": True}, json.loads(result.stdout))

    def test_static_bake_style_open_tags_stay_paired_under_attribute_sweep(self) -> None:
        program = r"""
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const {bakeSvg} = await import(pathToFileURL(path.join(process.argv[1], 'renderers/shared/svg-bake.mjs')));
const wrap = (body) => `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">${body}</svg>`;
const alphabet = ['x', '"', "'", '/', '=', ' '];
const cases = [''];
for (let len = 1; len <= 5; len += 1) {
  for (const s of cases.filter((s) => s.length === len - 1)) for (const ch of alphabet) cases.push(s + ch);
}
const returned = [];
for (const attrs of cases) {
  try {
    const svg = bakeSvg(wrap(`<style${attrs}>.n{fill:red}</style><rect width="4" height="4"/>`), { theme: 'dark', preset: 'classic' });
    returned.push({ attrs, svg });
  } catch (_) {}
}
console.log(JSON.stringify({ alphabet: alphabet.join(''), depth: 5, checked: cases.length, threw: cases.length - returned.length, returned: returned.length, cases: returned }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=120,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("x\"'/= ", payload["alphabet"])
        self.assertEqual(9331, payload["checked"])
        self.assertEqual(payload["checked"], payload["threw"] + payload["returned"])
        accepted = {case["attrs"] for case in payload["cases"]}
        for wellformed in ("", " ", "  ", " x=\"\""):
            self.assertIn(wellformed, accepted, wellformed)
        self.assertGreater(payload["returned"], 0)
        for case in payload["cases"]:
            try:
                dom = minidom.parseString(case["svg"])
            except Exception as exc:
                self.fail(f"attrs {case['attrs']!r} baked a non-well-formed artifact: {exc}")
            self.assertEqual(2, len(dom.getElementsByTagName("style")), case["attrs"])

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
const variantSvg = '<svg><STYLE><script xmlns="http://www.w3.org/2000/svg">alert(1)</script></STYLE><rect/></svg>';
let variantOut = null;
try { variantOut = scopeEmbeddedStyles(variantSvg, 'native-1'); } catch (_) {}
if (variantOut !== null && (/<script/i.test(variantOut) || ![...variantOut.matchAll(/<\/?[sS][tT][yY][lL][eE]\b/g)].every((m) => m[0] === '<style' || m[0] === '</style'))) {
  assert.fail('case-variant style payload survived scoping: ' + variantOut);
}
console.log(JSON.stringify({ cases: cases.length, threw, expected: hostile.length, caseVariant: variantOut === null ? 'threw' : 'neutralized', passed: true }));
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", program, str(SKILL_DIR)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual({"cases": 3, "threw": 4, "expected": 4, "caseVariant": "neutralized", "passed": True}, json.loads(result.stdout))

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
