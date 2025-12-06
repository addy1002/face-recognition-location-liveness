import os
import cv2
import face_recognition
import pickle

# Paths
folderPath = 'Images'
pathList = os.listdir(folderPath)
print(" Found images:", pathList)

imgList = []
studentIds = []

# Load all student images
for path in pathList:
    fullPath = os.path.join(folderPath, path)
    img = cv2.imread(fullPath)
    if img is None:
        print(f" Could not read {path}, skipping...")
        continue
    imgList.append(img)
    studentIds.append(os.path.splitext(path)[0])
    print(f" Loaded {path} as ID: {os.path.splitext(path)[0]}")

# Encode faces
def findEncodings(imagesList):
    encodeList = []
    for idx, img in enumerate(imagesList):
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(img)
        if len(encodings) == 0:
            print(f" No face found in image {studentIds[idx]}")
            continue
        encodeList.append(encodings[0])
        print(f" Encoded: {studentIds[idx]}")
    return encodeList

print("\n Encoding Started...")
encodeListKnown = findEncodings(imgList)
print(" Encoding Complete! Encoded faces:", len(encodeListKnown))

# Save encodings
encodeListKnownWithIds = [encodeListKnown, studentIds]
with open("EncodeFile.p", "wb") as file:
    pickle.dump(encodeListKnownWithIds, file)
    print(" EncodeFile.p saved successfully!")

print("\n All done! You can now run app.py to start recognition.")
