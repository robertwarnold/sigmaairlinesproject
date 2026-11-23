(() => {
  const views = [...document.querySelectorAll('.workspace-view')];
  const nav = document.querySelector('.workspace-nav');
  if (!nav) return;

  function showView(moveFocus) {
    const hash = window.location.hash.slice(1);
    const view = views.find(candidate => candidate.id === hash) || views[0];
    views.forEach(candidate => { candidate.hidden = candidate !== view; });
    nav.querySelectorAll('a').forEach(link => {
      if (link.hash === '#' + view.id) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    document.title = view.querySelector('h1').textContent + ' | Sigma Airlines';
    window.dispatchEvent(new Event('resize'));
    if (moveFocus) {
      view.querySelector('h1').focus({preventScroll: true});
      window.scrollTo(0, 0);
    }
  }

  window.addEventListener('hashchange', () => showView(true));
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-open-system], [data-open-run]');
    if (!link || !window.Shiny || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if (link.dataset.openSystem) Shiny.setInputValue('open_system',link.dataset.openSystem,{priority:'event'});
    if (link.dataset.openRun) Shiny.setInputValue('open_run',link.dataset.openRun,{priority:'event'});
  });
  showView(false);
})();
