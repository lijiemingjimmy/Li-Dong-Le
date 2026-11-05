'use strict';
sessionStorage.removeItem('android-access');
history.replaceState(null, '', '/');
const screen = document.querySelector('#screen'), status = document.querySelector('#status');
let paused = false, busy = false, pointer = null, objectURL = null;
async function request(path, options = {}) {
  const response = await fetch(path, {...options, cache: 'no-store'});
  if (!response.ok) { const body = await response.json(); throw new Error(body.error || '连接失败'); }
  return response;
}
async function refresh() {
  if (paused || document.hidden || busy) return;
  busy = true;
  try {
    const blob = await (await request('/screen')).blob();
    const next = URL.createObjectURL(blob);
    screen.src = next;
    if (objectURL) URL.revokeObjectURL(objectURL);
    objectURL = next;
    status.textContent = '已连接 · ' + new Date().toLocaleTimeString();
  } catch (error) { status.textContent = error.message; }
  finally { busy = false; }
}
async function input(body) {
  status.textContent = '操作中…';
  try {
    await request('/input', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    setTimeout(refresh, 250);
  } catch (error) { status.textContent = error.message; }
}
function point(event) {
  const r=screen.getBoundingClientRect(), iw=screen.naturalWidth, ih=screen.naturalHeight;
  const scale=Math.min(r.width/iw,r.height/ih), left=r.left+(r.width-iw*scale)/2, top=r.top+(r.height-ih*scale)/2;
  return {x:Math.max(0,Math.min(iw-1,(event.clientX-left)/scale)),y:Math.max(0,Math.min(ih-1,(event.clientY-top)/scale))};
}
screen.addEventListener('pointerdown', event => { if (!screen.naturalWidth) return; pointer = {...point(event), time:performance.now()}; screen.setPointerCapture(event.pointerId); event.preventDefault(); });
screen.addEventListener('pointerup', event => {
  if (!pointer) return;
  const end = point(event), start = pointer; pointer = null;
  if (Math.hypot(end.x-start.x,end.y-start.y)<14 && performance.now()-start.time<500) input({action:'tap',x:end.x,y:end.y});
  else input({action:'swipe',x:start.x,y:start.y,endX:end.x,endY:end.y,duration:Math.max(100,Math.min(1500,performance.now()-start.time))});
});
screen.addEventListener('pointercancel', () => pointer = null);
document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => input({action:button.dataset.action})));
document.querySelector('#typing').addEventListener('submit', async event => { event.preventDefault(); const field = document.querySelector('#text'); if (field.value) { const value = field.value; field.value = ''; await input({action:'text',text:value}); } });
document.querySelector('#toggle').addEventListener('click', event => { const field = document.querySelector('#text'); field.type = field.type === 'password' ? 'text' : 'password'; event.target.textContent = field.type === 'password' ? '显示输入' : '隐藏输入'; });
document.querySelector('#pause').addEventListener('click', event => { paused = !paused; event.target.textContent = paused ? '恢复画面' : '暂停画面'; if (paused) status.textContent = '画面已暂停'; else refresh(); });
refresh(); setInterval(refresh, 1200);
