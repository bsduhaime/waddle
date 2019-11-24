'''
Valve Goldsrc WAD3 Reader/Writer
Version 0.1
Written by Brian Duhaime
Date created: 11/23/19
Date updated: 11/23/19

Kudos for the information on WAD files from this site:
http://hlbsp.sourceforge.net/index.php?content=waddef
'''

from PIL import Image
import ctypes
import struct


class WADHeader():
    def __init__(self, szMagic, nDir, nDirOffset):
        self.szMagic = szMagic
        self.nDir = ctypes.c_uint32(nDir)
        self.nDirOffset = ctypes.c_uint32(nDirOffset)

    def __str__(self):
        result = "Type: " + self.szMagic + ", "
        result += "Number of Entries: " + str(self.nDir.value) + ", "
        result += "Directory Location: " + str(self.nDirOffset.value)

    # Getters so we don't have to figure out what's a ctype or not
    def getszMagic(self):
        return self.szMagic

    def getnDir(self):
        return self.nDir.value

    def getnDirOffset(self):
        return self.nDirOffset.value


class WADDirEntry():
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
    def __init__(self, name, width, height, offsets):
        self.name = name
        w = ctypes.c_uint32(width)
        h = ctypes.c_uint32(height)
        self.size = (w.value, h.value)
        self.offsets = [ctypes.c_uint8(i) for i in offsets]
        self.colors = None
        self.image = None

    def __str__(self):
        result = self.name + ", "
        result += "Dimensions: " + str(self.size) + ", "
        offsetTemp = [i.value for i in self.offsets]
        result += "Mipmap Offsets: " + str(offsetTemp)
        return result


class WADFile():
    def __init__(self, wadLoc=None):
        # Create a dictionary for directory entries and texture data
        self.reference = {}
        if wadLoc is not None:
            self.readFile(wadLoc)
        else:
            self.header = None
            self.directory = None

    def readFile(self, wadLoc):
        wadContent = []
        with open(wadLoc, mode="rb") as wadFile:
            wadContent = wadFile.read()
            # Read in the header data
        hData = struct.unpack("@4sII", wadContent[:12])
        tName = hData[0].decode("utf-8")
        self.header = WADHeader(tName, hData[1], hData[2])

        # Read in the directory entries
        self.directory = []
        # 3*4b + 2*1b + 1*2b + 16*1b = 32b
        DIR_ENTRY_SIZE = 32   # bytes
        start = self.header.getnDirOffset()
        end = start + (self.header.getnDir() * DIR_ENTRY_SIZE)
        for byte in range(start, end, DIR_ENTRY_SIZE):
            dStop = byte + DIR_ENTRY_SIZE
            dirEntry = struct.unpack("@IIIB?H16s", wadContent[byte:dStop])
            tName = dirEntry[-1].decode("utf-8")
            tName = (tName[:-1] + "\0").upper()   # All texture names are null terminated
            self.directory.append(WADDirEntry(dirEntry[0], dirEntry[1], dirEntry[2], dirEntry[3], dirEntry[4], tName))
            # self.reference[tName] = [self.directory[-1]]

        # Read in image header & data, and create objects
        self.content = []
        H_SIZE = 16 + 8 + 4
        COL_SIZE = 256 * 3  # 256 elements with 3 RGB bytes each
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
            # Pixel data
            pixelPtr = mips[0] + headerLoc
            pixelLen = header[1] * header[2]
            pixelArray = wadContent[pixelPtr:pixelPtr + pixelLen]
            # Palette Data
            # Sum total offsets of each mip from each other
            totalOffset = sum(mips)
            # Color palette found from offset + header of texture + summation of all mipmap pixels + 2
            colPtr = headerLoc + totalOffset + int(pixelLen * 1.328125) + 2
            colPalette = list(struct.unpack("@"+str(COL_SIZE)+"B", wadContent[colPtr:colPtr+COL_SIZE]))
            self.content[-1].colors = colPalette
            # Image object creation and palette assignment
            self.content[-1].image = Image.frombytes("P", (header[1], header[2]), pixelArray, "raw")
            self.content[-1].image.putpalette(colPalette)

            # self.reference[tName].append(self.content[-1])


wadTest = WADFile("halflife.wad")
print(wadTest.header.getszMagic())

# Medkit - 55
i = 128
print(wadTest.content[i])
wadTest.content[i].image.show()
