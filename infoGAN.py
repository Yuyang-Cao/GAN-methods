from tensorflow.keras.datasets import mnist
from tensorflow.keras.layers import Input, Dense, Reshape, Flatten, Dropout, multiply, concatenate
from tensorflow.keras.layers import BatchNormalization, Activation, Embedding, ZeroPadding2D, Lambda
from tensorflow.keras.layers import LeakyReLU,UpSampling2D, Conv2D
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.utils import to_categorical
import tensorflow.keras.backend as K

import numpy as np
import matplotlib.pyplot as plt

class INFOGAN():
    #initialize the parameters for this GAN. MNIST data is 28*28*1 on greyscale, and we set class=10 for 10 digits, latent_dim is 72 by convention.
    def __init__(self):
        self.img_rows = 28
        self.img_cols = 28
        self.channels = 1
        self.num_classes = 10
        self.img_shape = (self.img_rows, self.img_cols, self.channels)
        self.latent_dim = 72
        
        optimizer = Adam(0.0002, 0.5)
        losses = ['binary_crossentropy', self.mutual_info_loss]
        
        self.discriminator, self.auxiliary = self.build_disc_and_q_net()
        
        self.discriminator.compile(loss = ['binary_crossentropy'], optimizer = optimizer, metrics = ['accuracy'])
        
        self.auxiliary.compile(loss = [self.mutual_info_loss], optimizer = optimizer, metrics = ['accuracy'])
        
        self.generator = self.build_generator()
        gen_input = Input(shape=(self.latent_dim,))
        fake_img = self.generator(gen_input)
        
        self.discriminator.trainable = False
        
        valid = self.discriminator(fake_img)
        target_label = self.auxiliary(fake_img)
        
        self.combined = Model(gen_input, [valid, target_label])
        self.combined.compile(loss=losses, optimizer = optimizer)
        
    def build_generator(self):
        model = Sequential()
        
        #similar to VGG-16
        model.add(Dense(128*7*7, activation = 'relu', input_dim = self.latent_dim))
        model.add(Reshape((7,7,128)))
        model.add(BatchNormalization(momentum=0.8))
        model.add(UpSampling2D())
        model.add(Conv2D(128, kernel_size=3, padding="same"))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))
        model.add(UpSampling2D())
        model.add(Conv2D(64, kernel_size=3, padding="same"))
        model.add(Activation("relu"))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(self.channels, kernel_size=3, padding='same'))
        model.add(Activation("tanh"))
        
        gen_input = Input(shape = (self.latent_dim,))
        fake_img = model(gen_input)
        model.summary()
        return Model(gen_input, fake_img)
    
    def build_disc_and_q_net(self):
        img = Input(shape = self.img_shape)
        
        model = Sequential()
        model.add(Conv2D(64, kernel_size=3, strides=2, input_shape=self.img_shape, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(Conv2D(128, kernel_size=3, strides=2, padding="same"))
        model.add(ZeroPadding2D(padding=((0,1),(0,1))))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(256, kernel_size=3, strides=2, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Conv2D(512, kernel_size=3, strides=2, padding="same"))
        model.add(LeakyReLU(alpha=0.2))
        model.add(Dropout(0.25))
        model.add(BatchNormalization(momentum=0.8))
        model.add(Flatten())
        
        img_embedding = model(img)
        
        validity = Dense(1, activation = 'sigmoid')(img_embedding)
        
        q_net = Dense(128, activation = 'relu')(img_embedding)
        label = Dense(self.num_classes, activation = 'softmax')(q_net)
        
        return Model(img, validity), Model(img,label)
    
    def mutual_info_loss(self, c, c_given_x):
        eps = 1e-8
        conditional_entropy = K.mean(-K.sum(K.log(c_given_x + eps)*c, axis=1))
        entropy = K.mean(-K.sum(K.log(c+eps)*c, axis = 1))
        
        return conditional_entropy + entropy
    
    def sample_generator_input(self, batch_size):
        sample_noise = np.random.normal(0,1,(batch_size,62))
        sample_labels = np.random.randint(0, self.num_classes, batch_size)
        sample_labels = to_categorical(sample_labels, num_classes = self.num_classes)
        
        return sample_noise, sample_labels
    
    def train(self, epochs, batch_size=128, sample_interval = 50):
        (X_train, y_train), (X_test, y_test) = mnist.load_data()
        X_train = (X_train.astype(np.float32) - 127.5)/127.5
        X_train = np.expand_dims(X_train, axis=3)
        y_train = y_train.reshape(-1,1)
        
        valid = np.ones((batch_size,1))
        fake = np.zeros((batch_size,1))
        
        for epoch in range(epochs):
            idx = np.random.randint(0, X_train.shape[0], batch_size)
            imgs = X_train[idx]
            
            sample_noise, sample_label = self.sample_generator_input(batch_size)
            gen_input = np.concatenate((sample_noise, sample_label), axis = 1)
            
            gen_imgs = self.generator.predict(gen_input)
            
            d_loss_real = self.discriminator.train_on_batch(imgs, valid)
            d_loss_fake = self.discriminator.train_on_batch(gen_imgs, fake)
            
            d_loss = np.add(d_loss_real, d_loss_fake)/2
            
            g_loss = self.combined.train_on_batch(gen_input,[valid, sample_label])
            print("%d [D loss: %.2f, acc: %.2f%%, Q loss: %.2f, G loss: %.2f]" %(epoch, d_loss[0], 100*d_loss[1], g_loss[1], g_loss[2]))
            
            if epoch % sample_interval == 0:
                self.sample_images(epoch)
                
    def sample_images(self, epoch):
        r, c = 10, 10
        fig, axs = plt.subplots(r,c)
        
        for i in range(c):
            sample_noise, _ = self.sample_generator_input(c)
            label = to_categorical(np.full(fill_value=i, shape=(r,1)), num_classes=self.num_classes)
            gen_input = np.concatenate((sample_noise, label), axis=1)
            gen_imgs = self.generator.predict(gen_input)
            print("DIMENSION:", gen_imgs.shape)
            gen_imgs = 0.5 * gen_imgs + 0.5
            for j in range(r):
                axs[j,i].imshow(gen_imgs[j,:,:,0], cmap='gray')
                axs[j,i].axis('off')
        plt.show()
        plt.close()

if __name__ == '__main__':
    infogan = INFOGAN()
    infogan.train(epochs=50000, batch_size=128, sample_interval=50)
