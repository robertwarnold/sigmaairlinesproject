document.addEventListener('click',function(event) {
  if(event.target.closest('#clear_record_context')) document.getElementById('eng_clear')?.click();
  const target=event.target.closest('[data-attention]');
  if(target && window.Shiny) {
    Shiny.setInputValue('analytics_attention_pick',target.dataset.attention,{priority:'event'});
    window.location.hash = 'explorer';
  }
  if(event.target.closest('[data-engineering-record]')) {
    document.getElementById('fmea-register')?.scrollIntoView({block:'start'});
    const details=document.getElementById('engineering-record-detail');
    if(details) {details.open=true;details.scrollIntoView({block:'nearest'});}
  }
  if(event.target.closest('[data-engineering-cell]')) window.location.hash = 'explorer';
});
