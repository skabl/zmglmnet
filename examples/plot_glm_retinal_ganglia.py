# -*- coding: utf-8 -*-
"""
=================================================================
GLM for Spike Trains Prediction in Primate Retinal Ganglion Cells
=================================================================

* Original tutorial adapted from Johnathan Pillow, Princeton University
* Dataset provided by E.J. Chichilnisky, Stanford University
* The dataset is granted by the original authors for educational use only
* Please contact ``pillow@princeton.edu`` if using beyond its purposes

The original MATLAB and Python tutorial can be found from
https://github.com/pillowlab/GLMspiketraintutorial.

These data were collected by Valerie Uzzell in the lab of
E.J. Chichilnisky at the Salk Institute. For full information see
Uzzell et al. (J Neurophys 04) [1]_, or Pillow et al. (J Neurosci 2005) [2]_.

In this tutorial, we will demonstrate how to fit linear GLM and
Poisson GLM to predict the spike counts
recorded from primate retinal ganglion cells.
The dataset contains spike responses from 2 ON and 2 OFF parasol
retinal ganglion cells (RGCs) in primate retina, stimulated with
full-field `binary white noise`. Two experiment performed consisted of a
long (20-minute) binary stochastic (non-repeating) stimulus
which can be used for computing the spike-triggered average
(or characterizing some other model of the response).

References
----------
.. [1] Uzzell, V. J., and E. J. Chichilnisky. "Precision of
   spike trains in primate retinal ganglion cells."
   Journal of Neurophysiology 92.2 (2004)
.. [2] Pillow, Jonathan W., et al. "Prediction and decoding of
   retinal ganglion cell responses with a probabilistic
   spiking model." Journal of Neuroscience 25.47 (2005)

"""

# Authors: Jonathan Pillow <pillow@princeton.edu>
# License: MIT

########################################################
#
# Import all the relevance libraries.

import os.path as op
import json

import numpy as np
from numpy.linalg import inv
from scipy.linalg import hankel

from pyglmnet import GLM

import matplotlib.pyplot as plt
from tempfile import TemporaryDirectory

########################################################
#
# Fetch the dataset. The JSON file contains the
# following keys:  ``stim`` (binary stochastic stimulation),
# ``stim_times`` (time of the stimulation), and
# ``spike_times`` (recorded time of the spikes)

from pyglmnet.datasets import fetch_RGCs_data

with TemporaryDirectory(prefix="tmp_glm-tools") as temp_dir:
    dpath = fetch_RGCs_data(dpath=temp_dir, accept_rgcs_license=True)
    with open(op.join(dpath, 'data_RGCs.json'), 'r') as f:
        rgcs_dataset = json.loads(f.read())

stim = np.array(rgcs_dataset['stim'])
stim_times = np.array(rgcs_dataset['stim_times'])

# spike times for all 4 cells (0-1 are OFF cells, 2-3 are ON cells)
spike_times = [
    np.array(rgcs_dataset['spike_times']['cell_0']),
    np.array(rgcs_dataset['spike_times']['cell_1']),
    np.array(rgcs_dataset['spike_times']['cell_2']),
    np.array(rgcs_dataset['spike_times']['cell_3']),
]

n_cells = len(spike_times)  # total number of cells
dt = stim_times[1] - stim_times[0]  # time between the stimulation
n_t = len(stim)  # total number of the stimulation
sfreq = 1. / dt  # frequency of the stimulation

########################################################
#
# You can pick a cell to work with and visualize the spikes for one second.
# In this case, we will pick cell number 2 (ON cell).

cell_idx = 2  # pick cell number 2 (ON cell)
spike_time = spike_times[cell_idx]  # pick spike time to work with
n_spikes = len(spike_time)  # number of spikes

# bin the spikes
t_bins = np.arange(n_t + 1) * dt
spikes_binned, _ = np.histogram(spike_time, t_bins)

