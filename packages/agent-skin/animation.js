/* A single scene for the supplied, private Q-version working illustration.
   The bitmap stays intact. A small texture mesh moves head/hands/hair locally;
   desk, laptop, skirt and feet remain registered. No skeleton asset is implied. */
(() => {
  'use strict';
  const $=s=>document.querySelector(s), clamp=x=>Math.max(0,Math.min(1,x));
  const ease=x=>{const t=clamp(x);return t*t*(3-2*t);};
  const DURATION=7800, native=Boolean(window.webkit?.messageHandlers?.launcher);
  const root=$('.window'),scene=$('.scene'),canvas=$('#azhou'),slider=$('#timeline');
  const nodes={title:$('#title'),english:$('#english'),subtitle:$('#subtitle'),code:$('.codex-label'),rule:$('.copy-rule'),lamp:$('.lamp'),glow:$('.lamp-glow'),track:$('.signal-track'),start:$('.signal-origin'),orbit:$('.small-orbit'),phase:$('#phase')};
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  let reduced=media.matches, motions=[], stageScale=1;
  let playing=false,loaded=false,complete=false,mode='preview',elapsed=0,origin=0,raf=0,hiddenPause=false,renderer=null,lastUI=-999,lastFrame=0;
  let sourceSize={width:0,height:0};
  let profile={frames:0,gaps:[],gapMarkers:[],draw:[],errors:[],maxBounds:[],renderer:'pending'};
  const milestones=[];
  const send=(action,details={})=>{if(native)window.webkit.messageHandlers.launcher.postMessage({action,...details});};
  if(native)document.body.classList.add('native');
  function layout(){
    const b=root.getBoundingClientRect(),dpr=devicePixelRatio||1;
    const s=Math.min(b.width/1000,b.height/658,(sourceSize.width||1254)/(540*dpr));
    stageScale=s;
    scene.style.transform=`translate(${(b.width-1000*s)/2}px,${(b.height-658*s)/2}px) scale(${s})`;
    const pixels=Math.min(sourceSize.width||1254,Math.ceil(540*s*dpr));
    if(canvas.width!==pixels){canvas.width=canvas.height=pixels;renderer?.resize();}
    if(loaded)render(elapsed);
  }
  new ResizeObserver(layout).observe(root);layout();
  function makeRenderer(img){
    const gl=canvas.getContext('webgl',{alpha:true,antialias:true,premultipliedAlpha:true,preserveDrawingBuffer:false,powerPreference:'low-power'});
    if(!gl)throw new Error('当前 WebKit 无法创建动画画布。请从本机应用重新预览。');
    const vertex=`
      attribute vec2 aUV; varying vec2 vUV;
      uniform float lean, nod, leftHand, rightHand, blink, tail;
      float soft(vec2 p,vec2 c,vec2 r){float d=length((p-c)/r);return 1.0-smoothstep(0.15,1.0,d);}
      void main(){
        vec2 p=aUV;
        float neck=(1.0-smoothstep(.40,.55,p.y))*smoothstep(.24,.36,p.x);
        neck*=1.0-smoothstep(.61,.66,p.x)*smoothstep(.425,.465,p.y);
        float angle=lean*.035+nod*.018;
        vec2 center=vec2(.532,.455),d=p-center;
        vec2 rotated=vec2(cos(angle)*d.x-sin(angle)*d.y,sin(angle)*d.x+cos(angle)*d.y)+center;
        p+=((rotated-aUV)+vec2(lean*.005,lean*.007+nod*.007))*neck;
        p.y-=leftHand*.0100*soft(aUV,vec2(.558,.583),vec2(.076,.032));
        p.y-=rightHand*.0080*soft(aUV,vec2(.624,.574),vec2(.033,.032));
        p.x+=tail*.008*soft(aUV,vec2(.164,.496),vec2(.155,.245));
        p.y-=tail*.003*soft(aUV,vec2(.164,.496),vec2(.155,.245));
        p.x+=tail*.002*soft(aUV,vec2(.305,.715),vec2(.12,.13));
        float eye1=soft(aUV,vec2(.491,.362),vec2(.043,.040));
        float eye2=soft(aUV,vec2(.608,.346),vec2(.039,.038));
        p.y-=(aUV.y-.362)*blink*.88*eye1;
        p.y-=(aUV.y-.346)*blink*.88*eye2;
        gl_Position=vec4(p.x*2.0-1.0,1.0-p.y*2.0,0,1);vUV=aUV;
      }`;
    const fragment=`precision mediump float;varying vec2 vUV;uniform sampler2D picture;uniform float warmth;void main(){vec4 c=texture2D(picture,vUV);c.rgb*=vec3(1.0+warmth*.018,1.0+warmth*.007,1.0-warmth*.012);gl_FragColor=vec4(c.rgb*c.a,c.a);}`;
    function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;}
    const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,vertex));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,fragment));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));gl.useProgram(program);
    const count=96,uv=[],indices=[];
    for(let y=0;y<=count;y++)for(let x=0;x<=count;x++)uv.push(x/count,y/count);
    for(let y=0;y<count;y++)for(let x=0;x<count;x++){const i=y*(count+1)+x;indices.push(i,i+1,i+count+1,i+1,i+count+2,i+count+1);}
    gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(uv),gl.STATIC_DRAW);
    const pos=gl.getAttribLocation(program,'aUV');gl.enableVertexAttribArray(pos);gl.vertexAttribPointer(pos,2,gl.FLOAT,false,0,0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,gl.createBuffer());gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);
    gl.bindTexture(gl.TEXTURE_2D,gl.createTexture());gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,img);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);
    const uniforms=Object.fromEntries(['lean','nod','leftHand','rightHand','blink','tail','warmth'].map(k=>[k,gl.getUniformLocation(program,k)]));
    canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();fail('动画画布中断，已停止播放。');});
    profile.renderer='WebGL / single image mesh';
    let lastState='';
    const draw=state=>{
      const stamp=Object.values(state).map(x=>x.toFixed(4)).join('|');
      if(stamp===lastState)return;
      lastState=stamp;draw.draws++;
      for(const [k,v] of Object.entries(state))gl.uniform1f(uniforms[k],v);
      gl.clear(gl.COLOR_BUFFER_BIT);gl.drawElements(gl.TRIANGLES,indices.length,gl.UNSIGNED_SHORT,0);
    };
    draw.draws=0;draw.resize=()=>{gl.viewport(0,0,canvas.width,canvas.height);lastState='';};
    return draw;
  }

  // Reuse the original project's preallocated particles, dial ticks and one-shot
  // gradient sweep. Fixed choreography uses WAAPI; the existing RAF is for the
  // illustration mesh and observation clock. No animation library or timer.
  const particles=Array.from({length:8},(_,i)=>{
    const node=document.createElement('i');node.className='particle';
    node.style.width=node.style.height=`${i%3===0?5:3.5}px`;
    $('.particles').appendChild(node);return node;
  });
  for(let i=0;i<36;i++){
    const tick=document.createElementNS('http://www.w3.org/2000/svg','line'),a=i*Math.PI/18;
    const inner=i%3===0?248:251;
    for(const [key,value] of Object.entries({x1:280+Math.sin(a)*inner,y1:280-Math.cos(a)*inner,x2:280+Math.sin(a)*258,y2:280-Math.cos(a)*258}))tick.setAttribute(key,value);
    tick.style.opacity=i%3===0?'.7':'.3';$('.ticks').appendChild(tick);
  }
  const easing=getComputedStyle(document.documentElement).getPropertyValue('--ease-out').trim();
  function track(node,frames){
    const animation=node.animate(frames,{duration:DURATION,fill:'both',easing:'linear'});
    animation.pause();animation.currentTime=elapsed;motions.push(animation);
  }
  const key=(ms,values)=>({offset:ms/DURATION,...values});
  function cue(node,start,duration,from='translateY(8px)',opacity=1){
    const a={opacity:0,transform:reduced?'none':from},b={opacity,transform:'none'};
    track(node,[key(0,a),key(start,{...a,easing}),key(start+(reduced?200:duration),b),key(DURATION,b)]);
  }
  function prepareMotion(){
    motions.forEach(a=>a.cancel());motions=[];
    cue(canvas,0,550,'translateY(12px)');
    cue(nodes.lamp,100,500,'translateY(5px)');
    cue($('.copy-paper'),1160,420,'translateY(8px) scale(.985)');
    cue(nodes.title,1380,550,'translateY(10px)');
    cue(nodes.english,1980,380,'translateY(5px)');
    cue(nodes.code,2650,240,'translateX(-5px)');
    cue(nodes.rule,2800,240,'translateX(-5px)');
    cue(nodes.subtitle,3220,420,'translateY(5px)');
    document.querySelectorAll('.idea-notes span').forEach((n,i)=>cue(n,3160+i*50,240,'translateY(5px)'));
    document.querySelectorAll('.lab-line').forEach((n,i)=>cue(n,120+i*40,380,'translateX(-8px)',.75));
    cue(nodes.orbit,3000,500,'rotate(-12deg)',.48);
    track(nodes.glow,[key(0,{opacity:0}),key(350,{opacity:.22}),key(2280,{opacity:.22}),key(2890,{opacity:.92}),key(DURATION,{opacity:.92})]);
    track($('.lab-dial'),[key(0,{opacity:0,transform:reduced?'none':'rotate(-7deg)'}),key(150,{opacity:0,transform:reduced?'none':'rotate(-7deg)',easing}),key(1250,{opacity:.34,transform:'none'}),key(DURATION,{opacity:.34,transform:'none'})]);
    track(nodes.track,[key(0,{opacity:0}),key(2200,{opacity:0}),key(2450,{opacity:.45}),key(3220,{opacity:.2}),key(6850,{opacity:.2}),key(7100,{opacity:0}),key(DURATION,{opacity:0})]);
    if(reduced){
      cue($('.screen-response'),2280,200,'none',.22);
      cue(nodes.start,2280,200,'none',.55);
    }else{
      const taps=[1320,1550,1800,2020,2280],frames=[key(0,{opacity:0})];
      taps.forEach((t,i)=>frames.push(key(t-105,{opacity:0}),key(t,{opacity:i===4?.68:.36}),key(t+105,{opacity:0})));
      frames.push(key(DURATION,{opacity:0}));track($('.screen-response'),frames);track(nodes.start,frames);
      // Single low-opacity sweep behind Azhou, never over the title or face.
      track($('.light-sweep'),[key(0,{opacity:0,transform:'translateX(0px)'}),key(2420,{opacity:0,transform:'translateX(0px)',easing}),key(2600,{opacity:.16,transform:'translateX(270px)'}),key(3080,{opacity:0,transform:'translateX(720px)'}),key(DURATION,{opacity:0,transform:'translateX(720px)'})]);
      track($('.response-ring'),[key(0,{opacity:0,transform:'scale(.94)'}),key(2870,{opacity:0,transform:'scale(.94)',easing}),key(2980,{opacity:.65,transform:'scale(1.04)'}),key(3220,{opacity:0,transform:'scale(1.15)'}),key(DURATION,{opacity:0,transform:'scale(1.15)'})]);
      particles.forEach((node,i)=>{
        const start=2280+i*40,frames=[key(0,{opacity:0,transform:'translate(431px,337px)'})];
        for(let j=0;j<=12;j++){
          const u=j/12,v=1-u;
          const x=v*v*v*431+3*v*v*u*489+3*v*u*u*477+u*u*u*605;
          const y=v*v*v*337+3*v*v*u*337+3*v*u*u*174+u*u*u*174+(i%3-1)*Math.sin(u*Math.PI)*2;
          frames.push(key(start+u*600,{opacity:j===0||j===12?0:1,transform:`translate(${x}px,${y}px)`}));
        }
        frames.push(key(DURATION,{opacity:0,transform:'translate(605px,174px)'}));track(node,frames);
      });
    }
    if(playing)motions.forEach(a=>a.play());
  }
  function setReduced(value){
    reduced=Boolean(value);if(!loaded)return;
    prepareMotion();render(elapsed);
  }
  media.addEventListener('change',event=>setReduced(event.matches));

  const pulse=(t,center,width)=>{const d=Math.abs(t-center)/width;return d>=1?0:Math.pow(Math.cos(d*Math.PI/2),2);};
  function stage(t){return t<.6?'enter':t<2.65?'typing':t<3.55?'respond':t<7.05?'read':'settle';}
  function render(ms){
    const started=performance.now(),t=ms/1000;
    const lean=ease((t-.55)/.8)*(1-ease((t-2.55)/.7));
    const leftTap=pulse(t,1.32,.15)+pulse(t,1.80,.15)+pulse(t,2.28,.19)*1.15;
    const rightTap=pulse(t,1.55,.15)+pulse(t,2.02,.16);
    const nod=pulse(t,3.02,.40)-pulse(t,3.45,.36)*.35;
    const blink=pulse(t,1.02,.09)+pulse(t,3.85,.105);
    const tail=Math.sin((t-.55)*2.4)*ease((t-.55)/.65)*(1-ease((t-3.5)/.8));
    renderer?.({lean:reduced?0:lean,nod:reduced?0:nod,leftHand:reduced?0:leftTap,rightHand:reduced?0:rightTap,blink:reduced?0:blink,tail:reduced?0:tail,warmth:ease((t-2.3)/.6)});
    if(!playing)motions.forEach(a=>{a.currentTime=ms;});
    if(ms-lastUI>65||ms===0||ms===DURATION){
      const st=stage(t);root.dataset.stage=st;root.dataset.elapsed=t.toFixed(3);
      if(milestones.at(-1)?.stage!==st)milestones.push({stage:st,time:t});
      slider.value=String(t);$('#elapsed').textContent=`${t.toFixed(1)} / ${(DURATION/1000).toFixed(1)} 秒`;
      nodes.phase.textContent=mode==='launch'?(t<2.65?'阿舟正在准备工作台':t<7.05?'和阿舟一起，准备开始':'准备交接到 Codex'):(t<.6?'实验室正在亮起来':t<2.65?'阿舟正在准备工作台':t<7.05?'和阿舟一起，准备开始':'动作收束 · 即将结束预览');
      lastUI=ms;
    }
    profile.draw.push(performance.now()-started);
  }
  function stop(){playing=false;motions.forEach(a=>{a.pause();a.currentTime=elapsed;});cancelAnimationFrame(raf);raf=0;root.dataset.playing='false';$('#pause').textContent='继续';}
  function report(){
    const stat=xs=>{const a=[...xs].sort((a,b)=>a-b);return a.length?{count:a.length,median:a[Math.floor(a.length*.5)],p95:a[Math.floor(a.length*.95)],max:a.at(-1)}:null;};
    const bounds={};for(const id of ['title','english','subtitle','azhou']){const b=$('#'+id).getBoundingClientRect(),w=root.getBoundingClientRect();bounds[id]={left:b.left-w.left,top:b.top-w.top,right:b.right-w.left,bottom:b.bottom-w.top,inside:b.left>=w.left-.5&&b.right<=w.right+.5&&b.top>=w.top-.5&&b.bottom<=w.bottom+.5};}
    const rect=canvas.getBoundingClientRect();
    const effects={particles:particles.map(n=>Number(getComputedStyle(n).opacity)),ring:Number(getComputedStyle($('.response-ring')).opacity),sweep:Number(getComputedStyle($('.light-sweep')).opacity)};
    return {assetDisplay:{cssWidth:rect.width,cssHeight:rect.height,pixelWidth:rect.width*devicePixelRatio,backingWidth:canvas.width,backingHeight:canvas.height,stageScale,upsampled:rect.width*devicePixelRatio>sourceSize.width+.5,draws:renderer?.draws||0},effects,elapsed:elapsed/1000,duration:DURATION/1000,playing,complete,mode,reduced,stage:root.dataset.stage,text:{title:$('#title').textContent,english:$('#english').textContent,subtitle:$('#subtitle').textContent},viewport:{width:root.clientWidth,height:root.clientHeight,dpr:devicePixelRatio},bounds,source:sourceSize,milestones:[...milestones],profile:{frames:profile.frames,rafGapMs:stat(profile.gaps),jsSubmitMs:stat(profile.draw),gapsOver50:profile.gaps.filter(x=>x>50).length,gapMarkers:profile.gapMarkers,renderer:profile.renderer,errors:profile.errors,scope:'RAF interval and JS submission only; excludes GPU/compositor timing'}};
  }
  function finish(skipped=false){if(complete)return;stop();elapsed=DURATION;render(elapsed);complete=true;root.dataset.completed='true';root.classList.add('finished');$('#replay-end').hidden=mode==='launch';nodes.phase.textContent=mode==='launch'?'正在交接到 Codex':skipped?'已结束预览':'预览结束';send('complete',{skipped,report:report()});}
  function tick(now){if(!playing)return;elapsed=Math.min(DURATION,now-origin);if(lastFrame){const gap=now-lastFrame;profile.gaps.push(gap);if(gap>35)profile.gapMarkers.push({time:elapsed/1000,ms:gap});}lastFrame=now;profile.frames++;render(elapsed);if(elapsed>=DURATION){finish();return;}raf=requestAnimationFrame(tick);}
  function play(){if(!loaded||playing)return;if(complete){replay();return;}playing=true;motions.forEach(a=>{a.currentTime=elapsed;a.play();});origin=performance.now()-elapsed;lastFrame=0;root.dataset.playing='true';$('#pause').textContent='暂停';raf=requestAnimationFrame(tick);}
  function replay(){if(!loaded)return;stop();elapsed=0;complete=false;profile.frames=0;profile.gaps=[];profile.gapMarkers=[];profile.draw=[];milestones.length=0;lastUI=-999;root.dataset.completed='false';root.classList.remove('finished');$('#replay-end').hidden=true;render(0);play();}
  function seek(seconds){if(!loaded)return;stop();complete=false;root.dataset.completed='false';elapsed=Math.max(0,Math.min(DURATION,seconds*1000));lastUI=-999;root.classList.remove('finished');$('#replay-end').hidden=true;render(elapsed);return report();}
  function fail(message){stop();profile.errors.push(message);$('#error-message').textContent=message;$('.error-panel').hidden=false;send('assetError',{message});}
  window.launcherUI={promoteLaunch(){mode='launch';document.body.classList.add('launch-mode');},beginLaunch(){mode='launch';document.body.classList.add('launch-mode');replay();},replay,seek,report,pause:stop,resume:play,setReduced,error(message){stop();$('#error-message').textContent=message;$('.error-panel').hidden=false;},waiting(){nodes.phase.textContent='仍在等待 Codex 启动…';}};
  $('#replay').addEventListener('click',replay);$('#replay-end').addEventListener('click',replay);
  $('#pause').addEventListener('click',()=>playing?stop():play());slider.addEventListener('input',()=>seek(Number(slider.value)));
  $('.skip').addEventListener('click',()=>finish(true));$('#dismiss').addEventListener('click',()=>{send('close');if(!native)$('.error-panel').hidden=true;});
  addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();if(!$('.error-panel').hidden)send('close');else finish(true);}else if(!native&&mode==='preview'&&event.code==='Space'&&!['BUTTON','INPUT'].includes(event.target.tagName)){event.preventDefault();$('#pause').click();}});
  document.addEventListener('visibilitychange',()=>{if(native)return;if(document.hidden&&playing){hiddenPause=true;stop();}else if(!document.hidden&&hiddenPause){hiddenPause=false;play();}});
  addEventListener('error',event=>{profile.errors.push(event.message);send('jsError',{message:event.message});});
  (async()=>{try{
    if(!window.AZHOU_WORKING_IMAGE)throw new Error('缺少本地阿舟素材。请运行 tools/prepare-azhou-assets.py 后重新构建。');
    const img=new Image();img.src=window.AZHOU_WORKING_IMAGE;await img.decode();
    if(img.naturalWidth<1080||img.naturalHeight<1080)throw new Error('工作姿态图片小于本机 Retina 显示所需尺寸。');
    sourceSize={width:img.naturalWidth,height:img.naturalHeight};renderer=makeRenderer(img);loaded=true;layout();prepareMotion();render(0);send('ready',{duration:DURATION});if(!native)play();
  }catch(error){fail(error.message);}})();
})();
