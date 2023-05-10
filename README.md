# batchSolve
Batch plate-solve provided .fit/.fits file(s) with astrometry.net. Requires astrometry API key

usage: python batchSolver.py [-h] [-w] [-v] [-k] [directory] [username OR APIKey]
positional arguments:
  directory     the directory of files (or file) to solve
  username      username associate with keyring credential (if using -k option)
  APIKey        astrometry.net API Key (if not using -k)

options:
  -h, --help    show this help message and exit
  -w, -write    write WCS coords to fits header of solved file
  -v, -verbose  enable verbose mode
  -k, -keyring  retrieve astrometry.net API key from system keyring credential "batchSolver:astrometry_net"
