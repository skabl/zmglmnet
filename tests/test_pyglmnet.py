import numpy as np
import scipy.sparse as sps
from sklearn.preprocessing import StandardScaler

from numpy.testing import assert_allclose

from pyglmnet import GLM


def test_glmnet():
    """Test glmnet."""
    glm = GLM(distr='poisson')
    scaler = StandardScaler()
    n_samples, n_features = 10000, 100
    density = 0.1

    # coefficients
    beta0 = np.random.rand()
    beta = sps.rand(n_features, 1, density=density).toarray()

    X_train = np.random.normal(0.0, 1.0, [n_samples, n_features])
    y_train = glm.simulate(beta0, beta, X_train)

    X_train = scaler.fit_transform(X_train)
    glm.fit(X_train, y_train)

    beta_ = glm.fit_[-2]['beta'][:]
    assert_allclose(beta[:], beta_, atol=0.1)  # check fit
    density_ = np.sum(beta_ > 0.1) / float(n_features)
    assert_allclose(density_, density, atol=0.05)  # check density

def test_multinomial_gradient():
    """Gradient of intercept params is different"""
    glm = GLM(distr='multinomial')
    X = np.array([[1,2,3], [4,5,6]])
    y = np.array([1,2])
    beta = np.zeros([4, 2])
    grad_beta0, grad_beta = glm.grad_L2loss(beta[0], beta[1:], 0, X, y)
    assert grad_beta0[0] != grad_beta0[1]