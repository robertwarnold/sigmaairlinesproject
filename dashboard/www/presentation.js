// Presentation focus is local UI state; it does not change research data.
document.addEventListener('click', function(event) {
  const row = event.target.closest('[data-generation]');
  if(row && window.Shiny) {
    Shiny.setInputValue('detail_run',row.dataset.generation,{priority:'event'});
    document.querySelector('[data-value="Experiment explorer"]')?.click();
    const details=document.getElementById('run-detail');
    if(details) {details.open=true; details.scrollIntoView({block:'nearest'});}
  }
  if (event.target.closest('#presentation_toggle')) {
    document.body.classList.toggle('presentation-focus');
    const active=document.body.classList.contains('presentation-focus');
    const button=document.getElementById('presentation_toggle');
    if(button) {button.textContent=active?'Exit presentation':'Present fullscreen';button.setAttribute('aria-pressed',String(active));}
    if (window.Shiny) Shiny.setInputValue('view', 'Presentation mode', {priority:'event'});
    const tab=document.querySelector('[data-value="Presentation mode"]');
    if(tab) tab.click();
    if(document.body.classList.contains('presentation-focus') && !document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(()=>{});
    else if(document.fullscreenElement) document.exitFullscreen?.();
  }
});
document.addEventListener('fullscreenchange',function() {
  if(!document.fullscreenElement) {
    document.body.classList.remove('presentation-focus');
    const button=document.getElementById('presentation_toggle');
    if(button) {button.textContent='Present fullscreen';button.setAttribute('aria-pressed','false');}
  }
});

document.addEventListener("keydown", function(event) {
  if(event.key==='Escape') {
    document.body.classList.remove('presentation-focus');
    if(document.fullscreenElement) document.exitFullscreen?.();
    const button=document.getElementById('presentation_toggle');
    if(button) {button.textContent='Present fullscreen';button.setAttribute('aria-pressed','false');}
  }
  if((event.key==="Enter" || event.key===" ") && event.target.matches(".clickable-run")) { event.preventDefault(); event.target.click(); }
});