print('Loaded RGC data: cell {}'.format(cell_idx))
print('Number of stim frames: {:d} ({:.1f} minutes)'.
      format(n_t, n_t * dt / 60))
print('Time bin size: {:.1f} ms'.format(dt * 1000))
print('Number of spikes: {} (mean rate = {:.1f} Hz)\n'.
      format(n_spikes, n_spikes / n_t * 60))

# sample indices for visualization
sample_index = np.arange(120)
t_sample = dt * sample_index

plt.subplot(3, 1, 1)
plt.step(t_sample, stim[sample_index])
plt.xlim([t_sample.min(), t_sample.max()])
plt.title('Raw Stimulus, spikes, and'
          ' spike counts')
plt.ylabel('Stimulation Intensity')

plt.subplot(3, 1, 2)
tspplot = spike_time[(spike_time >= t_sample.min()) &
                     (spike_time < t_sample.max())]
plt.stem(spike_time[sample_index],
         [1] * len(spike_time[sample_index]))
plt.xlim([t_sample.min(), t_sample.max()])
plt.ylim([0, 2])
plt.ylabel('Spikes')

plt.subplot(3, 1, 3)
markerline, _, _ = plt.stem(t_sample, spikes_binned[sample_index])
markerline.set_markerfacecolor('none')
plt.xlim([t_sample.min(), t_sample.max()])
plt.xlabel('Time (s)')
plt.ylabel('Binned Spike counts')
plt.show()

########################################################
#
# We can use ``scipy``'s function ``hankel`` to make our design matrix.
# Design matrix :math:`X` can be created using the stimulation and its history.
# Later in the tutorial, we will also incorporate spikes history into our
# design matrix.

n_t_filt = 25  # tweak this to see different results
stim_padded = np.pad(stim, (n_t_filt - 1, 0))
Xdsgn = hankel(stim_padded[0: -n_t_filt + 1], stim[-n_t_filt:])

plt.imshow(Xdsgn[:50, :],
           cmap='binary',
           aspect='auto',
           interpolation='nearest')
plt.xlabel('lags before spike time')
plt.ylabel('time bin of response')
plt.title('Sample first 50 rows of design'
          ' matrix created using Hankel')
plt.show()

########################################################
# **Fitting and predicting with a linear-Gaussian GLM**
#
# For a general linear model, an observed spikes can be
# thought of an underlying parameter
# :math:`\beta_0, \beta` that control the spiking:
# :math:`y = (\beta_0 + X \beta) \ + \epsilon` and
# :math:`y \sim \text{Poiss}(\beta_0 + X \beta)` where
# :math:`X` is the stimulation and history of stimulation
#
# We can add an offset or a "constant" to our design matrix.
# This can be done by concatenating a column of 1 to
# our previously created design matrix.

Xdsgn_offset = np.hstack((np.ones((n_t, 1)), Xdsgn))

# compute whitened spike-triggered average (STA)
wsta_offset = inv(Xdsgn_offset.T @ Xdsgn_offset)\
    @ Xdsgn_offset.T.dot(spikes_binned)

const, wsta_offset = wsta_offset[0], wsta_offset[1:]
spikes_pred_lgGLM_offset = const + (Xdsgn @ wsta_offset)

########################################################
# **Fitting and predicting with a Gaussian GLM**
#
# We can also assume that their is a non-linear function governing
# the underlying the firing patterns. Concreately, we can write down as
# :math:`y = q(\beta_0 + X \beta) + \epsilon`, and
# :math:`y \sim \text{Poiss}(\beta_0 + X \beta)`.
# We call :math:`q^{-1}` a "link function".
# Here, we can use Pyglmnet's `GLM` to predict the parameters.

# create possion GLM instance
glm_poisson = GLM(distr='poisson',
                  verbose=False, alpha=0.05,
                  max_iter=1000, learning_rate=0.2,
                  score_metric='pseudo_R2',
                  reg_lambda=1e-7, eta=4.0)

