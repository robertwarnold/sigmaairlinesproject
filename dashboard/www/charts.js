// SVG marks use native title tooltips; selection also works with a keyboard.
document.addEventListener('click', function (event) {
  const record = event.target.closest('[data-engineering-record]');
  if(record && window.Shiny) Shiny.setInputValue('eng_pick',record.dataset.engineeringRecord,{priority:'event'});
  const cell = event.target.closest('[data-engineering-cell]');
  if(cell && window.Shiny) Shiny.setInputValue('eng_risk_cell',cell.dataset.engineeringCell,{priority:'event'});
  const mark = event.target.closest('[data-run]');
  if (mark && window.Shiny) Shiny.setInputValue('chart_run', mark.dataset.run, {priority: 'event'});
});
document.addEventListener('keydown', function (event) {
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-engineering-record],[data-engineering-cell]')) {
    event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  }
  if ((event.key === 'Enter' || event.key === ' ') && event.target.matches('[data-run]')) {
    event.preventDefault(); event.target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
  }
});
