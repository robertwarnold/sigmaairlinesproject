# Shared semantic tokens for dashboard HTML/SVG and academic ggplot/PDF figures.
chart_tokens <- list(background='#0B1016',surface='#121A23',raised='#18232E',ink='#EAF0F4',
  muted='#A3B2BF',accent='#62C5D1',grid='#26323E',warning='#d4b774',failure='#df9492')
palette <- c('v2.0'='#a5b1bd','v3.0'='#b9a1e1','v3.0-audit'='#d4b774','v4.0-inventory'='#62C5D1')
chart_css_tokens <- function() htmltools::tags$style(htmltools::HTML(paste0(':root {',
  paste0('--',names(chart_tokens),':',unlist(chart_tokens),';',collapse=''),
  '--line:',chart_tokens$grid,';}')))
