import assert from 'node:assert/strict';
import { Readable } from 'node:stream';
import { validateSafeCss, compileSafeCss, decodeAndValidateSafeCss } from '../vendor/dream-safe-css-validator.mjs';
import { parseSafeCssAst, compileSafeCss as compileAstCss, decodeAndValidateSafeCss as decodeAstCss } from '../vendor/dream-safe-css-ast.mjs';
import { generatedDream } from './test-dream-generated.mjs';
const manifest = {schemaVersion:1,id:'boundary',name:'Boundary',image:'background.png'};
const selector = '[data-ds-part="main"]';
const css = (property,value) => `${selector}{${property}:${value};}`;
// Positive and negative examples for every supported value grammar. The generated
// limited profile must validate the source, then reject unmapped declarations.
const values = {
 'color': [['#fff','currentColor','rgb(0,100%,255)','rgba(0,0,0,50%)','var(--ds-theme-color-text)'],['transparent','rgb(0,0)','rgba(0,0,0,2)','rgb(256,0,0)','rgb(101%,0,0)','var(--ds-theme-font-family)']],
 'background-color': [['transparent','#12345678'],['red']],
 'border-width': [['0','1px 2px 3px 4px'],['5px','1px 2px 3px 4px 1px']],
 'border-style': [['solid dashed dotted none'],['double']],
 'border-radius': [['var(--ds-theme-surface-radius)','0 28px'],['29px']],
 'gap': [['0','24px'],['25px']],
 'box-shadow': [['none','0 1px #fff','inset -2px 2px 3px -1px rgba(0,0,0,.5)','0 0 #fff, 1px 1px #000'],['0 #fff','0 0 0 0 0 #fff','0 0 red','33px 0 #fff','0 0 49px #fff','0 0 2px 17px #fff','0 0 #fff,0 0 #fff,0 0 #fff']],
 'opacity': [['.65','var(--ds-theme-surface-opacity)'],['.64']],
 'backdrop-filter': [['none','blur(0)','blur(var(--ds-theme-surface-blur)) saturate(.5) brightness(.8) contrast(1.5)'],['saturate(1)','blur(1px) blur(2px)','blur(31px)','blur(1px) saturate(3)','blur(1px) brightness(.7)','blur(1px) sepia(1)']],
 'font-family': [['system-ui, sans-serif','ui-rounded,ui-serif,ui-monospace,serif'],['arial','serif,serif,serif,serif,serif']],
 'font-size': [['12px','20px'],['21px']],
 'font-weight': [['bold','700'],['800']],
 'line-height': [['1.1','1.8'],['2']],
 'letter-spacing': [['0','2px'],['-1px']],
 'transition-duration': [['0,100ms,.4s'],['401ms','.5s','1px','0,0,0,0,0']],
 'transition-property': [['color,opacity,font-size'],['display','color,color,color,color,color']],
};
for(const [property,[valid,invalid]] of Object.entries(values)) {
 for(const value of valid) {
  const source=css(property,value);
  assert.equal(validateSafeCss(source).status,'validated',source);
  const ast=parseSafeCssAst(source);assert.equal(ast.rules[0].declarations[0].value,value);
  assert.match(compileSafeCss(source),/!important/);
  assert.equal(compileAstCss(source),compileSafeCss(source));
  if(property==='background-color') assert.equal(generatedDream.mapDreamTheme(manifest,source).declarationCount,1);
  else assert.throws(()=>generatedDream.mapDreamTheme(manifest,source),/dream_profile_unmapped_declaration/);
 }
 for(const value of invalid) {
  const source=css(property,value);
  for(const parse of [validateSafeCss,parseSafeCssAst,s=>generatedDream.mapDreamTheme(manifest,s)])
   assert.throws(()=>parse(source),e=>e.code==='value/unsupported',source);
 }
}
const malformed=[['','limit/bytes'],[' ','stylesheet/empty'],['x','syntax/block'],['{color:#fff}','selector/empty'],[`${selector}{`,'syntax/block'],[`${selector}{}`,'declaration/empty'],[`${selector}{color`,'syntax/declaration'],[`${selector}{color;}`,'syntax/declaration'],[`${selector}{1color:#fff}`,'property/name'],[`${selector}{display:none}`,'property/unsupported'],[`${selector}{color:}`,'value/empty'],[`${selector}{color:rgb(0,0,0}`,'syntax/function'],[`${selector}{color:rgb(0,0,0))}`,'syntax/function'],['\n\n'+selector+'{color:#fff}\n*/','syntax/comment'],['\n'+selector+'{color:\u0000}','syntax/control']];
for(const [source,code] of malformed) for(const parse of [validateSafeCss,parseSafeCssAst,s=>generatedDream.mapDreamTheme(manifest,s)]) assert.throws(()=>parse(source),e=>e.code===code,source);
for(const parse of [validateSafeCss,parseSafeCssAst]) assert.throws(()=>parse(null),TypeError);
assert.throws(()=>decodeAndValidateSafeCss('bad'),TypeError);
assert.throws(()=>decodeAndValidateSafeCss(Uint8Array.of(255)),e=>e.code==='syntax/utf8');
const runtime=decodeAndValidateSafeCss(new TextEncoder().encode('[data-ds-part="root"]{color:#fff;opacity:1;}[data-ds-part="composer"]{border-color:#fff;}[data-ds-part="composer"]:hover{border-color:#000;}[data-ds-part="home-hero"]{font-size:14px;}[data-ds-part="composer-toolbar"]{color:#fff;}[data-ds-part="sidebar"]{background-color:#fff;}'));
assert.match(runtime.runtimeSource,/--ds-community-composer-border-color/);
assert.match(runtime.runtimeSource,/::after/);assert.match(runtime.runtimeSource,/ body/);
assert.match(runtime.runtimeSource,/:where\(button/);assert.match(runtime.runtimeSource,/background-image: none/);
assert.equal(runtime.validation.ruleCount,6);
assert.deepEqual(decodeAstCss(new TextEncoder().encode(runtime.source)),runtime);
assert.throws(()=>decodeAstCss('bad'),TypeError);
assert.throws(()=>decodeAstCss(Uint8Array.of(255)),e=>e.code==='syntax/utf8');
// Exercise the actual stdin CLI module in-process so Node measures its source.
const stdin=Object.getOwnPropertyDescriptor(process,'stdin'),write=process.stdout.write;let output='';
try {
 Object.defineProperty(process,'stdin',{configurable:true,value:Readable.from([Buffer.from(css('color','#fff'))])});
 process.stdout.write=chunk=>{output+=chunk;return true;};
 await import('./reference-safe-css.mjs');
} finally {Object.defineProperty(process,'stdin',stdin);process.stdout.write=write;}
assert.deepEqual(JSON.parse(output),{schema:'azhou-agent-skin.reference-safe-css.v1',contract:'dreamskin-safe-css/1',status:'passed',reasons:[]});
