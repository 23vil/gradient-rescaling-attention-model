from keras.layers import Add, BatchNormalization, Conv2D, Dense, Flatten, Input, LeakyReLU, PReLU, Concatenate, Lambda
from keras.models import Model
from keras.applications.vgg19 import VGG19

from keras import backend as K
from .common import SubpixelConv2D, Normalization_01, Normalization_m11, Denormalization_m11

LR_SIZE = 24
HR_SIZE = 96


def upsample(x_in, num_filters):
	x = Conv2D(num_filters * 4, kernel_size=3, padding='same')(x_in)
	x = SubpixelConv2D(2)(x)
	return PReLU(shared_axes=[1, 2])(x)


def res_block(x_in, num_filters):
	x = Conv2D(num_filters, kernel_size=3, padding='same')(x_in)
	x = BatchNormalization()(x)
	x = PReLU(shared_axes=[1, 2])(x)
	x = Conv2D(num_filters, kernel_size=3, padding='same')(x)
	x = BatchNormalization()(x)
	x = Add()([x_in, x])
	return x


def discr_block(x_in, num_filters, strides=1, bn=True):
	x = Conv2D(num_filters, kernel_size=3, strides=strides, padding='same')(x_in)
	x = LeakyReLU(alpha=0.2)(x)
	if bn:
		x = BatchNormalization()(x)
	return x


def sr_resnet(num_filters=64, num_res_blocks=16, pred_logvar=False):
	x_in = Input(shape=(None, None, 3))
	x = Normalization_01()(x_in)

	x = Conv2D(num_filters, kernel_size=9, padding='same')(x)
	x = x_1 = PReLU(shared_axes=[1, 2])(x)

	for _ in range(num_res_blocks):
		x = res_block(x, num_filters)

	x = Conv2D(num_filters, kernel_size=3, padding='same')(x)
	x = BatchNormalization()(x)
	x = Add()([x_1, x])

	x = upsample(x, num_filters)
	x = upsample(x, num_filters)

	x_mean = Conv2D(3, kernel_size=9, padding='same', activation='tanh')(x)
	x_mean = Denormalization_m11()(x_mean)
	if pred_logvar:
		x_logvar = Conv2D(3, kernel_size=9, padding='same')(x)
		x_mean = Concatenate()([x_mean, x_logvar])

	m = Model(x_in, x_mean)
	return m




def generator(num_filters=64, num_res_blocks=16, pred_logvar=False):
	return sr_resnet(num_filters, num_res_blocks, pred_logvar=pred_logvar)


def discriminator(num_filters=64):
	x_in = Input(shape=(HR_SIZE, HR_SIZE, 3))
	x = Normalization_m11()(x_in)

	x = discr_block(x, num_filters, bn=False)
	x = discr_block(x, num_filters, strides=2)

	x = discr_block(x, num_filters * 2)
	x = discr_block(x, num_filters * 2, strides=2)

	x = discr_block(x, num_filters * 8)
	x = discr_block(x, num_filters * 8, strides=2)

	x = discr_block(x, num_filters * 8)
	x = discr_block(x, num_filters * 8, strides=2)

	x = Flatten()(x)

	x = Dense(1024)(x)
	x = LeakyReLU(alpha=0.2)(x)
	x = Dense(1, activation='sigmoid')(x)

	return Model(x_in, x)


def srgan(generator, discriminator):
	discriminator.trainable = False

	x_in = Input(shape=(LR_SIZE, LR_SIZE, 3))
	x_1 = generator(x_in)
	x_1_mean = Lambda(lambda x: x[:,:,:,:3])(x_1)
	x = discriminator(x_1_mean)

	return Model(x_in, [x_1, x])


def vgg_22():
	return _vgg(5)


def vgg_54():
	return _vgg(20)


def _vgg(output_layer):
	vgg = VGG19(input_shape=(None, None, 3), include_top=False)
	mdl = Model(vgg.input, vgg.layers[output_layer].output)
	mdl.trainable = False
	return mdl
