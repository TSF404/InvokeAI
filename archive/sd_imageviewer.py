
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import time
import random
import os
import cv2
import numpy

OUTPUT_FOLDER = os.getcwd() + "\outputs\img-samples\img2img_output"



def get_latest_image(dirpath, valid_extensions=('jpg','jpeg','png')):
    """
    Get the latest image file in the given directory
    """

    valid_files = [os.path.join(dirpath, filename) for filename in os.listdir(dirpath)]
    valid_files = [f for f in valid_files if '.' in f and \
        f.rsplit('.',1)[-1] in valid_extensions and os.path.isfile(f)]
    if not valid_files:
        raise ValueError("No valid images in %s" % dirpath)
    return max(valid_files, key=os.path.getmtime)


def update_image():
    try:
        print("Updating")
        pilImage = Image.open(get_latest_image(OUTPUT_FOLDER, ".png"))
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

        ms_delay = 50
        root.after(ms_delay, update_image)
    except:
        print("Fail")
        update_image()

root = tk.Tk()
root.attributes("-disabled", 0)

# label for showing image
label = tk.Label(root, bg="black")
label.pack(fill="both", expand=1)

update_image() # start the slide show
root.mainloop()






'''





while True:
   image = cv2.imread(get_latest_image(OUTPUT_FOLDER,".png"))
   cv2.imshow('image', image)
   key = cv2.waitKeyEx()
   cv2.waitKeyEx(1)
   print("update")
'''
#while True:
#    time.sleep(1)

#cv2.imshow('image window', image)
#cv2.waitKey(1000)

#cv2.destroyAllWindows()
