'''
Valve Goldsrc WAD3 Reader/Writer
Version 0.2.2
Written by Brian Duhaime
Date created: 11/23/19
Date updated: 11/24/19

Kudos for the information on WAD files from these sites:
http://hlbsp.sourceforge.net/index.php?content=waddef
http://www.j0e.io/tutorials/wad3-format/
'''

from PIL import Image, ImageTk
import ctypes
import struct
import sys
import tkinter as tk


class WADHeader():
    SIZE = 12

    def __init__(self, szMagic, nDir, nDirOffset, fSize=-1):
        self.szMagic = szMagic
        self.nDir = ctypes.c_uint32(nDir)
        self.nDirOffset = ctypes.c_uint32(nDirOffset)
        self.fileSize = fSize   # Number of bytes

    def __str__(self):
        result = "Type: " + self.szMagic + ", "
        if self.fileSize >= 0:
            result += "File Size (bytes): " + str(self.fileSize) + ", "
        result += "Number of Entries: " + str(self.nDir.value) + ", "
        result += "Directory Location: " + str(self.nDirOffset.value)
        return result

    # Getters so we don't have to figure out what's a ctype or not
    def getszMagic(self):
        return self.szMagic

    def getnDir(self):
        return self.nDir.value

    def getnDirOffset(self):
        return self.nDirOffset.value


class WADDirEntry():
    SIZE = 32  # bytes

    def __init__(self, nFilePos, nDiskSize, nSize, nType, comp, name):
        self.nFilePos = ctypes.c_uint32(nFilePos)
        self.nDiskSize = ctypes.c_uint32(nDiskSize)
        self.nSize = ctypes.c_uint32(nSize)
        self.nType = ctypes.c_uint8(nType)
        self.compression = comp
        self.name = name

    def __str__(self):
        result = "File Pos: " + str(self.nFilePos.value) + ", "
        result += "Disk Size: " + str(self.nDiskSize.value) + ", "
        result += "Compressed Size: " + str(self.nSize.value) + ", "
        result += "Type: " + str(self.nType.value) + ", "
        result += "Compressed? " + str(self.compression) + ", "
        result += "Name: " + self.name
        return result


class WADTexture():
    H_SIZE = 28        # Header size in bytes
    COL_SIZE = 768     # palette size in bytes

    def __init__(self, name, width, height, offsets):
        self.name = name
        w = ctypes.c_uint32(width)
        h = ctypes.c_uint32(height)
        self.size = (w.value, h.value)
        self.offsets = [ctypes.c_uint8(i) for i in offsets]
        self.colors = None
        self.images = [None] * 4

    def __str__(self):
        formattedName = self.name
        # Remove non-printable characters
        formattedName = ''.join([c for c in formattedName if ord(c) > 31 or ord(c) == 9])
        result = formattedName + ", "
        result += "Dimensions: " + str(self.size) + ", "
        offsetTemp = [i.value for i in self.offsets]
        result += "Mipmap Offsets: " + str(offsetTemp)
        return result

    def getSize(self):
        # Mip offset size + color table + padding
        result = sum([i.value for i in self.offsets]) + 768 + 4
        for img in self.images:
            result += len(bytearray(img.tobytes()))
        return result


