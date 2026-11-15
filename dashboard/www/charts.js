// SVG marks use native title tooltips; selection also works with a keyboard.
document.addEventListener('click', function (event) {
  const mark = event.target.closest('[data-run]');
  if (mark && window.Shiny) Shiny.setInputValue('chart_run', mark.dataset.run, {priority: 'event'});
});
document.addEventListener('keydown', function (event) {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-run]')) {
    event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  }
});
