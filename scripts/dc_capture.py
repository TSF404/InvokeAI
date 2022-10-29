
#
#   This script is used to capture the Game Window
#   as well as display the Stable Diffusion output
#


import os
import time
import re
import sys

import json # -DC-
import multiprocessing # -DC-
from threading import Thread 
import signal # -DC-
import datetime # -DC-
import win32gui # -DC-
import pyautogui # -DC-
import PIL # -DC-
from PIL import Image, ImageTk, ImageDraw, ImageFont # -DC-
import tkinter as tk # -DC-
import cv2 # -DC-
import numpy  # -DC-



WINDOW_TARGETING = True
DEFAULT_WINDOW = "Snipping Tool"
    
def getInDirPath(settings):
    return os.getcwd() + "/" + settings["inDir"]+"_"+settings["sessionID"]
    
def getOutDirPath(settings):
    return os.getcwd() + "/" + settings["outDir"]+"_"+settings["sessionID"]
    
def getLatestImageInPath(dirpath, valid_extensions=('jpg','jpeg','png')):
    valid_files = [os.path.join(dirpath, filename) for filename in os.listdir(dirpath)]
    valid_files = [f for f in valid_files if '.' in f and \
        f.rsplit('.',1)[-1] in valid_extensions and os.path.isfile(f)]
    if not valid_files:
        raise ValueError("No valid images in %s" % dirpath)
    return max(valid_files, key=os.path.getmtime)
    
def getInitSettings(): # -DC-
    global WINDOW_TARGETING, DEFAULT_WINDOW

    print("\n\n\n---------------------")
    print("\nEnter a Session Identifier")
    print("(Blank input defaults it to 123)\n")
    chosenID = input("Session Identifier > ")
    if chosenID == "":
        chosenID = "123"
        print("Setting ID to " + chosenID)
    
    settingsJSONData = json.load(open(os.getcwd() + "/settings.json"))
    WINDOW_TARGETING = settingsJSONData["windowTargeting"]

    chosenInDir = "outputs/img2img/img2img_input"
    chosenOutDir = "outputs/img2img/img2img_output"
    
    if WINDOW_TARGETING:
        print("\n---------------------")
        print("\nActive Windows:\n")
        for window in pyautogui.getAllWindows():
            if window.title.strip() != "":
                print(window.title)
        print("")
        print("\nEnter Windows Title of Game Window from the list above\n")
        chosenGameWindowTitle = input("Title > ")
        if chosenGameWindowTitle == "":
            chosenGameWindowTitle = DEFAULT_WINDOW
        else:
            foundMatchingWindow = False
            foundBestMatch = False
            for window in pyautogui.getAllWindows():
                if chosenGameWindowTitle == window.title:
                    foundMatchingWindow = True
                elif chosenGameWindowTitle in window.title: # Search for the best matching title (contains letters + least characters in title)
                    if foundBestMatch:
                        if len(window.title) < len(bestMatch):
                            bestMatch = window.title
                    else:
                        bestMatch = window.title
                    foundBestMatch = True
            if not foundMatchingWindow:
                if foundBestMatch:
                    chosenGameWindowTitle = bestMatch
                else:
                    chosenGameWindowTitle = DEFAULT_WINDOW
                    
                    
            
        print("Setting Window Title to " + chosenGameWindowTitle)
        mouseTopLeft=(0,0)
        mouseBottomRight=(0,0)
    else:
        print("\n---------------------")
        print("\nPosition your mouse at the top left corner")
        input("Press Enter > ")
        mouseTopLeft = pyautogui.position()
        print(mouseTopLeft)
        print("\nPosition your mouse at the bottom right corner")
        input("Press Enter > ")
        mouseBottomRight = pyautogui.position()
        chosenGameWindowTitle=0

    input("-")
    print("\n---------------------\n")
    return {"sessionID":chosenID, 
            "gameWindowTitle":chosenGameWindowTitle,
            "mouseCoords":[mouseTopLeft[0], mouseTopLeft[1], mouseBottomRight[0], mouseBottomRight[1]],
            "inDir":chosenInDir, "outDir":chosenOutDir}

def createInitDir(settings):
    if not os.path.exists(getInDirPath(settings)):
        os.makedirs(getInDirPath(settings))
    if not os.path.exists(getOutDirPath(settings)):
        os.makedirs(getOutDirPath(settings))