class WADFile():
    def __init__(self, wadLoc=None):
        # Create a dictionary for directory entries and texture data
        self.reference = {}
        if wadLoc is not None:
            self.readFile(wadLoc)
        else:
            self.header = None
            self.directory = []
            self.content = []

    def readFile(self, wadLoc):
        wadContent = []
        with open(wadLoc, mode="rb") as wadFile:
            wadContent = wadFile.read()
            # Read in the header data
        hData = struct.unpack("@4sII", wadContent[:12])
        tName = hData[0].decode("utf-8")
        if tName != "WAD2" and tName != "WAD3":
            print("Given file is not in WAD2/WAD3 Format! Given:", tName)
            raise SystemExit
        self.header = WADHeader(tName, hData[1], hData[2], len(wadContent))

        # Read in the directory entries
        self.directory = []
        # 3*4b + 2*1b + 1*2b + 16*1b = 32b
        DIR_ENTRY_SIZE = WADDirEntry.SIZE   # bytes
        start = self.header.getnDirOffset()
        end = start + (self.header.getnDir() * DIR_ENTRY_SIZE)
        for byte in range(start, end, DIR_ENTRY_SIZE):
            dStop = byte + DIR_ENTRY_SIZE
            dirEntry = struct.unpack("@IIIB?H16s", wadContent[byte:dStop])
            tName = dirEntry[-1].decode("utf-8")
            tName = (tName[:-1] + "\0").upper()   # All texture names are null terminated
            self.directory.append(WADDirEntry(dirEntry[0], dirEntry[1], dirEntry[2], dirEntry[3], dirEntry[4], tName))

        # Read in image header & data, and create objects
        self.content = []
        H_SIZE = WADTexture.H_SIZE
        COL_SIZE = WADTexture.COL_SIZE  # 256 elements with 3 RGB bytes each
        for entry in self.directory:
            # Create the header info for the object
            headerLoc = entry.nFilePos.value
            header = struct.unpack("@16sII4B", wadContent[headerLoc:headerLoc+H_SIZE])
            tName = header[0].decode("utf-8")
            tName = (tName[:-1] + "\0").upper()   # All texture names are null terminated
            mips = [header[3], header[4], header[5], header[6]]
            self.content.append(WADTexture(tName, header[1], header[2], mips))
            # TODO: Handle compressed images?

            # Read in actual image data and create an appropriate Pillow Image object
            # Pixel data length
            pixelLen = header[1] * header[2]
            # Palette Data
            # Sum total offsets of each mip from each other
            totalOffset = sum(mips)
            # Color palette found from offset + header of texture + summation of all mipmap pixels + 2
            colPtr = headerLoc + totalOffset + int(pixelLen * 1.328125) + 2
            colPalette = list(struct.unpack("@"+str(COL_SIZE)+"B", wadContent[colPtr:colPtr+COL_SIZE]))
            self.content[-1].colors = colPalette
            # Image object creation and palette assignment for each mip level
            w, h = header[1], header[2]
            pixelPtr = headerLoc
            for i in range(len(mips)):
                pixelPtr += mips[i]
                pixelLen = int(w * h)
                pixelArray = wadContent[pixelPtr:pixelPtr + pixelLen]
                self.content[-1].images[i] = Image.frombytes("P", (int(w), int(h)), pixelArray, "raw")
                self.content[-1].images[i].putpalette(colPalette)
                w /= 2
                h /= 2
                pixelPtr += pixelLen

            self.reference[tName] = (entry, self.content[-1])

    def writeFile(self, outLoc):
        self.recalculateOffsets()    # Reformat offset info for final file
        out = [0] * ((self.header.getnDir() * 32) + self.header.getnDirOffset())
        # Pack and write the header, record its location
        hLump = struct.pack("@4sII", bytes(self.header.getszMagic(), "utf-8"), self.header.getnDir(), self.header.getnDirOffset())
        h_hLump = 0
        # Pack and write the directory, record its location
        dLump = bytearray()
        h_dLump = self.header.getnDirOffset()
        hs_tLump = []   # List of headers for each texture
        for entry in self.directory:
            eData = struct.pack("@IIIB?H16s", entry.nFilePos.value, entry.nDiskSize.value, entry.nSize.value, entry.nType.value, int(entry.compression), 0, bytes(entry.name, "utf-8"))
            dLump.extend(eData)
            hs_tLump.append(entry.nFilePos.value)
        # Pack and write each texture
        tLumps = []
        for tex in self.content:
            tData = struct.pack("@16sII4B", bytes(tex.name, "utf-8"), tex.size[0], tex.size[1], tex.offsets[0].value, tex.offsets[1].value, tex.offsets[2].value, tex.offsets[3].value)
            tData = bytearray(tData)
            for i in range(len(tex.offsets)):
                # Since we're dealing with an offset from the previous mip
                # except in the case of the first mip.
                mip = 0
                if i == 0:
                    mip = tex.offsets[i].value - len(tData)
                else:
                    mip = tex.offsets[i].value
                mipX = bytearray(b'\x00') * mip
                mipX.extend(tex.images[i].tobytes())
                tData.extend(mipX)
            tData.extend(b'\x00\x00')   # Two dummy bytes before the color palette
            tData.extend(bytearray(tex.colors))
            tLumps.append(tData)
        # Push bytes out to the file
        for i in range(h_hLump, h_hLump + len(hLump)):
            out[i] = hLump[i-h_hLump]
        for j in range(h_dLump, h_dLump + len(dLump)):
            out[j] = dLump[j-h_dLump]
        for k in range(len(tLumps)):
            tPtr = hs_tLump[k]
            tData = tLumps[k]
            for b in range(tPtr, tPtr + len(tData)):
                out[b] = tData[b-tPtr]
        with open(outLoc, "wb") as outFile:
            outFile.write(bytearray(out))

    def recalculateOffsets(self):
        # Call this when saving and/or changing texture data
        # Count all directory entries and update header info
        self.header.nDir = ctypes.c_uint32(len(self.directory))
        # Determine directory offset based off new texture info
        # TODO: change directory entry start positions here too
        offset = WADHeader.SIZE   # Start for header
        for tex in self.content:
            offset += tex.getSize()
        self.header.nDirOffset = ctypes.c_uint32(offset)


