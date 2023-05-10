import sys, os, keyring, time, requests,json, argparse  # manage files, api key, runtime, astrometry.net connection
from astropy.coordinates import SkyCoord  # manage coords
from astroquery.astrometry_net import AstrometryNet  # make API requests
from astropy.io import fits
from astropy.utils.data import get_pkg_data_filename
from astropy.table import Table

headerKeywords = ["WCSAXES", "CTYPE1", "CTYPE2", "EQUINOX", "LONPOLE", "LATPOLE", "CRVAL1", "CRVAL2", "CRPIX1", "CRPIX2", "CUNIT1", "CUNIT2", "CD1_1", "CD1_2", "CD2_1", "CD2_2", "IMAGEW", "IMAGEH",
                  "A_ORDER", "A_0_0", "A_0_1", "A_0_2", "A_1_0", "A_1_1", "A_2_0", "B_ORDER", "B_0_0", "B_0_1", "B_0_2", "B_1_0", "B_1_1", "B_2_0", "AP_ORDER", "AP_0_0", "AP_0_1", "AP_0_2", "AP_1_0",
                  "AP_1_1", "AP_2_0", "BP_ORDER", "BP_0_0", "BP_0_1", "BP_0_2", "BP_1_0", "BP_1_1", "BP_2_0"]

def isFits(filePath):
    return filePath[-4:] == ".fit" or filePath[-4:] == "fits"


# recursively gather a list of the paths of the files in our subdirectories
def expandPath(workingDir, returner):
    if not os.path.isdir(workingDir):  # we're a file. append ourselves and return!
        returner.append(workingDir)
        return returner
    else:  # call our nodes
        for item in os.listdir(workingDir):
            returner = expandPath(workingDir + "/" + item, returner)
        return returner

def solveImg(filePath, ast):
    wcs_header = ast.solve_from_image(filePath)
    return wcs_header

def formatOutput(coords):
    decimal = coords.to_string("decimal").split(" ")
    sexagesimal = coords.to_string("hmsdms").split(" ")
    return decimal[0]+", "+ decimal[1]+" / "+ sexagesimal[0] +", "+ sexagesimal[1]

def writeToFITS(path, solvedDict,keywords=None):  # new dict should be {headerKeyword:newValue}
    global headerKeywords
    s = time.perf_counter()
    if not keywords:
        keywords = headerKeywords
    print("Loading file",path)
    hduList = fits.open(path, mode='update')
    print("Writing pos",formatOutput(SkyCoord(float(solvedDict["CRVAL1"]), float(solvedDict["CRVAL2"]), unit='deg')),"to file")
    for field in keywords:
        hduList[0].header[field] = solvedDict[field]
    hduList.close()
    elapsed = time.perf_counter() - s

    print(f"Written in {elapsed:0.2f} seconds. \n- - - -")


def batchSolve(directory, APIKey, write = False, verbose=False, keywords=None):
    # check astrometry.net connection
    response = requests.head("https://nova.astrometry.net/user_images/7840195#annotated", allow_redirects=False)
    code = int(response.status_code)
    if code in range(400, 600):
        raise ConnectionError("[ERROR] Connection to astrometry.net failed. Got HTTP status code " + str(code))
    global headerKeywords
    failList = []
    headers = {}
    if verbose:
        print("Setting Up...")
    if not os.path.exists(directory):
        raise AttributeError("Could not find " + directory)
    filePaths = [p for p in expandPath(directory, []) if isFits(p)]
    if not len(filePaths):
        raise AttributeError("No .fit or .fits files found in directory")
    try:
        ast = AstrometryNet()
        ast.api_key = APIKey
        AstrometryNet.key = APIKey
    except Exception as e:
        raise AttributeError("API Key Rejected")

    if not keywords:
        keywords = headerKeywords
    if verbose:
        print(len(filePaths), "files found. Solving....")

    for i, file in enumerate(filePaths):
        num = "[" + str(i+1) + "/" + str(len(filePaths)) + "]"
        solveDict = {}
        s = time.perf_counter()
        solveResult = solveImg(file, ast)  # this may also raise an exception?
        elapsed = time.perf_counter() - s
        if len(solveResult):
            for key in headerKeywords:
                solveDict[key] = solveResult[key]
            headers[file] = solveDict
            if verbose:
                print('\n\033[1;32m' + num, "Solved file", file, '\033[0;0m', f"in {elapsed:0.2f} seconds.")
            if write:
                writeToFITS(file, headers[file])

        else:
            if verbose:
                print('\n\033[1;31m' + num, "Solve failed on file", file, '\033[0;0m', f"in {elapsed:0.2f} seconds")
            failList.append(file)
    return headers, failList


# usage: python fieldCorrector.py filepath coordsPath (path to text file with coordinates) overwrite APIKey (if not added to keyring as "astrometry")
if __name__ == "__main__":
    readLocal = False
    parser = argparse.ArgumentParser(description='Batch plate-solve provided .fit/.fits file(s) with astrometry.net. Requires astrometry API key')
    parser.add_argument('directory', type=str,
                        help='the directory of files (or file) to solve')
    parser.add_argument('-w', '-write',
                        action='store_true', dest= "writeToHeader", help = "write WCS coords to fits header of solved file")
    parser.add_argument('-v', '-verbose', action='store_true', dest="verbose", help='enable verbose mode')
    parser.add_argument('-k', '-keyring',dest="keyring",
                        action='store_true', help='retrieve astrometry.net API key from system keyring credential \"batchSolver:astrometry_net\"')
    parsed,remaining = parser.parse_known_args()
    if parsed.keyring:
        parser.add_argument('username', type=str,
                            help="username associated with the astrometry keyring credential")
    else:
        parser.add_argument('APIKey', help='astrometry.net API key to be used for fits submission')
    remaining = [parsed.directory] + remaining
    args = parser.parse_known_args(remaining, namespace=parsed)[0]
    if len(sys.argv) < 4:
        raise AttributeError(
            "Usage: python3 batchSolve.py [dir] [writeToHeader] (True or False - write wcs to header of input FITs file(s) when solved) [keyring] (True or False - retrieve astrometry.net API key from system keyring credential \"batchSolver:astrometry_net\") [AstrometryAPIKey OR username] (leave username blank if using keyring and entry has no username associated)")
    path = os.path.abspath(args.directory)
    if args.keyring:
        if not args.username:
            username = ""
        else:
            username = args.username
        APIKey = keyring.get_password("batchSolve:astrometry_net", username)
    else:
        APIKey = args.APIKey
    if not APIKey:
        raise AttributeError("Unable to find API Key in keyring that matches provided username")
    print("Args",args)
    if not readLocal:
        headers,failed = batchSolve(path,APIKey,args.writeToHeader,args.verbose)  #{filename : header dictionary}, list of failed filenames
        # with open("solvedDicts.json", "w") as outfile:
        #     json.dump(headers, outfile)
        print("\nResults:")
        print("Solved",len(headers.keys()),"out of",(len(failed)+len(headers.keys())))
        print("Failed to solve the following files:",failed)
        print("Solutions:")
        for file in headers.keys():
            head = headers[file]
            formattedCoords = formatOutput(SkyCoord(float(head["CRVAL1"]), float(head["CRVAL2"]), unit='deg'))
            print(file+":",formattedCoords)
    else:
        headers = json.load(open("solvedDicts.json"))