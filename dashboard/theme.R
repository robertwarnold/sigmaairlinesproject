# Shared semantic tokens for dashboard HTML/SVG and academic ggplot/PDF figures.
chart_tokens <- list(background='#0c1118',surface='#111820',raised='#17212c',ink='#e9f0f6',
  muted='#aebdcb',accent='#6ac9df',grid='#283440',warning='#d4b774',failure='#df9492')
palette <- c('v2.0'='#a5b1bd','v3.0'='#b9a1e1','v3.0-audit'='#d4b774','v4.0'='#6ac9df')
chart_css_tokens <- function() htmltools::tags$style(htmltools::HTML(paste0(':root {',
  paste0('--',names(chart_tokens),':',unlist(chart_tokens),';',collapse=''),
  '--line:',chart_tokens$grid,';}')))