def main_captureGame(args):
    global WINDOW_TARGETING
    
    def capture(fileNum):
                
        # save screenshot
        screenshotImage = pyautogui.screenshot() 
        
        # setup crop boundaries
        if WINDOW_TARGETING:
            gameWindow = win32gui.FindWindowEx(None, None, None, programState["settings"]["gameWindowTitle"])
            rect = win32gui.GetWindowRect(gameWindow)
        else:
            rect = programState["settings"]["mouseCoords"]
        
        left = rect[0]
        top = rect[1]
        right = rect[2]
        bottom = rect[3]
        
        TOP_CROP = 35
        BOTTOM_CROP = 15
        LEFT_CROP = 10
        RIGHT_CROP = 10
        
        print(left,top,right,bottom)
        
        # save cropped screenshot
        filenameCropped = "in_" + str(fileNum) + ".png" 
        filepathCropped = getInDirPath(programState["settings"]) + "/" + filenameCropped
        
        screenshotCropped = screenshotImage.crop((left + LEFT_CROP, top + TOP_CROP, right - RIGHT_CROP, bottom - BOTTOM_CROP))
        screenshotCropped = screenshotCropped.resize((512,512))
        screenshotCropped.save(filepathCropped, quality=100)
        
        print("[Capture]: Saved " + filepathCropped)
        
    INTERVAL = 1
    
    prevTime = datetime.datetime.now()
    timeCounter = 0
    fileCounter = 1

    while True:
        timeDiff = datetime.datetime.now() - prevTime
        prevTime = datetime.datetime.now()
        deltaTime = timeDiff.total_seconds()
        timeCounter += deltaTime
        
        if timeCounter > INTERVAL:
            try:
                capture(fileCounter)
                fileCounter += 1
                timeCounter = 0
            except:
                print("[Capture]: Error Capturing failed")
        
        if programState["sequence"] == "END": 
            break


def main_displayOutput(programState):
    def updateDisplay():
        print("[Display]: Updating")
        
        try:
            outPath = getOutDirPath(programState["settings"])
            
            pilImage = PIL.Image.open(getLatestImageInPath(outPath, ".png"))
            imgWidth, imgHeight = pilImage.size
            
            opencvImage = cv2.cvtColor(numpy.array(pilImage), cv2.COLOR_RGB2BGR)
            opencvImage = cv2.cvtColor(opencvImage, cv2.COLOR_BGR2RGB)
            canvasWidth, canvasHeight = label.winfo_width(), label.winfo_height()

            minCanvasSize = int(min(canvasWidth, canvasHeight)) # Square Ratio

            resizedImage = cv2.resize(opencvImage, (minCanvasSize, minCanvasSize), cv2.INTER_AREA)
            resizedImagePIL = Image.fromarray(resizedImage).convert("RGB") # to PIL format

            # update image
            tkimg = ImageTk.PhotoImage(resizedImagePIL)
            label.config(image=tkimg)
            label.image = tkimg # save a reference to avoid garbage collected
        except:
            print("[Display]: Cannot update display")
            
            emptyImg = img = Image.new("RGB", (512,512))
            tkimg = ImageTk.PhotoImage(emptyImg)
            label.config(image=tkimg)
            label.image = tkimg

        ms_delay = 50
        root.after(ms_delay, updateDisplay)
    
    root = tk.Tk()
    root.attributes("-disabled", 0)
    label = tk.Label(root, bg="black", width=512, height=512)
    label.pack(fill="both", expand=1)
    updateDisplay()
    root.mainloop()


def signal_handler(signum, frame):
    global programState, captureGameThread
    programState["sequence"] = "END"
    captureGameThread.join() 
    sys.exit(0)

if __name__ == '__main__':

    initSettings = getInitSettings() # -DC-
    createInitDir(initSettings)

    signal.signal(signal.SIGINT, signal_handler)

    programState = {"sequence":"BEGIN", "settings":initSettings}
    
    captureGameThread = Thread(target = main_captureGame, args =(lambda : programState,))

    captureGameThread.start()
    
    main_displayOutput(programState)

    # Keeps it alive (so program can be terminated with SIGINT)
    while True:
        time.sleep(1)
    
    
