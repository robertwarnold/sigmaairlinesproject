# Explicit trusted-workstation launcher; never deploy this mode to a public host.
Sys.setenv(SIGMA_ENGINEERING_PRIVATE='1')
.libPaths(c('.venv/r-library',.libPaths()))
shiny::runApp('dashboard',host='127.0.0.1',port=5393,launch.browser=FALSE)
