"""
DogFaceNet
Dataset retrieving for landmarks detection

Licensed under the MIT License (see LICENSE for details)
Written by Guillaume Mougeot
"""

import numpy as np
import os
import skimage as sk
import pandas as pd
from ast import literal_eval # string to dict
import matplotlib.pyplot as plt
from tqdm import tqdm


############################################################
#  Data pre-processing for landmarks detection
############################################################


def resize_dataset(path='../data/landmarks/', output_shape=(500,500,3)):
    """
    Resize images from the {path + 'images/'} directory and the labels from
    the csv file in the {path} directory.
    The size of the output images is defined by output_shape.
    Then the resized images will be saved in {path + 'resized/'} directory
    and the resized labels in {path + 'resized_labels.npy'}
    """
    csv_path = path
    for file in os.listdir(path):
        if '.csv' in file:
            csv_path += file
    df = pd.read_csv(csv_path)

    index = df.index
    
    filenames = df.loc[:,'filename']
    dictionary = [literal_eval(df.loc[:,'region_shape_attributes'][i]) for i in range(len(index))]

    h,w,_ = output_shape
    labels = np.empty((0,7,2))
    
    print("Resizing images...")
    for i in tqdm(range(0,len(filenames)-7,7)):
        image = sk.io.imread(path + 'images/' + filenames[i])
        
        if len(image.shape)>1:
            image_resized = sk.transform.resize(image, output_shape, mode='reflect', anti_aliasing=False)

            sk.io.imsave(path + 'resized/' + str(i//7) + '.jpg', image_resized)

            x, y, _ = image.shape
            a = h/x
            b = w/y

            landmarks = np.empty((7,2))
            for j in range(7):
                landmarks[j] = np.array([
                    dictionary[i + j]['cx'] * b,
                    dictionary[i + j]['cy'] * a
                    ])
            
            labels = np.append(labels, np.expand_dims(landmarks, axis=0), axis=0)
        
    np.save(path + 'resized_labels.npy', labels)
    print("Done.")

    
def re_resize_dataset(path='../data/landmarks/', output_shape=(100,100,3)):
    """
    Re-resize the dataset after resize_dataset function
    """
    labels = np.load(path+'resized_labels.npy')
    h,w,_ = output_shape
    filenames = os.listdir(path+'resized/')
    output_labels = np.copy(labels)
    for i in tqdm(range(len(filenames))):
        image = sk.io.imread(path+'resized/'+filenames[i])
        
        x, y, _ = image.shape
        a = h/x
        b = w/y
        for j in range(7):
            output_labels[i][j] = np.array([labels[i][j][0] * a, labels[i][j][1] * b])

        image_resized = sk.transform.resize(image, output_shape, mode='reflect', anti_aliasing=False)
        sk.io.imsave(path + 're_resized/' + str(i) + '.jpg', image_resized)
    np.save(path + 're_resized_labels.npy', output_labels)


def rename_dataset(path='../data/landmarks/re_resized/'):
    filenames = os.listdir(path)
    for i in tqdm(range(len(filenames))):
        image = sk.io.imread(path+filenames[i])
        os.remove(path+filenames[i])
        sk.io.imsave(path+str(i)+'.jpg',image)

# Too slow...
def get_resized_dataset(path='../data/landmarks/', split=0.8, shape=(500,500,3)):
    labels = np.load(path+'resized_labels.npy')
    h,w,c = shape
    images = np.empty((0,h,w,c))


    csv_path = path
    for file in os.listdir(path):
        if '.csv' in file:
            csv_path += file
    df = pd.read_csv(csv_path)

    filenames = df.loc[:,'filename']

    print("Getting images...")
    for i in tqdm(range(0,len(filenames)-7,7)):
        image = sk.io.imread(path + 'resized/' + filenames[i])
        if len(image.shape)>1:
            images = np.append(images, np.expand_dims(image, axis=0), axis=0)
    print("Done.")

    assert len(images)==len(labels)

    train_split = int(split*len(images))

    return images[:train_split], labels[:train_split], images[train_split:], labels[train_split:]


############################################################
#  Data pre-processing for MTCNN
############################################################

def solve(dictionary, n):
    """
    Arguments:
     -dictionary: the dictionary containing the images
     -n: image index (times 7 as there are 7 labels per images in the dataset)
    Return:
    [[s*cos(theta) -s*sin(theta) tx]
     [s*sin(theta) s*cos(theta)  ty]
     [0            0             1 ]]
    """

    # Here we are in matplotlib coordinate system
    x_6 = dictionary[5+n]['cx']
    y_6 = dictionary[5+n]['cy']
    x_7 = dictionary[6+n]['cx']
    y_7 = dictionary[6+n]['cy']

    x_2 = dictionary[1+n]['cx']
    y_2 = dictionary[1+n]['cy']
    x_4 = dictionary[3+n]['cx']
    y_4 = dictionary[3+n]['cy']

    x_1 = dictionary[0+n]['cx']
    y_1 = dictionary[0+n]['cy']
    x_5 = dictionary[4+n]['cx']
    y_5 = dictionary[4+n]['cy']

    A = np.array([[x_6, -y_6, 1, 0], [y_6, x_6, 0, 1], [x_7, -y_7, 1, 0], [y_7, x_7, 0, 1]])
    b = np.array([1/2.0, 1, 1/2.0, 0])

#     sol = np.linalg.inv(A.T.dot(A)).dot(A.T.dot(b))

    # Add constraints: the eyes middle point and nose middle points should be in the middle of the picture
    A_c = np.append(A, np.array([[x_1 + x_5, -(y_1 + y_5), 2, 0], [x_2 + x_4, -(y_2 + y_4), 2, 0]]), axis=0)
    b_c = np.append(b, [1, 1])

    # Add constraints: the eyes y axis should be equal (eyes are horizontal)
    # y_1 = y_5 => y_1 - y_5 = 0
    A_c = np.append(A_c, np.array([[y_1 - y_5, x_1 - x_5,0,0],[y_2 - y_4, x_2 - x_4,0,0]]), axis=0)
    b_c = np.append(b_c, [0,0])

    sol = np.linalg.inv(A_c.T.dot(A_c)).dot(A_c.T.dot(b_c))
    
    return np.array([[sol[0], -sol[1], sol[2]],[sol[1], sol[0], sol[3]], [0,0,1]])



def compute_masks(path_cvs='../data/landmarks/', path_in='../data/landmarks/images/', path_out='../data/landmarks/masks/'):
    """
    Compute masks
    """

    for file in os.listdir(path_cvs):
        if '.csv' in file:
            df = pd.read_csv(path_cvs + file)
            df = df[df['region_count']==7]

    index = df.index
    # Contains the position of the different labels
    # dictionary[7*i + 1]['cx'] gives the x index of label 2 in image 1
    dictionary = [literal_eval(df.loc[:,'region_shape_attributes'][i]) for i in range(len(index))]

    filenames = df.loc[:,'filename']

    for i in tqdm(range(len(filenames)//7)):
        n = i*7
        image = sk.io.imread(path_in + filenames[n])
        if len(image.shape)>2:
            M = solve(dictionary, n)
            P = np.linalg.inv(M)
            A = P.dot([0,0,1])
            B = P.dot([1,0,1])
            D = P.dot([0,1,1])

            AB = np.array([B[0]-A[0],B[1]-A[1]])
            AD = np.array([D[0]-A[0],D[1]-A[1]])

            n_ab = np.linalg.norm(AB)**2
            n_ad = np.linalg.norm(AD)**2

            h , w = image.shape[0:2]
            mask = np.zeros((h,w), dtype=float)

            for i in range(h):
                for j in range(w):
                    AX = np.array([j-A[0], i-A[1]])
                    dot1 = AX.T.dot(AB)/n_ab
                    dot2 = AX.T.dot(AD)/n_ad
                    if dot1 >= 0 and dot1 <= 1 and dot2 >= 0 and dot2 <= 1:
                        mask[i][j] = 1.0
            
            sk.io.imsave(path_out + filenames[n], mask)






if __name__=="__main__":
    #resize_dataset(output_shape=(100,100,3))
    #re_resize_dataset(output_shape=(100,100,3))
    #train_images, train_labels, valid_images, valid_labels = get_resized_dataset()
    #rename_dataset()

    compute_masks()

    