# fitting to a design matrix
glm_poisson.fit(Xdsgn, spikes_binned)

# predict spike counts using Poisson GLM
# alternatively, you can also use
# np.exp(glm_poisson.beta0_ + X.dot(glm_poisson.beta_))
spikes_pred_poissonGLM = glm_poisson.predict(Xdsgn)

#############################################################################
# **Adding spikes history for predicting spike counts**
#
# We can even further predict the spikes by concatenating the spikes history.
# **Note** the spike-history portion of the design
# matrix had better be shifted so that we aren't allowed to use the spike
# count on this time bin to predict itself!

n_t_filt = 25  # same as before, stimulation history
n_t_hist = 20  # spikes history

# using both stimulation history and spikes history
spikes_padded = np.pad(spikes_binned, (n_t_hist, 0))

Xstim = hankel(stim_padded[:-n_t_filt + 1], stim[-n_t_filt:])
Xspikes = hankel(spikes_padded[:-n_t_hist], stim[-n_t_hist:])
Xdsgn_hist = np.hstack((Xstim, Xspikes))  # design matrix with spikes history

# Now, we are ready to fit Poisson GLM with spikes history.
# create possion GLM instance
glm_poisson_hist = GLM(distr='poisson',
                       verbose=False, alpha=0.05,
                       max_iter=1000, learning_rate=0.2,
                       score_metric='pseudo_R2',
                       reg_lambda=1e-7, eta=4.0)

# fitting to a design matrix with spikes history
glm_poisson_hist.fit(Xdsgn_hist, spikes_binned)

# predict spike counts
spikes_pred_poissonGLM_hist = glm_poisson_hist.predict(Xdsgn_hist)

#############################################################################
# **Putting all together**
#
# We are plotting the prediction of spike counts using
# linear Gaussian GLM with offset, Poisson GLM, and
# Poisson GLM with spikes history for one second.

markerline, _, _ = plt.stem(t_sample, spikes_binned[sample_index])
markerline.set_markerfacecolor('none')
plt.plot(t_sample, spikes_pred_lgGLM_offset[sample_index],
         color='gold', linewidth=2, label='lgGLM with offset')
plt.plot(t_sample, spikes_pred_poissonGLM[sample_index],
         color='green', linewidth=2, label='poissonGLM')
plt.plot(t_sample, spikes_pred_poissonGLM_hist[sample_index],
         color='red', linewidth=2, label='poissonGLM_hist')
plt.xlim([t_sample.min(), t_sample.max()])
plt.title('Spike count prediction')
plt.xlabel('Time (sec)')
plt.ylabel('Binned Spike Counts')
plt.legend()
plt.show()

# performance of the fitted models
mse_lgGLM_offset = np.mean((
    spikes_binned - spikes_pred_lgGLM_offset) ** 2)
mse_poissonGLM = np.mean((
    spikes_binned - spikes_pred_poissonGLM) ** 2)
mse_poissonGLM_hist = np.mean((
    spikes_binned - spikes_pred_poissonGLM_hist) ** 2)
rss = np.mean((spikes_binned - np.mean(spikes_binned)) ** 2)

print('Training perf (R^2): lin-gauss GLM, w/ offset: {:.2f}'
      .format(1 - mse_lgGLM_offset / rss))
print('Training perf (R^2): poisson GLM {:.2f}'
      .format(1 - mse_poissonGLM / rss))
print('Training perf (R^2): poisson GLM w/ spikes history {:.2f}'
      .format(1 - mse_poissonGLM_hist / rss))
print('Training perf (R^2): Pyglmnet possion GLM {:.2f}'
      .format(glm_poisson.score(Xdsgn, spikes_binned)))
print('Training perf (R^2): Pyglmnet poisson GLM w/ spikes history {:.2f}'
      .format(glm_poisson_hist.score(Xdsgn_hist, spikes_binned)))