// Presentation focus is local UI state; it does not change research data.
document.addEventListener('click', function(event) {
  if (event.target.closest('#presentation_toggle')) {
    document.body.classList.toggle('presentation-focus');
    if (window.Shiny) Shiny.setInputValue('view', 'Presentation mode', {priority:'event'});
    const tab=document.querySelector('[data-value="Presentation mode"]');
    if(tab) tab.click();
    if(document.body.classList.contains('presentation-focus') && !document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(()=>{});
    else if(document.fullscreenElement) document.exitFullscreen?.();
  }
});

document.addEventListener("keydown", function(event) { if((event.key==="Enter" || event.key===" ") && event.target.matches(".clickable-run")) { event.preventDefault(); event.target.click(); } });
