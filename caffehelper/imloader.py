# -*- coding: utf-8 -*-


import numpy as np
import io
import random



def easy_oversample(images, crop_dims):
    """
    :return images with their mirrored versions.

    Parameters
    ----------
    image : iterable of (H x W x K) ndarrays
    crop_dims : (height, width) tuple for the crops.

    Returns
    -------
    crops : (2*N x H x W x K) ndarray of crops for number of inputs N.
    """
    # Dimensions and center.
    im_shape = np.array(images[0].shape)
    crop_dims = np.array(crop_dims)


    # Extract crops
    crops = np.empty((2 * len(images), crop_dims[0], crop_dims[1],
                      im_shape[-1]), dtype=np.float32)
    ix = 0
    for im in images:
        crops[ix] = im
        ix += 1
        crops[ix] = im[:, ::-1, :]  # flip for mirrors
        ix += 1
    return crops

def general_oversample(images, crop_dims, num):
    if not num > 0:
        num = 1
    # Dimensions and center.
    im_shape = np.array(images[0].shape)
    crop_dims = np.array(crop_dims)

    # Extract crops
    crops = np.empty((num * len(images), crop_dims[0], crop_dims[1],
                      im_shape[-1]), dtype=np.float32)
    for im in images:
        for ix in range(num):
            x_p = random.randint(0, im_shape[0]- crop_dims[0])
            y_p = random.randint(0, im_shape[1] - crop_dims[1])
            crops[ix] = im[x_p:x_p+crop_dims[0], y_p:y_p+crop_dims[1],:]
    return crops





class CaffeIO():
    """
    image loader with caffe mode used for tensorflow model transfered from caffe 
    by scaling, center cropping, or oversampling.
    by handle with mean

    Parameters
    ----------
    image_dims : dimensions to scale input for cropping/sampling.
        Default is to scale to net input size for whole-image crop.
    mean, input_scale, raw_scale, channel_swap: params for
        preprocessing options.
    """
    def __init__(self, in_='data',image_dims=None,
                 mean_file=None, input_scale=None, raw_scale=None,
                 channel_swap=None):
        self.inputs = []
        self.inputs.append(in_)
        data_shape = (10,3,image_dims[0],image_dims[1])
        # configure pre-processing
        self.transformer = io.Transformer(
            {in_: data_shape})
        self.transformer.set_transpose(in_, (2, 0, 1))
        if mean_file is not None:
            self.transformer.set_mean(in_, self.load_meanfile(mean_file))
        if input_scale is not None:
            self.transformer.set_input_scale(in_, input_scale)
        if raw_scale is not None:
            self.transformer.set_raw_scale(in_, raw_scale)
        if channel_swap is not None:
            self.transformer.set_channel_swap(in_, channel_swap)

        self.crop_dims = np.array(data_shape[2:])
        if not image_dims:
            image_dims = self.crop_dims
        self.image_dims = image_dims

    def get_image(self, inputs, oversample=2, oversample_num = 10):
        """
        Get image for tensorflow model's predicting

        Parameters
        ----------
        inputs : iterable of (H x W x K) input ndarrays.
        oversample : boolean
            average predictions across center, corners, and mirrors
            when True (default). Center-only prediction when False.

        Returns
        -------
        images: (H x W x K) ndarray of image ndarrays after handle with mean
        """
        # Scale to standardize input dimensions.
        if len(inputs) == 1:
            input_ = np.zeros((len(inputs),
                               inputs[0].shape[0],
                               inputs[0].shape[1],
                               inputs[0].shape[2]),
                              dtype=np.float32)
            for ix, in_ in enumerate(inputs):
                input_[ix] = in_
        else:
            input_ = np.zeros((len(inputs),
                               self.image_dims[0],
                               self.image_dims[1],
                               inputs[0].shape[2]),
                              dtype=np.float32)
            for ix, in_ in enumerate(inputs):
                input_[ix] = io.resize_image(in_, self.image_dims)

        if oversample == 1:
            # Generate center, corner, and mirrored crops.
            input_ = io.oversample(input_, self.crop_dims)
        elif oversample == 2:
            input_ = easy_oversample(input_, self.crop_dims)
        elif oversample == 3:
            input_ = general_oversample(input_, self.crop_dims,oversample_num)
        else:
            # Take center crop.
            center = np.array(self.image_dims) / 2.0
            crop = np.tile(center, (1, 2))[0] + np.concatenate([
                -self.crop_dims / 2.0,
                self.crop_dims / 2.0
            ])
            crop = crop.astype(int)
            input_ = input_[:, crop[0]:crop[2], crop[1]:crop[3], :]
        images = np.zeros(np.array(input_.shape)[[0, 3, 1, 2]],
                            dtype=np.float32)
        for ix, in_ in enumerate(input_):
            images[ix] = self.transformer.preprocess(self.inputs[0], in_)

        # caffe and tensorflow orders are different ,transfer to tensorflow mode (?,227,227,3)
        images = np.transpose(images, (0, 2, 3, 1))
        return images

    def get_image_path(self,image_paths,oversample=True):
        """
        Get image for tensorflow model's predicting

        Parameters
        ----------
        image_paths : array of image paths
        oversample : boolean
            average predictions across center, corners, and mirrors
            when True (default). Center-only prediction when False.

        Returns
        -------
        images: (H x W x K) ndarray of image ndarrays after handle with mean
        """
        img_ar = []
        if not len(image_paths):
            raise Exception('image_paths should be a array of image paths '
                            'and the length of it should not be zero')
        for image_path in image_paths:
            img_ar.append(io.load_image(image_path))
        return self.get_image(img_ar,oversample)


    def load_meanfile(self,mean_file):
        """
        load mean file
        Parameters
        ----------
        mean_file : image mean file path
        
        Returns
        -------
        numpy format for mean
        
        """
        proto_data = open(mean_file, "rb").read()
        a = io.caffe_pb2.BlobProto.FromString(proto_data)
        mean = io.blobproto_to_array(a)[0]
        return mean