wadTest = WADFile(sys.argv[1])

# Initialization of Tkinter and all our variables.
W_WIDTH, W_HEIGHT = (1024, 768)
root = tk.Tk()
root.title(wadTest.header)
canvas = tk.Canvas(root, width=W_WIDTH, height=W_HEIGHT)
canvas.pack()
index = tk.IntVar(value=0)
currTex = wadTest.content[index.get()]
currTexLbl = tk.StringVar()
currTexLbl.set("Texture "+str(index.get())+"\n"+str(currTex))
mip0Tex = ImageTk.PhotoImage(currTex.images[0])


def updateTexture(i):
    global currTex, mip0, mip0Tex, currTexLbl
    if i < 0:
        index.set(len(wadTest.content)-1)
    elif i >= len(wadTest.content):
        index.set(0)
    else:
        index.set(i)
    currTex = wadTest.content[index.get()]
    mip0Tex = ImageTk.PhotoImage(currTex.images[0])
    mip0.configure(image=mip0Tex)
    currTexLbl.set("Texture "+str(index.get())+"\n"+str(currTex))


# Holds the image display
imgFrame = tk.Frame(root)                   # Holds the current image
imgFrame.place(relx=0.05, rely=0.05, relwidth=0.9, relheight=0.7)
mip0 = tk.Label(imgFrame, image=mip0Tex)
mip0.place(anchor='n', relx=0.5, rely=0.5)

# Holds the prev/next buttons, and image label
btnFrame = tk.Frame(root)                   # For all buttons/labels
btnFrame.place(relx=0.05, rely=0.75, relwidth=0.9, relheight=0.15)
imgInfo = tk.Label(btnFrame, textvariable=currTexLbl)  # Holds curr image name
imgInfo.place(anchor="n", relx=0.5, rely=0.2)
btnNext = tk.Button(btnFrame, text="Next", command=lambda: updateTexture(index.get()+1))      # Holds next button
btnNext.place(relx=0.8, rely=0.15, relwidth=0.15, relheight=0.7)
btnPrev = tk.Button(btnFrame, text="Previous", command=lambda: updateTexture(index.get()-1))  # Holds previous button
btnPrev.place(relx=0.05, rely=0.15, relwidth=0.15, relheight=0.7)
root.mainloop()
